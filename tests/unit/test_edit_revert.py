from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from vibeops.models.iac import TerraformValidationResult
from vibeops.models.state import FlowStage, GraphState
from vibeops.services.review import apply_user_edit

_ORIGINAL = 'resource "google_compute_instance" "gpu_vm" { name = "original" }\n'
_EDIT_1 = 'resource "google_compute_instance" "gpu_vm" { name = "edit-one" }\n'
_EDIT_2 = 'resource "google_compute_instance" "gpu_vm" { name = "edit-two" }\n'


def _state(tmp_path: Path, content: str = _ORIGINAL) -> GraphState:
    (tmp_path / "main.tf").write_text(content, encoding="utf-8")
    return GraphState(
        user_prompt="test",
        stage=FlowStage.AWAITING_APPROVAL,
        terraform_dir=str(tmp_path),
        terraform_files={"main.tf": content},
        terraform_files_original={"main.tf": _ORIGINAL},
    )


def _save(state: GraphState, content: str) -> GraphState:
    new_state, err = apply_user_edit(state, "main.tf", content)
    assert err is None
    return new_state


class TestEditRevert:
    def test_revert_after_single_edit(self, tmp_path: Path) -> None:
        """After one edit, reverting restores original_files content."""
        with patch(
            "vibeops.services.review.validate",
            return_value=TerraformValidationResult(ok=True),
        ), patch(
            "vibeops.services.review.check_resource_allowlist",
            return_value=__import__("unittest.mock", fromlist=["MagicMock"]).MagicMock(
                ok=True, violations=[]
            ),
        ):
            state = _state(tmp_path)
            state = _save(state, _EDIT_1)
            assert state.terraform_files["main.tf"] == _EDIT_1

        # Revert: simulate what the UI does — restore from terraform_files_original
        reverted = {**state.terraform_files, "main.tf": state.terraform_files_original["main.tf"]}
        state = state.model_copy(update={"terraform_files": reverted})
        assert state.terraform_files["main.tf"] == _ORIGINAL

    def test_revert_after_multiple_edits_restores_generated(self, tmp_path: Path) -> None:
        """Revert always goes back to the originally generated content, not the previous edit."""
        with patch(
            "vibeops.services.review.validate",
            return_value=TerraformValidationResult(ok=True),
        ), patch(
            "vibeops.services.review.check_resource_allowlist",
            return_value=__import__("unittest.mock", fromlist=["MagicMock"]).MagicMock(
                ok=True, violations=[]
            ),
        ):
            state = _state(tmp_path)
            state = _save(state, _EDIT_1)
            state = _save(state, _EDIT_2)
            assert state.terraform_files["main.tf"] == _EDIT_2

        # Revert always to original, not to EDIT_1
        reverted = {**state.terraform_files, "main.tf": state.terraform_files_original["main.tf"]}
        state = state.model_copy(update={"terraform_files": reverted})
        assert state.terraform_files["main.tf"] == _ORIGINAL
        assert state.terraform_files["main.tf"] != _EDIT_1

    def test_terraform_files_original_never_changes(self, tmp_path: Path) -> None:
        """apply_user_edit must not mutate terraform_files_original."""
        with patch(
            "vibeops.services.review.validate",
            return_value=TerraformValidationResult(ok=True),
        ), patch(
            "vibeops.services.review.check_resource_allowlist",
            return_value=__import__("unittest.mock", fromlist=["MagicMock"]).MagicMock(
                ok=True, violations=[]
            ),
        ):
            state = _state(tmp_path)
            state = _save(state, _EDIT_1)
            state = _save(state, _EDIT_2)

        assert state.terraform_files_original["main.tf"] == _ORIGINAL
