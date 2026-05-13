from __future__ import annotations

from vibeops.models.deployment import StateResource


class TerraformPlanError(Exception):
    def __init__(self, stderr: str) -> None:
        super().__init__(stderr)
        self.stderr = stderr


class TerraformApplyError(Exception):
    def __init__(
        self,
        stderr: str,
        partial_state: bool = False,
        created_resources: list[StateResource] | None = None,
    ) -> None:
        super().__init__(stderr)
        self.stderr = stderr
        self.partial_state = partial_state
        self.created_resources: list[StateResource] = created_resources or []


class TerraformDestroyError(Exception):
    def __init__(
        self,
        stderr: str,
        created_resources: list[StateResource] | None = None,
    ) -> None:
        super().__init__(stderr)
        self.stderr = stderr
        self.created_resources: list[StateResource] = created_resources or []
