from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from vibeops.core.errors import GCPToolError
from vibeops.core.gcp_context import GcpContext
from vibeops.models.results import NetworksResult


def _ctx() -> GcpContext:
    ctx = MagicMock(spec=GcpContext)
    ctx.project_id = "test-project"
    ctx.credentials = MagicMock()
    ctx.get_cached.return_value = None
    ctx.set_cached.return_value = None
    return ctx


def test_returns_network_list() -> None:
    ctx = _ctx()
    mock_net = MagicMock()
    mock_net.name = "default"
    mock_net.self_link = "https://example.com/networks/default"
    mock_net.auto_create_subnetworks = True

    with patch("vibeops.tools.resource_manager.compute_v1.NetworksClient") as MockClient:
        MockClient.return_value.list.return_value = [mock_net]
        from vibeops.tools.resource_manager import list_existing_networks
        result = list_existing_networks(ctx)

    assert isinstance(result, NetworksResult)
    assert len(result.networks) == 1
    assert result.networks[0].name == "default"
    assert result.networks[0].auto_create_subnetworks is True


def test_calls_correct_project() -> None:
    ctx = _ctx()
    with patch("vibeops.tools.resource_manager.compute_v1.NetworksClient") as MockClient:
        MockClient.return_value.list.return_value = []
        from vibeops.tools.resource_manager import list_existing_networks
        list_existing_networks(ctx)

    MockClient.return_value.list.assert_called_once_with(project="test-project")


def test_raises_gcp_tool_error_on_failure() -> None:
    ctx = _ctx()
    from google.api_core import exceptions as gcp_exc

    with patch("vibeops.tools.resource_manager.compute_v1.NetworksClient") as MockClient:
        MockClient.return_value.list.side_effect = gcp_exc.PermissionDenied("denied")
        from vibeops.tools.resource_manager import list_existing_networks

        with pytest.raises(GCPToolError, match="list_existing_networks failed"):
            list_existing_networks(ctx)
