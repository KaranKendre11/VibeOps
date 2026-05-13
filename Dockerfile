# syntax=docker/dockerfile:1.6
# ---------------------------------------------------------------------------
# VibeOps — Hugging Face Spaces (Docker SDK) image
#
# Why Docker SDK?  We need the Terraform CLI on the container, which Streamlit
# Community Cloud cannot install.  HF Spaces Docker SDK gives us full control.
#
# HF Spaces rules we follow:
#   * App must listen on $PORT (HF sets it; default 7860 — see app_port in README)
#   * Container must run as a non-root user with UID 1000
#   * $HOME must be writable (Streamlit caches go there)
# ---------------------------------------------------------------------------

FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    TERRAFORM_VERSION=1.9.5

# Terraform CLI + minimal build deps
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

# Dependency layer — copy only what's needed for `pip install`
COPY --chown=user:user pyproject.toml ./

# Install Python deps. We don't use uv.lock here because pip is the safest
# install path inside the HF Spaces sandbox.
RUN pip install --user --no-cache-dir \
        "streamlit>=1.40" \
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
COPY --chown=user:user app.py ./
COPY --chown=user:user .streamlit ./.streamlit

# Make the source tree importable
ENV PYTHONPATH="/home/user/app/src:${PYTHONPATH}"

# HF Spaces default port; overridable via $PORT
ENV PORT=7860
EXPOSE 7860

# Streamlit-on-HF tuning:
#   --server.headless=true    — no browser launch attempt
#   --server.enableCORS=false — HF proxies the app
#   --server.enableXsrfProtection=false — same reason
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD curl -fsS "http://localhost:${PORT}/_stcore/health" || exit 1

CMD ["sh", "-c", "streamlit run app.py --server.port=${PORT} --server.address=0.0.0.0 --server.headless=true --server.enableCORS=false --server.enableXsrfProtection=false"]
