from __future__ import annotations

import streamlit as st

_FONTS_HTML = """\
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200" rel="stylesheet">
"""

_CSS = """\
/* ── Variables ───────────────────────────────────────── */
:root {
  --bg:             #000000;
  --bg-alt:         #050505;
  --surface:        #0d0d0d;
  --surface-2:      #1d1d1d;
  --text:           #ffffff;
  --text-muted:     #d6d6d6;
  --text-dim:       #888888;
  --border:         rgba(255,255,255,0.18);
  --border-strong:  rgba(255,255,255,0.30);
  --accent:         #00DEFF;
  --accent-soft:    rgba(0,222,255,0.16);
  --accent-glow:    0 0 20px rgba(0,222,255,0.55), 0 0 60px rgba(0,222,255,0.25);
  --accent-glow-sm: 0 0 12px rgba(0,222,255,0.35);
  --r-sm:           8px;
  --r-md:           16px;
  --r-lg:           25px;
  --r-pill:         100px;
  --sans:           'Space Grotesk', system-ui, -apple-system, BlinkMacSystemFont, sans-serif;
  --mono:           'JetBrains Mono', 'SF Mono', ui-monospace, monospace;
}

/* ── Global ───────────────────────────────────────────── */
html, body, [class*="css"], [data-testid] {
  font-family: var(--sans) !important;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}
html { scroll-behavior: smooth; }

.stApp {
  background: var(--bg) !important;
}

.main .block-container {
  padding-top: 1rem !important;
  padding-bottom: 2rem !important;
  max-width: 1200px !important;
}

/* ── Typography ───────────────────────────────────────── */
h1 {
  font-family: var(--sans) !important;
  font-size: 2rem !important;
  font-weight: 700 !important;
  letter-spacing: -0.03em !important;
  color: var(--text) !important;
  line-height: 1.1 !important;
  margin-bottom: 0.5rem !important;
}
h2 {
  font-family: var(--sans) !important;
  font-size: 1.375rem !important;
  font-weight: 600 !important;
  letter-spacing: -0.02em !important;
  color: var(--text) !important;
}
h3 {
  font-family: var(--sans) !important;
  font-size: 1rem !important;
  font-weight: 600 !important;
  color: var(--text) !important;
}
p, li {
  font-family: var(--sans) !important;
  font-size: 14px !important;
  line-height: 1.6 !important;
  color: var(--text) !important;
}
span, label {
  font-family: var(--sans) !important;
  font-size: 14px !important;
  color: var(--text) !important;
}
.gradient-accent {
  color: var(--accent) !important;
  text-shadow: 0 0 16px rgba(0,222,255,0.6);
}

/* ── Divider ──────────────────────────────────────────── */
hr {
  border: none !important;
  border-top: 1px solid var(--border) !important;
  margin: 1.5rem 0 !important;
}

/* ── Buttons (pill style, accent glow on hover) ───────── */
.stButton > button {
  font-family: var(--sans) !important;
  font-size: 14px !important;
  font-weight: 500 !important;
  background: transparent !important;
  color: var(--text) !important;
  border: 1px solid var(--border) !important;
  border-radius: var(--r-pill) !important;
  padding: 10px 24px !important;
  box-shadow: none !important;
  transition: background 0.2s, border-color 0.2s, box-shadow 0.25s, transform 0.15s !important;
  line-height: 1.4 !important;
  backdrop-filter: blur(6px);
  -webkit-backdrop-filter: blur(6px);
}
.stButton > button:hover {
  border-color: var(--accent) !important;
  box-shadow: var(--accent-glow) !important;
  background: rgba(0,222,255,0.06) !important;
  transform: translateY(-1px) !important;
}
.stButton > button:active {
  transform: translateY(0) !important;
}
.stButton > button[kind="primary"] {
  background: var(--accent) !important;
  color: #000 !important;
  border: 1px solid var(--accent) !important;
  font-weight: 600 !important;
  box-shadow: var(--accent-glow-sm) !important;
}
.stButton > button[kind="primary"]:hover {
  background: var(--accent) !important;
  color: #000 !important;
  box-shadow: var(--accent-glow) !important;
}
/* Force black text on primary button descendants (overrides global span/label color) */
.stButton > button[kind="primary"] *,
.stButton > button[kind="primary"] p,
.stButton > button[kind="primary"] span,
.stButton > button[kind="primary"] div,
.stButton > button[kind="primary"] label {
  color: #000 !important;
  font-weight: 600 !important;
}
.stButton > button:disabled,
.stButton > button[disabled] {
  opacity: 0.35 !important;
  cursor: not-allowed !important;
  box-shadow: none !important;
  transform: none !important;
}

/* ── Text inputs ──────────────────────────────────────── */
.stTextInput input,
.stNumberInput input {
  font-family: var(--sans) !important;
  font-size: 14px !important;
  border: 1px solid var(--border) !important;
  border-radius: var(--r-pill) !important;
  background: var(--surface) !important;
  color: var(--text) !important;
  padding: 10px 18px !important;
  box-shadow: none !important;
  transition: border-color 0.2s, box-shadow 0.25s !important;
}
.stTextInput input:focus,
.stNumberInput input:focus {
  border-color: var(--accent) !important;
  box-shadow: var(--accent-glow-sm) !important;
  outline: none !important;
}
.stTextInput input[type="password"] {
  font-family: var(--mono) !important;
  letter-spacing: 0.08em !important;
}

.stTextArea textarea {
  font-family: var(--mono) !important;
  font-size: 13px !important;
  border: 1px solid var(--border) !important;
  border-radius: var(--r-md) !important;
  background: var(--surface) !important;
  color: var(--text) !important;
  box-shadow: none !important;
}
.stTextArea textarea:focus {
  border-color: var(--accent) !important;
  box-shadow: var(--accent-glow-sm) !important;
  outline: none !important;
}

/* ── Selectbox ────────────────────────────────────────── */
.stSelectbox > div > div,
[data-baseweb="select"] {
  font-family: var(--sans) !important;
  font-size: 13px !important;
  border: 1px solid var(--border) !important;
  border-radius: var(--r-pill) !important;
  background: var(--surface) !important;
}
[data-baseweb="select"] span {
  color: var(--text) !important;
}

/* ── File uploader ────────────────────────────────────── */
[data-testid="stFileUploader"] section {
  border: 1px dashed var(--border) !important;
  border-radius: var(--r-md) !important;
  background: var(--surface) !important;
  transition: border-color 0.2s, box-shadow 0.25s !important;
}
[data-testid="stFileUploader"] section:hover {
  border-color: var(--accent) !important;
  box-shadow: var(--accent-glow-sm) !important;
}

/* ── Code / mono ──────────────────────────────────────── */
pre, code, kbd {
  font-family: var(--mono) !important;
}
[data-testid="stCode"] > div,
.stCode {
  background: var(--surface) !important;
  border: 1px solid var(--border) !important;
  border-radius: var(--r-md) !important;
  font-family: var(--mono) !important;
  font-size: 12.5px !important;
}
[data-testid="stCode"] code {
  font-family: var(--mono) !important;
  font-size: 12.5px !important;
  color: var(--text) !important;
}

/* ── Chat messages ────────────────────────────────────── */
[data-testid="stChatMessage"] {
  display: flex !important;
  flex-direction: row !important;
  align-items: flex-start !important;
  gap: 14px !important;
  background: transparent !important;
  border: none !important;
  border-bottom: 1px solid var(--border) !important;
  border-radius: 0 !important;
  padding: 18px 0 !important;
  animation: fadeUp 0.22s ease-out both !important;
}
[data-testid="stChatMessage"]:last-of-type {
  border-bottom: none !important;
}
[data-testid="stChatMessage"] > div:first-child,
[data-testid="stChatMessage"] > img:first-child {
  flex: 0 0 32px !important;
  width: 32px !important;
  min-width: 32px !important;
  max-width: 32px !important;
}
[data-testid="stChatMessageContent"] {
  flex: 1 1 auto !important;
  min-width: 0 !important;
  background: transparent !important;
  overflow: hidden !important;
}
[data-testid="chatAvatarIcon-user"],
[data-testid="chatAvatarIcon-assistant"] {
  width: 30px !important;
  height: 30px !important;
  min-width: 30px !important;
  border-radius: 50% !important;
  flex-shrink: 0 !important;
  font-size: 12px !important;
  font-weight: 600 !important;
}
[data-testid="chatAvatarIcon-user"] {
  background: var(--surface-2) !important;
  border: 1px solid var(--border) !important;
  color: var(--text-muted) !important;
}
[data-testid="chatAvatarIcon-assistant"] {
  background: var(--accent-soft) !important;
  border: 1px solid var(--accent) !important;
  color: var(--accent) !important;
  box-shadow: var(--accent-glow-sm) !important;
}

/* ── Chat input ───────────────────────────────────────── */
[data-testid="stChatInput"] {
  border-top: 1px solid var(--border) !important;
  background: var(--bg) !important;
  padding: 14px 0 !important;
}
[data-testid="stChatInput"] textarea {
  font-family: var(--sans) !important;
  font-size: 14px !important;
  border: 1px solid var(--border) !important;
  border-radius: var(--r-pill) !important;
  background: var(--surface) !important;
  color: var(--text) !important;
  box-shadow: none !important;
  resize: none !important;
  padding: 12px 20px !important;
}
[data-testid="stChatInput"] textarea:focus {
  border-color: var(--accent) !important;
  box-shadow: var(--accent-glow-sm) !important;
}
[data-testid="stChatInput"] button {
  background: var(--accent) !important;
  border-radius: 50% !important;
  border: none !important;
  box-shadow: var(--accent-glow-sm) !important;
}
[data-testid="stChatInput"] button:hover {
  box-shadow: var(--accent-glow) !important;
}
[data-testid="stChatInput"] button svg {
  fill: #000 !important;
}

/* ── Alerts ───────────────────────────────────────────── */
[data-testid="stAlert"],
.stSuccess > div,
.stError > div,
.stWarning > div,
.stInfo > div {
  font-family: var(--sans) !important;
  font-size: 13px !important;
  border-radius: var(--r-md) !important;
  border-width: 1px !important;
  border-style: solid !important;
  backdrop-filter: blur(6px);
}
.stSuccess > div {
  background: rgba(22,163,74,0.08) !important;
  border-color: rgba(22,163,74,0.4) !important;
  color: #4ade80 !important;
}
.stError > div {
  background: rgba(220,38,38,0.08) !important;
  border-color: rgba(220,38,38,0.4) !important;
  color: #f87171 !important;
}
.stWarning > div {
  background: rgba(215,119,6,0.08) !important;
  border-color: rgba(215,119,6,0.4) !important;
  color: #fbbf24 !important;
}
.stInfo > div {
  background: var(--surface) !important;
  border-color: var(--border) !important;
  color: var(--text-muted) !important;
}

/* ── Metrics ──────────────────────────────────────────── */
[data-testid="metric-container"] {
  border: 1px solid var(--border) !important;
  border-radius: var(--r-lg) !important;
  padding: 18px 22px !important;
  background: var(--surface) !important;
  transition: border-color 0.2s, box-shadow 0.25s !important;
}
[data-testid="metric-container"]:hover {
  border-color: var(--border-strong) !important;
  background: radial-gradient(at center center, rgba(0,222,255,0.06) 0%, rgba(0,0,0,0) 75%), var(--surface) !important;
}
[data-testid="stMetricLabel"] > div {
  font-size: 11px !important;
  font-weight: 500 !important;
  color: var(--text-dim) !important;
  text-transform: uppercase !important;
  letter-spacing: 0.08em !important;
}
[data-testid="stMetricValue"] > div {
  font-size: 1.625rem !important;
  font-weight: 700 !important;
  letter-spacing: -0.02em !important;
  color: var(--text) !important;
}

/* ── Progress ─────────────────────────────────────────── */
[data-testid="stProgress"] > div {
  background: var(--border) !important;
  border-radius: 2px !important;
  height: 3px !important;
}
[data-testid="stProgress"] > div > div {
  background: var(--accent) !important;
  border-radius: 2px !important;
  height: 3px !important;
  box-shadow: var(--accent-glow-sm);
}

/* ── Expander ─────────────────────────────────────────── */
[data-testid="stExpander"] {
  border: 1px solid var(--border) !important;
  border-radius: var(--r-md) !important;
  overflow: hidden !important;
  background: var(--surface) !important;
  transition: border-color 0.2s !important;
}
[data-testid="stExpander"]:hover {
  border-color: var(--border-strong) !important;
}
[data-testid="stExpander"] summary {
  font-family: var(--sans) !important;
  font-size: 13px !important;
  font-weight: 500 !important;
  color: var(--text-muted) !important;
  background: var(--surface) !important;
  padding: 12px 16px !important;
}
[data-testid="stExpander"] summary:hover {
  color: var(--accent) !important;
}

/* ── Tabs ─────────────────────────────────────────────── */
[data-baseweb="tab-list"] {
  border-bottom: 1px solid var(--border) !important;
  background: transparent !important;
  gap: 0 !important;
}
[data-baseweb="tab"] {
  font-family: var(--sans) !important;
  font-size: 13px !important;
  font-weight: 500 !important;
  color: var(--text-dim) !important;
  border: none !important;
  background: transparent !important;
  padding: 10px 18px !important;
  border-bottom: 2px solid transparent !important;
  margin-bottom: -1px !important;
  transition: color 0.2s !important;
}
[data-baseweb="tab"]:hover {
  color: var(--text-muted) !important;
}
[aria-selected="true"][data-baseweb="tab"] {
  color: var(--accent) !important;
  border-bottom-color: var(--accent) !important;
  background: transparent !important;
}
[data-baseweb="tab-highlight"] {
  background-color: var(--accent) !important;
  height: 2px !important;
  box-shadow: var(--accent-glow-sm);
}
[data-baseweb="tab-panel"] {
  padding: 18px 0 !important;
}

/* ── Radio (selectable cards) ─────────────────────────── */
[data-testid="stRadio"] > div {
  gap: 10px !important;
  flex-direction: column !important;
}
[data-testid="stRadio"] label {
  border: 1px solid var(--border) !important;
  border-radius: var(--r-md) !important;
  padding: 14px 18px !important;
  background: var(--surface) !important;
  cursor: pointer !important;
  transition: all 0.25s !important;
  width: 100% !important;
}
[data-testid="stRadio"] label:hover {
  border-color: var(--border-strong) !important;
  background: radial-gradient(at center center, rgba(0,222,255,0.10) 0%, rgba(0,0,0,0) 75%), var(--surface) !important;
}
[data-testid="stRadio"] label[data-checked="true"] {
  border-color: var(--accent) !important;
  background: radial-gradient(at center center, rgba(0,222,255,0.16) 0%, rgba(0,0,0,0) 75%), var(--surface) !important;
  box-shadow: var(--accent-glow-sm) !important;
}

/* ── Caption ──────────────────────────────────────────── */
.stCaption,
[data-testid="stCaptionContainer"] {
  font-family: var(--sans) !important;
  font-size: 12px !important;
  color: var(--text-dim) !important;
  line-height: 1.5 !important;
}

/* ── Status widget ────────────────────────────────────── */
[data-testid="stStatusWidget"],
.stStatus {
  border: 1px solid var(--border) !important;
  border-radius: var(--r-md) !important;
  background: var(--surface) !important;
  font-family: var(--sans) !important;
  font-size: 13px !important;
}

/* ── Sidebar ──────────────────────────────────────────── */
[data-testid="stSidebar"] {
  background: var(--bg-alt) !important;
  border-right: 1px solid var(--border) !important;
}
[data-testid="stSidebar"] > div:first-child {
  padding: 1.5rem 1rem !important;
}
[data-testid="stSidebar"] .stButton > button {
  background: transparent !important;
  color: var(--text-muted) !important;
  border: 1px solid var(--border) !important;
  width: 100% !important;
  text-align: left !important;
  justify-content: flex-start !important;
  font-size: 13px !important;
  border-radius: var(--r-pill) !important;
}
[data-testid="stSidebar"] .stButton > button:hover {
  background: rgba(0,222,255,0.06) !important;
  border-color: var(--accent) !important;
  color: var(--text) !important;
  box-shadow: var(--accent-glow-sm) !important;
}

/* ── Spinner ──────────────────────────────────────────── */
[data-testid="stSpinner"] p {
  font-family: var(--sans) !important;
  font-size: 13px !important;
  color: var(--text-muted) !important;
}
[data-testid="stSpinner"] > div > div {
  border-top-color: var(--accent) !important;
  filter: drop-shadow(0 0 6px rgba(0,222,255,0.5));
}

/* ── Checkbox ─────────────────────────────────────────── */
[data-testid="stCheckbox"] label span {
  font-family: var(--sans) !important;
  font-size: 13px !important;
  color: var(--text) !important;
}

/* ── Markdown ─────────────────────────────────────────── */
.stMarkdown strong { font-weight: 600; color: var(--text); }
.stMarkdown a {
  color: var(--accent);
  text-decoration: underline;
  text-underline-offset: 3px;
  transition: text-shadow 0.2s;
}
.stMarkdown a:hover { text-shadow: 0 0 12px rgba(0,222,255,0.6); }

/* ── Animations ───────────────────────────────────────── */
@keyframes fadeUp {
  from { opacity: 0; transform: translateY(10px); }
  to   { opacity: 1; transform: translateY(0); }
}
@keyframes fadeIn {
  from { opacity: 0; }
  to   { opacity: 1; }
}
@keyframes accentPulse {
  0%, 100% { box-shadow: 0 0 20px rgba(0,222,255,0.4), 0 0 60px rgba(0,222,255,0.2); }
  50%      { box-shadow: 0 0 28px rgba(0,222,255,0.65), 0 0 90px rgba(0,222,255,0.35); }
}
@keyframes scrollX {
  from { transform: translateX(0); }
  to   { transform: translateX(-50%); }
}
.stApp > .main > .block-container {
  animation: fadeIn 0.25s ease-out both;
}

/* ── Scrollbar ────────────────────────────────────────── */
::-webkit-scrollbar { width: 8px; height: 8px; }
::-webkit-scrollbar-track { background: var(--bg); }
::-webkit-scrollbar-thumb {
  background: var(--accent);
  border-radius: 8px;
}
::-webkit-scrollbar-thumb:hover {
  background: var(--accent);
  box-shadow: var(--accent-glow-sm);
}

/* ── Custom glow cursor ───────────────────────────────── */
.vibe-cursor {
  position: fixed;
  top: 0; left: 0;
  width: 12px; height: 12px;
  background: var(--accent);
  border-radius: 50%;
  pointer-events: none;
  z-index: 99999;
  transform: translate(-50%, -50%);
  mix-blend-mode: screen;
  box-shadow:
    0 0 18px rgba(0,222,255,0.95),
    0 0 60px rgba(0,222,255,0.6),
    0 0 160px rgba(0,222,255,0.3);
  transition: width 0.18s ease, height 0.18s ease, background 0.18s ease, box-shadow 0.18s ease;
}
.vibe-cursor.hover {
  width: 30px; height: 30px;
  background: rgba(0,222,255,0.18);
  border: 1px solid rgba(0,222,255,0.85);
}
.vibe-cursor.click {
  width: 38px; height: 38px;
  background: rgba(0,222,255,0.30);
}
@media (max-width: 768px) {
  .vibe-cursor { display: none; }
}

/* ── Ambient background blobs (static, GPU-light) ─────── */
.vibe-bg {
  position: fixed;
  inset: 0;
  z-index: 0;
  pointer-events: none;
  overflow: hidden;
}
.vibe-blob {
  position: absolute;
  border-radius: 50%;
  filter: blur(60px);
  background: #00DEFF;
  opacity: 0.05;
}
.vibe-blob.b1 { width: 500px; height: 500px; top: -180px; left: -120px; }
.vibe-blob.b2 { width: 450px; height: 450px; bottom: -160px; right: -100px; opacity: 0.04; }

/* ── Circular cyan Exit button (marker-based targeting) ── */
.element-container:has(.vibe-exit-marker) {
  display: none !important;  /* hide the marker container itself */
}
.element-container:has(.vibe-exit-marker) + .element-container .stButton > button,
.element-container:has(.vibe-exit-marker) + div .stButton > button {
  border-radius: 50% !important;
  width: 44px !important;
  height: 44px !important;
  min-width: 44px !important;
  padding: 0 !important;
  font-size: 18px !important;
  font-weight: 700 !important;
  background: rgba(0,222,255,0.08) !important;
  border: 1.5px solid #00DEFF !important;
  color: #00DEFF !important;
  display: flex !important;
  align-items: center !important;
  justify-content: center !important;
  box-shadow: 0 0 14px rgba(0,222,255,0.30) !important;
  transition: background 0.2s, box-shadow 0.25s, transform 0.15s !important;
}
.element-container:has(.vibe-exit-marker) + .element-container .stButton > button:hover,
.element-container:has(.vibe-exit-marker) + div .stButton > button:hover {
  background: rgba(0,222,255,0.18) !important;
  box-shadow: 0 0 24px rgba(0,222,255,0.6) !important;
  transform: scale(1.06) !important;
  border-color: #00DEFF !important;
}
.element-container:has(.vibe-exit-marker) + .element-container .stButton > button *,
.element-container:has(.vibe-exit-marker) + div .stButton > button * {
  color: #00DEFF !important;
}

/* ── Material Symbols icons (file uploader, chat avatar, etc.) ── */
span[data-testid="stIconMaterial"],
span.material-symbols-rounded,
span.material-symbols-outlined,
[class*="material-symbols"] {
  font-family: 'Material Symbols Rounded' !important;
  font-weight: normal !important;
  font-style: normal !important;
  line-height: 1 !important;
  letter-spacing: normal !important;
  text-transform: none !important;
  display: inline-block;
  white-space: nowrap;
  word-wrap: normal;
  direction: ltr;
  -webkit-font-feature-settings: 'liga';
  -webkit-font-smoothing: antialiased;
  font-feature-settings: 'liga';
}

/* ── Hide Streamlit chrome ────────────────────────────── */
#MainMenu       { visibility: hidden; }
footer          { visibility: hidden; }
header          { visibility: hidden; }
[data-testid="stDecoration"] { display: none; }
[data-testid="stHeader"]     { display: none; }
[data-testid="stToolbar"]    { display: none; }
"""

_CURSOR_JS = """
<div class="vibe-cursor" id="vibe-cursor"></div>
<script>
(function(){
  const c = document.getElementById('vibe-cursor');
  if (!c || window.matchMedia('(max-width:768px)').matches) return;
  let mx = innerWidth/2, my = innerHeight/2, cx = mx, cy = my;
  const HOVER = 'a, button, [role="button"], input, textarea, select, label, [data-baseweb="tab"], [data-testid="stRadio"] label';

  document.addEventListener('mousemove', e => {
    mx = e.clientX; my = e.clientY;
    const t = e.target;
    c.classList.remove('hover');
    if (t && t.closest && t.closest(HOVER)) c.classList.add('hover');
  }, {passive: true});
  document.addEventListener('mousedown', () => c.classList.add('click'));
  document.addEventListener('mouseup',   () => c.classList.remove('click'));

  function tick(){
    cx += (mx - cx) * 0.32;
    cy += (my - cy) * 0.32;
    c.style.transform = 'translate(' + cx + 'px, ' + cy + 'px) translate(-50%, -50%)';
    requestAnimationFrame(tick);
  }
  tick();
})();
</script>
"""


_BG_HTML = """\
<div class="vibe-bg">
  <div class="vibe-blob b1"></div>
  <div class="vibe-blob b2"></div>
</div>
"""


def inject_theme() -> None:
    st.markdown(_FONTS_HTML, unsafe_allow_html=True)
    st.markdown(f"<style>{_CSS}</style>", unsafe_allow_html=True)
    st.markdown(_BG_HTML, unsafe_allow_html=True)
