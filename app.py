from __future__ import annotations

import streamlit as st

from vibeops.config import AppConfig
from vibeops.core.logging import configure_logging
from vibeops.core.secrets import get_setup_complete, load_credentials_from_cache
from vibeops.ui.chat import render_chat
from vibeops.ui.setup import render_setup
from vibeops.ui.theme import inject_theme

_config = AppConfig()
configure_logging(_config.log_level)

st.set_page_config(
    page_title="VibeOps",
    page_icon=":cloud:",
    layout="wide",
    initial_sidebar_state="auto",
)

inject_theme()

if "cache_loaded" not in st.session_state:
    st.session_state["cache_loaded"] = True
    load_credentials_from_cache()

if not get_setup_complete():
    render_setup()
else:
    render_chat()
