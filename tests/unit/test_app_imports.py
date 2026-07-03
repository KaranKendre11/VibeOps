from __future__ import annotations

import importlib

_MODULES = [
    "vibeops",
    "vibeops.config",
    "vibeops.core.errors",
    "vibeops.core.logging",
    "vibeops.core.auth",
    "vibeops.core.llm",
    "vibeops.core.analytics",
    "vibeops.models.state",
    "vibeops.models.requirement",
    "vibeops.models.spec",
    "vibeops.models.results",
    "vibeops.graph.state",
    "vibeops.graph.orchestrator",
    "vibeops.agents.requirement",
    "vibeops.agents.architecture",
    "vibeops.agents.iac",
    "vibeops.agents.deployment",
    "vibeops.api.main",
    "vibeops.api.session",
    "vibeops.services.review",
    "vibeops.services.conversation",
]


def test_all_modules_importable() -> None:
    """Catch circular imports and missing __init__ files early."""
    for module in _MODULES:
        mod = importlib.import_module(module)
        assert mod is not None, f"Failed to import {module}"


def test_build_graph_is_callable() -> None:
    from vibeops.graph.orchestrator import build_graph

    assert callable(build_graph)


def test_approval_router_is_callable() -> None:
    from vibeops.graph.orchestrator import approval_router

    assert callable(approval_router)
