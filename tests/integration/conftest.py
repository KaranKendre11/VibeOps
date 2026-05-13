from __future__ import annotations

import os

import pytest


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    if os.getenv("VIBEOPS_LIVE_TESTS") != "1":
        skip = pytest.mark.skip(reason="set VIBEOPS_LIVE_TESTS=1 to run live tests")
        for item in items:
            if item.get_closest_marker("live"):
                item.add_marker(skip)
