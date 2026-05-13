from __future__ import annotations

from typing import Any

import streamlit as st

from vibeops.core.gcp_context import GcpContext
from vibeops.core.llm import LLMClient
from vibeops.core.secrets import (
    clear_credentials_cache,
    get_or_create_graph_thread_id,
    is_multi_tenant_env,
)
from vibeops.models.conversation import ConversationTurn, RequirementPhase, TurnRole
from vibeops.models.state import GraphState
from vibeops.ui.architecture import render_architecture_card
from vibeops.ui.deployment import render_deployment
from vibeops.ui.graph_sync import sync_graph_stage
from vibeops.ui.review import render_review
from vibeops.ui.setup import reset_setup_state
from vibeops.ui.vm_inventory import get_inventory_counts, vm_inventory_dialog
from vibeops.ui.widgets import render_token_counter

_CHAT_CSS = """
<style>
/* Sidebar branding */
.sidebar-wordmark {
  font-size: 1.125rem;
  font-weight: 700;
  letter-spacing: -0.02em;
  color: #ffffff;
  margin-bottom: 2px;
}
.sidebar-tagline {
  font-size: 11px;
  color: #888;
  margin: 0;
  font-family: 'JetBrains Mono', monospace;
}

/* Landing page hero - compact */
.hero-wrap {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 16px 24px 12px;
  text-align: center;
  position: relative;
}
.hero-sub {
  font-size: 14px;
  color: #d6d6d6;
  margin: 0 auto 16px;
  max-width: 520px;
  line-height: 1.5;
  animation: heroSubFade 0.5s ease-out 0.4s both;
}
@keyframes heroSubFade {
  from { opacity: 0; transform: translateY(8px); }
  to   { opacity: 1; transform: translateY(0); }
}

/* ── VIBEOPS title — splash (one-shot) + continuous breathing glow ── */
.hero-title-vibeops {
  font-family: 'Space Grotesk', system-ui, sans-serif;
  font-size: clamp(2.5rem, 5vw, 4rem);
  font-weight: 700;
  letter-spacing: -0.04em;
  line-height: 1;
  margin: 0 0 10px;
  color: #ffffff;
  position: relative;
  display: inline-block;
}

/* Splash variant: scale + clip-path reveal + cyan flash, runs once */
.hero-title-vibeops.splash {
  animation:
    titleSplash 0.95s cubic-bezier(0.16, 1, 0.3, 1) both,
    titleGlow 4.5s ease-in-out 1s infinite;
}
/* Non-splash variant (returning to landing): just the breathing glow */
.hero-title-vibeops.no-splash {
  animation: titleGlow 4.5s ease-in-out infinite;
  text-shadow:
    0 0 30px rgba(0,222,255,0.55),
    0 0 80px rgba(0,222,255,0.30),
    0 0 140px rgba(0,222,255,0.15);
}

@keyframes titleSplash {
  0% {
    opacity: 0;
    transform: scale(0.75);
    filter: blur(20px);
    text-shadow:
      0 0 80px rgba(0,222,255,0.95),
      0 0 160px rgba(0,222,255,0.65);
  }
  55% {
    opacity: 1;
    transform: scale(1.04);
    filter: blur(0px);
    text-shadow:
      0 0 60px rgba(0,222,255,0.85),
      0 0 120px rgba(0,222,255,0.55);
  }
  100% {
    opacity: 1;
    transform: scale(1);
    filter: blur(0px);
    text-shadow:
      0 0 30px rgba(0,222,255,0.55),
      0 0 80px rgba(0,222,255,0.30),
      0 0 140px rgba(0,222,255,0.15);
  }
}
@keyframes titleGlow {
  0%, 100% {
    text-shadow:
      0 0 30px rgba(0,222,255,0.55),
      0 0 80px rgba(0,222,255,0.30),
      0 0 140px rgba(0,222,255,0.15);
  }
  50% {
    text-shadow:
      0 0 50px rgba(0,222,255,0.80),
      0 0 110px rgba(0,222,255,0.45),
      0 0 180px rgba(0,222,255,0.25);
  }
}

/* Soft radial halo behind the title — only on splash render */
.hero-title-vibeops.splash::before {
  content: "";
  position: absolute;
  inset: -40% -20%;
  background: radial-gradient(circle, rgba(0,222,255,0.45) 0%, rgba(0,222,255,0) 65%);
  filter: blur(40px);
  z-index: -1;
  animation: titleHalo 1.6s ease-out 0.1s both;
  pointer-events: none;
}
@keyframes titleHalo {
  0%   { opacity: 0; transform: scale(0.5); }
  35%  { opacity: 1; transform: scale(1.2); }
  100% { opacity: 0.35; transform: scale(1); }
}

/* Service / example cards - compact */
.svc-card {
  position: relative;
  border: 1px solid rgba(255,255,255,0.18);
  border-radius: 18px;
  padding: 16px 18px;
  background: #000;
  transition: background 0.25s, border-color 0.2s;
  height: 100%;
  min-height: 130px;
  display: flex;
  flex-direction: column;
  animation: fadeUp 0.25s ease-out both;
}
.svc-card:hover {
  border-color: rgba(0,222,255,0.4);
  background: radial-gradient(at center center, rgba(0,222,255,0.16) 0%, rgba(0,0,0,0) 75%), #000;
}
.svc-icon {
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  background: rgba(0,222,255,0.10);
  border: 1px solid rgba(0,222,255,0.3);
  color: #00DEFF;
  font-size: 14px;
  font-weight: 700;
  margin-bottom: 10px;
  box-shadow: 0 0 10px rgba(0,222,255,0.2);
}
.svc-title {
  font-size: 14px;
  font-weight: 600;
  color: #00DEFF;
  margin: 0 0 6px;
  letter-spacing: 0.04em;
}
.svc-text {
  font-size: 12.5px;
  color: #d6d6d6;
  line-height: 1.45;
  margin: 0;
  flex: 1;
}

/* Marquee - compact */
.marquee-wrap {
  overflow: hidden;
  width: 100%;
  margin: 16px 0 8px;
  border-top: 1px solid rgba(255,255,255,0.10);
  border-bottom: 1px solid rgba(255,255,255,0.10);
  padding: 10px 0;
  -webkit-mask-image: linear-gradient(90deg, transparent, #000 12%, #000 88%, transparent);
          mask-image: linear-gradient(90deg, transparent, #000 12%, #000 88%, transparent);
}
.marquee-track {
  display: flex;
  width: max-content;
  animation: scrollX 30s linear infinite;
}
.marquee-item {
  font-size: 14px;
  font-weight: 500;
  color: #d6d6d6;
  letter-spacing: 0.02em;
  padding: 0 18px;
  display: flex;
  align-items: center;
  white-space: nowrap;
}
.marquee-item .dot {
  width: 5px; height: 5px;
  border-radius: 50%;
  background: #00DEFF;
  margin-left: 18px;
  box-shadow: 0 0 8px rgba(0,222,255,0.6);
}

/* Chat history wrap */
.chat-hint {
  font-size: 13px;
  color: #888;
  margin: 12px 0 8px;
  font-family: 'JetBrains Mono', monospace;
}

/* Subtle ambient cyan glow blobs for hero */
.hero-wrap::before,
.hero-wrap::after {
  content: "";
  position: absolute;
  width: 320px;
  height: 320px;
  border-radius: 50%;
  filter: blur(80px);
  opacity: 0.35;
  z-index: -1;
  background: #00DEFF;
}
.hero-wrap::before { top: 0; left: 10%; }
.hero-wrap::after { bottom: 0; right: 10%; opacity: 0.18; }

/* Running VM banner */
.vm-banner {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 18px;
  border: 1px solid rgba(0,222,255,0.30);
  border-radius: 100px;
  background: rgba(0,222,255,0.06);
  margin: 0 0 16px;
  width: fit-content;
  animation: fadeUp 0.35s ease-out both;
}
.vm-banner .pulse-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #00DEFF;
  box-shadow: 0 0 10px rgba(0,222,255,0.8);
  animation: vmPulse 2s ease-in-out infinite;
}
.vm-banner .vm-banner-text {
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
  color: #00DEFF;
  letter-spacing: 0.04em;
}
@keyframes vmPulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50%      { opacity: 0.4; transform: scale(1.3); }
}
</style>
"""

_EXAMPLES = [
    (
        "⚡",
        "JUPYTER",
        "Jupyter notebook on a T4 with port 8888 open to the web for remote access",
    ),
    (
        "◆",
        "WEB APP",
        "Run nginx in a container with ports 80 and 443 open for public traffic",
    ),
    (
        "◇",
        "FINE-TUNE",
        "Fine-tune Llama 3 8B on an A100 with a 200GB checkpoint disk, preemptible",
    ),
]


_AFFIRMATIVE_TOKENS = (
    "yes", "yeah", "yep", "yup", "y", "sure", "ok", "okay", "k",
    "go", "ship", "ship it", "deploy", "do it", "proceed", "confirm",
    "looks good", "lgtm", "perfect", "great", "fine", "correct", "right",
    "sounds good", "good", "all good", "send it", "let's go", "lets go",
)


def _is_affirmative(text: str) -> bool:
    """True when the user message looks like a confirmation.

    Conservative — short messages containing an affirmative token count.
    Long messages don't count even if they contain "yes" somewhere, because
    those usually contain additional change requests.
    """
    t = text.strip().lower()
    if not t:
        return False
    # Trim punctuation
    t = t.rstrip(".!?,;:")
    if t in _AFFIRMATIVE_TOKENS:
        return True
    # Short messages (≤ 20 chars) starting with an affirmative token also count
    if len(t) <= 20:
        first_word = t.split()[0] if t.split() else ""
        if first_word in _AFFIRMATIVE_TOKENS:
            return True
    return False


def _ensure_clients() -> None:
    if "llm_client" not in st.session_state:
        openai_key: str | None = st.session_state.get("openai_key")
        if openai_key:
            st.session_state["llm_client"] = LLMClient(api_key=openai_key)

    if "gcp_context" not in st.session_state:
        sa_json: dict[str, object] | None = st.session_state.get("gcp_sa_json")
        project_id: str | None = st.session_state.get("gcp_project_id")
        if sa_json and project_id:
            st.session_state["gcp_context"] = GcpContext(
                service_account_info=sa_json, project_id=project_id
            )


def _render_sidebar() -> None:
    with st.sidebar:
        st.markdown(_CHAT_CSS, unsafe_allow_html=True)
        st.markdown('<p class="sidebar-wordmark">VIBEOPS</p>', unsafe_allow_html=True)
        project = st.session_state.get("gcp_project_id", "")
        if project:
            st.markdown(f'<p class="sidebar-tagline">{project}</p>', unsafe_allow_html=True)
        st.divider()

        if st.button("New deployment", key="sidebar.new", use_container_width=True):
            _reset_chat()

        if st.button("Running VMs", key="sidebar.vms", use_container_width=True):
            st.session_state.pop("_vm_inventory", None)
            st.session_state.pop("_vm_inventory_error", None)
            st.session_state.pop("_vm_pending_delete", None)
            st.session_state["_show_vm_inventory"] = True
            st.rerun()

        if st.button("Reconfigure", key="sidebar.reconfigure", use_container_width=True):
            clear_credentials_cache()
            reset_setup_state()
            st.rerun()

        st.divider()
        render_token_counter()


def _open_vm_inventory() -> None:
    st.session_state.pop("_vm_inventory", None)
    st.session_state.pop("_vm_inventory_error", None)
    st.session_state.pop("_vm_pending_delete", None)
    st.session_state["_show_vm_inventory"] = True
    st.rerun()


def _has_active_flow() -> bool:
    """True when the user is mid-conversation/architecture/review/deployment.

    Used to decide whether to show the Exit button in the header.
    The landing page (no graph_stage, no history) is the "no active flow" state.
    """
    stage = st.session_state.get("graph_stage")
    history = st.session_state.get("display_history")
    return bool(stage) or bool(history)


def _render_global_header() -> None:
    """Top header bar — VM banner (left), Exit + Settings (right).

    Rendered at the top of every chat screen so the user can always reach
    their running VMs, abandon a stuck conversation, and access credentials.
    """
    st.markdown(_CHAT_CSS, unsafe_allow_html=True)
    running, total = get_inventory_counts()
    show_exit = _has_active_flow()

    if show_exit:
        col_vm, _, col_exit, col_settings = st.columns([3, 3, 1, 1])
    else:
        col_vm, _, col_settings = st.columns([3, 4, 1])
        col_exit = None

    with col_vm:
        if total > 0:
            label = (
                f"{running} RUNNING · {total} TOTAL VM{'S' if total != 1 else ''}"
                if running > 0
                else f"{total} VM{'S' if total != 1 else ''} IN PROJECT"
            )
            st.markdown(
                f'<div class="vm-banner">'
                f'<div class="pulse-dot"></div>'
                f'<span class="vm-banner-text">{label}</span>'
                f"</div>",
                unsafe_allow_html=True,
            )
            if st.button("Manage VMs →", key="header.manage_vms"):
                _open_vm_inventory()
        else:
            st.markdown(
                '<div class="vm-banner" style="opacity:0.5">'
                '<div class="pulse-dot" style="background:#555;box-shadow:none;animation:none"></div>'
                '<span class="vm-banner-text" style="color:#888">NO VMS IN PROJECT</span>'
                "</div>",
                unsafe_allow_html=True,
            )

    if col_exit is not None:
        with col_exit:
            # The marker div is hidden by CSS; its only job is to flag the
            # following button so we can give it the circular-cyan style
            # without affecting other buttons in the app.
            st.markdown(
                '<div class="vibe-exit-marker"></div>',
                unsafe_allow_html=True,
            )
            if st.button("✕", key="header.exit", help="Exit this deployment"):
                _reset_chat()

    with col_settings:
        if st.button("⚙ Settings", key="header.settings", use_container_width=True):
            st.session_state["show_settings"] = not st.session_state.get("show_settings", False)

    if st.session_state.get("show_settings", False):
        with st.expander("Credentials", expanded=True):
            if is_multi_tenant_env():
                st.caption(
                    "🔒 Your credentials live only in this browser session and "
                    "are discarded when you close the tab. They are never "
                    "stored on the server. Click **Reconfigure** to clear them now."
                )
            else:
                st.caption(
                    "Your credentials are cached locally at "
                    "`~/.vibeops/credentials.json`. Click **Reconfigure** to "
                    "clear them and re-run setup."
                )
            project = st.session_state.get("gcp_project_id", "—")
            openai_key = st.session_state.get("openai_key", "")
            st.markdown(f"**GCP Project:** `{project}`")
            if openai_key:
                st.markdown(f"**OpenAI Key:** `…{openai_key[-4:]}`")
            if st.button("Reconfigure", key="header.reconfigure", type="primary"):
                clear_credentials_cache()
                reset_setup_state()
                st.rerun()


def render_chat() -> None:
    _ensure_clients()
    _render_sidebar()

    if st.session_state.get("_show_vm_inventory", False):
        vm_inventory_dialog()

    _render_global_header()

    from vibeops.graph.orchestrator import build_graph

    if "graph" not in st.session_state:
        st.session_state["graph"] = build_graph()
    graph: Any = st.session_state["graph"]

    graph_stage: str = st.session_state.get("graph_stage", "idle")
    thread: dict[str, Any] = {"configurable": {"thread_id": get_or_create_graph_thread_id()}}
    llm = st.session_state.get("llm_client")
    gcp_ctx = st.session_state.get("gcp_context")
    if llm is not None or gcp_ctx is not None:
        thread["configurable"]["llm_client"] = llm
        thread["configurable"]["gcp_context"] = gcp_ctx

    if graph_stage == "awaiting_approval":
        snapshot: dict[str, object] = graph.get_state(thread).values
        current_state = GraphState.model_validate(snapshot)
        render_review(graph, current_state, thread)
        return

    if graph_stage == "deployment_active":
        snapshot = graph.get_state(thread).values
        current_state = GraphState.model_validate(snapshot)
        render_deployment(graph, current_state, thread)
        return

    if graph_stage in ("cancelled", "done"):
        _render_terminal_state(graph_stage)
        return

    if graph_stage == "asking":
        snapshot = graph.get_state(thread).values
        current_state = GraphState.model_validate(snapshot)
        _render_asking(graph, current_state, thread)
        return

    if graph_stage == "awaiting_confirmation":
        snapshot = graph.get_state(thread).values
        current_state = GraphState.model_validate(snapshot)
        _render_asking(graph, current_state, thread)
        return

    if graph_stage == "awaiting_architecture":
        snapshot = graph.get_state(thread).values
        current_state = GraphState.model_validate(snapshot)
        render_architecture_card(current_state, graph, thread)
        return

    history: list[dict[str, str]] = st.session_state.get("display_history", [])
    if not history:
        _render_landing(graph)
    else:
        _render_history(history)
        st.markdown('<p class="chat-hint">// continue or start a new deployment</p>', unsafe_allow_html=True)
        user_input = st.chat_input("Message…", key="initial_prompt")
        if user_input and user_input.strip():
            _run_graph(graph, user_input.strip())


def _render_landing(graph: Any) -> None:
    st.markdown(_CHAT_CSS, unsafe_allow_html=True)

    # Splash plays once per browser session — track in session state.
    if not st.session_state.get("_landing_splash_shown", False):
        st.session_state["_landing_splash_shown"] = True
        title_class = "hero-title-vibeops splash"
    else:
        title_class = "hero-title-vibeops no-splash"

    st.markdown(
        '<div class="hero-wrap">'
        f'<div class="{title_class}">VIBEOPS</div>'
        '<p class="hero-sub">Natural language to a running GPU instance — ship infrastructure in minutes.</p>'
        "</div>",
        unsafe_allow_html=True,
    )

    cols = st.columns(3, gap="medium")
    for i, (icon, label, prompt) in enumerate(_EXAMPLES):
        with cols[i]:
            st.markdown(
                f'<div class="svc-card">'
                f'<div class="svc-icon">{icon}</div>'
                f'<h3 class="svc-title">{label}</h3>'
                f'<p class="svc-text">{prompt}</p>'
                f"</div>",
                unsafe_allow_html=True,
            )
            if st.button("Try this →", key=f"example_{i}", use_container_width=True):
                _run_graph(graph, prompt)

    st.markdown(
        '<div class="marquee-wrap"><div class="marquee-track">'
        '<span class="marquee-item">Describe your workload<span class="dot"></span></span>'
        '<span class="marquee-item">Pick a zone<span class="dot"></span></span>'
        '<span class="marquee-item">Review terraform<span class="dot"></span></span>'
        '<span class="marquee-item">Approve & deploy<span class="dot"></span></span>'
        '<span class="marquee-item">Tear down when done<span class="dot"></span></span>'
        '<span class="marquee-item">Describe your workload<span class="dot"></span></span>'
        '<span class="marquee-item">Pick a zone<span class="dot"></span></span>'
        '<span class="marquee-item">Review terraform<span class="dot"></span></span>'
        '<span class="marquee-item">Approve & deploy<span class="dot"></span></span>'
        '<span class="marquee-item">Tear down when done<span class="dot"></span></span>'
        "</div></div>",
        unsafe_allow_html=True,
    )

    user_input = st.chat_input(
        "Describe the GPU infrastructure you need…",
        key="initial_prompt",
    )
    if user_input and user_input.strip():
        _run_graph(graph, user_input.strip())


def _render_history(history: list[dict[str, str]]) -> None:
    for entry in history:
        role = entry.get("role", "user")
        agent = entry.get("agent", "")
        content = entry.get("content", "")
        avatar = "👤" if role == "user" else "🤖"
        prefix = f"**[{agent.upper()}]**  \n" if agent else ""
        with st.chat_message(role, avatar=avatar):
            st.markdown(prefix + content if prefix else content)


def _render_asking(graph: Any, state: GraphState, thread: dict[str, Any]) -> None:
    from vibeops.agents.requirement import build_conversation_messages_with_context

    llm = st.session_state.get("llm_client")
    conversation = state.conversation

    for turn in conversation:
        role = "user" if turn.role.value == "user" else "assistant"
        avatar = "👤" if role == "user" else "🤖"
        with st.chat_message(role, avatar=avatar):
            st.markdown(turn.content)

    reply = st.chat_input("Message…", key="chat.requirement_input")
    if not reply:
        return

    with st.chat_message("user", avatar="👤"):
        st.markdown(reply)

    messages = build_conversation_messages_with_context(
        conversation, reply, state.extracted_intent
    )
    with st.chat_message("assistant", avatar="🤖"):
        if llm:
            response: str = st.write_stream(llm.stream_text(messages, temperature=0.7))
        else:
            response = "[[PROCEED]]"
            st.markdown("Proceeding with defaults.")

    # Code-side safety: even if the LLM emits [[PROCEED]] together with the
    # summary on the first turn (a known failure mode), only honor it when the
    # user's latest message actually looks like a confirmation. This prevents
    # the conversation from jumping past the summary without explicit consent.
    proceed_token_present = "[[PROCEED]]" in response
    looks_like_confirmation = _is_affirmative(reply)
    proceed = proceed_token_present and looks_like_confirmation

    clean = response.replace("[[PROCEED]]", "").strip()
    if proceed_token_present and not looks_like_confirmation:
        # Don't show the bare token in the visible message — let the LLM
        # ask the user again on the next turn.
        clean = clean or "Does this look good? Reply 'yes' to deploy or tell me what to change."

    new_conv = [t.model_dump() for t in conversation]
    new_conv.append(ConversationTurn(role=TurnRole.USER, content=reply[:1000]).model_dump())
    new_conv.append(ConversationTurn(role=TurnRole.AGENT, content=clean).model_dump())

    if proceed:
        graph.update_state(
            thread,
            {
                "conversation": new_conv,
                "requirement_phase": RequirementPhase.RESUMING_CONFIRMATION.value,
            },
        )
        with st.status("Checking GPU availability…", expanded=False):
            st.write("Extracting requirements from conversation")
            graph.invoke(None, thread)
            st.write("Fetched available zones and machine types")
        sync_graph_stage(graph, thread)
    else:
        graph.update_state(
            thread,
            {
                "conversation": new_conv,
                "requirement_phase": RequirementPhase.ASKING.value,
            },
        )
        sync_graph_stage(graph, thread)

    st.rerun()


def _run_graph(graph: Any, prompt: str) -> None:
    from vibeops.graph.orchestrator import build_graph
    from vibeops.models.state import GraphState

    st.session_state["graph"] = build_graph()
    graph = st.session_state["graph"]
    st.session_state.pop("display_history", None)

    thread_id = get_or_create_graph_thread_id()
    thread: dict[str, Any] = {"configurable": {"thread_id": thread_id}}

    llm = st.session_state.get("llm_client")
    gcp_ctx = st.session_state.get("gcp_context")
    if llm is not None or gcp_ctx is not None:
        thread["configurable"]["llm_client"] = llm
        thread["configurable"]["gcp_context"] = gcp_ctx

    initial = GraphState(user_prompt=prompt)
    st.session_state["display_history"] = [{"role": "user", "content": prompt}]

    with st.spinner("Analyzing your request…"):
        graph.invoke(initial.model_dump(), thread)

    sync_graph_stage(graph, thread)
    st.rerun()


def _render_terminal_state(stage: str) -> None:
    if stage == "deployment":
        history: list[dict[str, str]] = st.session_state.get("display_history", [])
        deployment_entries = [e for e in history if e.get("agent") == "deployment"]
        if deployment_entries:
            st.success("Deployment complete.")
            st.markdown(deployment_entries[-1]["content"])
        else:
            st.success("Deployment complete.")
        if st.button("New deployment", key="new_deploy_btn"):
            _reset_chat()
    elif stage == "cancelled":
        st.warning("Deployment cancelled.")
        if st.button("Start over", key="start_over_btn"):
            _reset_chat()


def _reset_chat() -> None:
    for key in ("graph", "graph_stage", "display_history", "graph_thread_id"):
        st.session_state.pop(key, None)
    st.rerun()
