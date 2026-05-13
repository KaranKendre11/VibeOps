from __future__ import annotations

import json

import streamlit as st

from vibeops.core.auth import (
    list_gcp_projects,
    validate_gcp_credentials,
    validate_gcp_sa_json_text,
    validate_openai_key,
)
from vibeops.core.errors import AuthError
from vibeops.core.secrets import (
    save_credentials_to_cache,
    set_gcp_project_id,
    set_gcp_sa_json,
    set_monthly_cost_cap,
    set_openai_key,
    set_setup_complete,
)

# ---------------------------------------------------------------------------
# State helpers
# ---------------------------------------------------------------------------


def reset_setup_state() -> None:
    """Clear every key the setup flow touches so it re-runs from step 1."""
    for k in (
        "openai_key",
        "openai_validated",
        "_openai_key_last_validated",
        "gcp_sa_json",
        "gcp_validated",
        "_gcp_sa_json",
        "_gcp_fingerprint",
        "gcp_project_id",
        "gcp_project_list",
        "monthly_cost_cap_usd",
        "setup_complete",
    ):
        st.session_state.pop(k, None)


def _back_to_openai() -> None:
    for k in ("openai_validated", "_openai_key_last_validated"):
        st.session_state.pop(k, None)


def _back_to_gcp() -> None:
    for k in (
        "gcp_validated",
        "_gcp_sa_json",
        "_gcp_fingerprint",
        "gcp_sa_json",
        "gcp_project_list",
    ):
        st.session_state.pop(k, None)


# ---------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------

_SETUP_CSS = """
<style>
.setup-wordmark {
  font-family: 'Space Grotesk', system-ui, sans-serif;
  font-size: clamp(2.5rem, 6vw, 4rem);
  font-weight: 700;
  letter-spacing: -0.04em;
  color: #ffffff;
  text-shadow: 0 0 40px rgba(0,222,255,0.5), 0 0 100px rgba(0,222,255,0.2);
  text-align: center;
  margin: 8px 0 4px;
  animation: fadeUp 0.35s ease-out both;
}
.setup-tagline {
  font-size: 12px;
  letter-spacing: 0.32em;
  text-transform: uppercase;
  color: #00DEFF;
  text-align: center;
  margin-bottom: 40px;
  text-shadow: 0 0 12px rgba(0,222,255,0.45);
  animation: fadeUp 0.4s ease-out 0.05s both;
}

/* Stepper - centered */
.stepper {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0;
  margin: 0 auto 48px;
  width: 100%;
  max-width: 460px;
  animation: fadeUp 0.45s ease-out 0.1s both;
}
.step-dot-wrap {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  flex: 0 0 auto;
}
.step-dot {
  width: 38px;
  height: 38px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  font-weight: 700;
  font-family: 'JetBrains Mono', monospace;
  border: 2px solid rgba(255,255,255,0.18);
  color: #888;
  background: #0d0d0d;
  transition: all 0.3s ease;
}
.step-dot.active {
  border-color: #00DEFF;
  color: #00DEFF;
  background: rgba(0,222,255,0.08);
  box-shadow: 0 0 22px rgba(0,222,255,0.55);
  animation: dotPulse 2.4s ease-in-out infinite;
}
.step-dot.done {
  background: #00DEFF;
  border-color: #00DEFF;
  color: #000;
  box-shadow: 0 0 18px rgba(0,222,255,0.6);
}
.step-label {
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.10em;
  text-transform: uppercase;
  color: #555;
}
.step-label.active, .step-label.done { color: #00DEFF; }
.step-connector {
  flex: 1;
  height: 2px;
  background: rgba(255,255,255,0.10);
  margin: 0 6px 26px;
  transition: background 0.4s ease;
}
.step-connector.done {
  background: #00DEFF;
  box-shadow: 0 0 8px rgba(0,222,255,0.5);
}
@keyframes dotPulse {
  0%, 100% { box-shadow: 0 0 18px rgba(0,222,255,0.45); }
  50%      { box-shadow: 0 0 30px rgba(0,222,255,0.75); }
}

/* Step title + subtitle */
.step-title {
  font-family: 'Space Grotesk', system-ui, sans-serif;
  font-size: 22px;
  font-weight: 700;
  color: #ffffff;
  letter-spacing: -0.01em;
  margin: 8px 0 6px;
  animation: fadeUp 0.3s ease-out both;
}
.step-title .num {
  font-family: 'JetBrains Mono', monospace;
  color: #00DEFF;
  margin-right: 8px;
  font-weight: 600;
}
.step-sub {
  font-size: 13px;
  color: #888;
  margin-bottom: 22px;
  animation: fadeUp 0.35s ease-out 0.05s both;
}

/* Validated done row */
.done-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  border: 1px solid rgba(0,222,255,0.22);
  border-radius: 14px;
  background: rgba(0,222,255,0.04);
  margin-bottom: 10px;
  animation: fadeUp 0.3s ease-out both;
}
.done-check {
  width: 22px; height: 22px;
  background: #00DEFF;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #000;
  font-weight: 700;
  font-size: 12px;
  box-shadow: 0 0 12px rgba(0,222,255,0.55);
  flex-shrink: 0;
}
.done-label {
  font-size: 13px;
  color: #ffffff;
  font-weight: 600;
  flex: 0 0 auto;
}
.done-value {
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
  color: #00DEFF;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.section-divider {
  height: 1px;
  background: rgba(255,255,255,0.08);
  margin: 24px 0;
}
</style>
"""


# ---------------------------------------------------------------------------
# Stepper
# ---------------------------------------------------------------------------


def _stepper_html(step: int) -> str:
    steps = ["API Key", "GCP SA", "Project"]
    parts = ['<div class="stepper">']
    for i, label in enumerate(steps):
        n = i + 1
        if n < step:
            dot_cls, lbl_cls, icon = "step-dot done", "step-label done", "✓"
        elif n == step:
            dot_cls, lbl_cls, icon = "step-dot active", "step-label active", str(n)
        else:
            dot_cls, lbl_cls, icon = "step-dot", "step-label", str(n)
        parts.append(
            f'<div class="step-dot-wrap">'
            f'<div class="{dot_cls}">{icon}</div>'
            f'<span class="{lbl_cls}">{label}</span>'
            f"</div>"
        )
        if i < len(steps) - 1:
            conn_cls = "step-connector done" if step > n else "step-connector"
            parts.append(f'<div class="{conn_cls}"></div>')
    parts.append("</div>")
    return "".join(parts)


def _done_row(label: str, value: str) -> None:
    st.markdown(
        f'<div class="done-row">'
        f'<div class="done-check">✓</div>'
        f'<span class="done-label">{label}</span>'
        f'<span class="done-value">{value}</span>'
        f"</div>",
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def render_setup() -> None:
    st.markdown(_SETUP_CSS, unsafe_allow_html=True)

    openai_ok = st.session_state.get("openai_validated", False)
    gcp_ok = (
        st.session_state.get("gcp_validated", False)
        and bool(st.session_state.get("gcp_sa_json"))
    )
    current_step = 1 if not openai_ok else (2 if not gcp_ok else 3)

    # Centered three-column layout
    _, main, _ = st.columns([1, 2, 1])
    with main:
        st.markdown('<div class="setup-wordmark">VIBEOPS</div>', unsafe_allow_html=True)
        st.markdown('<div class="setup-tagline">GPU · GCP · INFRASTRUCTURE</div>', unsafe_allow_html=True)
        st.markdown(_stepper_html(current_step), unsafe_allow_html=True)

        # Render compact "done" rows for previously completed steps
        if current_step >= 2:
            prev_key = st.session_state.get("_openai_key_last_validated", "")
            _done_row("OpenAI Key", f"…{prev_key[-4:] if prev_key else 'saved'}")
        if current_step >= 3:
            fingerprint = st.session_state.get("_gcp_fingerprint", "saved")
            _done_row("GCP Service Account", fingerprint)

        if current_step >= 2:
            st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)

        # Render the active step
        if current_step == 1:
            _render_step_openai()
        elif current_step == 2:
            _render_step_gcp()
        elif current_step == 3:
            _render_step_project()


# ---------------------------------------------------------------------------
# Step 1 — OpenAI
# ---------------------------------------------------------------------------


def _render_step_openai() -> None:
    st.markdown(
        '<div class="step-title"><span class="num">①</span>OpenAI API Key</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="step-sub">Used for natural-language requirement gathering.</div>',
        unsafe_allow_html=True,
    )

    key_input = st.text_input(
        "OpenAI API key",
        type="password",
        key="openai_key_input",
        placeholder="sk-…",
        label_visibility="collapsed",
    )
    if st.button("Validate →", key="openai_validate_btn", type="primary", use_container_width=True):
        with st.spinner("Validating…"):
            result = validate_openai_key(key_input)
        if result.ok:
            set_openai_key(key_input)
            st.session_state["openai_validated"] = True
            st.session_state["_openai_key_last_validated"] = key_input
            st.rerun()
        else:
            st.error(result.message)


# ---------------------------------------------------------------------------
# Step 2 — GCP Service Account
# ---------------------------------------------------------------------------


def _render_step_gcp() -> None:
    st.markdown(
        '<div class="step-title"><span class="num">②</span>GCP Service Account</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="step-sub">Upload a service-account JSON file or paste it below.</div>',
        unsafe_allow_html=True,
    )

    sa_json: dict[str, object] | None = None

    uploaded = st.file_uploader(
        "Service-account JSON",
        type=["json"],
        key="gcp_sa_upload",
        label_visibility="collapsed",
    )
    if uploaded is not None:
        try:
            sa_json = json.loads(uploaded.read().decode())
        except json.JSONDecodeError:
            st.error("File is not valid JSON.")

    paste_text = st.text_area(
        "Or paste JSON",
        height=120,
        key="gcp_sa_paste",
        placeholder='{ "type": "service_account", … }',
        label_visibility="collapsed",
    )
    if sa_json is None and paste_text.strip():
        try:
            sa_json = json.loads(paste_text)
        except json.JSONDecodeError:
            pass

    col_back, col_validate = st.columns([1, 3])
    with col_back:
        if st.button("← Back", key="gcp_back_btn", use_container_width=True):
            _back_to_openai()
            st.rerun()
    with col_validate:
        if st.button("Validate →", key="gcp_validate_btn", type="primary", use_container_width=True):
            raw = paste_text.strip() if sa_json is None else None
            result = None
            if raw:
                result = validate_gcp_sa_json_text(raw)
                if result.ok:
                    try:
                        sa_json = json.loads(raw)
                    except json.JSONDecodeError:
                        pass
            elif sa_json is not None:
                with st.spinner("Validating GCP credentials…"):
                    result = validate_gcp_credentials(sa_json)
            else:
                st.error("Provide a service-account JSON file or paste the JSON.")

            if result and result.ok and sa_json is not None:
                set_gcp_sa_json(sa_json)
                st.session_state["gcp_validated"] = True
                st.session_state["_gcp_sa_json"] = True
                st.session_state["_gcp_fingerprint"] = (
                    result.fingerprint or sa_json.get("client_email", "validated")
                )
                st.rerun()
            elif result and not result.ok:
                st.error(result.message)


# ---------------------------------------------------------------------------
# Step 3 — Project + Cost cap
# ---------------------------------------------------------------------------


def _render_step_project() -> None:
    st.markdown(
        '<div class="step-title"><span class="num">③</span>GCP Project & Cost Cap</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="step-sub">Pick a project and set a monthly spend ceiling.</div>',
        unsafe_allow_html=True,
    )

    sa_json = st.session_state.get("gcp_sa_json")
    if sa_json is None:
        st.error("GCP credentials missing.")
        if st.button("← Back to credentials", key="proj_back_missing", use_container_width=True):
            _back_to_gcp()
            st.rerun()
        return

    if "gcp_project_list" not in st.session_state:
        with st.spinner("Loading projects…"):
            try:
                project_result = list_gcp_projects(sa_json)
                st.session_state["gcp_project_list"] = project_result.project_ids
            except AuthError as exc:
                st.error(f"Could not list projects: {exc}")
                return

    project_ids: list[str] = st.session_state["gcp_project_list"]

    if not project_ids:
        st.error(
            "No projects found. The service account needs "
            "`resourcemanager.projects.get` on at least one project."
        )
        if st.button("← Back to credentials", key="proj_back_empty", use_container_width=True):
            _back_to_gcp()
            st.rerun()
        return

    selected = st.selectbox(
        "Project",
        project_ids,
        key="gcp_project_select",
        label_visibility="collapsed",
    )
    cap = st.number_input(
        "Monthly cap (USD)",
        min_value=0,
        max_value=10_000,
        value=200,
        key="cost_cap_input",
    )

    col_back, col_launch = st.columns([1, 3])
    with col_back:
        if st.button("← Back", key="proj_back_btn", use_container_width=True):
            _back_to_gcp()
            st.rerun()
    with col_launch:
        if st.button(
            "Launch VibeOps →",
            key="setup_continue_btn",
            type="primary",
            use_container_width=True,
        ):
            set_gcp_project_id(str(selected))
            set_monthly_cost_cap(float(cap))
            set_setup_complete(True)
            save_credentials_to_cache()
            st.rerun()
