from __future__ import annotations

from langchain_core.tools import StructuredTool

from vibeops.core.gcp_context import GcpContext
from vibeops.tools.compute import (
    get_accelerator_quota,
    list_machine_types,
    list_os_images,
    list_zones_with_accelerator,
)
from vibeops.tools.resource_manager import list_existing_networks


def build_tools(ctx: GcpContext) -> list[StructuredTool]:
    """Wrap all GCP tools for potential LangGraph tool-calling use."""

    def _zones(gpu_type: str) -> object:
        """List GCP zones that have the specified GPU accelerator type available."""
        return list_zones_with_accelerator(ctx, gpu_type)

    def _machine_types(zone: str, gpu_compatible: bool = True) -> object:
        """List machine types in a GCP zone, optionally filtered to GPU-compatible ones."""
        return list_machine_types(ctx, zone, gpu_compatible)

    def _os_images(family_filter: str = "") -> object:
        """List available OS disk images, optionally filtered by image family prefix."""
        return list_os_images(ctx, family_filter or None)

    def _quota(region: str, gpu_type: str) -> object:
        """Get accelerator quota for a region and GPU type."""
        return get_accelerator_quota(ctx, region, gpu_type)

    def _networks() -> object:
        """List VPC networks in the GCP project."""
        return list_existing_networks(ctx)

    return [
        StructuredTool.from_function(_zones, name="list_zones_with_accelerator"),
        StructuredTool.from_function(_machine_types, name="list_machine_types"),
        StructuredTool.from_function(_os_images, name="list_os_images"),
        StructuredTool.from_function(_quota, name="get_accelerator_quota"),
        StructuredTool.from_function(_networks, name="list_existing_networks"),
    ]
