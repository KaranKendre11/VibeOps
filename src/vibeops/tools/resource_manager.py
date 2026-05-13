from __future__ import annotations

from google.api_core import exceptions as gcp_exceptions
from google.cloud import compute_v1

from vibeops.core.errors import GCPToolError
from vibeops.core.gcp_context import GcpContext
from vibeops.models.results import Network, NetworksResult

_CACHE_KEY = ("list_existing_networks",)


def list_existing_networks(ctx: GcpContext) -> NetworksResult:
    cached = ctx.get_cached(_CACHE_KEY)
    if cached is not None:
        return cached  # type: ignore[return-value]
    try:
        client = compute_v1.NetworksClient(credentials=ctx.credentials)
        pager = client.list(project=ctx.project_id)
        networks = [
            Network(
                name=item.name,
                self_link=item.self_link,
                auto_create_subnetworks=bool(item.auto_create_subnetworks),
            )
            for item in pager
        ]
        result = NetworksResult(networks=networks)
        ctx.set_cached(_CACHE_KEY, result)
        return result
    except gcp_exceptions.GoogleAPICallError as exc:
        raise GCPToolError(f"list_existing_networks failed: {exc}") from exc
