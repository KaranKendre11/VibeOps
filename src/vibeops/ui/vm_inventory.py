from __future__ import annotations

import streamlit as st

from vibeops.core.errors import GCPToolError
from vibeops.core.gcp_context import GcpContext
from vibeops.models.results import RunningInstance
from vibeops.tools.compute import delete_instance, list_running_instances

_INV_CSS = """
<style>
.inv-summary {
  font-size: 12px;
  color: #888;
  font-family: 'JetBrains Mono', monospace;
  margin-bottom: 12px;
  letter-spacing: 0.04em;
}
.inv-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 14px;
  border: 1px solid rgba(255,255,255,0.12);
  border-radius: 12px;
  background: #0d0d0d;
  margin-bottom: 8px;
}
.inv-row.selected {
  border-color: rgba(0,222,255,0.5);
  background: rgba(0,222,255,0.05);
  box-shadow: 0 0 14px rgba(0,222,255,0.10);
}
.inv-status {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}
.inv-status.running      { background: #00DEFF; box-shadow: 0 0 10px rgba(0,222,255,0.7); }
.inv-status.stopping     { background: #fbbf24; box-shadow: 0 0 10px rgba(251,191,36,0.6); }
.inv-status.provisioning { background: #00DEFF; opacity: 0.6; }
.inv-status.terminated   { background: #555; }
.inv-status.other        { background: #888; }
.inv-meta { flex: 1; min-width: 0; }
.inv-name {
  font-family: 'JetBrains Mono', monospace;
  font-size: 13px;
  color: #ffffff;
  font-weight: 600;
  margin-bottom: 2px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.inv-details {
  font-size: 11px;
  color: #888;
  font-family: 'JetBrains Mono', monospace;
}
.inv-details .sep { color: #444; margin: 0 6px; }
.inv-details .gpu { color: #00DEFF; }
.inv-status-label {
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  padding: 3px 8px;
  border-radius: 5px;
  font-family: 'JetBrains Mono', monospace;
  flex-shrink: 0;
}
.inv-status-label.running      { background: rgba(0,222,255,0.15); color: #00DEFF; }
.inv-status-label.stopping     { background: rgba(251,191,36,0.15); color: #fbbf24; }
.inv-status-label.provisioning { background: rgba(0,222,255,0.12); color: #00DEFF; }
.inv-status-label.terminated   { background: rgba(136,136,136,0.15); color: #888; }
.inv-status-label.other        { background: rgba(136,136,136,0.15); color: #888; }
.inv-empty {
  text-align: center;
  padding: 32px 16px;
  color: #888;
  font-size: 13px;
}
.inv-warn {
  background: rgba(248,113,113,0.06);
  border: 1px solid rgba(248,113,113,0.30);
  border-radius: 12px;
  padding: 12px 16px;
  margin-top: 12px;
  font-size: 12px;
  color: #f87171;
  font-family: 'JetBrains Mono', monospace;
}
</style>
"""


def _status_class(status: str) -> str:
    s = status.upper()
    if s == "RUNNING":
        return "running"
    if s == "STOPPING":
        return "stopping"
    if s in ("PROVISIONING", "STAGING", "REPAIRING"):
        return "provisioning"
    if s in ("TERMINATED", "STOPPED", "SUSPENDED"):
        return "terminated"
    return "other"


def _row_html(inst: RunningInstance, selected: bool) -> str:
    details_parts = [inst.machine_type]
    if inst.gpu_summary:
        details_parts.append(f'<span class="gpu">{inst.gpu_summary}</span>')
    details_parts.append(inst.zone)
    if inst.external_ip:
        details_parts.append(inst.external_ip)
    elif inst.internal_ip:
        details_parts.append(f"int: {inst.internal_ip}")
    details_html = '<span class="sep">·</span>'.join(details_parts)
    sc = _status_class(inst.status)
    sel_class = " selected" if selected else ""
    return (
        f'<div class="inv-row{sel_class}">'
        f'<div class="inv-status {sc}"></div>'
        f'<div class="inv-meta">'
        f'<div class="inv-name">{inst.name}</div>'
        f'<div class="inv-details">{details_html}</div>'
        f"</div>"
        f'<span class="inv-status-label {sc}">{inst.status}</span>'
        f"</div>"
    )


def _refresh_inventory(ctx: GcpContext) -> None:
    try:
        result = list_running_instances(ctx)
        st.session_state["_vm_inventory"] = result.instances
        st.session_state["_vm_inventory_error"] = None
    except GCPToolError as exc:
        st.session_state["_vm_inventory"] = []
        st.session_state["_vm_inventory_error"] = str(exc)


def get_inventory_counts() -> tuple[int, int]:
    """Return (running_count, total_count) from the cached inventory."""
    ctx: GcpContext | None = st.session_state.get("gcp_context")
    if ctx is None:
        return (0, 0)
    if "_vm_inventory" not in st.session_state:
        _refresh_inventory(ctx)
    insts: list[RunningInstance] = st.session_state.get("_vm_inventory") or []
    running = sum(1 for i in insts if i.status.upper() == "RUNNING")
    return (running, len(insts))


def _close_dialog() -> None:
    for k in ("_show_vm_inventory", "_vm_selection", "_vm_confirm_phase", "_vm_delete_results"):
        st.session_state.pop(k, None)


@st.dialog("Running VMs", width="large")
def vm_inventory_dialog() -> None:
    st.markdown(_INV_CSS, unsafe_allow_html=True)

    ctx: GcpContext | None = st.session_state.get("gcp_context")
    if ctx is None:
        st.error("GCP context unavailable — reconfigure credentials from the sidebar.")
        return

    if "_vm_inventory" not in st.session_state:
        with st.spinner("Querying Compute Engine…"):
            _refresh_inventory(ctx)

    instances: list[RunningInstance] = st.session_state.get("_vm_inventory") or []
    err: str | None = st.session_state.get("_vm_inventory_error")
    selection: set[str] = st.session_state.setdefault("_vm_selection", set())
    confirm_phase: bool = st.session_state.get("_vm_confirm_phase", False)
    delete_results: list[tuple[str, bool, str]] = st.session_state.get("_vm_delete_results", [])

    # Drop any selected IDs that aren't in the current inventory (e.g. after deletion)
    current_ids = {f"{i.zone}/{i.name}" for i in instances}
    selection &= current_ids
    st.session_state["_vm_selection"] = selection

    running = sum(1 for i in instances if i.status.upper() == "RUNNING")
    col_proj, col_refresh = st.columns([4, 1])
    with col_proj:
        st.markdown(
            f'<div class="inv-summary">PROJECT · {ctx.project_id} · '
            f'{running} RUNNING · {len(instances)} TOTAL</div>',
            unsafe_allow_html=True,
        )
    with col_refresh:
        if st.button("↻ Refresh", key="inv.refresh", use_container_width=True):
            with st.spinner("Refreshing…"):
                _refresh_inventory(ctx)
            st.rerun()

    if err:
        st.error(f"Could not list instances: {err}")
        return

    if not instances:
        st.markdown('<div class="inv-empty">No VMs in this project.</div>', unsafe_allow_html=True)
        if st.button("Close", key="inv.close.empty"):
            _close_dialog()
            st.rerun()
        return

    # Show prior deletion results (if any) then clear
    if delete_results:
        for name, ok, msg in delete_results:
            if ok:
                st.success(f"✓ Deleted {name}")
            else:
                st.error(f"✗ {name}: {msg}")
        st.session_state.pop("_vm_delete_results", None)

    # Render each VM row with a checkbox (only for deletable instances)
    for inst in instances:
        row_id = f"{inst.zone}/{inst.name}"
        deletable = inst.status.upper() not in ("TERMINATED", "STOPPED")
        is_selected = row_id in selection

        col_cb, col_row = st.columns([0.5, 11.5])
        with col_cb:
            if deletable:
                checked = st.checkbox(
                    "select",
                    key=f"inv.cb.{row_id}",
                    value=is_selected,
                    label_visibility="collapsed",
                    disabled=confirm_phase,
                )
                if checked and not is_selected:
                    selection.add(row_id)
                    st.session_state["_vm_selection"] = selection
                elif not checked and is_selected:
                    selection.discard(row_id)
                    st.session_state["_vm_selection"] = selection
            else:
                st.markdown("&nbsp;", unsafe_allow_html=True)
        with col_row:
            st.markdown(_row_html(inst, is_selected), unsafe_allow_html=True)

    st.markdown("---")

    n_selected = len(selection)

    # CONFIRM PHASE: show a destructive primary button + cancel
    if confirm_phase:
        st.markdown(
            f'<div class="inv-warn">⚠ About to permanently delete {n_selected} VM'
            f'{"s" if n_selected != 1 else ""}. Auto-delete disks will be removed. This cannot be undone.</div>',
            unsafe_allow_html=True,
        )
        col_back, col_confirm = st.columns([1, 1])
        with col_back:
            if st.button("← Back", key="inv.confirm.back", use_container_width=True):
                st.session_state["_vm_confirm_phase"] = False
                st.rerun()
        with col_confirm:
            if st.button(
                f"Yes, tear down {n_selected}",
                key="inv.confirm.yes",
                type="primary",
                use_container_width=True,
            ):
                results: list[tuple[str, bool, str]] = []
                with st.spinner(f"Deleting {n_selected} instance{'s' if n_selected != 1 else ''}…"):
                    for row_id in list(selection):
                        zone, name = row_id.split("/", 1)
                        try:
                            delete_instance(ctx, zone, name)
                            results.append((name, True, ""))
                        except GCPToolError as exc:
                            results.append((name, False, str(exc)))
                st.session_state["_vm_delete_results"] = results
                st.session_state["_vm_confirm_phase"] = False
                st.session_state["_vm_selection"] = set()
                _refresh_inventory(ctx)
                st.rerun()
        return

    # NORMAL PHASE: select-all + tear-down selected + close
    col_all, col_clear, col_action, col_close = st.columns([1, 1, 2, 1])
    with col_all:
        if st.button("Select all", key="inv.selall", use_container_width=True):
            for inst in instances:
                if inst.status.upper() not in ("TERMINATED", "STOPPED"):
                    selection.add(f"{inst.zone}/{inst.name}")
            st.session_state["_vm_selection"] = selection
            st.rerun()
    with col_clear:
        if st.button("Clear", key="inv.clear", use_container_width=True, disabled=n_selected == 0):
            st.session_state["_vm_selection"] = set()
            st.rerun()
    with col_action:
        label = f"Tear down ({n_selected})" if n_selected else "Tear down"
        if st.button(
            label,
            key="inv.teardown",
            type="primary",
            use_container_width=True,
            disabled=n_selected == 0,
        ):
            st.session_state["_vm_confirm_phase"] = True
            st.rerun()
    with col_close:
        if st.button("Close", key="inv.close", use_container_width=True):
            _close_dialog()
            st.rerun()

    st.caption(
        "_Tear down calls the Compute Engine API directly. Auto-delete disks go too. "
        "Network and firewall resources are left intact._"
    )
