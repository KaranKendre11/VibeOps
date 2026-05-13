from __future__ import annotations

from unittest.mock import MagicMock, patch

from vibeops.agents.deployment import deployment_agent, destroy_agent
from vibeops.models.deployment import ApplyResult, DeploymentPhase, DestroyResult, PlanResult, StateResource
from vibeops.models.state import FlowStage, GraphState


def _deploy_state() -> GraphState:
    return GraphState(
        user_prompt="test",
        terraform_dir="/tmp/tf",
        approved=True,
        stage=FlowStage.AWAITING_APPROVAL,
    )


def _destroy_state() -> GraphState:
    return GraphState(
        user_prompt="test",
        terraform_dir="/tmp/tf",
        destroy_confirmed=True,
        deployment_phase=DeploymentPhase.AWAITING_DESTROY_CONFIRM,
        created_resources=[StateResource(type="google_compute_instance", name="vm")],
    )


def test_deployment_agent_never_calls_llm() -> None:
    """deployment_agent must not call LLMClient even when one is provided in config."""
    llm = MagicMock()
    llm.chat_completion.side_effect = AssertionError("deployment_agent called LLM — architectural violation")

    from langchain_core.runnables import RunnableConfig
    config = RunnableConfig(configurable={"llm_client": llm})

    with (
        patch("vibeops.agents.deployment.runner.plan", return_value=PlanResult(plan_file="/tmp/tf/tfplan")),
        patch("vibeops.agents.deployment.runner.apply", return_value=ApplyResult(full_log="done", resources_created=0)),
        patch("vibeops.agents.deployment.runner.parse_state_resources", return_value=[]),
    ):
        deployment_agent(_deploy_state(), config)

    llm.chat_completion.assert_not_called()


def test_destroy_agent_never_calls_llm() -> None:
    """destroy_agent must not call LLMClient even when one is provided."""
    llm = MagicMock()
    llm.chat_completion.side_effect = AssertionError("destroy_agent called LLM — architectural violation")

    from langchain_core.runnables import RunnableConfig
    config = RunnableConfig(configurable={"llm_client": llm})

    with patch("vibeops.agents.deployment.runner.destroy", return_value=DestroyResult(full_log="done", resources_destroyed=1)):
        destroy_agent(_destroy_state(), config)

    llm.chat_completion.assert_not_called()
