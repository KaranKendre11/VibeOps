from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from vibeops.models.spec import DeploymentSpec

_TEMPLATES_DIR = Path(__file__).parent / "templates" / "gpu_vm"
_TEMPLATE_NAMES = ("main.tf.j2", "variables.tf.j2", "outputs.tf.j2")
_OUTPUT_NAMES = ("main.tf", "variables.tf", "outputs.tf")

_DEFAULT_SSH_USERNAME = "vibeops"


def _build_startup_script(spec: DeploymentSpec) -> str:
    """Combine package install + user startup script into one shell script.

    Returns "" if neither packages nor a user script were specified.
    """
    parts: list[str] = []
    app = spec.app

    if app.software_packages:
        # Conservative apt install — works on Ubuntu/Debian/COS-derivatives.
        # Allow alphanumeric, dot, dash, underscore, plus (covers things like docker.io,
        # libnvidia-compute-535, python3.11, nvidia-cuda-toolkit).
        def _safe_pkg(p: str) -> bool:
            return all(c.isalnum() or c in ".-_+" for c in p) and len(p) > 0
        pkgs = " ".join(p for p in app.software_packages if _safe_pkg(p))
        if pkgs:
            parts.append("#!/bin/bash")
            parts.append("set -euo pipefail")
            parts.append("export DEBIAN_FRONTEND=noninteractive")
            parts.append("apt-get update -y || true")
            parts.append(f"apt-get install -y {pkgs} || true")

    if app.startup_script:
        if not parts:
            parts.append("#!/bin/bash")
            parts.append("set -euo pipefail")
        parts.append("# --- user startup script ---")
        parts.append(app.startup_script.strip())

    return "\n".join(parts).strip()


def _build_context(spec: DeploymentSpec, fragment: str) -> dict[str, object]:
    region = "-".join(spec.compute.zone.split("-")[:-1])
    app = spec.app
    startup_body = _build_startup_script(spec)

    return {
        "project_id": spec.project_id,
        "region": region,
        "zone": spec.compute.zone,
        "machine_type": spec.compute.machine_type,
        "gpu_type": spec.compute.gpu_type.value,
        "gpu_count": spec.compute.gpu_count,
        "disk_size_gb": spec.storage.disk_size_gb,
        "os_image_family": spec.storage.os_image_family,
        "os_image_project": spec.storage.os_image_project,
        "network_name": spec.network.network_name,
        "preemptible": spec.compute.preemptible,
        "open_ports": sorted(set(spec.network.open_ports)),
        # public_ip auto-enables when ports are open, regardless of explicit flag
        "public_ip": spec.network.create_external_ip or bool(spec.network.open_ports),
        "startup_script_body": startup_body,
        "has_startup_script": bool(startup_body),
        "container_image": app.container_image,
        "ssh_public_key": app.ssh_public_key,
        "ssh_username": _DEFAULT_SSH_USERNAME,
        "labels": app.labels,
        "llm_fragment": fragment,
    }


def render_templates(
    spec: DeploymentSpec,
    output_dir: Path,
    fragment: str = "",
) -> dict[str, str]:
    """Render all three Terraform templates into output_dir.

    Uses StrictUndefined so missing context keys raise immediately.
    Returns a mapping of filename → rendered content.
    """
    env = Environment(
        loader=FileSystemLoader(str(_TEMPLATES_DIR)),
        undefined=StrictUndefined,
        keep_trailing_newline=True,
        trim_blocks=True,
        lstrip_blocks=True,
    )

    ctx = _build_context(spec, fragment)
    result: dict[str, str] = {}

    for template_name, output_name in zip(_TEMPLATE_NAMES, _OUTPUT_NAMES, strict=True):
        template = env.get_template(template_name)
        rendered = template.render(**ctx)
        out_path = output_dir / output_name
        out_path.write_text(rendered, encoding="utf-8")
        result[output_name] = rendered

    return result
