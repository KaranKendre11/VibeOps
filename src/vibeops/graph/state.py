from __future__ import annotations

# Re-export so that `from vibeops.graph.state import GraphState` works
# (SYSTEM_RULES §2 advertises graph/state.py; canonical definition is in models/state.py).
from vibeops.models.state import FlowStage as FlowStage
from vibeops.models.state import GraphState as GraphState
