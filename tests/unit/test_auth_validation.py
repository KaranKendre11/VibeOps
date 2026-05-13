from __future__ import annotations

from unittest.mock import MagicMock, patch

import openai
import pytest

from vibeops.core.auth import list_gcp_projects, validate_gcp_credentials, validate_openai_key
from vibeops.core.errors import AuthError

_VALID_SA: dict[str, object] = {
    "type": "service_account",
    "project_id": "my-project",
    "private_key_id": "key-id",
    "private_key": (
        "-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA\n-----END RSA PRIVATE KEY-----\n"
    ),
    "client_email": "sa@my-project.iam.gserviceaccount.com",
    "client_id": "123",
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
}


# ---------------------------------------------------------------------------
# OpenAI key validation
# ---------------------------------------------------------------------------


class TestValidateOpenAIKey:
    def test_valid_key_returns_ok(self) -> None:
        with patch("vibeops.core.auth.openai.OpenAI") as mock_cls:
            mock_cls.return_value.models.list.return_value = []
            result = validate_openai_key("sk-testkey12345678")
        assert result.ok is True
        assert result.fingerprint is not None
        assert result.fingerprint.endswith("5678")

    def test_auth_error_returns_invalid_message(self) -> None:
        with patch("vibeops.core.auth.openai.OpenAI") as mock_cls:
            mock_cls.return_value.models.list.side_effect = openai.AuthenticationError(
                message="Invalid auth",
                response=MagicMock(status_code=401, headers={}),
                body={},
            )
            result = validate_openai_key("sk-bad")
        assert result.ok is False
        assert "invalid" in result.message.lower() or "key" in result.message.lower()

    def test_connection_error_mentions_connectivity(self) -> None:
        with patch("vibeops.core.auth.openai.OpenAI") as mock_cls:
            mock_cls.return_value.models.list.side_effect = openai.APIConnectionError(
                request=MagicMock()
            )
            result = validate_openai_key("sk-somekey12345678")
        assert result.ok is False
        assert "connect" in result.message.lower() or "reach" in result.message.lower()

    def test_empty_key_rejected_without_api_call(self) -> None:
        with patch("vibeops.core.auth.openai.OpenAI") as mock_cls:
            result = validate_openai_key("")
        assert result.ok is False
        mock_cls.assert_not_called()


# ---------------------------------------------------------------------------
# GCP credential validation
# ---------------------------------------------------------------------------


class TestValidateGCPCredentials:
    def _mock_gcp(self, projects: list[str] | None = None) -> tuple[MagicMock, MagicMock]:
        """Return (mock_creds_class, mock_projects_client_class)."""
        mock_creds = MagicMock()
        mock_creds_cls = MagicMock(return_value=mock_creds)
        mock_client = MagicMock()
        if projects is not None:
            mock_project_objs = [MagicMock(project_id=p) for p in projects]
            mock_client.search_projects.return_value = iter(mock_project_objs)
        mock_client_cls = MagicMock(return_value=mock_client)
        return mock_creds_cls, mock_client_cls

    def test_valid_credentials_return_ok(self) -> None:
        mock_creds_cls, mock_client_cls = self._mock_gcp(["proj-1"])
        with (
            patch(
                "vibeops.core.auth.service_account.Credentials.from_service_account_info",
                mock_creds_cls,
            ),
            patch("vibeops.core.auth.resourcemanager_v3.ProjectsClient", mock_client_cls),
        ):
            result = validate_gcp_credentials(_VALID_SA)
        assert result.ok is True
        assert "sa" in (result.fingerprint or "")

    def test_missing_fields_returns_error(self) -> None:
        result = validate_gcp_credentials({"type": "service_account"})
        assert result.ok is False

    def test_permission_denied_returns_iam_hint(self) -> None:
        from google.api_core import exceptions as gcp_exceptions

        mock_creds_cls, _ = self._mock_gcp()
        mock_client = MagicMock()
        mock_client.search_projects.side_effect = gcp_exceptions.PermissionDenied("denied")  # type: ignore[no-untyped-call]
        mock_client_cls = MagicMock(return_value=mock_client)

        with (
            patch(
                "vibeops.core.auth.service_account.Credentials.from_service_account_info",
                mock_creds_cls,
            ),
            patch("vibeops.core.auth.resourcemanager_v3.ProjectsClient", mock_client_cls),
        ):
            result = validate_gcp_credentials(_VALID_SA)
        assert result.ok is False
        assert "permission" in result.message.lower() or "iam" in result.message.lower()


class TestListGCPProjects:
    def test_returns_project_ids(self) -> None:
        mock_creds_cls = MagicMock()
        mock_project_objs = [MagicMock(project_id="proj-a"), MagicMock(project_id="proj-b")]
        mock_client = MagicMock()
        mock_client.search_projects.return_value = iter(mock_project_objs)
        mock_client_cls = MagicMock(return_value=mock_client)

        with (
            patch(
                "vibeops.core.auth.service_account.Credentials.from_service_account_info",
                mock_creds_cls,
            ),
            patch("vibeops.core.auth.resourcemanager_v3.ProjectsClient", mock_client_cls),
        ):
            result = list_gcp_projects(_VALID_SA)
        assert result.project_ids == ["proj-a", "proj-b"]

    def test_bad_json_raises_auth_error(self) -> None:
        with pytest.raises(AuthError):
            list_gcp_projects({"type": "service_account"})
