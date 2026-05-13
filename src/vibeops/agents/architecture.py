from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Optional

from langchain_core.runnables import RunnableConfig

from vibeops.core.gcp_context import GcpContext
from vibeops.models.architecture import ArchitectureCandidate, ArchitectureOptions
from vibeops.models.requirement import RegionPreference
from vibeops.models.results import Network
from vibeops.models.spec import (
    AppSpec,
    ComputeSpec,
    DeploymentSpec,
    GpuType,
    NetworkSpec,
    StorageSpec,
)
from vibeops.models.state import FlowStage, GraphState
from vibeops.tools.compute import (
    get_accelerator_quota,
    list_machine_types,
    list_zones_with_accelerator,
    resolve_os_image,
)
from vibeops.tools.resource_manager import list_existing_networks

logger = logging.getLogger(__name__)

_MAX_WORKERS = 4
_MAX_CANDIDATES = 3

_REGION_PREFIX_MAP: dict[RegionPreference, str] = {
    RegionPreference.AMERICAS: "us-",
    RegionPreference.EUROPE: "europe-",
    RegionPreference.ASIA: "asia-",
}


def architecture_agent(state: GraphState, config: Optional[RunnableConfig] = None) -> GraphState:
    """Deterministic GCP-aware architecture resolver. Uses no LLM.

    Falls back to M1 stub when no GcpContext is in config.
    """
    gcp_ctx: GcpContext | None = None
    if config:
        configurable: dict[str, Any] = config.get("configurable") or {}
        gcp_ctx = configurable.get("gcp_context")

    if gcp_ctx is None:
        return _stub_fallback(state)

    if state.back_to_requirements:
        return state.model_copy(
            update={
                "back_to_requirements": False,
                "stage": FlowStage.REQUIREMENT,
                "architecture_response": None,
            }
        )

    if state.architecture_response is not None:
        return _finalize(state, gcp_ctx)

    return _discover(state, gcp_ctx)


def _stub_fallback(state: GraphState) -> GraphState:
    spec = DeploymentSpec(
        compute=ComputeSpec(
            machine_type="n1-standard-4",
            zone="us-central1-a",
            gpu_type=GpuType.T4,
            gpu_count=1,
            preemptible=False,
        ),
        storage=StorageSpec(
            disk_size_gb=100,
            os_image_family="common-cu121",
            os_image_project="deeplearning-platform-release",
        ),
        network=NetworkSpec(network_name="default"),
        project_id="stub-project",
    )
    return state.model_copy(
        update={
            "deployment_spec": spec,
            "stage": FlowStage.IAC,
            "chat_history": state.chat_history
            + [
                {
                    "role": "agent",
                    "agent": "architecture",
                    "content": (
                        "Produced DeploymentSpec for n1-standard-4 + T4 in us-central1-a (stub)."
                    ),
                }
            ],
        }
    )


def _discover(state: GraphState, ctx: GcpContext) -> GraphState:
    draft = state.requirement_draft
    if draft is None:
        return state.model_copy(
            update={"error": "No requirement draft available for architecture resolution."}
        )

    gpu_type_str = draft.gpu_type.value
    cpu_floor_int = int(draft.cpu_floor.value)
    mem_floor_float = float(draft.memory_floor.value)
    region_prefix = _REGION_PREFIX_MAP.get(draft.region_preference)

    try:
        zones_result = list_zones_with_accelerator(ctx, gpu_type_str)
    except Exception as exc:  # noqa: BLE001
        return state.model_copy(
            update={"error": f"Failed to list accelerator zones: {exc}"}
        )

    candidate_zones = [
        z for z in zones_result.zones
        if (region_prefix is None or z.region.startswith(region_prefix))
        and z.zone not in state.excluded_zones
    ]

    if not candidate_zones:
        return state.model_copy(
            update={
                "error": (
                    f"No zones offering {draft.gpu_type.name} found"
                    + (f" in {draft.region_preference.value}" if region_prefix else "")
                    + ". Try a different region preference."
                ),
                "stage": FlowStage.REQUIREMENT,
            }
        )

    quota_map: dict[str, int] = {}
    quota_total_map: dict[str, int] = {}
    machine_map: dict[str, list[tuple[str, int, float]]] = {}

    def fetch_zone(zone_av: Any) -> None:
        zone: str = zone_av.zone
        region: str = zone_av.region
        try:
            q = get_accelerator_quota(ctx, region, gpu_type_str)
            quota_map[region] = q.remaining
            quota_total_map[region] = q.limit
        except Exception:  # noqa: BLE001
            quota_map[region] = 0
            quota_total_map[region] = 0
        try:
            mt_result = list_machine_types(ctx, zone, gpu_compatible=True)
            fits = [
                (m.name, m.cpus, m.memory_gb)
                for m in mt_result.machine_types
                if m.cpus >= cpu_floor_int and m.memory_gb >= mem_floor_float
            ]
            machine_map[zone] = fits
        except Exception:  # noqa: BLE001
            machine_map[zone] = []

    with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as pool:
        futures = [pool.submit(fetch_zone, z) for z in candidate_zones]
        for f in as_completed(futures):
            f.result()

    candidates: list[ArchitectureCandidate] = []
    for zone_av in candidate_zones:
        zone = zone_av.zone
        region = zone_av.region
        q_remaining = quota_map.get(region, 0)
        q_total = quota_total_map.get(region, 0)
        if q_remaining <= 0:
            continue
        fits = machine_map.get(zone, [])
        if not fits:
            continue
        fits.sort(key=lambda t: t[1])
        best_name, best_cpus, best_mem = fits[0]
        rationale = _make_rationale(q_remaining, q_total, best_cpus, mem_floor_float)
        candidates.append(
            ArchitectureCandidate(
                zone=zone,
                region=region,
                machine_type=best_name,
                cpus=best_cpus,
                memory_gb=best_mem,
                quota_total=q_total,
                quota_remaining=q_remaining,
                rationale=rationale,
            )
        )

    if not candidates:
        all_zero = all(quota_map.get(z.region, 0) <= 0 for z in candidate_zones)
        if all_zero:
            return state.model_copy(
                update={
                    "error": (
                        f"Your project has no {draft.gpu_type.name} quota in any eligible zone. "
                        "Request quota at console.cloud.google.com → IAM & Admin → Quotas."
                    )
                }
            )
        return state.model_copy(
            update={
                "error": (
                    f"No machine type satisfies {cpu_floor_int} vCPU / {int(mem_floor_float)} GB "
                    f"with {draft.gpu_type.name}. Loosen CPU/memory floor or pick a different GPU."
                ),
                "stage": FlowStage.REQUIREMENT,
            }
        )

    candidates.sort(
        key=lambda c: (
            -c.quota_remaining,
            c.cpus,
            0 if (region_prefix and c.region.startswith(region_prefix)) else 1,
            c.zone,
        )
    )
    top = candidates[:_MAX_CANDIDATES]

    try:
        nets_result = list_existing_networks(ctx)
        networks: list[Network] = nets_result.networks
    except Exception:  # noqa: BLE001
        networks = [Network(name="default", self_link="", auto_create_subnetworks=True)]

    options = ArchitectureOptions(
        candidates=top,
        networks=networks,
        requirement=draft,
    )
    return state.model_copy(
        update={
            "architecture_options": options,
            "stage": FlowStage.AWAITING_ARCHITECTURE,
            "chat_history": state.chat_history
            + [
                {
                    "role": "agent",
                    "agent": "architecture",
                    "content": (
                        f"Found {len(top)} deployment candidate(s) for "
                        f"{draft.gpu_type.name} in {len(candidate_zones)} zone(s)."
                    ),
                }
            ],
        }
    )


def _finalize(state: GraphState, ctx: GcpContext) -> GraphState:
    options = state.architecture_options
    resp = state.architecture_response or {}
    if options is None:
        return state.model_copy(update={"error": "No architecture options to finalize."})

    idx_raw = resp.get("candidate_index", 0)
    try:
        idx = int(idx_raw)
    except (ValueError, TypeError):
        idx = 0

    if idx < 0 or idx >= len(options.candidates):
        return state.model_copy(
            update={"error": f"Invalid candidate index {idx}. Please select a valid option."}
        )

    candidate = options.candidates[idx]
    network_name: str = str(resp.get("network_name", "default"))
    req = options.requirement
    draft = state.requirement_draft or req

    os_proj, os_family = resolve_os_image(ctx, req.os_family)

    spec = DeploymentSpec(
        compute=ComputeSpec(
            machine_type=candidate.machine_type,
            zone=candidate.zone,
            gpu_type=GpuType(req.gpu_type.value),
            gpu_count=draft.gpu_count,
            preemptible=draft.preemptible,
        ),
        storage=StorageSpec(
            disk_size_gb=draft.disk_size_gb,
            os_image_family=os_family,
            os_image_project=os_proj,
        ),
        network=NetworkSpec(
            network_name=network_name,
            create_external_ip=draft.public_ip or bool(draft.open_ports),
            open_ports=list(draft.open_ports),
        ),
        project_id=ctx.project_id,
        app=AppSpec(
            startup_script=draft.startup_script,
            software_packages=list(draft.software_packages),
            container_image=draft.container_image,
            ssh_public_key=draft.ssh_public_key,
            labels=dict(draft.labels),
            purpose=draft.purpose,
        ),
    )
    return state.model_copy(
        update={
            "deployment_spec": spec,
            "architecture_response": None,
            "stage": FlowStage.IAC,
            "chat_history": state.chat_history
            + [
                {
                    "role": "agent",
                    "agent": "architecture",
                    "content": (
                        f"Architecture confirmed: {candidate.machine_type} in {candidate.zone}, "
                        f"network '{network_name}'."
                    ),
                }
            ],
        }
    )


def _make_rationale(q_rem: int, q_total: int, cpus: int, mem_floor: float) -> str:
    if q_rem == q_total:
        quota_part = "Full quota"
    else:
        quota_part = f"Limited quota ({q_rem}/{q_total})"
    return f"{quota_part}; smallest machine satisfying {cpus} vCPU / {int(mem_floor)} GB."
