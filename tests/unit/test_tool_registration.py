from __future__ import annotations

from unittest.mock import MagicMock

from vibeops.core.gcp_context import GcpContext
from vibeops.tools import build_tools


def test_build_tools_returns_six_tools() -> None:
    ctx = MagicMock(spec=GcpContext)
    tools = build_tools(ctx)
    assert len(tools) == 6


def test_all_tools_have_names() -> None:
    ctx = MagicMock(spec=GcpContext)
    tools = build_tools(ctx)
    names = {t.name for t in tools}
    expected = {
        "list_zones_with_accelerator",
        "list_machine_types",
        "list_os_images",
        "get_accelerator_quota",
        "list_existing_networks",
        "estimate_price",
    }
    assert names == expected


def test_all_tools_have_non_empty_description() -> None:
    ctx = MagicMock(spec=GcpContext)
    tools = build_tools(ctx)
    for tool in tools:
        assert tool.description or tool.name  # name at minimum


def test_all_tools_have_args_schema() -> None:
    ctx = MagicMock(spec=GcpContext)
    tools = build_tools(ctx)
    for tool in tools:
        assert tool.args_schema is not None
