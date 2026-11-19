"""Tests for SessionManager and APIClient."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import requests

from internetbox_client.utils.APIClient import _NO_AUTH_HEADERS, APIClient, SessionManager, normalize_hostname

# ── Hostname normalisation / SSL verification ─────────────────────────


class TestNormalizeHostname:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("192.168.0.254", "https://192.168.0.254"),
            ("192.168.0.254:8443", "https://192.168.0.254:8443"),
            ("http://192.168.0.254", "https://192.168.0.254"),
            ("http://192.168.0.254:80", "https://192.168.0.254"),
            ("http://192.168.0.254:8080", "https://192.168.0.254:8080"),
            ("HTTPS://Box.Local/", "https://box.local"),
            ("https://box.local/some/path?x=1", "https://box.local"),
            ("  internetbox.swisscom.ch  ", "https://internetbox.swisscom.ch"),
            ("[fe80::1]", "https://[fe80::1]"),
        ],
    )
    def test_normalize(self, raw: str, expected: str) -> None:
        assert normalize_hostname(raw) == expected

    @pytest.mark.parametrize("raw", ["ftp://box.local", "https://", ""])
    def test_invalid(self, raw: str) -> None:
        with pytest.raises(ValueError):
            normalize_hostname(raw)


class TestSslVerify:
    @pytest.fixture(autouse=True)
    def _no_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("IB_SSL_VERIFY", raising=False)

    def test_hostname_verifies(self) -> None:
        assert SessionManager(hostname="https://internetbox.swisscom.ch").session.verify is True

    @pytest.mark.parametrize("host", ["192.168.0.254", "http://192.168.0.254:80", "[fe80::1]"])
    def test_ip_auto_insecure(self, host: str) -> None:
        assert SessionManager(hostname=host).session.verify is False

    def test_explicit_overrides_ip(self) -> None:
        assert SessionManager(hostname="192.168.0.254", ssl_verify=True).session.verify is True

    def test_explicit_insecure(self) -> None:
        assert SessionManager(hostname="internetbox.swisscom.ch", ssl_verify=False).session.verify is False

    def test_env_overrides_ip(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("IB_SSL_VERIFY", "true")
        assert SessionManager(hostname="192.168.0.254").session.verify is True


# ── SessionManager ────────────────────────────────────────────────────


class TestSessionManagerInit:
    """Test SessionManager construction (login flow)."""

    def _make_login_response(self, context_id: str = "ctx-123") -> MagicMock:
        resp = MagicMock(spec=requests.Response)
        resp.json.return_value = {"data": {"contextID": context_id}}
        resp.raise_for_status = MagicMock()
        return resp

    @patch("internetbox_client.utils.APIClient.requests.Session")
    def test_successful_login(self, mock_session_cls: MagicMock) -> None:
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_session.post.return_value = self._make_login_response("ctx-abc")

        sm = SessionManager(hostname="https://box.local", password="secret", username="admin")
        sm._ensure_authenticated()

        assert sm.context_id == "ctx-abc"
        assert sm.base_url == "https://box.local"
        mock_session.post.assert_called_once()
        call_kwargs = mock_session.post.call_args
        assert call_kwargs.kwargs["url"] == "https://box.local/ws"
        login_data = call_kwargs.kwargs["json"]
        assert login_data["parameters"]["password"] == "secret"

    @patch("internetbox_client.utils.APIClient.requests.Session")
    def test_login_failure_raises(self, mock_session_cls: MagicMock) -> None:
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_session.post.return_value.raise_for_status.side_effect = requests.exceptions.HTTPError("401")

        sm = SessionManager(password="wrong")
        with pytest.raises(requests.exceptions.HTTPError):
            sm._ensure_authenticated()


class TestSessionManagerClose:
    """Test SessionManager.close() logout flow."""

    @patch("internetbox_client.utils.APIClient.requests.Session")
    def _build_sm(self, mock_session_cls: MagicMock) -> tuple[SessionManager, MagicMock]:
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        resp = MagicMock()
        resp.json.return_value = {"data": {"contextID": "ctx-1"}}
        mock_session.post.return_value = resp
        sm = SessionManager(password="p")
        sm._ensure_authenticated()
        mock_session.reset_mock()
        return sm, mock_session

    def test_close_sends_logout(self) -> None:
        sm, mock_session = self._build_sm()
        sm.close()

        mock_session.post.assert_called_once()
        logout_data = mock_session.post.call_args.kwargs["json"]
        assert logout_data["method"] == "releaseContext"
        assert sm.context_id is None
        mock_session.close.assert_called_once()

    def test_close_noop_when_no_context(self) -> None:
        sm, mock_session = self._build_sm()
        sm.context_id = None
        sm.close()
        mock_session.post.assert_not_called()


class TestSessionManagerContextManager:
    @patch("internetbox_client.utils.APIClient.requests.Session")
    def test_enter_returns_self(self, mock_session_cls: MagicMock) -> None:
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        resp = MagicMock()
        resp.json.return_value = {"data": {"contextID": "ctx-1"}}
        mock_session.post.return_value = resp

        sm = SessionManager(password="p")
        assert sm.__enter__() is sm

    @patch("internetbox_client.utils.APIClient.requests.Session")
    def test_exit_calls_close(self, mock_session_cls: MagicMock) -> None:
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        resp = MagicMock()
        resp.json.return_value = {"data": {"contextID": "ctx-1"}}
        mock_session.post.return_value = resp

        sm = SessionManager(password="p")
        sm.__exit__(None, None, None)
        assert sm.context_id is None


class TestSessionManagerRequests:
    """Test get/post delegation."""

    @patch("internetbox_client.utils.APIClient.requests.Session")
    def _build_sm(self, mock_session_cls: MagicMock) -> tuple[SessionManager, MagicMock]:
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        resp = MagicMock()
        resp.json.return_value = {"data": {"contextID": "ctx-1"}}
        mock_session.post.return_value = resp
        sm = SessionManager(password="p")
        sm._ensure_authenticated()
        mock_session.reset_mock()
        return sm, mock_session

    def test_get_authenticated(self) -> None:
        sm, mock_session = self._build_sm()
        mock_session.get.return_value = MagicMock(text="ok")
        result = sm.get("/foo")
        assert result == "ok"
        call_kwargs = mock_session.get.call_args
        assert call_kwargs.kwargs["headers"] == {}

    def test_get_unauthenticated(self) -> None:
        sm, mock_session = self._build_sm()
        mock_session.get.return_value = MagicMock(text="ok")
        sm.get("/foo", auth_required=False)
        call_kwargs = mock_session.get.call_args
        assert call_kwargs.kwargs["headers"] == _NO_AUTH_HEADERS

    def test_post_with_data(self) -> None:
        sm, mock_session = self._build_sm()
        mock_session.post.return_value = MagicMock(text='{"status":"ok"}')
        result = sm.post("/ws", data={"key": "val"})
        assert result == '{"status":"ok"}'
        call_kwargs = mock_session.post.call_args
        assert call_kwargs.kwargs["json"] == {"key": "val"}


# ── APIClient ─────────────────────────────────────────────────────────


class TestAPIClient:
    def test_delegates_to_session_manager(self, mock_session_manager: MagicMock) -> None:
        with patch.object(APIClient, "__init__", lambda self, **_: None):
            client = object.__new__(APIClient)
        client._sm = mock_session_manager
        client._owns_session = False

        client.get("/ep")
        mock_session_manager.get.assert_called_once_with("/ep", True)

        client.post("/ws", data={"a": 1})
        mock_session_manager.post.assert_called_once_with("/ws", {"a": 1}, True)

    def test_base_url_property(self, mock_session_manager: MagicMock) -> None:
        with patch.object(APIClient, "__init__", lambda self, **_: None):
            client = object.__new__(APIClient)
        client._sm = mock_session_manager
        assert client.base_url == "https://internetbox.swisscom.ch"

    def test_close_session_owned(self, mock_session_manager: MagicMock) -> None:
        with patch.object(APIClient, "__init__", lambda self, **_: None):
            client = object.__new__(APIClient)
        client._sm = mock_session_manager
        client._owns_session = True
        client.close_session()
        mock_session_manager.close.assert_called_once()

    def test_close_session_not_owned(self, mock_session_manager: MagicMock) -> None:
        with patch.object(APIClient, "__init__", lambda self, **_: None):
            client = object.__new__(APIClient)
        client._sm = mock_session_manager
        client._owns_session = False
        client.close_session()
        mock_session_manager.close.assert_not_called()
