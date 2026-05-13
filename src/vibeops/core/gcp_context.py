from __future__ import annotations

from google.oauth2 import service_account

_GCP_SCOPES = ["https://www.googleapis.com/auth/cloud-platform"]


class GcpContext:
    """Session-scoped GCP credential and response cache carrier.

    Passed via LangGraph config['configurable']['gcp_context']; never stored in GraphState.
    The cache is keyed by (tool_name, *args) and lives for the session lifetime.
    """

    def __init__(self, service_account_info: dict[str, object], project_id: str) -> None:
        self.service_account_info = service_account_info
        self.project_id = project_id
        self._cache: dict[str, object] = {}
        self._creds: service_account.Credentials | None = None

    @property
    def credentials(self) -> service_account.Credentials:
        if self._creds is None:
            self._creds = service_account.Credentials.from_service_account_info(  # type: ignore[no-untyped-call]
                self.service_account_info,
                scopes=_GCP_SCOPES,
            )
        return self._creds

    def get_cached(self, key: tuple[object, ...]) -> object | None:
        return self._cache.get(str(key))

    def set_cached(self, key: tuple[object, ...], value: object) -> None:
        self._cache[str(key)] = value

    def clear_cache(self) -> None:
        self._cache.clear()
