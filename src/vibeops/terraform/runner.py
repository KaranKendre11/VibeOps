from __future__ import annotations

import json
import os
import re
import shutil
import signal
import subprocess
import sys
import threading
from collections.abc import Callable
from pathlib import Path

from vibeops.models.deployment import ApplyResult, DestroyResult, PlanResult, StateResource
from vibeops.models.iac import TerraformValidationResult
from vibeops.terraform.errors import TerraformApplyError, TerraformDestroyError, TerraformPlanError


class TerraformInitError(Exception):
    pass


# Service-account key file dropped into a work dir so terraform authenticates to GCP (both the
# Google provider and, when configured, the GCS state backend). Consumed by ``_tf_env``.
SA_CREDENTIALS_FILENAME = "sa_credentials.json"


def write_sa_credentials(work_dir: Path, service_account_info: dict[str, object]) -> None:
    """Write ``sa_credentials.json`` into ``work_dir`` for terraform to authenticate with.

    ``_tf_env`` picks this up and sets ``GOOGLE_APPLICATION_CREDENTIALS`` so both the Google
    provider and (when enabled) the GCS state backend authenticate with the service account.
    """
    (work_dir / SA_CREDENTIALS_FILENAME).write_text(
        json.dumps(service_account_info),
        encoding="utf-8",
    )


def _find_terraform() -> str:
    """Resolve the terraform executable path.

    On Windows, winget updates the registry PATH but not the current process
    environment. This function falls back to reading the registry directly so
    newly-installed binaries are found without requiring a terminal restart.
    """
    found = shutil.which("terraform")
    if found:
        return found

    if sys.platform == "win32":
        import winreg

        reg_paths: list[str] = []
        for hive, subkey in [
            (winreg.HKEY_CURRENT_USER, "Environment"),
            (
                winreg.HKEY_LOCAL_MACHINE,
                r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment",
            ),
        ]:
            try:
                with winreg.OpenKey(hive, subkey) as key:
                    val, _ = winreg.QueryValueEx(key, "PATH")
                    reg_paths.extend(p for p in str(val).split(";") if p.strip())
            except (FileNotFoundError, OSError):
                pass

        for dir_path in reg_paths:
            candidate = Path(dir_path) / "terraform.exe"
            if candidate.is_file():
                return str(candidate)

    raise TerraformInitError(
        "terraform binary not found in PATH. "
        "Install: https://developer.hashicorp.com/terraform/install  "
        "(Windows: winget install Hashicorp.Terraform, then restart this app)"
    )


def _tf_env(work_dir: Path | None = None) -> dict[str, str]:
    """Environment for terraform subprocess calls.

    Sets a shared plugin cache so providers are downloaded once across
    deployments, making the runner faster and resilient to registry blips.
    If work_dir contains sa_credentials.json, sets GOOGLE_APPLICATION_CREDENTIALS
    so the Google provider authenticates with the service account.
    """
    cache_dir = Path.home() / ".terraform.d" / "plugin-cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "TF_PLUGIN_CACHE_DIR": str(cache_dir)}
    if work_dir is not None:
        creds_file = work_dir / SA_CREDENTIALS_FILENAME
        if creds_file.is_file():
            env["GOOGLE_APPLICATION_CREDENTIALS"] = str(creds_file)
    return env


class TerraformValidateError(Exception):
    pass


def init(
    work_dir: Path,
    timeout: int = 300,
    backend_config: list[str] | None = None,
) -> None:
    """Run `terraform init` in work_dir.

    When ``backend_config`` is given (e.g. ``["-backend-config=bucket=...",
    "-backend-config=prefix=..."]``), the flags are appended so terraform initializes the
    configured remote backend. When ``None``, terraform uses whatever backend the config
    declares (local state by default).

    Raises TerraformInitError on non-zero exit or timeout.
    """
    cmd = [_find_terraform(), "init", "-no-color", "-input=false"]
    if backend_config:
        cmd.extend(backend_config)
    try:
        proc = subprocess.run(
            cmd,
            cwd=work_dir,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=_tf_env(work_dir),
        )
    except subprocess.TimeoutExpired as exc:
        raise TerraformInitError(f"terraform init timed out after {timeout}s") from exc
    except (FileNotFoundError, TerraformInitError) as exc:
        raise TerraformInitError("terraform binary not found in PATH") from exc

    if proc.returncode != 0:
        raise TerraformInitError(proc.stderr or proc.stdout)


def validate(work_dir: Path, timeout: int = 30) -> TerraformValidationResult:
    """Run `terraform validate -json` in work_dir.

    Raises TerraformValidateError on subprocess errors or timeout.
    Returns TerraformValidationResult (ok may be False if HCL is invalid).
    """
    try:
        proc = subprocess.run(
            [_find_terraform(), "validate", "-no-color", "-json"],
            cwd=work_dir,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=_tf_env(work_dir),
        )
    except subprocess.TimeoutExpired as exc:
        raise TerraformValidateError(f"terraform validate timed out after {timeout}s") from exc
    except (FileNotFoundError, TerraformInitError) as exc:
        raise TerraformValidateError("terraform binary not found in PATH") from exc

    # terraform validate -json writes JSON on both success and failure
    try:
        data: dict[str, object] = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        # Non-JSON output means validate itself crashed before producing output
        raise TerraformValidateError(proc.stderr or proc.stdout or "unknown error") from exc

    ok: bool = bool(data.get("valid", False))
    errors: list[str] = []
    diagnostics = data.get("diagnostics") or []
    if isinstance(diagnostics, list):
        for diag in diagnostics:
            if isinstance(diag, dict) and diag.get("severity") == "error":
                errors.append(str(diag.get("summary", "")) + ": " + str(diag.get("detail", "")))

    return TerraformValidationResult(ok=ok, errors=errors)


def plan(work_dir: Path, timeout: int = 60) -> PlanResult:
    """Run `terraform plan -no-color -out=tfplan -input=false`.

    Returns PlanResult with resource counts parsed from stdout.
    Raises TerraformPlanError on non-zero exit, timeout, or missing binary.
    """
    plan_file = str(work_dir / "tfplan")
    try:
        proc = subprocess.run(
            [_find_terraform(), "plan", "-no-color", f"-out={plan_file}", "-input=false"],
            cwd=work_dir,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=_tf_env(work_dir),
        )
    except subprocess.TimeoutExpired as exc:
        raise TerraformPlanError(f"terraform plan timed out after {timeout}s") from exc
    except (FileNotFoundError, TerraformInitError) as exc:
        raise TerraformPlanError("terraform binary not found in PATH") from exc

    if proc.returncode != 0:
        raise TerraformPlanError(proc.stderr or proc.stdout)

    add_count = 0
    m = re.search(r"(\d+) to add", proc.stdout)
    if m:
        add_count = int(m.group(1))

    change_count = 0
    m = re.search(r"(\d+) to change", proc.stdout)
    if m:
        change_count = int(m.group(1))

    destroy_count = 0
    m = re.search(r"(\d+) to destroy", proc.stdout)
    if m:
        destroy_count = int(m.group(1))

    return PlanResult(
        plan_file=plan_file,
        add_count=add_count,
        change_count=change_count,
        destroy_count=destroy_count,
    )


def _stream_subprocess(
    cmd: list[str],
    work_dir: Path,
    on_log: Callable[[str], None],
    timeout: int,
    cancel_event: threading.Event | None,
    env: dict[str, str],
) -> tuple[str, int]:
    """Popen a command, stream stdout line-by-line via on_log.

    Returns (full_log, returncode). Sends SIGINT if cancel_event is set.
    Sends SIGTERM (then kill) on timeout.
    """
    proc = subprocess.Popen(
        cmd,
        cwd=work_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        env=env,
    )

    log_lines: list[str] = []
    sigint_sent = False

    while True:
        line = proc.stdout.readline()  # type: ignore[union-attr]
        if not line:
            break
        line = line.rstrip("\n")
        log_lines.append(line)
        on_log(line)

        if cancel_event is not None and cancel_event.is_set() and not sigint_sent:
            proc.send_signal(signal.SIGINT)
            sigint_sent = True

    try:
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        raise

    return "\n".join(log_lines), proc.returncode


def apply(
    work_dir: Path,
    on_log: Callable[[str], None],
    timeout: int = 600,
    cancel_event: threading.Event | None = None,
) -> ApplyResult:
    """Run `terraform apply -no-color -auto-approve tfplan`.

    Streams stdout line-by-line via on_log.
    Raises TerraformApplyError on non-zero exit or timeout.
    """
    plan_file = str(work_dir / "tfplan")
    try:
        tf_bin = _find_terraform()
    except TerraformInitError as exc:
        raise TerraformApplyError(str(exc)) from exc
    cmd = [tf_bin, "apply", "-no-color", "-auto-approve", plan_file]

    try:
        full_log, returncode = _stream_subprocess(
            cmd, work_dir, on_log, timeout, cancel_event, env=_tf_env(work_dir)
        )
    except subprocess.TimeoutExpired as exc:
        created = parse_state_resources(work_dir)
        raise TerraformApplyError(
            f"terraform apply timed out after {timeout}s",
            partial_state=bool(created),
            created_resources=created,
        ) from exc

    if returncode != 0:
        created = parse_state_resources(work_dir)
        raise TerraformApplyError(
            full_log,
            partial_state=bool(created),
            created_resources=created,
        )

    resources_created = 0
    m = re.search(r"(\d+) added", full_log)
    if m:
        resources_created = int(m.group(1))

    return ApplyResult(full_log=full_log, resources_created=resources_created)


def destroy(
    work_dir: Path,
    on_log: Callable[[str], None],
    timeout: int = 600,
    cancel_event: threading.Event | None = None,
) -> DestroyResult:
    """Run `terraform destroy -no-color -auto-approve`.

    Streams stdout line-by-line via on_log.
    Raises TerraformDestroyError on non-zero exit or timeout.
    """
    try:
        tf_bin = _find_terraform()
    except TerraformInitError as exc:
        raise TerraformDestroyError(str(exc)) from exc
    cmd = [tf_bin, "destroy", "-no-color", "-auto-approve"]

    try:
        full_log, returncode = _stream_subprocess(
            cmd, work_dir, on_log, timeout, cancel_event, env=_tf_env(work_dir)
        )
    except subprocess.TimeoutExpired as exc:
        remaining = parse_state_resources(work_dir)
        raise TerraformDestroyError(
            f"terraform destroy timed out after {timeout}s",
            created_resources=remaining,
        ) from exc

    if returncode != 0:
        remaining = parse_state_resources(work_dir)
        raise TerraformDestroyError(full_log, created_resources=remaining)

    resources_destroyed = 0
    m = re.search(r"(\d+) destroyed", full_log)
    if m:
        resources_destroyed = int(m.group(1))

    return DestroyResult(full_log=full_log, resources_destroyed=resources_destroyed)


def parse_state_resources(work_dir: Path) -> list[StateResource]:
    """Run `terraform show -json` and return the current resource list.

    Returns empty list if no state exists, binary missing, or JSON is invalid.
    """
    try:
        proc = subprocess.run(
            [_find_terraform(), "show", "-json"],
            cwd=work_dir,
            capture_output=True,
            text=True,
            timeout=30,
            env=_tf_env(work_dir),
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, TerraformInitError):
        return []

    if proc.returncode != 0:
        return []

    try:
        data: dict[str, object] = json.loads(proc.stdout)
    except (json.JSONDecodeError, ValueError):
        return []

    resources: list[StateResource] = []
    values = data.get("values") or {}
    root_module = (values if isinstance(values, dict) else {}).get("root_module") or {}
    raw_resources = (root_module if isinstance(root_module, dict) else {}).get("resources") or []

    for r in raw_resources if isinstance(raw_resources, list) else []:
        if not isinstance(r, dict):
            continue
        rvalues = r.get("values") or {}
        zone = (rvalues if isinstance(rvalues, dict) else {}).get("zone")
        resources.append(
            StateResource(
                type=str(r.get("type", "")),
                name=str(r.get("name", "")),
                zone=str(zone) if zone else None,
                provider=str(r.get("provider_name", "")) or None,
            )
        )

    return resources
