from __future__ import annotations

from typing import Any

import streamlit as st

from vibeops.models.deployment import DeploymentPhase, StateResource
from vibeops.models.state import FlowStage, GraphState
from vibeops.ui.graph_sync import sync_graph_stage

_DEPLOY_CSS = """
<style>
.deploy-section-label {
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.12em;
  color: #00DEFF;
  margin-bottom: 12px;
  text-shadow: 0 0 10px rgba(0,222,255,0.35);
}
.deploy-card-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}
.deploy-status-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
}
.deploy-status-dot.success { background: #00DEFF; box-shadow: 0 0 12px rgba(0,222,255,0.7); }
.deploy-status-dot.error   { background: #f87171; box-shadow: 0 0 12px rgba(248,113,113,0.6); }
.deploy-status-dot.warn    { background: #fbbf24; box-shadow: 0 0 12px rgba(251,191,36,0.6); }
.deploy-card-title {
  font-size: 18px;
  font-weight: 700;
  color: #ffffff;
  letter-spacing: -0.02em;
}
.resource-row {
  display: flex;
  align-items: baseline;
  gap: 10px;
  padding: 8px 0;
  border-bottom: 1px solid rgba(255,255,255,0.10);
  font-size: 13px;
}
.resource-row:last-child { border-bottom: none; }
.resource-type { color: #888; font-size: 11px; text-transform: uppercase; letter-spacing: 0.05em; }
.resource-name { font-family: 'JetBrains Mono', monospace; font-size: 13px; color: #ffffff; }
.resource-zone { color: #00DEFF; font-size: 11px; font-family: 'JetBrains Mono', monospace; }
.ssh-label {
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.12em;
  color: #00DEFF;
  margin-bottom: 6px;
  margin-top: 16px;
}
.billing-note {
  font-size: 13px;
  color: #d6d6d6;
  margin-top: 12px;
}
</style>
"""


def _is_confirm_valid(text: str) -> bool:
    return text.strip().lower() == "destroy"


def _exit_to_start() -> None:
    for key in ("graph", "graph_stage", "display_history", "graph_thread_id"):
        st.session_state.pop(key, None)
    st.rerun()


def render_deployment(graph: Any, state: GraphState, thread: dict[str, Any]) -> None:
    st.markdown(_DEPLOY_CSS, unsafe_allow_html=True)
    phase = state.deployment_phase

    if phase in (DeploymentPhase.PLANNING, DeploymentPhase.APPLYING, DeploymentPhase.DESTROYING):
        _render_log_panel(state)
    elif phase == DeploymentPhase.SUCCEEDED:
        _render_success_card(state, graph, thread)
    elif phase == DeploymentPhase.FAILED:
        _render_failure_card(state, graph, thread)
    elif phase == DeploymentPhase.AWAITING_DESTROY_CONFIRM:
        _render_destroy_confirm(state, graph, thread)
    elif phase == DeploymentPhase.DESTROYED:
        _render_destroyed_card()
    else:
        st.info("Preparing deployment…")


def _render_log_panel(state: GraphState) -> None:
    phase = state.deployment_phase
    if phase == DeploymentPhase.DESTROYING:
        st.markdown("## Destroying resources")
    else:
        zone = state.deployment_spec.compute.zone if state.deployment_spec else ""
        st.markdown(f"## Deploying to `{zone}`" if zone else "## Deploying")

    log_text = "\n".join(state.deployment_logs) if state.deployment_logs else "Waiting for output…"
    st.code(log_text, language="shellsession")


def _render_resource_list(resources: list[StateResource]) -> None:
    html = '<div style="border:1px solid rgba(255,255,255,0.18);border-radius:16px;padding:12px 20px;background:#0d0d0d;margin:10px 0">'
    for r in resources:
        zone_html = f'<span class="resource-zone"> · {r.zone}</span>' if r.zone else ""
        html += (
            f'<div class="resource-row">'
            f'<span class="resource-type">{r.type}</span>'
            f'<span class="resource-name">{r.name}</span>'
            f"{zone_html}"
            f"</div>"
        )
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)


def _lookup_external_ip(instance_name: str) -> str:
    """Query the inventory (Compute Engine API) to find the external IP of an instance.

    Returns "" if we can't find it (e.g. GCP context unavailable or VM still booting).
    """
    try:
        from vibeops.core.gcp_context import GcpContext
        from vibeops.tools.compute import list_running_instances

        ctx: GcpContext | None = st.session_state.get("gcp_context")
        if ctx is None:
            return ""
        result = list_running_instances(ctx)
        for inst in result.instances:
            if inst.name == instance_name:
                return inst.external_ip or ""
    except Exception:  # noqa: BLE001
        return ""
    return ""


def _render_success_card(state: GraphState, graph: Any, thread: dict[str, Any]) -> None:
    st.markdown(
        '<div class="deploy-card-header">'
        '<div class="deploy-status-dot success"></div>'
        '<span class="deploy-card-title">Deployment complete</span>'
        "</div>",
        unsafe_allow_html=True,
    )

    if state.created_resources:
        st.markdown('<p class="deploy-section-label">Resources created</p>', unsafe_allow_html=True)
        _render_resource_list(state.created_resources)

    if state.deployment_spec:
        spec = state.deployment_spec
        instance_name = _instance_name(state)

        # Look up the actual external IP via the Compute Engine API
        external_ip = _lookup_external_ip(instance_name) if spec.network.create_external_ip or spec.network.open_ports else ""

        # Per-port URLs (clickable)
        if spec.network.open_ports and external_ip:
            st.markdown('<p class="ssh-label">Public endpoints</p>', unsafe_allow_html=True)
            urls_html = '<div style="border:1px solid rgba(0,222,255,0.25);border-radius:14px;padding:12px 16px;background:rgba(0,222,255,0.04);margin-bottom:12px">'
            for port in sorted(set(spec.network.open_ports)):
                scheme = "https" if port == 443 else "http"
                url = f"{scheme}://{external_ip}:{port}" if port not in (80, 443) else f"{scheme}://{external_ip}"
                label = (
                    f"port {port}"
                    + (" (HTTPS)" if port == 443 else " (HTTP)" if port == 80 else "")
                )
                urls_html += (
                    f'<div style="font-family:\'JetBrains Mono\',monospace;font-size:13px;'
                    f'padding:4px 0">'
                    f'<span style="color:#888;margin-right:10px">{label}</span>'
                    f'<a href="{url}" target="_blank" style="color:#00DEFF;text-decoration:none">{url} →</a>'
                    f"</div>"
                )
            urls_html += "</div>"
            st.markdown(urls_html, unsafe_allow_html=True)
        elif spec.network.open_ports and not external_ip:
            st.markdown('<p class="ssh-label">Public endpoints</p>', unsafe_allow_html=True)
            ports_str = ", ".join(str(p) for p in sorted(set(spec.network.open_ports)))
            st.info(
                f"External IP is still being assigned. Open ports: {ports_str}. "
                f"Run the command below to fetch the IP, then visit "
                f"`http://<EXTERNAL_IP>:{spec.network.open_ports[0]}`."
            )
            st.code(
                f"gcloud compute instances describe {instance_name} "
                f"--zone={spec.compute.zone} "
                "--format='value(networkInterfaces[0].accessConfigs[0].natIP)'",
                language="bash",
            )

        st.markdown('<p class="ssh-label">Connect via SSH</p>', unsafe_allow_html=True)
        st.code(
            f"gcloud compute ssh {instance_name} --zone={spec.compute.zone}",
            language="bash",
        )

        # Container status helper (only when a container was deployed)
        if spec.app.container_image:
            st.markdown('<p class="ssh-label">Container status</p>', unsafe_allow_html=True)
            st.code(
                f"gcloud compute ssh {instance_name} --zone={spec.compute.zone} "
                f"--command='sudo docker ps -a && sudo docker logs --tail 50 $(sudo docker ps -aq | head -1)'",
                language="bash",
            )

        # Serial console (useful when startup script ran)
        if spec.app.startup_script or spec.app.software_packages:
            st.markdown('<p class="ssh-label">Startup script output</p>', unsafe_allow_html=True)
            st.code(
                f"gcloud compute instances get-serial-port-output {instance_name} "
                f"--zone={spec.compute.zone} | tail -n 200",
                language="bash",
            )

    if state.cost_estimate:
        hourly = state.cost_estimate.hourly_usd
        st.markdown(
            f'<p class="billing-note">Billing at ~${hourly:.3f}/hr · tear down when finished.</p>',
            unsafe_allow_html=True,
        )

    st.divider()
    col_teardown, col_done, _ = st.columns([1, 1, 4])
    with col_teardown:
        if st.button("Tear down", type="primary", key="deploy.teardown"):
            graph.update_state(
                thread,
                {
                    "destroy_requested": True,
                    "deployment_phase": DeploymentPhase.AWAITING_DESTROY_CONFIRM.value,
                },
            )
            st.session_state["graph_stage"] = "deployment_active"
            st.rerun()
    with col_done:
        if st.button("Done", key="deploy.done"):
            _exit_to_start()


def _is_insufficient_resources(state: GraphState) -> bool:
    if state.deployment_error and "insufficient capacity" in state.deployment_error.lower():
        return True
    return any(
        "does not have enough resources available" in log
        for log in state.deployment_logs
    )


def _render_failure_card(state: GraphState, graph: Any, thread: dict[str, Any]) -> None:
    st.markdown(
        '<div class="deploy-card-header">'
        '<div class="deploy-status-dot error"></div>'
        '<span class="deploy-card-title">Deployment failed</span>'
        "</div>",
        unsafe_allow_html=True,
    )

    if state.deployment_error:
        st.markdown(
            f'<p style="font-size:13px;color:#f87171;margin:0 0 12px">{state.deployment_error}</p>',
            unsafe_allow_html=True,
        )

    with st.expander("Full error output"):
        logs = "\n".join(state.deployment_logs)
        st.code(logs, language="shellsession")

    if state.created_resources:
        st.markdown('<p class="deploy-section-label">Resources created so far</p>', unsafe_allow_html=True)
        _render_resource_list(state.created_resources)

        if state.cost_estimate:
            hourly = state.cost_estimate.hourly_usd
            st.markdown(
                f'<p class="billing-note" style="color:#fbbf24">Billing has started for the resources above (~${hourly:.3f}/hr).</p>',
                unsafe_allow_html=True,
            )

    st.divider()
    capacity_error = _is_insufficient_resources(state)
    ncols = 4 if capacity_error else 3
    cols = st.columns(ncols)

    with cols[0]:
        if st.button("Retry apply", key="deploy.retry"):
            graph.update_state(thread, {"retry_requested": True})
            with st.status("Retrying deployment…", expanded=True) as status:
                st.write("Running terraform plan")
                st.write("Applying configuration (this may take several minutes)")
                graph.invoke(None, thread)
                status.update(label="Retry complete", state="complete", expanded=False)
            sync_graph_stage(graph, thread)
            st.rerun()

    with cols[1]:
        destroy_disabled = not bool(state.created_resources)
        if st.button(
            "Destroy what was created",
            key="deploy.destroy_partial",
            disabled=destroy_disabled,
        ):
            graph.update_state(
                thread,
                {
                    "destroy_requested": True,
                    "deployment_phase": DeploymentPhase.AWAITING_DESTROY_CONFIRM.value,
                },
            )
            st.session_state["graph_stage"] = "deployment_active"
            st.rerun()

    with cols[2]:
        if st.button("Leave as-is and exit", key="deploy.leave"):
            _exit_to_start()

    if capacity_error:
        with cols[3]:
            if st.button("Try a different zone", type="primary", key="deploy.retry_zone"):
                _on_try_different_zone(state, graph, thread)


def _on_try_different_zone(state: GraphState, graph: Any, thread: dict[str, Any]) -> None:
    from langchain_core.runnables import RunnableConfig

    from vibeops.agents.architecture import architecture_agent

    failed_zone = state.deployment_spec.compute.zone if state.deployment_spec else None
    new_excluded = list(state.excluded_zones)
    if failed_zone and failed_zone not in new_excluded:
        new_excluded.append(failed_zone)

    gcp_ctx = st.session_state.get("gcp_context")

    discovery_state = state.model_copy(
        update={
            "excluded_zones": new_excluded,
            "architecture_response": None,
            "back_to_requirements": False,
        }
    )
    config = RunnableConfig(configurable={"gcp_context": gcp_ctx})

    with st.spinner("Fetching available zones from GCP…"):
        new_arch_state = architecture_agent(discovery_state, config)

    if new_arch_state.error:
        st.error(f"No alternative zone found: {new_arch_state.error}")
        return
    if new_arch_state.architecture_options is None:
        st.error("Zone discovery returned no candidates.")
        return

    graph.update_state(
        thread,
        {
            "excluded_zones": new_excluded,
            "architecture_options": new_arch_state.architecture_options.model_dump(),
            "stage": FlowStage.AWAITING_ARCHITECTURE.value,
            "deployment_phase": DeploymentPhase.IDLE.value,
            "deployment_error": None,
            "deployment_logs": [],
            "created_resources": [],
            "approved": False,
            "retry_requested": False,
            "leave_as_is_requested": False,
            "destroy_requested": False,
            "destroy_confirmed": False,
            "architecture_response": None,
        },
        as_node="architecture_pause",
    )

    st.session_state["graph_stage"] = "awaiting_architecture"
    st.rerun()


@st.dialog("Destroy these resources?")
def _destroy_dialog(state: GraphState, graph: Any, thread: dict[str, Any]) -> None:
    if state.created_resources:
        st.markdown("**The following resources will be permanently destroyed:**")
        for r in state.created_resources:
            zone_info = f" in {r.zone}" if r.zone else ""
            st.markdown(f"- **{r.type}** `{r.name}`{zone_info}")
    else:
        st.markdown("All resources in the current terraform state will be destroyed.")

    st.markdown("*You'll lose any data on these resources that isn't backed up elsewhere.*")

    if state.cost_estimate:
        st.info("Billing stops once destroy completes.")

    confirm_text = st.text_input("Type 'destroy' to confirm", key="destroy_confirm_text")
    valid = _is_confirm_valid(confirm_text)

    col_yes, col_cancel = st.columns([1, 1])
    with col_yes:
        if st.button("Yes, destroy", type="primary", disabled=not valid, key="destroy.yes"):
            graph.update_state(thread, {"destroy_confirmed": True})
            with st.status("Destroying resources…", expanded=True) as status:
                st.write("Running terraform destroy (this may take several minutes)")
                # Single invoke runs: deployment_decision → destroy_confirm → destroy_agent
                # (destroy_confirm is NOT in interrupt_before, so no mid-flow pause)
                graph.invoke(None, thread)
                status.update(label="Destroy complete", state="complete", expanded=False)
            sync_graph_stage(graph, thread)
            st.rerun()
    with col_cancel:
        if st.button("Cancel", key="destroy.cancel"):
            prev_phase = (
                DeploymentPhase.SUCCEEDED.value
                if state.deployment_phase == DeploymentPhase.AWAITING_DESTROY_CONFIRM
                else DeploymentPhase.FAILED.value
            )
            graph.update_state(
                thread,
                {
                    "destroy_requested": False,
                    "deployment_phase": prev_phase,
                },
            )
            sync_graph_stage(graph, thread)
            st.rerun()


def _render_destroy_confirm(state: GraphState, graph: Any, thread: dict[str, Any]) -> None:
    _destroy_dialog(state, graph, thread)


def _render_destroyed_card() -> None:
    st.markdown(
        '<div class="deploy-card-header">'
        '<div class="deploy-status-dot success"></div>'
        '<span class="deploy-card-title">Resources destroyed</span>'
        "</div>"
        '<p style="font-size:13px;color:#6b6b76;margin:0 0 16px">All resources have been deleted. Billing has stopped.</p>',
        unsafe_allow_html=True,
    )
    st.divider()
    if st.button("Done", key="destroyed.done"):
        _exit_to_start()


def _instance_name(state: GraphState) -> str:
    for r in state.created_resources:
        if "instance" in r.type:
            return r.name
    return "instance"
