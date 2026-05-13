from __future__ import annotations


class VibeOpsError(Exception):
    """Base exception for all VibeOps domain errors."""


class AuthError(VibeOpsError):
    """Raised when credential validation fails."""


class ValidationError(VibeOpsError):
    """Raised when a Pydantic model or input fails validation."""


class GCPToolError(VibeOpsError):
    """Raised when a GCP API call fails inside a LangGraph tool."""


class LLMError(VibeOpsError):
    """Raised when an LLM call fails or produces an unexpected response."""


class PolicyError(VibeOpsError):
    """Raised when a generated resource type is not on the allowlist."""


class TerraformError(VibeOpsError):
    """Raised when terraform init / validate / plan / apply returns a non-zero exit code."""
