# CLAUDE.md

Guidance for Claude Code when working in this repository.

## Project: VibeOps

React (Vite) + FastAPI + LangGraph app that turns natural language into a running GPU VM on GCP
via generated Terraform. Bring-your-own OpenAI key + GCP service-account JSON.

- **Entry point:** FastAPI at `src/vibeops/api/main.py`, run with `uvicorn vibeops.api.main:app` —
  it serves the built React SPA **and** the JSON/SSE API on one port (7860 in Docker / HF Spaces;
  8000 locally). The React app lives in `frontend/`. (The old Streamlit `app.py`/`ui/` were retired.)
- **Backend source:** `src/vibeops/` — `api/` (FastAPI routers + cookie session store + graph
  runtime), `services/` (UI-agnostic logic: review edits, conversation), `agents/`, `core/`,
  `cost/`, `graph/` (LangGraph orchestrator), `models/` (Pydantic state), `terraform/`
  (Jinja2 + runner), `tools/` (GCP wrappers).
- **Frontend:** `frontend/` — React 18 + TS + Tailwind + Framer Motion (Vite). Screens in flow
  order: `setup` → `chat` (requirement, SSE tokens) → `architecture` → `review` → `deployment`
  (live-log SSE) → vm-inventory. The active screen is chosen from the API's `stage` field.
- **State:** the LangGraph `GraphState` is the source of truth. Per-browser-session server state
  (credentials, `LLMClient`/`GcpContext`, the compiled graph) lives in the in-memory
  `api/session.py` store keyed by an httpOnly cookie — never persisted (multi-tenant safe). The
  graph pauses at `interrupt_before` points; the API drives resume.

## Common commands

This machine: `uv` is **not** on PATH — call it as `python -m uv ...`.

```bash
# Backend (serves the built SPA + API on one port):
python -m uv run uvicorn vibeops.api.main:app --port 8000
python -m pytest -m "not live" -q                        # backend unit tests (skip live-cloud)
python -m ruff check .                                   # lint
python -m ruff format .                                  # format
python -m mypy src                                       # type-check (strict)

# Frontend (run inside frontend/):
npm install && npm run build     # build SPA into frontend/dist (served by FastAPI)
npm run dev                       # Vite dev server (proxies /api → :8000)
npm run lint && npx tsc --noEmit  # frontend lint + strict type-check
```

The `live` pytest marker = tests that hit real external services; skip them in
normal runs with `-m "not live"`.

---

## Feature-completion workflow (REQUIRED)

When you finish a **feature** — any meaningful, self-contained unit of work (a new
capability, an enhancement, or a bug fix) that you have implemented and verified —
you **MUST**, before telling the user the task is done, spawn **two subagents in
parallel**: both `Agent` tool calls go in a **single message** so they run
concurrently.

1. **Changelog agent** — records what changed in `CHANGELOG.md`.
2. **Browser E2E test agent** — exercises the new feature end-to-end in a real
   browser, plus one other feature at random as a regression check.

**Skip only** for trivial non-functional edits (typos, comments, formatting,
doc-only changes). When in doubt, run them.

### Critical: subagents start with a FRESH context

The subagents do **not** see this conversation. Every prompt you give them must be
**fully self-contained**. Before spawning, gather the facts to pass in:

- A 1–3 sentence description of the feature you just completed.
- The changed files: run `git diff --stat` and `git status` and include the list.
- For the test agent: the exact UI path/steps a user takes to reach and use the feature.

Use `subagent_type: "general-purpose"` for both — they need the full tool set
(file editing for the changelog; the Playwright MCP browser tools for testing).
(Alternative: `subagent_type: "fork"` inherits this session's context automatically,
so you can pass a shorter prompt — but it's heavier. Prefer `general-purpose` with a
self-contained prompt.)

### Subagent 1 — Changelog

Instruct it to:

- Open `CHANGELOG.md` at the repo root. If it doesn't exist, create it using the
  [Keep a Changelog](https://keepachangelog.com) format with an `## [Unreleased]` section.
- Verify the actual diff itself: `git diff`, `git diff --stat`, `git status` — do
  **not** rely solely on the summary; record only what genuinely changed.
- Add an entry under `## [Unreleased]`, grouped as **Added / Changed / Fixed /
  Removed**, dated with today's date, written in user-facing terms (what changed and
  why), naming the key files touched.
- Keep it concise and human-readable. Do not invent changes. Do **not** commit —
  just write the file.

### Subagent 2 — Browser E2E test

Instruct it to:

- **Ensure the app is up:** the SPA + API are served together by FastAPI. Build the frontend
  if needed (`cd frontend && npm run build`), then check `http://localhost:8000`; if it's down,
  start it with `python -m uv run uvicorn vibeops.api.main:app --port 8000` in the background and
  wait until it responds. (For live UI hot-reload you can instead run `npm run dev` in `frontend/`.)
- Use the **Playwright MCP** browser tools: `browser_navigate`, `browser_snapshot`
  (accessibility tree — the reliable way to find React elements), `browser_click`,
  `browser_type`, `browser_wait_for`, `browser_take_screenshot`, `browser_console_messages`.
- **Test A — the new feature:** drive the exact UI path you provided. Assert the
  expected elements/behavior appear. Screenshot the result.
- **Test B — random regression check:** pick **one** other feature/screen **at
  random** and smoke-test it (renders + basic interaction works). Choose from:
  `setup/credentials`, `requirement chat`, `architecture/zone discovery`,
  `review (spec + HCL + cost)`, `deployment`, `VM inventory`, `theme/landing`.
  Screenshot it.
- **Credential constraint:** everything past the **setup** screen needs a real
  OpenAI key + GCP service-account JSON. If credentials aren't available, test up to
  the credential gate (rendering, input validation, navigation, form behavior,
  console errors) and **report what couldn't be exercised as a limitation — not a
  failure.**
- Capture browser console errors. Save screenshots under `test-artifacts/`.
- Return a clear **PASS / FAIL per check** with evidence (screenshot paths, console errors).

### After both subagents return

- Summarize both results to the user (changelog entry written + test outcomes).
- If the test agent found a **regression** or the new feature is broken, **fix it
  before considering the task done**, then re-run the test agent.
- Treat the changelog update as part of the feature, not an afterthought.
