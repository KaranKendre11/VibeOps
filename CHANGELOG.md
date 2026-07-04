# Changelog

All notable changes to VibeOps are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **"The problem" section on the marketing landing page (2026-07-03).** A new
  section contrasts the nine-step manual grind of standing up a GPU VM (pick a
  machine type, hunt for a zone with GPU quota, hand-write the Terraform, open
  firewall ports, remember to tear it all down…) against a single plain-English
  sentence, shown in a terminal-style prompt card — so the page actually explains
  the pain VibeOps removes. (`frontend/src/landing/LandingScreen.tsx`)
- **Full six-stage pipeline on the landing page (2026-07-03).** The thin
  three-step "How it works" was replaced by the real pipeline —
  Understand → Locate → Generate → Price → Deploy → Live — each stage with a
  proper description and the worked example *"Jupyter notebook on a T4 with port
  8888 open to the web."* This pipeline and the site footer were merged into one
  closing section: on desktop the llama video pins on the left while the pipeline
  and brand/footer scroll on the right (retiring the old standalone step section
  and the separate footer). (`frontend/src/landing/LandingScreen.tsx`)
- **Richer README with screenshots (2026-07-03).** `README.md` was rewritten to
  tell the full story — the problem, the six-stage pipeline, a "See it in action"
  demo walkthrough, and capabilities — with 8 embedded screenshots of the landing
  page, setup, review, deployment, and VM inventory. New assets `setup.png`,
  `deployment.png`, `inventory.png`, `landing-problem.png`, `landing-finale.png`,
  and `landing-capabilities.png` were added, and `landing.png` and `review.png`
  were refreshed. (`README.md`, `screenshots/`)
- **Optional remote Terraform state on a GCS backend (issue #3, 2026-07-03).** Set
  `VIBEOPS_TF_STATE_BUCKET` to a GCS bucket and each deployment now writes a
  `backend "gcs"` block and runs `terraform init -backend-config=…` with a unique
  per-deployment prefix (`<VIBEOPS_TF_STATE_PREFIX>/<project>/<uuid>`), so state lives
  durably in the cloud instead of an ephemeral temp dir — a lost process/session no
  longer orphans real VMs or breaks `destroy` (which keeps running against the
  persisted state). The prefix is recorded on `GraphState.terraform_state_prefix`.
  When the bucket is unset, behavior is unchanged (local temp-dir state) and a warning
  is logged that state is ephemeral. (`src/vibeops/terraform/backend.py`,
  `src/vibeops/config.py`, `src/vibeops/terraform/runner.py`,
  `src/vibeops/agents/iac.py`, `src/vibeops/models/state.py`)

### Changed

- **Landing capabilities grid expanded from 4 vague cards to 6 specific ones
  (2026-07-03).** Intent extraction, GPU-aware zones, Editable Terraform, Real
  cost estimates, Firewall/startup & containers, and Inventory & recovery — with
  the hero subhead copy tightened alongside.
  (`frontend/src/landing/LandingScreen.tsx`)

### Fixed

- **Monthly cost cap is now enforced at the deploy gate (2026-07-03).** Previously
  the cost cap was computed and shown in the UI but never enforced on the server, so
  an over-budget plan could still be deployed — including by a direct API call that
  bypassed the review screen. `POST /api/deploy/start` now rejects an over-cap plan
  with `409 Conflict` unless the caller explicitly opts in with
  `{"override_cost_cap": true}`, and the graph's `approval_router` fails closed as
  defence in depth (an over-cap plan is cancelled unless `cost_cap_override` is
  literal `True`), so the resume endpoint can't be used to sidestep the check. The
  session's monthly cap is now the single source of truth: the IaC agent reads it
  from the graph context instead of an unrelated hardcoded `$500` default, so the
  "cap exceeded" flag matches the cap you actually set at setup.
  (`src/vibeops/api/routes_deploy.py`, `src/vibeops/graph/orchestrator.py`,
  `src/vibeops/agents/iac.py`, `src/vibeops/api/graph_runtime.py`)

- **White vertical bar on the right whenever a page scrolled, on Chromium
  (2026-07-03).** The custom `::-webkit-scrollbar` styled only the thumb, so
  Chromium fell back to painting the track white, and the `<html>` element had no
  background so the scrollbar gutter showed the browser's white canvas (it
  appeared to come and go as the window aspect ratio changed). `html`/`#root` are
  now painted with the app background, and the scrollbar track/corner are
  transparent. (`frontend/src/styles/globals.css`)

### Security

- **Hardened the Terraform resource allowlist against edit-time and deploy-time
  bypasses (2026-07-03).** The review-screen allowlist only ran on `main.tf`, so a
  disallowed resource (e.g. an IAM binding or storage bucket) added via `outputs.tf`
  or any other file slipped through; the edit filename was also unsanitized, which
  allowed writing outside the working directory (path traversal). Now every `*.tf`
  file in the work dir is checked on each edit, the edit filename is restricted to a
  strict whitelist (`main.tf`, `variables.tf`, `outputs.tf` — rejecting path
  separators, `..`, and non-`.tf` names before anything is written to disk), and the
  allowlist is re-validated immediately before `terraform apply` so a tampered or
  unparseable config fails closed instead of deploying. (`src/vibeops/core/policy.py`,
  `src/vibeops/services/review.py`, `src/vibeops/agents/deployment.py`)

## [2.0.1] - 2026-07-03

### Fixed

- **Session cookie now works inside the HuggingFace Spaces iframe.** The app is
  embedded in a cross-site iframe on huggingface.co, where browsers refuse to send a
  `SameSite=Lax` cookie — so every API call after `POST /api/session` arrived without
  the session cookie and failed with "No active session; POST /api/session first."
  The session cookie is now set `SameSite=None; Secure` when the app is served over
  HTTPS (detected via the `X-Forwarded-Proto` header / the HF `SPACE_ID` env var), and
  still falls back to `SameSite=Lax` for local HTTP dev (where `Secure` cookies aren't
  stored). (`src/vibeops/api/main.py`)

## [2.0.0] - 2026-07-03

### Added

- **Real VibeOps brand logo wired in everywhere (2026-07-03).** The abstract
  placeholder mark was replaced with the actual VibeOps app icon — a neon-goggled
  magenta alpaca. A new reusable `<BrandIcon>` renders it as a rounded "squircle"
  chip at any size, and it now appears as the browser favicon, apple-touch-icon,
  and Open Graph / Twitter card image, in the landing-page navbar and footer, in
  the app header pill next to the wordmark, and on the boot splash. The old
  abstract `VibeMark` SVG was removed. (new `frontend/public/icon.png`, new
  `frontend/src/components/BrandIcon.tsx`, removed `frontend/src/landing/VibeMark.tsx`;
  `frontend/index.html`, `frontend/src/landing/LandingScreen.tsx`,
  `frontend/src/components/Chrome.tsx`, `frontend/src/App.tsx`)
- **Cinematic marketing landing page that gates the app (2026-07-02).** On load,
  visitors now see a full-screen, scroll-driven landing page before the product;
  clicking any "Try it" button (nav, hero, or bottom CTA) enters the existing setup →
  chat → deploy flow. The page is a black/white, Space Mono composition with an "Anton
  SC" background watermark, five full-viewport CloudFront background videos, Framer
  Motion animations, and custom scramble text effects. Sections in order: a hero with a
  mouse-scrubbed video and animated "Ship / Any Cloud" + "One / Prompt" headings and the
  VibeOps tagline; a cinematic 3D-rotated scroll passage; metrics (~60s / 100% / $0); a
  capabilities grid (Natural Language, Generated Terraform, Cost Preview, Safe Teardown);
  a three-step "Describe / Plan / Apply" how-it-works; and a footer with video and the
  VibeOps mark. Session boot runs in the background while the landing shows, so the app
  is ready by the time the user clicks in. (`frontend/src/landing/LandingScreen.tsx`,
  `frontend/src/landing/scramble.tsx`, `frontend/src/landing/VibeMark.tsx`,
  `frontend/src/App.tsx`, `frontend/src/store/useStore.ts` — `entered` gate +
  `enterApp()`, `frontend/index.html` — Space Mono + Anton SC fonts)
- **Animated backdrop, glass surfaces & interactive progress rail (2026-07-02).** A
  full-bleed **"Plexus" network background** rendered on a canvas
  (`<PlexusBackground>`): drifting cyan/violet nodes joined by distance-faded links
  with pseudo-depth and cursor reactivity, under a legibility scrim; renders a single
  static frame under prefers-reduced-motion. Refined `.liquid-glass` /
  `.liquid-glass-strong` frosted surfaces with a masked gradient-edge "rim" (plus a
  `glass` Button variant). The pipeline stepper (Describe → Plan → Review → Deploy →
  Live) became an **interactive, guarded tab bar**: reached stages are clickable,
  unreached/locked stages are disabled, and risky backward moves prompt a confirmation
  (`<ConfirmNav>`) before switching — navigation is UI-only and never mutates the
  LangGraph state. Subtle pointer **parallax** on the hero (`useParallax`),
  reduced-motion aware. (`frontend/src/components/PlexusBackground.tsx`,
  `AmbientBlobs.tsx`, `JourneyLine.tsx`, `ConfirmNav.tsx`, `Button.tsx`,
  `frontend/src/lib/useParallax.ts`, `frontend/src/store/useStore.ts`,
  `frontend/src/styles/globals.css`, `frontend/tailwind.config.js`)
- **Credential-free demo mode.** The setup screen now has a
  "▶ Try the live demo — no credentials needed" button that lets anyone run the
  full flow — requirement chat → architecture → generated Terraform → cost
  estimate → review — on a sample project without an OpenAI key or GCP
  service-account JSON. It renders real Terraform from the spec and shows a
  representative offline cost, but deployment is hard-blocked: the Approve &
  Deploy button is disabled and the deployment agent early-returns as
  defense-in-depth. A demo banner is shown throughout.
  (`src/vibeops/ui/setup.py`, `src/vibeops/ui/chat.py`, `src/vibeops/ui/review.py`,
  `src/vibeops/agents/iac.py`, `src/vibeops/agents/deployment.py`,
  `tests/unit/test_demo_mode.py`)
- **Privacy-safe funnel analytics.** New `src/vibeops/core/analytics.py` provides
  `track()`/`track_once()`, which emit one JSON line per funnel event (prefixed
  `VIBEOPS_EVENT`) through the existing credential-redacting logger and optionally
  POST to a hosted sink when `VIBEOPS_ANALYTICS_URL` is set. Events carry only an
  anonymous per-session id and non-sensitive props — never credentials, project
  ids, or emails. Funnel events are hooked at UI call sites: `demo_started`,
  `setup_completed`, `requirement_submitted`, `architecture_chosen`,
  `review_reached`, `cost_estimated`, `deploy_approved`, `apply_succeeded`,
  `apply_failed`, `destroyed`, and `cost_saved_by_teardown`.
  (`src/vibeops/core/analytics.py`, `src/vibeops/ui/*.py`,
  `tests/unit/test_analytics.py`)
- **Continuous integration.** New GitHub Actions workflow runs `ruff check .`,
  `mypy src`, and `pytest -m "not live"` on every push and pull request
  (Python 3.11). (`.github/workflows/ci.yml`)

### Changed

- **Scramble text is now the app-wide motion motif (2026-07-03).** The landing page's
  character-shuffle "scramble" effect replaced the app's two other text motifs (the
  masked wipe-up entrance and the scroll-up hover roll). Screen headings, step titles,
  phase labels, eyebrow micro-labels, and the corner wordmark now scramble in on
  entrance; every Button variant (not just the primary one) scrambles its label on
  hover, and the "VM Inventory" chrome button and the Review screen's Terraform file
  tabs scramble on hover too. Body copy, streaming chat tokens, Terraform code, and
  live deployment log lines are deliberately left readable (logs keep the wipe-up
  reveal), and prefers-reduced-motion renders plain text with no scrambling. The
  scramble components moved to a shared `frontend/src/components/scramble.tsx` with new
  `ScrambleReveal` (entrance) and `ScrambleHover` (hover) wrappers; the old
  `frontend/src/landing/scramble.tsx` and `frontend/src/components/RollText.tsx` were
  removed. (`frontend/src/components/scramble.tsx`, `Button.tsx`, `Chrome.tsx`,
  `Wordmark.tsx`, `frontend/src/landing/LandingScreen.tsx`,
  `frontend/src/screens/SetupScreen.tsx`, `ChatScreen.tsx`, `ArchitectureScreen.tsx`,
  `ReviewScreen.tsx`, `DeploymentScreen.tsx`, `TerminalScreen.tsx`)
- **Magenta accent + cosmic-crimson restyle (2026-07-03).** Shifted the app's accent from
  cyan (`#00DEFF`) to a magenta / crimson-pink (`#ff4d8d`) to match the marketing landing
  page's hot-pink nebula hue. The new accent flows everywhere through the `accent` Tailwind
  token and `shadow-glow` utilities plus hardcoded literals: buttons, links, focus rings,
  selection highlight, scrollbars, and the progress rail's charged line, glow, and pulsing
  "you are here" ring. Surfaces were warmed from navy-black toward crimson-black
  (`--surface`/`--surface-2`, the opaque `.surface-solid` panel, `--line`, and muted text
  greys), a layered deep-crimson **nebula wash** was added behind the app-wide Plexus network
  background, and the Plexus nodes were recolored to a magenta pair (light rose majority
  + deeper accent pink). (`frontend/tailwind.config.js`,
  `frontend/src/styles/globals.css`, `frontend/src/components/JourneyLine.tsx`,
  `frontend/src/components/PlexusBackground.tsx`, `frontend/src/components/AmbientBlobs.tsx`)
- **Cosmic palette + restyle of every screen (2026-07-02).** Evolved the jet-black +
  cyan (`#00DEFF`) look toward deep navy-black surfaces and cooler greys, with a new
  violet "nebula" accent used only in the animated background, and re-skinned every
  screen (product logic unchanged) with liquid-glass panels and the interactive rail;
  the persistent chrome and wordmark float as liquid-glass pills. Typography stays the
  original Space Grotesk (display/UI) + JetBrains Mono (code/logs/data), and copy is
  plain, product-focused VibeOps wording — no themed labels. (An interim pass that
  introduced an Instrument Serif/Barlow "mission control" treatment and a looping
  background video was reverted in favor of this.) This supersedes the earlier
  milez.jp-inspired cyan-on-jet-black pass noted below. (`frontend/src/screens/*.tsx`,
  `frontend/src/components/Chrome.tsx`, `Wordmark.tsx`, `InventoryDialog.tsx`,
  `frontend/index.html`, `frontend/tailwind.config.js`, `frontend/src/styles/globals.css`)
- **Frontend re-platformed to React + FastAPI (2026-07-02).** The Streamlit UI
  (`app.py` + `src/vibeops/ui/`, now removed) was replaced by a React 18 + TypeScript
  SPA (Vite, Tailwind, Framer Motion, Radix) served by a FastAPI backend that wraps
  the existing LangGraph orchestrator on one port. Chat tokens and live Terraform logs
  stream over SSE; per-session state (creds, clients, graph) lives in an in-memory
  cookie-keyed store — never persisted. UI-embedded logic moved into `src/vibeops/services/`.
  (`frontend/**`, `src/vibeops/api/**`, `src/vibeops/services/**`, `Dockerfile`)
- **milez.jp-inspired cyan-on-jet-black redesign.** Pure black + white with a single
  restrained cyan (`#00DEFF`) glow in the negative space; a "journey-line" pipeline
  stepper (Describe → Plan → Review → Deploy) as the signature element; corner-anchored
  chrome; frosted-glass panels for chrome while dense content (Terraform, logs, spec,
  inventory) stays on near-opaque surfaces for legibility; masked wipe-up reveals and
  hover text-rolls on the signature easing `cubic-bezier(0.23,1,0.32,1)`; reduced-motion
  respected. (`frontend/**`)
- **Demo mode is a full deterministic end-to-end walkthrough.** Demo shows a fixed
  pre-written example (identical for every visitor) instead of free chat, and Approve &
  Deploy / Retry / Teardown are simulated — streamed canned Terraform logs plus a fake
  instance — so the deployed VM appears in the VM inventory, all without credentials.
  (`src/vibeops/agents/deployment.py`, `src/vibeops/api/**`, `frontend/src/screens/**`)
- **Streamlit fully removed** as a dependency (analytics/secrets decoupled from
  `st.session_state`; `secrets.py` deleted). (`pyproject.toml`, `src/vibeops/core/analytics.py`)
- **Repositioned product copy** toward "an AI agent that safely operates your
  cloud — describe the change, review the plan, approve, done," with GPU VMs on
  GCP framed as the beachhead. Updated the README title and short description, the
  landing-page hero and marquee, and the setup tagline. No functional change.
  (`README.md`, `src/vibeops/ui/chat.py`, `src/vibeops/ui/setup.py`)
- Ignore browser E2E test screenshots in git. (`.gitignore` — `test-artifacts/`)
- Registered an `expensive` pytest marker (a subset of `live`, for tests that
  incur real cloud cost) and scoped the `E501` line-length rule out of the inline
  HTML/CSS UI layer and the prompt/regex string-constant modules via
  per-file-ignores. (`pyproject.toml`)

### Fixed

- **Brand logo, landing hamburger & a new exit-to-home button (2026-07-03).** The
  brand icon was cleaned up — auto-cropped to a rounded, transparent-background tile
  (removing the grey backdrop that showed behind the alpaca) and shrunk from ~2.3 MB
  to ~0.45 MB (512×512) — and `<BrandIcon>` now renders it with `object-contain` and
  no extra CSS rounding since the PNG is pre-rounded. It was also enlarged everywhere:
  landing navbar pill (38px), landing footer (44px), app header pill (32px), and the
  boot splash (96px, now with a shape-following `drop-shadow` glow instead of a square
  box-shadow). The landing hamburger menu was fixed: its middle bar was mis-centered
  (Framer's transform overrode the Tailwind `-translate-y-1/2`), so `SquashHamburger`
  was rewritten to place the three bars at explicit `top` values — evenly spaced when
  closed and meeting cleanly at center to form the "X" when open — and the nav pills
  were standardized to a uniform 48px height so the logo pill, menu, and "Try it"
  button align. Added an X (close) button to the app header (top-right) that returns
  you to the marketing landing page via a new `exitToLanding()` store action (clears
  the `entered` gate; session state is kept). (`frontend/public/icon.png`,
  `frontend/src/components/BrandIcon.tsx`, `frontend/src/components/Chrome.tsx`,
  `frontend/src/landing/LandingScreen.tsx`, `frontend/src/App.tsx`,
  `frontend/src/store/useStore.ts`)
- **Progress-rail active marker now hugs the current node (2026-07-02).** Replaced the
  small filled triangle (▲) that floated in the empty space above the active stage dot —
  which read as detached and awkward — with a pulsing accent-cyan "you are here" ring that
  wraps the active node itself, so the marker clearly belongs to the circle. It still
  slides smoothly between stages (shared `layoutId` retained) and the soft glow behind the
  node is unchanged. (`frontend/src/components/JourneyLine.tsx`)
- Cleared pre-existing lint debt (unused imports, import ordering, several long
  lines) so `ruff check .` is clean, and fixed 6 pre-existing `mypy --strict`
  errors: a GCP untyped-call annotation, two loose `object`→typed conversions in
  the requirement parser, and a Streamlit `write_stream` return-type narrowing.
  (`src/vibeops/agents/requirement.py`, `src/vibeops/graph/orchestrator.py`,
  `src/vibeops/models/deployment.py`, `src/vibeops/terraform/runner.py`,
  `src/vibeops/tools/compute.py`, `src/vibeops/ui/chat.py`, and mechanical
  unused-import / import-sort cleanups across `tests/`)
