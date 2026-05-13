from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

import streamlit as st

# ---------------------------------------------------------------------------
# Local credential cache (~/.vibeops/credentials.json)
# ---------------------------------------------------------------------------

_CACHE_DIR = Path.home() / ".vibeops"
_CACHE_FILE = _CACHE_DIR / "credentials.json"


def _ensure_cache_dir() -> None:
    _CACHE_DIR.mkdir(exist_ok=True)


def save_credentials_to_cache() -> None:
    """Persist current session credentials to the local cache file."""
    _ensure_cache_dir()
    data: dict[str, Any] = {
        "openai_key": get_openai_key(),
        "gcp_sa_json": get_gcp_sa_json(),
        "gcp_project_id": get_gcp_project_id(),
        "monthly_cost_cap_usd": get_monthly_cost_cap(),
    }
    _CACHE_FILE.write_text(json.dumps(data), encoding="utf-8")


def load_credentials_from_cache() -> bool:
    """Restore credentials from the cache file into session state.

    Returns True if all required fields were present and setup_complete was set.
    """
    if not _CACHE_FILE.exists():
        return False
    try:
        data: dict[str, Any] = json.loads(_CACHE_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return False

    openai_key = data.get("openai_key")
    gcp_sa_json = data.get("gcp_sa_json")
    gcp_project_id = data.get("gcp_project_id")

    if openai_key:
        st.session_state["openai_key"] = openai_key
        st.session_state["openai_validated"] = True
        st.session_state["_openai_key_last_validated"] = openai_key
    if gcp_sa_json:
        st.session_state["gcp_sa_json"] = gcp_sa_json
        st.session_state["gcp_validated"] = True
        st.session_state["_gcp_sa_json"] = True
        st.session_state["_gcp_fingerprint"] = gcp_sa_json.get("client_email", "cached")
    if gcp_project_id:
        st.session_state["gcp_project_id"] = gcp_project_id
    cap = data.get("monthly_cost_cap_usd")
    if cap is not None:
        st.session_state["monthly_cost_cap_usd"] = float(cap)

    if openai_key and gcp_sa_json and gcp_project_id:
        set_setup_complete(True)
        return True
    return False


def clear_credentials_cache() -> None:
    """Delete the local credentials cache file."""
    if _CACHE_FILE.exists():
        _CACHE_FILE.unlink()


# ---------------------------------------------------------------------------
# Session-state helpers
# ---------------------------------------------------------------------------


def set_openai_key(key: str) -> None:
    """Store the OpenAI API key in session state."""
    st.session_state["openai_key"] = key


def get_openai_key() -> str | None:
    """Return the OpenAI API key from session state, or None if not set."""
    value: Any = st.session_state.get("openai_key")
    return str(value) if value is not None else None


def set_gcp_sa_json(sa_json: dict[str, object]) -> None:
    """Store the GCP service-account JSON dict in session state."""
    st.session_state["gcp_sa_json"] = sa_json


def get_gcp_sa_json() -> dict[str, object] | None:
    """Return the GCP SA JSON dict from session state, or None if not set."""
    value: Any = st.session_state.get("gcp_sa_json")
    return dict(value) if value is not None else None


def set_gcp_project_id(project_id: str) -> None:
    """Store the selected GCP project ID in session state."""
    st.session_state["gcp_project_id"] = project_id


def get_gcp_project_id() -> str | None:
    """Return the selected GCP project ID from session state, or None if not set."""
    value: Any = st.session_state.get("gcp_project_id")
    return str(value) if value is not None else None


def set_monthly_cost_cap(cap_usd: float) -> None:
    """Store the user's monthly cost cap in session state."""
    st.session_state["monthly_cost_cap_usd"] = cap_usd


def get_monthly_cost_cap() -> float:
    """Return the monthly cost cap, defaulting to 200.0 if not configured."""
    return float(st.session_state.get("monthly_cost_cap_usd", 200.0))


def set_setup_complete(complete: bool) -> None:
    """Mark whether the setup gate has been passed."""
    st.session_state["setup_complete"] = complete


def get_setup_complete() -> bool:
    """Return True if the setup gate has been passed."""
    return bool(st.session_state.get("setup_complete", False))


def get_or_create_graph_thread_id() -> str:
    """Return a stable per-session thread ID for the LangGraph checkpointer."""
    if "graph_thread_id" not in st.session_state:
        st.session_state["graph_thread_id"] = str(uuid.uuid4())
    return str(st.session_state["graph_thread_id"])


def clear_all_credentials() -> None:
    """Remove all credential-related keys from session state."""
    for key in (
        "openai_key",
        "gcp_sa_json",
        "gcp_project_id",
        "monthly_cost_cap_usd",
        "setup_complete",
        "graph_thread_id",
    ):
        st.session_state.pop(key, None)
