from __future__ import annotations

from google.api_core import exceptions as gcp_exceptions
from google.cloud import compute_v1

from vibeops.core.errors import GCPToolError
from vibeops.core.gcp_context import GcpContext
from vibeops.models.requirement import OsFamily
from vibeops.models.results import (
    InstancesResult,
    MachineType,
    MachineTypesResult,
    OsImage,
    OsImagesResult,
    QuotaResult,
    RunningInstance,
    ZoneAvailability,
    ZonesWithAcceleratorResult,
)

_GPU_QUOTA_METRICS: dict[str, str] = {
    "nvidia-tesla-t4": "NVIDIA_T4_GPUS",
    "nvidia-l4": "NVIDIA_L4_GPUS",
    "nvidia-tesla-a100": "NVIDIA_A100_GPUS",
}

_GPU_COMPATIBLE_PREFIXES = ("n1-", "a2-", "g2-")

_OS_IMAGE_PROJECTS = [
    "deeplearning-platform-release",
    "ubuntu-os-cloud",
    "debian-cloud",
]

# Per-OsFamily: (image_project, family_prefix, substrings_to_exclude)
# Prefix and exclusions narrow the image list to standard, GPU-compatible families.
_OS_RESOLVE_CONFIG: dict[OsFamily, tuple[str, str, list[str]]] = {
    OsFamily.DEEP_LEARNING: ("deeplearning-platform-release", "common-cu", []),
    OsFamily.UBUNTU_LTS: ("ubuntu-os-cloud", "ubuntu-", ["minimal", "arm64", "pro"]),
    OsFamily.DEBIAN: ("debian-cloud", "debian-", ["backports", "sid", "testing"]),
}

# Fallbacks used when the API call fails.
_OS_RESOLVE_FALLBACK: dict[OsFamily, tuple[str, str]] = {
    OsFamily.DEEP_LEARNING: ("deeplearning-platform-release", "common-cu121"),
    OsFamily.UBUNTU_LTS: ("ubuntu-os-cloud", "ubuntu-2204-lts"),
    OsFamily.DEBIAN: ("debian-cloud", "debian-12"),
}


def _cache_key(*parts: object) -> tuple[object, ...]:
    return tuple(parts)


def list_zones_with_accelerator(ctx: GcpContext, gpu_type: str) -> ZonesWithAcceleratorResult:
    key = _cache_key("list_zones_with_accelerator", gpu_type)
    cached = ctx.get_cached(key)
    if cached is not None:
        return cached  # type: ignore[return-value]
    try:
        client = compute_v1.AcceleratorTypesClient(credentials=ctx.credentials)
        pager = client.aggregated_list(project=ctx.project_id)
        zones: list[ZoneAvailability] = []
        for zone_path, scoped in pager:
            if not zone_path.startswith("zones/"):
                continue
            zone_name = zone_path.removeprefix("zones/")
            items = getattr(scoped, "accelerator_types", None) or []
            for item in items:
                if item.name == gpu_type:
                    region = "-".join(zone_name.split("-")[:-1])
                    zones.append(
                        ZoneAvailability(
                            zone=zone_name,
                            region=region,
                            gpu_available=True,
                            quota_total=0,
                            quota_used=0,
                        )
                    )
        result = ZonesWithAcceleratorResult(gpu_type=gpu_type, zones=zones)
        ctx.set_cached(key, result)
        return result
    except gcp_exceptions.GoogleAPICallError as exc:
        raise GCPToolError(f"list_zones_with_accelerator failed: {exc}") from exc


def list_machine_types(
    ctx: GcpContext, zone: str, gpu_compatible: bool = True
) -> MachineTypesResult:
    key = _cache_key("list_machine_types", zone, gpu_compatible)
    cached = ctx.get_cached(key)
    if cached is not None:
        return cached  # type: ignore[return-value]
    try:
        client = compute_v1.MachineTypesClient(credentials=ctx.credentials)
        pager = client.list(project=ctx.project_id, zone=zone)
        machine_types: list[MachineType] = []
        for item in pager:
            is_gpu_compat = any(item.name.startswith(p) for p in _GPU_COMPATIBLE_PREFIXES)
            if gpu_compatible and not is_gpu_compat:
                continue
            machine_types.append(
                MachineType(
                    name=item.name,
                    cpus=item.guest_cpus,
                    memory_gb=round(item.memory_mb / 1024, 1),
                    gpu_compatible=is_gpu_compat,
                )
            )
        result = MachineTypesResult(zone=zone, machine_types=machine_types)
        ctx.set_cached(key, result)
        return result
    except gcp_exceptions.GoogleAPICallError as exc:
        raise GCPToolError(f"list_machine_types failed: {exc}") from exc


def list_os_images(
    ctx: GcpContext, family_filter: str | None = None
) -> OsImagesResult:
    key = _cache_key("list_os_images", family_filter or "")
    cached = ctx.get_cached(key)
    if cached is not None:
        return cached  # type: ignore[return-value]
    try:
        client = compute_v1.ImagesClient(credentials=ctx.credentials)
        images: list[OsImage] = []
        for project in _OS_IMAGE_PROJECTS:
            try:
                pager = client.list(project=project)
                for item in pager:
                    if family_filter and item.family != family_filter:
                        continue
                    if not item.family:
                        continue
                    images.append(
                        OsImage(
                            family=item.family,
                            project=project,
                            description=item.description or "",
                        )
                    )
            except gcp_exceptions.GoogleAPICallError:
                continue
        # Deduplicate by (family, project)
        seen: set[tuple[str, str]] = set()
        deduped: list[OsImage] = []
        for img in images:
            pair = (img.family, img.project)
            if pair not in seen:
                seen.add(pair)
                deduped.append(img)
        result = OsImagesResult(images=deduped)
        ctx.set_cached(key, result)
        return result
    except gcp_exceptions.GoogleAPICallError as exc:
        raise GCPToolError(f"list_os_images failed: {exc}") from exc


def resolve_os_image(ctx: GcpContext, os_family: OsFamily) -> tuple[str, str]:
    """Return (image_project, image_family) for the given OsFamily.

    Queries the GCP Images API for non-deprecated families matching the
    OsFamily's project and prefix, then picks the family whose most recent
    image has the latest creation timestamp.  Falls back to known-good
    values if the API call fails.
    """
    key = _cache_key("resolve_os_image", os_family.value)
    cached = ctx.get_cached(key)
    if cached is not None:
        return cached  # type: ignore[return-value]

    project, prefix, excludes = _OS_RESOLVE_CONFIG[os_family]

    try:
        client = compute_v1.ImagesClient(credentials=ctx.credentials)
        pager = client.list(project=project)

        # Track the latest creation_timestamp seen for each family.
        # ISO 8601 strings sort lexicographically, so max() works correctly.
        family_latest: dict[str, str] = {}
        for item in pager:
            if not item.family or not item.family.startswith(prefix):
                continue
            if any(excl in item.family for excl in excludes):
                continue
            if item.deprecated and item.deprecated.state in ("DEPRECATED", "OBSOLETE", "DELETED"):
                continue
            ts = item.creation_timestamp or ""
            if item.family not in family_latest or ts > family_latest[item.family]:
                family_latest[item.family] = ts

        if family_latest:
            best = max(family_latest, key=lambda f: family_latest[f])
            result: tuple[str, str] = (project, best)
            ctx.set_cached(key, result)
            return result
    except gcp_exceptions.GoogleAPICallError:
        pass

    return _OS_RESOLVE_FALLBACK[os_family]


def list_running_instances(ctx: GcpContext) -> InstancesResult:
    """List every Compute Engine instance in the project (any status).

    Uses aggregated_list to fetch instances across every zone in a single call.
    Does NOT cache — callers want fresh data when opening the inventory.
    Returns all statuses (RUNNING, STOPPED, TERMINATED, etc.) so the user
    sees the complete picture.
    """
    try:
        client = compute_v1.InstancesClient(credentials=ctx.credentials)
        pager = client.aggregated_list(project=ctx.project_id)
        instances: list[RunningInstance] = []
        for zone_path, scoped in pager:
            if not zone_path.startswith("zones/"):
                continue
            zone_name = zone_path.removeprefix("zones/")
            for item in getattr(scoped, "instances", None) or []:
                status = str(item.status or "UNKNOWN")
                machine_type_short = (item.machine_type or "").rsplit("/", 1)[-1]
                internal_ip = ""
                external_ip = ""
                for nic in item.network_interfaces or []:
                    internal_ip = nic.network_i_p or internal_ip
                    for ac in nic.access_configs or []:
                        if ac.nat_i_p:
                            external_ip = ac.nat_i_p
                            break
                gpu_summary = ""
                for acc in getattr(item, "guest_accelerators", None) or []:
                    gpu_name = (acc.accelerator_type or "").rsplit("/", 1)[-1]
                    gpu_summary = f"{acc.accelerator_count}× {gpu_name}"
                    break
                labels = dict(item.labels) if item.labels else {}
                instances.append(
                    RunningInstance(
                        name=item.name or "",
                        zone=zone_name,
                        machine_type=machine_type_short,
                        status=status,
                        internal_ip=internal_ip,
                        external_ip=external_ip,
                        creation_timestamp=item.creation_timestamp or "",
                        labels=labels,
                        gpu_summary=gpu_summary,
                    )
                )
        # Sort: running first, then by creation time descending
        priority = {"RUNNING": 0, "PROVISIONING": 1, "STAGING": 2, "STOPPING": 3, "REPAIRING": 4}
        instances.sort(
            key=lambda i: (
                priority.get(i.status, 99),
                -1 * len(i.creation_timestamp),
                i.creation_timestamp,
            ),
            reverse=False,
        )
        return InstancesResult(instances=instances)
    except gcp_exceptions.GoogleAPICallError as exc:
        raise GCPToolError(f"list_running_instances failed: {exc}") from exc


def delete_instance(ctx: GcpContext, zone: str, name: str) -> None:
    """Delete a single Compute Engine instance. Blocks until the operation completes."""
    try:
        client = compute_v1.InstancesClient(credentials=ctx.credentials)
        op = client.delete(project=ctx.project_id, zone=zone, instance=name)
        op.result(timeout=300)  # type: ignore[no-untyped-call]
    except gcp_exceptions.GoogleAPICallError as exc:
        raise GCPToolError(f"delete_instance failed for {name} in {zone}: {exc}") from exc


def get_accelerator_quota(ctx: GcpContext, region: str, gpu_type: str) -> QuotaResult:
    key = _cache_key("get_accelerator_quota", region, gpu_type)
    cached = ctx.get_cached(key)
    if cached is not None:
        return cached  # type: ignore[return-value]
    metric = _GPU_QUOTA_METRICS.get(gpu_type, f"NVIDIA_{gpu_type.upper()}_GPUS")
    try:
        client = compute_v1.RegionsClient(credentials=ctx.credentials)
        region_obj = client.get(project=ctx.project_id, region=region)
        limit = 0
        usage = 0
        for quota in region_obj.quotas:
            if quota.metric == metric:
                limit = int(quota.limit)
                usage = int(quota.usage)
                break
        result = QuotaResult(
            region=region, gpu_type=gpu_type, limit=limit, usage=usage
        )
        ctx.set_cached(key, result)
        return result
    except gcp_exceptions.GoogleAPICallError as exc:
        raise GCPToolError(f"get_accelerator_quota failed: {exc}") from exc
