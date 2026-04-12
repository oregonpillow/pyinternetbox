"""Tests for the top-level InternetBoxClient facade."""

from __future__ import annotations

from unittest.mock import MagicMock, patch


class TestInternetBoxClient:
    @patch("internetbox_client.client.SessionManager")
    def test_creates_session_and_resources(self, mock_sm_cls: MagicMock) -> None:
        mock_sm = MagicMock()
        mock_sm_cls.return_value = mock_sm

        from internetbox_client import InternetBoxClient

        client = InternetBoxClient(password="test")

        mock_sm_cls.assert_called_once_with(password="test")
        # Spot-check a few resource attributes
        assert hasattr(client, "devices")
        assert hasattr(client, "wifi")
        assert hasattr(client, "vpn")
        assert hasattr(client, "speedtest")

    @patch("internetbox_client.client.SessionManager")
    def test_context_manager(self, mock_sm_cls: MagicMock) -> None:
        mock_sm = MagicMock()
        mock_sm_cls.return_value = mock_sm

        from internetbox_client import InternetBoxClient

        with InternetBoxClient(password="test") as client:
            assert client is not None
        mock_sm.close.assert_called_once()

    @patch("internetbox_client.client.SessionManager")
    def test_close(self, mock_sm_cls: MagicMock) -> None:
        mock_sm = MagicMock()
        mock_sm_cls.return_value = mock_sm

        from internetbox_client import InternetBoxClient

        client = InternetBoxClient(password="test")
        client.close()
        mock_sm.close.assert_called_once()
