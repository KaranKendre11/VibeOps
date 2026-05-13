from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from vibeops.models.iac import TerraformValidationResult
from vibeops.models.state import FlowStage, GraphState
from vibeops.ui.review import apply_user_edit

_ORIGINAL = 'resource "google_compute_instance" "gpu_vm" { name = "ok" }\n'
_BROKEN = 'resource "google_compute_instance" "gpu_vm" { name = MISSING_QUOTE }\n'


def _state(tmp_path: Path) -> GraphState:
    (tmp_path / "main.tf").write_text(_ORIGINAL, encoding="utf-8")
    return GraphState(
        user_prompt="test",
        stage=FlowStage.AWAITING_APPROVAL,
        terraform_dir=str(tmp_path),
        terraform_files={"main.tf": _ORIGINAL},
        terraform_files_original={"main.tf": _ORIGINAL},
    )


class TestEditSaveInvalidHcl:
    def test_error_returned_when_validate_fails(self, tmp_path: Path) -> None:
        state = _state(tmp_path)

        with patch(
            "vibeops.ui.review.validate",
            return_value=TerraformValidationResult(
                ok=False, errors=["Invalid expression: An argument definition must end with a newline."]
            ),
        ):
            _, err = apply_user_edit(state, "main.tf", _BROKEN)

        assert err is not None
        assert "Validation failed" in err

    def test_state_not_updated_on_invalid(self, tmp_path: Path) -> None:
        state = _state(tmp_path)

        with patch(
            "vibeops.ui.review.validate",
            return_value=TerraformValidationResult(ok=False, errors=["syntax error"]),
        ):
            new_state, _ = apply_user_edit(state, "main.tf", _BROKEN)

        assert new_state.terraform_files["main.tf"] == _ORIGINAL

    def test_file_restored_on_disk_on_invalid(self, tmp_path: Path) -> None:
        state = _state(tmp_path)

        with patch(
            "vibeops.ui.review.validate",
            return_value=TerraformValidationResult(ok=False, errors=["bad syntax"]),
        ):
            apply_user_edit(state, "main.tf", _BROKEN)

        assert (tmp_path / "main.tf").read_text(encoding="utf-8") == _ORIGINAL

    def test_cost_estimate_not_stale_on_failure(self, tmp_path: Path) -> None:
        state = _state(tmp_path)

        with patch(
            "vibeops.ui.review.validate",
            return_value=TerraformValidationResult(ok=False, errors=["err"]),
        ):
            new_state, _ = apply_user_edit(state, "main.tf", _BROKEN)

        assert new_state.cost_estimate_stale is False
