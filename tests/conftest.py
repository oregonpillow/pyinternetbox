"""Shared test fixtures for the Internet Box client test suite."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

from internetbox_client.utils.APIClient import APIClient, SessionManager


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Skip tests that interrupt the network for everyone (e.g. Wi-Fi off) unless IB_E2E_DISRUPTIVE=1 is set."""
    if os.getenv("IB_E2E_DISRUPTIVE") == "1":
        return
    skip = pytest.mark.skip(reason="interrupts the network for others; set IB_E2E_DISRUPTIVE=1 to run")
    for item in items:
        if "disruptive" in item.keywords:
            item.add_marker(skip)


@pytest.fixture()
def mock_session_manager() -> MagicMock:
    """Return a MagicMock that stands in for a real SessionManager.

    The mock pre-configures `.get()` and `.post()` to return an empty JSON
    object string, and `.base_url` / `.session` to sensible defaults.
    """
    sm = MagicMock(spec=SessionManager)
    sm.base_url = "https://internetbox.swisscom.ch"
    sm.session = MagicMock()
    sm.get.return_value = "{}"
    sm.post.return_value = "{}"
    sm.context_id = "fake-context-id"
    return sm


@pytest.fixture()
def api_client(mock_session_manager: MagicMock) -> APIClient:
    """Return an APIClient backed by the mock SessionManager."""
    with patch.object(APIClient, "__init__", lambda self, **_: None):
        client = object.__new__(APIClient)
    client._sm = mock_session_manager
    client._owns_session = False
    return client
