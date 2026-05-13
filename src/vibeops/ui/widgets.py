from __future__ import annotations

import streamlit as st

from vibeops.core.prices import PRICES_AS_OF


def render_token_counter() -> None:
    from vibeops.core.llm import LLMClient

    llm: LLMClient | None = st.session_state.get("llm_client")
    spend = llm.session_spend_usd() if llm is not None else float(st.session_state.get("session_spend_usd", 0.0))
    st.markdown(
        f'<div style="font-family:\'JetBrains Mono\',monospace;font-size:10px;color:#888;letter-spacing:0.08em;text-transform:uppercase;margin-bottom:4px">// LLM SPEND</div>'
        f'<div style="font-family:\'Space Grotesk\',sans-serif;font-size:18px;font-weight:600;color:#00DEFF;text-shadow:0 0 10px rgba(0,222,255,0.4);letter-spacing:-0.01em">${spend:.4f}</div>'
        f'<div style="font-family:\'JetBrains Mono\',monospace;font-size:10px;color:#666;margin-top:4px">prices as of {PRICES_AS_OF}</div>',
        unsafe_allow_html=True,
    )


def render_credentials_note() -> None:
    st.caption(
        "_Credentials are cached locally in `~/.vibeops/credentials.json` "
        "and restored automatically on refresh. Use 'Reconfigure' in the sidebar to clear them._"
    )
