"""Remote Terraform state backend wiring (issue #3).

By default VibeOps renders Terraform into an ephemeral ``tempfile.mkdtemp`` work dir with
**local** state, so a lost process/session orphans real billing resources and breaks
``destroy``. This module lets a deployment instead persist its state in a **GCS bucket**.

Design:
  * A *partial* ``backend "gcs" {}`` block is written to ``backend.tf`` in the work dir. The
    concrete ``bucket`` + ``prefix`` are supplied at ``terraform init`` time via
    ``-backend-config`` flags (see :meth:`BackendConfig.init_args`). This keeps the generated
    file generic and mirrors the idiomatic Terraform "partial backend configuration" pattern.
  * The bucket comes from ``VIBEOPS_TF_STATE_BUCKET`` (see :class:`vibeops.config.AppConfig`).
    When it is unset we write **no** backend file and log a clear warning — preserving today's
    local-state behavior (and the demo/stub/test paths).
  * The ``prefix`` uniquely keys one deployment's state under the bucket, e.g.
    ``vibeops/<project>/<uuid>``. Once ``terraform init`` runs, the backend is cached in the
    work dir's ``.terraform/`` dir, so subsequent ``plan``/``apply``/``destroy`` in the same
    dir operate against the persisted remote state without re-passing the config.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from pathlib import Path

from vibeops.config import AppConfig

logger = logging.getLogger(__name__)

# Name of the generated partial-backend file dropped into a work dir. Kept out of the
# user-editable ``terraform_files`` set on purpose — editing backend config could strand state.
BACKEND_TF_FILENAME = "backend.tf"

# Partial GCS backend block. ``bucket``/``prefix`` are injected at init time via -backend-config.
_GCS_BACKEND_TF = """\
# Managed by VibeOps — remote Terraform state (GCS backend).
# bucket + prefix are supplied at `terraform init` time via -backend-config flags.
terraform {
  backend "gcs" {}
}
"""


@dataclass(frozen=True)
class BackendConfig:
    """Resolved GCS location for a single deployment's Terraform state."""

    bucket: str
    prefix: str

    def init_args(self) -> list[str]:
        """``-backend-config`` flags to pass to ``terraform init``."""
        return [
            f"-backend-config=bucket={self.bucket}",
            f"-backend-config=prefix={self.prefix}",
        ]

    @property
    def location(self) -> str:
        """Human-readable ``gs://`` URI for logs / UI."""
        return f"gs://{self.bucket}/{self.prefix}"


def _sanitize(component: str) -> str:
    """Reduce a string to a safe GCS-prefix path segment (alnum, dash, underscore)."""
    cleaned = "".join(c if (c.isalnum() or c in "-_") else "-" for c in component.strip().lower())
    return cleaned.strip("-") or "deployment"


def make_state_prefix(
    base: str,
    *,
    project_id: str | None = None,
    unique: str | None = None,
) -> str:
    """Build a unique, GCS-safe state prefix for one deployment.

    Shape: ``<base>/<project_id?>/<unique>`` — e.g. ``vibeops/my-proj/3f9a1c...``. A random
    ``uuid4`` hex is used when ``unique`` is not supplied so concurrent deployments never
    collide on the same state object.
    """
    parts = [_sanitize(base)]
    if project_id:
        parts.append(_sanitize(project_id))
    parts.append(_sanitize(unique) if unique else uuid.uuid4().hex)
    return "/".join(parts)


def configure_backend(
    work_dir: Path,
    *,
    project_id: str | None = None,
    prefix: str | None = None,
    config: AppConfig | None = None,
) -> BackendConfig | None:
    """Set up a remote GCS backend in ``work_dir``, or fall back to ephemeral local state.

    When a state bucket is configured (``VIBEOPS_TF_STATE_BUCKET``) this writes ``backend.tf``
    and returns the resolved :class:`BackendConfig` (whose :meth:`~BackendConfig.init_args`
    should be passed to :func:`vibeops.terraform.runner.init`). When it is **not** configured,
    no file is written, a warning is logged, and ``None`` is returned — preserving the existing
    local-state behavior.

    ``prefix`` may be passed to reuse an existing deployment's state key (e.g. reattaching);
    otherwise a fresh unique prefix is generated.
    """
    cfg = config or AppConfig()
    bucket = cfg.tf_state_bucket
    if not bucket:
        logger.warning(
            "VIBEOPS_TF_STATE_BUCKET is not set — Terraform state will live only in the "
            "ephemeral work dir %s and be LOST if this process/session ends, orphaning any "
            "cloud resources it created and breaking `destroy`. Set VIBEOPS_TF_STATE_BUCKET "
            "to a GCS bucket to persist state remotely.",
            work_dir,
        )
        return None

    resolved_prefix = prefix or make_state_prefix(cfg.tf_state_prefix, project_id=project_id)
    (work_dir / BACKEND_TF_FILENAME).write_text(_GCS_BACKEND_TF, encoding="utf-8")
    backend = BackendConfig(bucket=bucket, prefix=resolved_prefix)
    logger.info("Terraform remote state backend configured: %s", backend.location)
    return backend
