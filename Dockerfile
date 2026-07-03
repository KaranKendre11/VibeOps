# syntax=docker/dockerfile:1.6
# ---------------------------------------------------------------------------
# VibeOps — Hugging Face Spaces (Docker SDK) image
#
# Multi-stage: stage 1 builds the React SPA; stage 2 is the Python runtime that
# serves the built bundle + the FastAPI API on a single port ($PORT, 7860) via
# uvicorn. Terraform CLI is installed for real deploys.
#
# HF Spaces rules we follow:
#   * App listens on $PORT (default 7860 — see app_port in README)
#   * Container runs as a non-root user with UID 1000
#   * $HOME is writable
# ---------------------------------------------------------------------------

# ---- Stage 1: build the React frontend -----------------------------------
FROM node:20-alpine AS frontend
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install
COPY frontend/ ./
RUN npm run build            # emits /build/dist

# ---- Stage 2: Python runtime ---------------------------------------------
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    TERRAFORM_VERSION=1.9.5

# Terraform CLI + minimal deps
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
        unzip \
        ca-certificates \
        git \
    && rm -rf /var/lib/apt/lists/* \
    && curl -fsSL "https://releases.hashicorp.com/terraform/${TERRAFORM_VERSION}/terraform_${TERRAFORM_VERSION}_linux_amd64.zip" -o /tmp/terraform.zip \
    && unzip /tmp/terraform.zip -d /usr/local/bin/ \
    && rm /tmp/terraform.zip \
    && chmod +x /usr/local/bin/terraform \
    && terraform -version

# Non-root user (HF Spaces requirement: UID 1000)
RUN useradd -m -u 1000 -s /bin/bash user
USER user
ENV HOME=/home/user \
    PATH="/home/user/.local/bin:${PATH}"
WORKDIR $HOME/app

# Dependency layer (kept explicit + pip-based for the HF Spaces sandbox)
COPY --chown=user:user pyproject.toml ./
RUN pip install --user --no-cache-dir \
        "fastapi>=0.139" \
        "uvicorn[standard]>=0.30" \
        "langgraph>=0.2" \
        "langchain-core>=0.3" \
        "openai>=1.50" \
        "pydantic>=2.9" \
        "pydantic-settings>=2.5" \
        "google-cloud-compute>=1.20" \
        "google-cloud-resource-manager>=1.13" \
        "google-cloud-billing>=1.13" \
        "jinja2>=3.1" \
        "tiktoken>=0.7" \
        "python-hcl2>=8.1.2"

# Application code
COPY --chown=user:user src ./src
# Built SPA from stage 1 → frontend/dist (served by FastAPI StaticFiles; the path
# matches api/main.py's `parents[3]/frontend/dist`).
COPY --chown=user:user --from=frontend /build/dist ./frontend/dist

ENV PYTHONPATH="/home/user/app/src:${PYTHONPATH}"
ENV PORT=7860
EXPOSE 7860

HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD curl -fsS "http://localhost:${PORT}/api/health" || exit 1

CMD ["sh", "-c", "uvicorn vibeops.api.main:app --host 0.0.0.0 --port ${PORT}"]
