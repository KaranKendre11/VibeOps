"""In-memory API session store (backend foundation for the React migration)."""
from __future__ import annotations

from vibeops.api.session import Session, SessionStore


def test_create_allocates_distinct_ids() -> None:
    store = SessionStore()
    s = store.create()
    assert s.id and s.thread_id and s.id != s.thread_id
    assert store.get(s.id) is s


def test_get_missing_or_none_returns_none() -> None:
    store = SessionStore()
    assert store.get("nope") is None
    assert store.get(None) is None


def test_delete_removes_session() -> None:
    store = SessionStore()
    s = store.create()
    store.delete(s.id)
    assert store.get(s.id) is None


def test_reset_credentials_clears_all() -> None:
    s = Session(
        id="a",
        thread_id="t",
        openai_key="sk-x",
        gcp_project_id="p",
        gcp_sa_json={"client_email": "x"},
        setup_complete=True,
        demo_mode=True,
    )
    s.reset_credentials()
    assert s.openai_key is None
    assert s.gcp_sa_json is None
    assert s.gcp_project_id is None
    assert s.gcp_context is None
    assert s.llm_client is None
    assert s.setup_complete is False
    assert s.demo_mode is False


def test_ensure_clients_is_noop_without_credentials() -> None:
    s = Session(id="a", thread_id="t")
    s.ensure_clients()
    assert s.llm_client is None
    assert s.gcp_context is None
