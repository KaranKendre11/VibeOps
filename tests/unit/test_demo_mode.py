"""Demo mode: credential-free walkthrough — renders real Terraform + a representative cost, and
SIMULATES apply/destroy (no real cloud) so the end-to-end demo (deploy → VM inventory) works."""
from __future__ import annotations

import tempfile
from unittest.mock import MagicMock, patch

from vibeops.agents.architecture import architecture_agent
from vibeops.agents.deployment import deployment_agent
from vibeops.agents.iac import iac_agent
from vibeops.agents.requirement import requirement_agent
from vibeops.models.deployment import DeploymentOutcome, DeploymentPhase
from vibeops.models.state import FlowStage, GraphState

_DEMO_CONFIG = {"configurable": {"demo_mode": True}}


def _spec_state() -> GraphState:
    """Requirement -> architecture stubs produce a valid DeploymentSpec (no creds)."""
    return architecture_agent(requirement_agent(GraphState(user_prompt="a T4 for Jupyter")))


class TestIacDemoPipeline:
    def test_renders_real_terraform(self) -> None:
        result = iac_agent(_spec_state(), _DEMO_CONFIG)
        assert result.stage == FlowStage.AWAITING_APPROVAL
        assert set(result.terraform_files) == {"main.tf", "variables.tf", "outputs.tf"}
        # Real rendered HCL, not an empty/placeholder blob.
        assert "google_compute_instance" in result.terraform_files["main.tf"]

    def test_shows_believable_cost(self) -> None:
        result = iac_agent(_spec_state(), _DEMO_CONFIG)
        assert result.cost_estimate is not None
        assert result.cost_estimate_usd is not None and result.cost_estimate_usd > 0
        assert any("demo" in n.lower() for n in result.cost_estimate.notes)
        assert result.cost_estimate.breakdown  # GPU + machine + disk line items

    def test_demo_wins_even_if_llm_client_leaks(self) -> None:
        # Regression: a stale real llm_client (e.g. Reconfigure -> demo in the same session)
        # must NOT knock demo mode into the real pipeline; the offline demo must still run.
        config = {"configurable": {"demo_mode": True, "llm_client": MagicMock()}}
        result = iac_agent(_spec_state(), config)
        assert result.cost_estimate is not None
        assert result.cost_estimate_usd and result.cost_estimate_usd > 0
        assert any("demo" in n.lower() for n in result.cost_estimate.notes)

    def test_no_config_keeps_static_stub_zero_cost(self) -> None:
        # Regression guard: the plain no-LLM stub path must stay $0.00 (test_stubs.py).
        result = iac_agent(_spec_state())
        assert result.cost_estimate_usd == 0.0


class TestDeploymentSimulatedInDemo:
    def _deploy_state(self) -> GraphState:
        return _spec_state().model_copy(
            update={
                "approved": True,
                "stage": FlowStage.DEPLOYMENT,
                "terraform_dir": tempfile.mkdtemp(prefix="vibeops_demo_test_"),
            }
        )

    def test_apply_is_simulated_without_running_terraform(self) -> None:
        logs: list[str] = []
        config = {"configurable": {"demo_mode": True, "on_log": logs.append}}
        with (
            patch("vibeops.agents.deployment.runner.plan") as plan_mock,
            patch("vibeops.agents.deployment.runner.apply") as apply_mock,
        ):
            result = deployment_agent(self._deploy_state(), config)

        plan_mock.assert_not_called()
        apply_mock.assert_not_called()
        assert result.deployment_phase == DeploymentPhase.SUCCEEDED
        assert result.deployment_outcome == DeploymentOutcome.SUCCEEDED
        assert result.created_resources
        assert result.created_resources[0].type == "google_compute_instance"
        assert any("Apply complete" in ln for ln in logs)  # streamed via on_log

    def test_destroy_is_simulated(self) -> None:
        from vibeops.agents.deployment import destroy_agent

        state = self._deploy_state().model_copy(update={"destroy_confirmed": True})
        with patch("vibeops.agents.deployment.runner.destroy") as destroy_mock:
            result = destroy_agent(state, _DEMO_CONFIG)

        destroy_mock.assert_not_called()
        assert result.deployment_phase == DeploymentPhase.DESTROYED
        assert result.created_resources == []
