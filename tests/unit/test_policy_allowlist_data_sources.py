from __future__ import annotations

import textwrap
from pathlib import Path

from vibeops.core.policy import check_resource_allowlist


def _write_hcl(tmp_path: Path, content: str) -> Path:
    p = tmp_path / "main.tf"
    p.write_text(textwrap.dedent(content))
    return p


class TestDataSources:
    def test_allowed_data_source_network_returns_ok(self, tmp_path: Path) -> None:
        hcl_path = _write_hcl(
            tmp_path,
            """
            data "google_compute_network" "net" {
              name = "default"
            }
            """,
        )
        result = check_resource_allowlist(hcl_path)
        assert result.ok is True
        assert result.violations == []

    def test_allowed_data_source_subnetwork_returns_ok(self, tmp_path: Path) -> None:
        hcl_path = _write_hcl(
            tmp_path,
            """
            data "google_compute_subnetwork" "sub" {
              name = "default"
            }
            """,
        )
        result = check_resource_allowlist(hcl_path)
        assert result.ok is True

    def test_allowed_data_source_image_returns_ok(self, tmp_path: Path) -> None:
        hcl_path = _write_hcl(
            tmp_path,
            """
            data "google_compute_image" "img" {
              family  = "debian-11"
              project = "debian-cloud"
            }
            """,
        )
        result = check_resource_allowlist(hcl_path)
        assert result.ok is True

    def test_resource_network_is_disallowed(self, tmp_path: Path) -> None:
        """google_compute_network is allowed as a data source but not as a resource block."""
        hcl_path = _write_hcl(
            tmp_path,
            """
            resource "google_compute_network" "net" {
              name = "my-vpc"
            }
            """,
        )
        result = check_resource_allowlist(hcl_path)
        assert result.ok is False
        assert result.violations[0].resource_type == "google_compute_network"

    def test_resource_subnetwork_is_disallowed(self, tmp_path: Path) -> None:
        hcl_path = _write_hcl(
            tmp_path,
            """
            resource "google_compute_subnetwork" "sub" {
              name = "my-sub"
            }
            """,
        )
        result = check_resource_allowlist(hcl_path)
        assert result.ok is False
        assert result.violations[0].resource_type == "google_compute_subnetwork"

    def test_mixed_allowed_data_and_disallowed_resource_in_same_file(
        self, tmp_path: Path
    ) -> None:
        """Data block is fine; resource block of the same type is not."""
        hcl_path = _write_hcl(
            tmp_path,
            """
            data "google_compute_network" "existing" {
              name = "default"
            }
            resource "google_compute_network" "new" {
              name = "my-new-vpc"
            }
            """,
        )
        result = check_resource_allowlist(hcl_path)
        assert result.ok is False
        assert len(result.violations) == 1
        assert result.violations[0].resource_type == "google_compute_network"

    def test_unknown_data_source_is_disallowed(self, tmp_path: Path) -> None:
        hcl_path = _write_hcl(
            tmp_path,
            """
            data "google_storage_bucket" "bucket" {
              name = "my-bucket"
            }
            """,
        )
        result = check_resource_allowlist(hcl_path)
        assert result.ok is False
        assert result.violations[0].resource_type == "google_storage_bucket"
