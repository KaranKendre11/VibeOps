"""Server-side enforcement of the monthly cost cap at the deploy gate (issue #1).

Covers the three required cases — over-cap is blocked, over-cap + override deploys, under-cap
deploys normally — at the router, HTTP route, and IaC-flagging layers, plus a defence-in-depth
graph check that a forced ``approved=True`` cannot bypass the cap.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from vibeops.agents.iac import iac_agent
from vibeops.api.main import app
from vibeops.api.session import SESSION_COOKIE, Session, get_store
from vibeops.graph.orchestrator import approval_router, build_graph
from vibeops.models.iac import CostEstimate, TerraformValidationResult
from vibeops.models.spec import ComputeSpec, DeploymentSpec, GpuType, NetworkSpec, StorageSpec
from vibeops.models.state import FlowStage, GraphState


def _state(**kwargs: object) -> GraphState:
    return GraphState(user_prompt="test prompt", **kwargs)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# approval_router — the fail-closed gate
# ---------------------------------------------------------------------------


class TestApprovalRouterCostCap:
    def test_over_cap_without_override_routes_to_cancelled(self) -> None:
        state = _state(
            approved=True,
            cost_cap_exceeded=True,
            cost_cap_override=False,
            stage=FlowStage.AWAITING_APPROVAL,
        )
        assert approval_router(state) == "cancelled"

    def test_over_cap_with_override_routes_to_deployment(self) -> None:
        state = _state(
            approved=True,
            cost_cap_exceeded=True,
            cost_cap_override=True,
            stage=FlowStage.AWAITING_APPROVAL,
        )
        assert approval_router(state) == "deployment"

    def test_under_cap_approved_routes_to_deployment(self) -> None:
        state = _state(approved=True, cost_cap_exceeded=False, stage=FlowStage.AWAITING_APPROVAL)
        assert approval_router(state) == "deployment"

    def test_unapproved_is_cancelled_even_with_override(self) -> None:
        state = _state(
            approved=False,
            cost_cap_exceeded=True,
            cost_cap_override=True,
            stage=FlowStage.AWAITING_APPROVAL,
        )
        assert approval_router(state) == "cancelled"

    def test_override_must_be_literal_true(self) -> None:
        """A non-True override must not unlock an over-cap deploy (fails closed)."""
        for value in (False, None):
            state = GraphState.model_construct(
                user_prompt="test",
                approved=True,
                cost_cap_exceeded=True,
                cost_cap_override=value,
                stage=FlowStage.AWAITING_APPROVAL,
                chat_history=[],
                terraform_files={},
            )
            assert approval_router(state) == "cancelled", f"override={value!r} should not deploy"


# ---------------------------------------------------------------------------
# Compiled graph — the over-cap plan must not reach the deployment node
# ---------------------------------------------------------------------------


def test_deployment_unreachable_over_cap_without_override(mocker: MagicMock) -> None:
    """Even with approved=True forced on, an over-cap plan (no override) is cancelled."""
    deploy_spy = mocker.patch("vibeops.agents.deployment.deployment_agent")

    graph = build_graph()
    thread = {"configurable": {"thread_id": "cap-gate-nooverride"}}
    graph.invoke(GraphState(user_prompt="test prompt").model_dump(), thread)

    graph.update_state(
        thread,
        {"approved": True, "cost_cap_exceeded": True, "cost_cap_override": False},
    )
    graph.invoke(None, thread)

    final = GraphState.model_validate(graph.get_state(thread).values)
    assert final.stage == FlowStage.CANCELLED
    deploy_spy.assert_not_called()


# ---------------------------------------------------------------------------
# HTTP route — POST /api/deploy/start enforces the cap
# ---------------------------------------------------------------------------


def _session_at_review(c: TestClient, **overrides: object) -> Session:
    """Create a session whose graph is paused at review with the given state overrides."""
    c.post("/api/session")
    session = get_store().get(c.cookies.get(SESSION_COOKIE))
    assert session is not None
    session.graph = build_graph()
    seed = GraphState(user_prompt="x", stage=FlowStage.AWAITING_APPROVAL, **overrides)  # type: ignore[arg-type]
    session.graph.update_state(
        {"configurable": {"thread_id": session.thread_id}}, seed.model_dump()
    )
    return session


def test_over_cap_deploy_blocked_returns_409() -> None:
    c = TestClient(app)
    _session_at_review(c, cost_cap_exceeded=True)
    with patch("vibeops.api.routes_deploy._launch") as mock_launch:
        r = c.post("/api/deploy/start")
    assert r.status_code == 409
    assert "cap" in r.json()["detail"].lower()
    mock_launch.assert_not_called()


def test_over_cap_deploy_with_override_starts() -> None:
    c = TestClient(app)
    _session_at_review(c, cost_cap_exceeded=True)
    with patch("vibeops.api.routes_deploy._launch") as mock_launch:
        r = c.post("/api/deploy/start", json={"override_cost_cap": True})
    assert r.status_code == 200
    assert r.json()["status"] == "started"
    mock_launch.assert_called_once()
    _, updates = mock_launch.call_args.args
    assert updates == {"approved": True, "cost_cap_override": True}


def test_under_cap_deploy_starts() -> None:
    c = TestClient(app)
    _session_at_review(c, cost_cap_exceeded=False)
    with patch("vibeops.api.routes_deploy._launch") as mock_launch:
        r = c.post("/api/deploy/start")
    assert r.status_code == 200
    mock_launch.assert_called_once()
    _, updates = mock_launch.call_args.args
    assert updates == {"approved": True, "cost_cap_override": False}


# ---------------------------------------------------------------------------
# IaC agent — the session cap (not a hardcoded 500) is the single source of truth
# ---------------------------------------------------------------------------


def _spec() -> DeploymentSpec:
    return DeploymentSpec(
        compute=ComputeSpec(
            machine_type="n1-standard-4",
            zone="us-central1-a",
            gpu_type=GpuType.T4,
            gpu_count=1,
            preemptible=False,
            custom_startup_script_request=None,
        ),
        storage=StorageSpec(
            disk_size_gb=100,
            os_image_family="common-cu121",
            os_image_project="deeplearning-platform-release",
        ),
        network=NetworkSpec(network_name="default"),
        project_id="test-project",
    )


def _run_iac_with_cost(cost_cap_usd: float, monthly_cost: float) -> GraphState:
    estimate = CostEstimate(
        hourly_usd=monthly_cost / 730.0,
        monthly_usd=monthly_cost,
        source="cloud_catalog",
        confidence="medium",
    )
    config = {
        "configurable": {
            "llm_client": MagicMock(),
            "gcp_context": None,
            "cost_cap_usd": cost_cap_usd,
        }
    }
    state = GraphState(user_prompt="deploy a T4 VM", deployment_spec=_spec(), stage=FlowStage.IAC)
    with (
        patch("vibeops.agents.iac.init"),
        patch("vibeops.agents.iac.validate", return_value=TerraformValidationResult(ok=True)),
        patch(
            "vibeops.agents.iac.check_resource_allowlist",
            return_value=MagicMock(ok=True, violations=[]),
        ),
        patch("vibeops.cost.estimate", return_value=estimate),
    ):
        return iac_agent(state, config)


def test_iac_flags_exceeded_against_session_cap() -> None:
    # $300/mo was UNDER the retired hardcoded $500 default but is OVER the real $200 session cap.
    result = _run_iac_with_cost(cost_cap_usd=200.0, monthly_cost=300.0)
    assert result.cost_cap_exceeded is True


def test_iac_not_flagged_when_under_session_cap() -> None:
    result = _run_iac_with_cost(cost_cap_usd=400.0, monthly_cost=300.0)
    assert result.cost_cap_exceeded is False


def test_no_hardcoded_cost_cap_constant_remains() -> None:
    import vibeops.agents.iac as iac_mod

    assert not hasattr(iac_mod, "_DEFAULT_COST_CAP_USD")


def test_demo_mode_is_never_cost_gated() -> None:
    """Demo deploys are simulated (no real spend), so the cap must not gate them."""
    from vibeops.agents.architecture import architecture_agent
    from vibeops.agents.requirement import requirement_agent

    spec_state = architecture_agent(requirement_agent(GraphState(user_prompt="a T4 for Jupyter")))
    # Tiny cap: the representative demo cost is far above it, yet demo must not be flagged.
    result = iac_agent(spec_state, {"configurable": {"demo_mode": True, "cost_cap_usd": 1.0}})
    assert result.cost_estimate_usd is not None and result.cost_estimate_usd > 1.0
    assert result.cost_cap_exceeded is False
