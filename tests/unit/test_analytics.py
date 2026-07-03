"""Privacy-safe funnel analytics: never raises, never emits PII, dedupes per session."""
from __future__ import annotations

import json
import logging

import pytest

from vibeops.core import analytics


def _events(caplog: pytest.LogCaptureFixture) -> list[dict]:
    out: list[dict] = []
    for rec in caplog.records:
        msg = rec.getMessage()
        if msg.startswith(analytics._EVENT_PREFIX):
            out.append(json.loads(msg[len(analytics._EVENT_PREFIX) + 1 :]))
    return out


def test_track_never_raises() -> None:
    analytics.track("weird", {"obj": object(), "n": 1}, session_id="s1")
    analytics.track("empty")  # no session id, no props


def test_blocked_keys_stripped_and_session_id_used(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO, logger="vibeops.analytics"):
        analytics.track(
            "requirement_submitted",
            {
                "gpu_type": "nvidia-tesla-t4",
                "openai_key": "sk-shouldnotappear",
                "private_key": "-----BEGIN PRIVATE KEY-----",
                "project_id": "secret-project",
                "client_email": "a@b.iam",
            },
            session_id="sess-1",
        )
    payload = _events(caplog)[0]
    assert payload["event"] == "requirement_submitted"
    assert payload["gpu_type"] == "nvidia-tesla-t4"
    assert payload["session_id"] == "sess-1"
    for blocked in ("openai_key", "private_key", "project_id", "client_email"):
        assert blocked not in payload
    raw = " ".join(r.getMessage() for r in caplog.records)
    assert "sk-shouldnotappear" not in raw
    assert "secret-project" not in raw


def test_track_once_dedupes_with_session_set(caplog: pytest.LogCaptureFixture) -> None:
    fired: set[str] = set()
    with caplog.at_level(logging.INFO, logger="vibeops.analytics"):
        analytics.track_once("review_reached", session_id="s1", fired=fired)
        analytics.track_once("review_reached", session_id="s1", fired=fired)
    assert len([e for e in _events(caplog) if e["event"] == "review_reached"]) == 1


def test_track_once_process_fallback_is_per_session(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO, logger="vibeops.analytics"):
        analytics.track_once("proc_only_evt", session_id="sA")
        analytics.track_once("proc_only_evt", session_id="sA")  # deduped
        analytics.track_once("proc_only_evt", session_id="sB")  # different session → fires
    events = [e for e in _events(caplog) if e["event"] == "proc_only_evt"]
    assert len(events) == 2
    assert {e["session_id"] for e in events} == {"sA", "sB"}
