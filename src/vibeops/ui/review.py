from __future__ import annotations

from pathlib import Path
from typing import Any

import streamlit as st

from vibeops.core.policy import ALLOWED_RESOURCE_TYPES, check_resource_allowlist
from vibeops.core.secrets import get_monthly_cost_cap
from vibeops.models.iac import CostEstimate  # noqa: F401
from vibeops.models.state import GraphState
from vibeops.terraform.runner import TerraformValidateError, validate
from vibeops.ui.graph_sync import sync_graph_stage

_REVIEW_CSS = """
<style>
.review-section-label {
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.12em;
  color: #00DEFF;
  margin-bottom: 12px;
  text-shadow: 0 0 10px rgba(0,222,255,0.35);
}
.spec-row {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  padding: 8px 0;
  border-bottom: 1px solid rgba(255,255,255,0.10);
  font-size: 13px;
}
.spec-row:last-child { border-bottom: none; }
.spec-key   { color: #888; font-size: 12px; text-transform: uppercase; letter-spacing: 0.05em; }
.spec-value { font-family: 'JetBrains Mono', monospace; font-size: 13px; color: #ffffff; }
.cost-cap-bar-wrap {
  background: rgba(255,255,255,0.10);
  border-radius: 4px;
  height: 4px;
  margin: 10px 0 6px;
  overflow: hidden;
}
</style>
"""


# ---------------------------------------------------------------------------
# Pure business logic
# ---------------------------------------------------------------------------

def apply_user_edit(
    state: GraphState,
    filename: str,
    new_content: str,
) -> tuple[GraphState, str | None]:
    if state.terraform_dir is None:
        return state, "No Terraform working directory — cannot validate edit."

    tf_dir = Path(state.terraform_dir)
    tf_file = tf_dir / filename
    original_content = state.terraform_files.get(filename, "")

    tf_file.write_text(new_content, encoding="utf-8")

    try:
        result = validate(tf_dir)
    except (TerraformValidateError, Exception) as exc:
        tf_file.write_text(original_content, encoding="utf-8")
        return state, f"Validation error: {exc}"

    if not result.ok:
        tf_file.write_text(original_content, encoding="utf-8")
        return state, f"Validation failed: {'; '.join(result.errors)}"

    if filename == "main.tf":
        allowlist_result = check_resource_allowlist(tf_file)
        if not allowlist_result.ok:
            bad = [v.resource_type for v in allowlist_result.violations]
            allowed = sorted(ALLOWED_RESOURCE_TYPES)
            tf_file.write_text(original_content, encoding="utf-8")
            return state, (
                f"Resource type not in allowlist: {', '.join(bad)}. "
                f"Allowed: {', '.join(allowed)}."
            )

    new_files = {**state.terraform_files, filename: new_content}
    return (
        state.model_copy(update={"terraform_files": new_files, "cost_estimate_stale": True}),
        None,
    )


# ---------------------------------------------------------------------------
# Streamlit review screen
# ---------------------------------------------------------------------------

def render_review(graph: Any, state: GraphState, thread: dict[str, Any]) -> None:
    st.markdown(_REVIEW_CSS, unsafe_allow_html=True)
    st.markdown("## Review deployment plan")
    st.caption("Inspect the configuration below before anything is deployed.")

    if state.validation_errors:
        _binary_missing = any("not found" in e.lower() for e in state.validation_errors)
        if _binary_missing:
            st.error(
                "**terraform CLI not found.** Install it and restart the app.  \n"
                "Windows: `winget install Hashicorp.Terraform`  \n"
                "Mac/Linux: https://developer.hashicorp.com/terraform/install"
            )
        else:
            st.error(
                "Terraform validation failed during generation. "
                "Edit the files below to fix the errors."
            )
        for err in state.validation_errors:
            st.code(err, language="text")

    st.divider()
    col_spec, col_tf, col_cost = st.columns([1, 2, 1])

    with col_spec:
        _render_spec_panel(state)

    with col_tf:
        new_state = _render_terraform_panel(state, graph, thread)
        if new_state is not state:
            graph.update_state(thread, new_state.model_dump())
            st.rerun()

    with col_cost:
        _render_cost_panel(state, graph, thread)

    st.divider()
    _render_action_bar(state, graph, thread)


def _render_spec_panel(state: GraphState) -> None:
    st.markdown('<p class="review-section-label">Spec</p>', unsafe_allow_html=True)
    spec = state.deployment_spec
    if spec is None:
        st.info("No spec available.")
        return

    rows: list[tuple[str, str]] = [
        ("Project", spec.project_id),
        ("Zone", spec.compute.zone),
        ("Machine", spec.compute.machine_type),
        ("GPU", f"{spec.compute.gpu_count}× {spec.compute.gpu_type.value}"),
        ("OS", spec.storage.os_image_family),
        ("Disk", f"{spec.storage.disk_size_gb} GB"),
        ("Network", spec.network.network_name),
        ("Preemptible", str(spec.compute.preemptible).lower()),
    ]

    # Extended spec rows (only render when set)
    if spec.network.open_ports:
        ports = ", ".join(str(p) for p in sorted(set(spec.network.open_ports)))
        rows.append(("Open ports", ports))
    rows.append(("Public IP", str(spec.network.create_external_ip or bool(spec.network.open_ports)).lower()))
    if spec.app.container_image:
        rows.append(("Container", spec.app.container_image))
    if spec.app.software_packages:
        rows.append(("Install", ", ".join(spec.app.software_packages)))
    if spec.app.startup_script:
        rows.append(("Startup script", "yes (see main.tf)"))
    if spec.app.ssh_public_key:
        rows.append(("SSH key", "provided"))
    if spec.app.purpose:
        rows.append(("Purpose", spec.app.purpose))

    html = '<div style="border:1px solid rgba(255,255,255,0.18);border-radius:16px;padding:16px 20px;background:#0d0d0d">'
    for key, val in rows:
        html += (
            f'<div class="spec-row">'
            f'<span class="spec-key">{key}</span>'
            f'<span class="spec-value">{val}</span>'
            f"</div>"
        )
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)


def _render_terraform_panel(
    state: GraphState, graph: Any, thread: dict[str, Any]
) -> GraphState:
    st.markdown('<p class="review-section-label">Terraform</p>', unsafe_allow_html=True)

    if not state.terraform_files:
        st.info("No Terraform files generated.")
        return state

    filenames = list(state.terraform_files.keys())
    tabs = st.tabs(filenames)

    current_state = state
    for tab, filename in zip(tabs, filenames, strict=False):
        with tab:
            content = current_state.terraform_files[filename]
            original = current_state.terraform_files_original.get(filename, "")
            is_modified = content != original and original != ""

            if is_modified:
                st.caption("Modified by you")

            edit_key = f"edit_mode.{filename}"
            in_edit = st.session_state.get(edit_key, False)

            if in_edit:
                edited = st.text_area(
                    f"Edit {filename}",
                    value=content,
                    height=480,
                    key=f"editor.{filename}",
                    label_visibility="collapsed",
                )
                save_col, revert_col, cancel_col = st.columns([1, 1, 1])

                with save_col:
                    if st.button("Save", key=f"review.save.{filename}"):
                        new_state, err = apply_user_edit(current_state, filename, edited)
                        if err:
                            st.error(err)
                        else:
                            st.session_state[edit_key] = False
                            current_state = new_state

                with revert_col:
                    if st.button("Revert", key=f"review.revert.{filename}"):
                        reverted_files = {
                            **current_state.terraform_files,
                            filename: current_state.terraform_files_original.get(filename, content),
                        }
                        current_state = current_state.model_copy(
                            update={"terraform_files": reverted_files}
                        )
                        st.session_state[edit_key] = False

                with cancel_col:
                    if st.button("Cancel", key=f"review.canceledit.{filename}"):
                        st.session_state[edit_key] = False
            else:
                st.code(content, language="hcl")
                if st.button("Edit", key=f"review.edit.{filename}"):
                    st.session_state[edit_key] = True

    return current_state


def _render_cost_panel(state: GraphState, graph: Any, thread: dict[str, Any]) -> None:
    st.markdown('<p class="review-section-label">Cost estimate</p>', unsafe_allow_html=True)
    estimate: CostEstimate | None = state.cost_estimate
    cap = get_monthly_cost_cap()

    if estimate is not None:
        st.metric("Monthly", f"${estimate.monthly_usd:.2f}")
        st.metric("Hourly", f"${estimate.hourly_usd:.4f}")

        ratio = estimate.monthly_usd / cap if cap > 0 else 0.0
        bar_pct = min(ratio, 1.0) * 100
        bar_color = "#00DEFF" if ratio < 0.70 else ("#fbbf24" if ratio <= 1.0 else "#f87171")
        st.markdown(
            f'<div class="cost-cap-bar-wrap">'
            f'<div style="width:{bar_pct:.1f}%;height:3px;background:{bar_color};border-radius:2px"></div>'
            f"</div>",
            unsafe_allow_html=True,
        )
        st.caption(
            f"${estimate.monthly_usd:.0f} / ${cap:.0f} cap · "
            f"{'Infracost' if estimate.source == 'infracost' else 'Cloud Catalog'}"
        )

        if estimate.breakdown:
            with st.expander("Breakdown"):
                for item in estimate.breakdown:
                    st.caption(f"{item.description} — ${item.hourly_usd:.4f}/hr")
    else:
        st.metric("Monthly", "—")
        st.caption("Cost estimation unavailable.")

    if state.cost_estimate_stale:
        if st.button("Re-estimate", key="review.reestimate"):
            _reestimate(state, graph, thread, cap)

    if estimate and estimate.notes:
        for note in estimate.notes:
            st.caption(note)


def _reestimate(
    state: GraphState, graph: Any, thread: dict[str, Any], cap: float
) -> None:
    if state.terraform_dir is None or state.deployment_spec is None:
        st.warning("Cannot re-estimate: missing working directory or spec.")
        return

    gcp_ctx = st.session_state.get("gcp_context")
    from vibeops.cost import estimate as cost_estimate_fn

    try:
        new_estimate = cost_estimate_fn(
            Path(state.terraform_dir), state.deployment_spec, gcp_ctx
        )
        graph.update_state(
            thread,
            {
                "cost_estimate": new_estimate.model_dump(),
                "cost_estimate_stale": False,
                "cost_cap_exceeded": new_estimate.monthly_usd > cap,
            },
        )
        st.rerun()
    except Exception as exc:
        st.error(f"Re-estimation failed: {exc}")


def _render_action_bar(state: GraphState, graph: Any, thread: dict[str, Any]) -> None:
    cap_exceeded = state.cost_cap_exceeded

    if cap_exceeded:
        st.warning(
            (
                f"Estimate ${state.cost_estimate.monthly_usd:.2f}/mo "
                f"exceeds your ${get_monthly_cost_cap():.0f}/mo cap. "
                "Check the box below to override."
            )
            if state.cost_estimate
            else "Cost cap exceeded. Check the box below to override."
        )
        override = st.checkbox("I understand — deploy anyway", key="cap_override")
    else:
        override = True

    approve_disabled = cap_exceeded and not override

    approve_col, cancel_col, _ = st.columns([1, 1, 4])

    with approve_col:
        if st.button(
            "Approve & Deploy",
            type="primary",
            key="review.approve",
            disabled=approve_disabled,
        ):
            graph.update_state(thread, {"approved": True})
            with st.status("Deploying to GCP…", expanded=True) as status:
                st.write("Running terraform plan")
                st.write("Applying configuration (this may take several minutes)")
                graph.invoke(None, thread)
                status.update(label="Deployment complete", state="complete", expanded=False)
            sync_graph_stage(graph, thread)
            st.rerun()

    with cancel_col:
        if st.button("Cancel", key="review.cancel"):
            graph.update_state(thread, {"approved": False})
            graph.invoke(None, thread)
            st.session_state["graph_stage"] = "cancelled"
            st.rerun()
