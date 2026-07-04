from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from vibeops.core.policy import (
    check_dir_allowlist,
    check_resource_allowlist,
    is_safe_edit_filename,
)


def _write_hcl(tmp_path: Path, content: str) -> Path:
    p = tmp_path / "main.tf"
    p.write_text(textwrap.dedent(content))
    return p


# ---------------------------------------------------------------------------
# Allowed resource types — should return ok=True
# ---------------------------------------------------------------------------


class TestAllowedResources:
    @pytest.mark.parametrize(
        "resource_type",
        [
            "google_compute_instance",
            "google_compute_disk",
            "google_compute_attached_disk",
            "google_compute_firewall",
        ],
    )
    def test_allowed_resource_returns_ok(self, tmp_path: Path, resource_type: str) -> None:
        hcl_path = _write_hcl(
            tmp_path,
            f"""
            resource "{resource_type}" "test" {{
              name = "test"
            }}
            """,
        )
        result = check_resource_allowlist(hcl_path)
        assert result.ok is True
        assert result.violations == []

    def test_empty_file_returns_ok(self, tmp_path: Path) -> None:
        hcl_path = tmp_path / "main.tf"
        hcl_path.write_text("")
        result = check_resource_allowlist(hcl_path)
        assert result.ok is True
        assert result.violations == []

    def test_multiple_allowed_resources_returns_ok(self, tmp_path: Path) -> None:
        hcl_path = _write_hcl(
            tmp_path,
            """
            resource "google_compute_instance" "vm" {
              name = "vm"
            }
            resource "google_compute_disk" "disk" {
              name = "disk"
            }
            """,
        )
        result = check_resource_allowlist(hcl_path)
        assert result.ok is True
        assert result.violations == []


# ---------------------------------------------------------------------------
# Disallowed resource types — should return ok=False with violation
# ---------------------------------------------------------------------------


class TestDisallowedResources:
    @pytest.mark.parametrize(
        "resource_type",
        [
            "google_project_iam_binding",
            "google_project_iam_member",
            "google_project_iam_policy",
            "google_storage_bucket",
            "google_sql_database_instance",
            "google_container_cluster",
        ],
    )
    def test_disallowed_resource_returns_violation(
        self, tmp_path: Path, resource_type: str
    ) -> None:
        hcl_path = _write_hcl(
            tmp_path,
            f"""
            resource "{resource_type}" "bad" {{
              name = "bad"
            }}
            """,
        )
        result = check_resource_allowlist(hcl_path)
        assert result.ok is False
        assert len(result.violations) == 1
        assert result.violations[0].resource_type == resource_type

    def test_violation_resource_type_is_exact_string(self, tmp_path: Path) -> None:
        hcl_path = _write_hcl(
            tmp_path,
            """
            resource "google_project_iam_binding" "bad" {
              role = "roles/viewer"
            }
            """,
        )
        result = check_resource_allowlist(hcl_path)
        assert result.violations[0].resource_type == "google_project_iam_binding"

    def test_mixed_allowed_and_disallowed_reports_only_violations(self, tmp_path: Path) -> None:
        hcl_path = _write_hcl(
            tmp_path,
            """
            resource "google_compute_instance" "vm" {
              name = "vm"
            }
            resource "google_storage_bucket" "bad" {
              name = "bad"
            }
            """,
        )
        result = check_resource_allowlist(hcl_path)
        assert result.ok is False
        assert len(result.violations) == 1
        assert result.violations[0].resource_type == "google_storage_bucket"

    def test_two_disallowed_resources_two_violations(self, tmp_path: Path) -> None:
        hcl_path = _write_hcl(
            tmp_path,
            """
            resource "google_project_iam_binding" "a" { role = "roles/viewer" }
            resource "google_storage_bucket" "b" { name = "b" }
            """,
        )
        result = check_resource_allowlist(hcl_path)
        assert result.ok is False
        types = {v.resource_type for v in result.violations}
        assert types == {"google_project_iam_binding", "google_storage_bucket"}


# ---------------------------------------------------------------------------
# Directory-wide allowlist — every *.tf is checked, not just main.tf
# ---------------------------------------------------------------------------


class TestCheckDirAllowlist:
    def test_all_allowed_across_files_is_ok(self, tmp_path: Path) -> None:
        (tmp_path / "main.tf").write_text(
            'resource "google_compute_instance" "vm" { name = "vm" }\n'
        )
        (tmp_path / "outputs.tf").write_text('output "n" { value = "vm" }\n')
        result = check_dir_allowlist(tmp_path)
        assert result.ok is True
        assert result.violations == []

    def test_disallowed_in_outputs_tf_is_flagged(self, tmp_path: Path) -> None:
        """The core of the bypass fix: a violation hiding outside main.tf is caught."""
        (tmp_path / "main.tf").write_text(
            'resource "google_compute_instance" "vm" { name = "vm" }\n'
        )
        (tmp_path / "outputs.tf").write_text(
            'resource "google_storage_bucket" "b" { name = "b" }\n'
        )
        result = check_dir_allowlist(tmp_path)
        assert result.ok is False
        assert [v.resource_type for v in result.violations] == ["google_storage_bucket"]

    def test_violations_aggregated_across_files(self, tmp_path: Path) -> None:
        (tmp_path / "main.tf").write_text('resource "google_storage_bucket" "a" { name = "a" }\n')
        (tmp_path / "extra.tf").write_text(
            'resource "google_project_iam_binding" "b" { role = "roles/editor" }\n'
        )
        result = check_dir_allowlist(tmp_path)
        assert result.ok is False
        assert {v.resource_type for v in result.violations} == {
            "google_storage_bucket",
            "google_project_iam_binding",
        }

    def test_non_tf_files_are_ignored(self, tmp_path: Path) -> None:
        (tmp_path / "main.tf").write_text(
            'resource "google_compute_instance" "vm" { name = "vm" }\n'
        )
        # A disallowed resource in a .tfvars / non-.tf file is not terraform config — ignore it.
        (tmp_path / "vibeops.auto.tfvars").write_text('project_id = "p"\n')
        (tmp_path / "notes.txt").write_text('resource "google_storage_bucket" "x" {}\n')
        result = check_dir_allowlist(tmp_path)
        assert result.ok is True

    def test_empty_dir_is_ok(self, tmp_path: Path) -> None:
        result = check_dir_allowlist(tmp_path)
        assert result.ok is True
        assert result.violations == []


# ---------------------------------------------------------------------------
# Edit-filename whitelist
# ---------------------------------------------------------------------------


class TestIsSafeEditFilename:
    @pytest.mark.parametrize("name", ["main.tf", "variables.tf", "outputs.tf"])
    def test_editable_files_are_safe(self, name: str) -> None:
        assert is_safe_edit_filename(name) is True

    @pytest.mark.parametrize(
        "name",
        [
            "../secrets.tf",
            "..\\..\\evil.tf",
            "/etc/passwd",
            "sub/dir.tf",
            "sub\\dir.tf",
            "provider.tf",
            "main.tf.bak",
            "evil.txt",
            "main.tf ",  # trailing space
            "",
        ],
    )
    def test_unsafe_names_are_rejected(self, name: str) -> None:
        assert is_safe_edit_filename(name) is False
