from __future__ import annotations

import json

import openai
from google.api_core import exceptions as gcp_exceptions
from google.auth import exceptions as google_auth_exceptions
from google.cloud import resourcemanager_v3
from google.oauth2 import service_account

from vibeops.core.errors import AuthError
from vibeops.models.results import ProjectListResult, ValidationResult

_OPENAI_SCOPES = ["https://www.googleapis.com/auth/cloud-platform"]


def validate_openai_key(key: str) -> ValidationResult:
    """Validate an OpenAI API key by calling the models list endpoint.

    Returns a ValidationResult with ok=True and a key fingerprint on success,
    or ok=False with a human-readable message on failure.
    """
    if not key or not key.strip():
        return ValidationResult(ok=False, message="API key must not be empty.")
    try:
        client = openai.OpenAI(api_key=key)
        client.models.list()
        fingerprint = f"…{key[-4:]}" if len(key) >= 4 else "…"
        return ValidationResult(ok=True, message="OpenAI key validated.", fingerprint=fingerprint)
    except openai.AuthenticationError:
        return ValidationResult(ok=False, message="Invalid OpenAI API key.")
    except openai.APIConnectionError:
        return ValidationResult(
            ok=False, message="Could not reach OpenAI. Check your internet connection."
        )
    except openai.APITimeoutError:
        return ValidationResult(
            ok=False, message="OpenAI request timed out. Try again in a moment."
        )
    except openai.RateLimitError:
        return ValidationResult(
            ok=False, message="OpenAI rate limit reached. Wait a moment and try again."
        )
    except Exception as exc:  # noqa: BLE001
        return ValidationResult(ok=False, message=f"Unexpected error validating key: {exc}")


def _credentials_from_sa_json(
    sa_json: dict[str, object],
) -> service_account.Credentials:
    """Build GCP credentials from a service-account dict, raising AuthError on failure."""
    try:
        creds: service_account.Credentials = service_account.Credentials.from_service_account_info(  # type: ignore[no-untyped-call]
            sa_json, scopes=_OPENAI_SCOPES
        )
        return creds
    except (ValueError, KeyError) as exc:
        raise AuthError(f"Service-account JSON is missing required fields: {exc}") from exc


def validate_gcp_credentials(sa_json: dict[str, object]) -> ValidationResult:
    """Validate GCP service-account credentials by listing accessible projects.

    Returns a ValidationResult; does not raise — all errors are returned as ok=False.
    """
    try:
        creds = _credentials_from_sa_json(sa_json)
        client = resourcemanager_v3.ProjectsClient(credentials=creds)
        # A successful iteration (even empty) confirms the SA can make API calls.
        next(iter(client.search_projects()), None)
        sa_email = str(sa_json.get("client_email", "unknown"))
        fingerprint = sa_email.split("@")[0] if "@" in sa_email else sa_email
        return ValidationResult(
            ok=True,
            message="GCP credentials validated.",
            fingerprint=fingerprint,
        )
    except AuthError as exc:
        return ValidationResult(ok=False, message=str(exc))
    except google_auth_exceptions.DefaultCredentialsError as exc:
        return ValidationResult(ok=False, message=f"GCP credential error: {exc}")
    except gcp_exceptions.PermissionDenied:
        return ValidationResult(
            ok=False,
            message=(
                "Permission denied. Check that the service account has at least "
                "the 'resourcemanager.projects.get' IAM permission."
            ),
        )
    except gcp_exceptions.Unauthenticated:
        return ValidationResult(
            ok=False, message="GCP authentication failed. The service-account key may be expired."
        )
    except json.JSONDecodeError:
        return ValidationResult(ok=False, message="Service-account file is not valid JSON.")
    except Exception as exc:  # noqa: BLE001
        return ValidationResult(ok=False, message=f"Unexpected GCP error: {exc}")


def list_gcp_projects(sa_json: dict[str, object]) -> ProjectListResult:
    """Return all GCP project IDs visible to the service account.

    Raises AuthError if credential construction fails outright;
    returns an empty list if the SA has project access but sees none.
    """
    creds = _credentials_from_sa_json(sa_json)
    client = resourcemanager_v3.ProjectsClient(credentials=creds)
    try:
        project_ids = [p.project_id for p in client.search_projects()]
        return ProjectListResult(project_ids=project_ids)
    except gcp_exceptions.GoogleAPICallError as exc:
        raise AuthError(f"Failed to list GCP projects: {exc}") from exc


def validate_gcp_sa_json_text(raw: str) -> ValidationResult:
    """Parse a raw JSON string and validate the resulting service-account dict.

    Convenience wrapper used by the setup screen's paste-as-text path.
    """
    try:
        sa_json: dict[str, object] = json.loads(raw)
    except json.JSONDecodeError:
        return ValidationResult(ok=False, message="Input is not valid JSON.")
    return validate_gcp_credentials(sa_json)
