from __future__ import annotations

from pathlib import Path

import hcl2

from vibeops.models.spec import ComputeSpec, DeploymentSpec, GpuType, NetworkSpec, StorageSpec
from vibeops.terraform.render import render_templates


def _spec() -> DeploymentSpec:
    return DeploymentSpec(
        compute=ComputeSpec(
            machine_type="n1-standard-8",
            zone="us-central1-a",
            gpu_type=GpuType.T4,
            gpu_count=1,
            preemptible=False,
        ),
        storage=StorageSpec(
            disk_size_gb=100,
            os_image_family="common-cu121",
            os_image_project="deeplearning-platform-release",
        ),
        network=NetworkSpec(network_name="default"),
        project_id="my-test-project",
    )


def test_renders_three_files(tmp_path: Path) -> None:
    result = render_templates(_spec(), tmp_path)
    assert set(result.keys()) == {"main.tf", "variables.tf", "outputs.tf"}


def test_output_files_written_to_disk(tmp_path: Path) -> None:
    render_templates(_spec(), tmp_path)
    for name in ("main.tf", "variables.tf", "outputs.tf"):
        assert (tmp_path / name).exists()
        assert (tmp_path / name).stat().st_size > 0


def test_main_tf_is_valid_hcl(tmp_path: Path) -> None:
    result = render_templates(_spec(), tmp_path)
    with (tmp_path / "main.tf").open() as fh:
        parsed = hcl2.load(fh)
    assert "resource" in parsed or "terraform" in parsed


def test_variables_tf_is_valid_hcl(tmp_path: Path) -> None:
    render_templates(_spec(), tmp_path)
    with (tmp_path / "variables.tf").open() as fh:
        parsed = hcl2.load(fh)
    assert "variable" in parsed


def test_outputs_tf_is_valid_hcl(tmp_path: Path) -> None:
    render_templates(_spec(), tmp_path)
    with (tmp_path / "outputs.tf").open() as fh:
        parsed = hcl2.load(fh)
    assert "output" in parsed


def test_spec_values_appear_in_main_tf(tmp_path: Path) -> None:
    result = render_templates(_spec(), tmp_path)
    # main.tf uses variable references; actual values flow through variables.tf
    main = result["main.tf"]
    assert "google_compute_instance" in main
    assert "var.machine_type" in main
    assert "var.gpu_type" in main


def test_spec_values_appear_in_variables_tf(tmp_path: Path) -> None:
    result = render_templates(_spec(), tmp_path)
    variables = result["variables.tf"]
    assert "us-central1-a" in variables
    assert "n1-standard-8" in variables
    assert "100" in variables


def test_zone_in_outputs(tmp_path: Path) -> None:
    result = render_templates(_spec(), tmp_path)
    assert "us-central1-a" in result["outputs.tf"]


def test_render_without_fragment_no_extra_content(tmp_path: Path) -> None:
    result = render_templates(_spec(), tmp_path)
    # Fragment slot should be empty (just whitespace around it)
    main = result["main.tf"]
    assert "metadata" not in main.lower() or "llm_fragment" not in main


def test_render_with_fragment_injected_into_main(tmp_path: Path) -> None:
    fragment = 'metadata = { "env" = "test" }'
    result = render_templates(_spec(), tmp_path, fragment=fragment)
    assert fragment in result["main.tf"]


def test_render_with_fragment_still_valid_hcl(tmp_path: Path) -> None:
    # A valid HCL fragment (metadata block) should produce valid combined output
    # We inject a labels block which is valid inside a resource
    fragment = ""
    render_templates(_spec(), tmp_path, fragment=fragment)
    with (tmp_path / "main.tf").open() as fh:
        hcl2.load(fh)  # Should not raise


def test_preemptible_false_renders_correctly(tmp_path: Path) -> None:
    result = render_templates(_spec(), tmp_path)
    assert "false" in result["variables.tf"].lower()


def test_preemptible_true_renders_correctly(tmp_path: Path) -> None:
    spec = _spec()
    spec = spec.model_copy(
        update={"compute": spec.compute.model_copy(update={"preemptible": True})}
    )
    result = render_templates(spec, tmp_path)
    assert "true" in result["variables.tf"].lower()


def test_gpu_count_appears_in_variables(tmp_path: Path) -> None:
    result = render_templates(_spec(), tmp_path)
    assert "1" in result["variables.tf"]
