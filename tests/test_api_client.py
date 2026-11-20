"""Tests for SessionManager and APIClient."""

from __future__ import annotations

import json
import threading
import time
from unittest.mock import MagicMock, patch

import pytest
import requests

from internetbox_client.utils.APIClient import (
    DEFAULT_TIMEOUT,
    TRANSFER_TIMEOUT,
    _NO_AUTH_HEADERS,
    APIClient,
    SessionManager,
    normalize_hostname,
)

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

    def test_requests_use_timeout(self) -> None:
        sm, mock_session = self._build_sm()
        sm.get("/foo")
        sm.post("/bar")
        assert mock_session.get.call_args.kwargs["timeout"] == DEFAULT_TIMEOUT
        assert mock_session.post.call_args.kwargs["timeout"] == DEFAULT_TIMEOUT

    @patch("internetbox_client.utils.APIClient.requests.Session")
    def test_login_uses_custom_timeout(self, mock_session_cls: MagicMock) -> None:
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_session.post.return_value.json.return_value = {"data": {"contextID": "ctx-1"}}
        sm = SessionManager(password="p", timeout=2)
        sm._ensure_authenticated()
        assert mock_session.post.call_args.kwargs["timeout"] == 2


class TestSessionManagerFileTransfer:
    """download() and upload() send the requests the web UI sends, checked on the request requests actually builds."""

    @pytest.fixture()
    def sm(self) -> SessionManager:
        sm = SessionManager(hostname="192.0.2.1", ssl_verify=False)
        sm.context_id = "ctx-1"  # logged in, with the headers a login sets
        sm.session.headers.update({"Content-Type": "application/x-sah-ws-4-call+json", "Authorization": "X-Sah ctx-1"})
        response = requests.Response()
        response.status_code, response._content, response.encoding = 200, b"QUJD\n", "ascii"
        sm.session.send = MagicMock(return_value=response)
        return sm

    def test_download_passes_the_context_in_the_url(self, sm: SessionManager) -> None:
        assert sm.download("/backup") == "QUJD\n"
        request = sm.session.send.call_args.args[0]
        assert (request.method, request.url) == ("GET", "https://192.0.2.1/backup?context=ctx-1")
        assert sm.session.send.call_args.kwargs["timeout"] == TRANSFER_TIMEOUT

    def test_upload_is_a_form_with_the_context_first(self, sm: SessionManager) -> None:
        sm.upload("/restore", "restore", "internetbox.cfg", b"QUJD\n")
        request = sm.session.send.call_args.args[0]
        assert (request.method, request.url) == ("POST", "https://192.0.2.1/restore")
        assert request.headers["Content-Type"].startswith("multipart/form-data; boundary=")
        context = request.body.index(b'Content-Disposition: form-data; name="context"\r\n\r\nctx-1\r\n')
        file = request.body.index(
            b'Content-Disposition: form-data; name="restore"; filename="internetbox.cfg"\r\n'
            b"Content-Type: application/octet-stream\r\n\r\nQUJD\n\r\n"
        )
        assert context < file
        assert sm.session.send.call_args.kwargs["timeout"] == TRANSFER_TIMEOUT

    def test_logs_in_first(self, sm: SessionManager) -> None:
        sm.context_id = None
        with patch.object(sm, "_ensure_authenticated") as login:
            sm.download("/backup")
            sm.upload("/restore", "restore", "internetbox.cfg", b"QUJD\n")
        assert login.call_count == 2

    @pytest.mark.parametrize("transfer", [lambda sm: sm.download("/backup"), lambda sm: sm.upload("/restore", "restore", "a.cfg", b"")])
    def test_http_errors_raise(self, sm: SessionManager, transfer) -> None:
        sm.session.send.return_value.status_code = 500
        with pytest.raises(requests.HTTPError):
            transfer(sm)


def _response(status: int, body: bytes = b"{}") -> requests.Response:
    response = requests.Response()
    response.status_code, response._content, response.encoding = status, body, "utf-8"
    return response


_LOGOUT = _response(200, b'{"status": 0}')
_REFUSED = _response(401, b'{"status": null, "errors": [{"error": 13, "description": "Permission denied", "info": "DNS"}]}')


def _login_response(context_id: str) -> requests.Response:
    return _response(200, f'{{"data": {{"contextID": "{context_id}"}}}}'.encode())


class TestSessionManagerLoginAgain:
    """The router answers HTTP 401 once a session has ended, e.g. after SessionTimeout without requests."""

    @pytest.fixture()
    def sm(self) -> SessionManager:
        sm = SessionManager(hostname="192.0.2.1", ssl_verify=False)
        sm.context_id = "ctx-1"  # logged in, with the headers a login sets
        sm.session.headers.update({"Content-Type": "application/x-sah-ws-4-call+json", "Authorization": "X-Sah ctx-1"})
        sm.session.send = MagicMock()
        return sm

    @staticmethod
    def _sent(sm: SessionManager) -> list[tuple[str, str]]:
        """The requests sent: their URL, and their Authorization header or, for logins and logouts, the method."""
        sent = []
        for call in sm.session.send.call_args_list:
            request = call.args[0]
            label = json.loads(request.body)["method"] if request.url.endswith("/ws") else request.headers.get("Authorization")
            sent.append((request.url, label))
        return sent

    def test_logs_in_again_and_resends(self, sm: SessionManager) -> None:
        sm.session.send.side_effect = [_REFUSED, _LOGOUT, _login_response("ctx-2"), _response(200, b'{"status": "ok"}')]
        assert sm.post("/sysbus/DNS:get", {"parameters": {}}) == '{"status": "ok"}'
        assert self._sent(sm) == [
            ("https://192.0.2.1/sysbus/DNS:get", "X-Sah ctx-1"),
            ("https://192.0.2.1/ws", "releaseContext"),
            ("https://192.0.2.1/ws", "createContext"),
            ("https://192.0.2.1/sysbus/DNS:get", "X-Sah ctx-2"),
        ]
        assert sm.context_id == "ctx-2"

    def test_get_logs_in_again(self, sm: SessionManager) -> None:
        sm.session.send.side_effect = [_REFUSED, _LOGOUT, _login_response("ctx-2"), _response(200, b"ok")]
        assert sm.get("/sysbus/NeMo/Intf/wl0/WPS") == "ok"
        assert self._sent(sm)[-1] == ("https://192.0.2.1/sysbus/NeMo/Intf/wl0/WPS", "X-Sah ctx-2")

    def test_an_endpoint_that_refuses_every_session_raises(self, sm: SessionManager) -> None:
        sm.session.send.side_effect = [_REFUSED, _LOGOUT, _login_response("ctx-2"), _REFUSED]
        with pytest.raises(requests.HTTPError, match="401"):
            sm.post("/sysbus/WebuiupgradeService:getReleaseNotes")
        assert sm.session.send.call_count == 4  # logged in again once, not more

    def test_logs_in_even_if_the_logout_fails(self, sm: SessionManager) -> None:
        sm.session.send.side_effect = [_REFUSED, requests.ConnectionError("reset"), _login_response("ctx-2"), _response(200)]
        sm.post("/sysbus/DNS:get")
        assert sm.context_id == "ctx-2"

    def test_a_failed_login_raises(self, sm: SessionManager) -> None:
        sm.session.send.side_effect = [_REFUSED, _LOGOUT, _response(401)]
        with pytest.raises(requests.HTTPError, match="401"):
            sm.post("/sysbus/DNS:get")
        assert sm.session.send.call_count == 3

    def test_requests_without_login_are_not_resent(self, sm: SessionManager) -> None:
        sm.session.send.side_effect = [_REFUSED]
        with pytest.raises(requests.HTTPError):
            sm.post("/sysbus/NMC/Wifi:get", auth_required=False)
        assert sm.session.send.call_count == 1

    def test_uses_the_session_another_thread_logged_in_with(self, sm: SessionManager) -> None:
        def send(request: requests.PreparedRequest, **kwargs) -> requests.Response:
            if sm.session.send.call_count == 1:  # another thread logs in while this request is refused
                sm.context_id = "ctx-2"
                sm.session.headers["Authorization"] = "X-Sah ctx-2"
                return _REFUSED
            return _response(200)

        sm.session.send.side_effect = send
        sm.post("/sysbus/DNS:get")
        assert self._sent(sm) == [("https://192.0.2.1/sysbus/DNS:get", "X-Sah ctx-1"), ("https://192.0.2.1/sysbus/DNS:get", "X-Sah ctx-2")]

    def test_download_resends_with_the_new_context(self, sm: SessionManager) -> None:
        sm.session.send.side_effect = [_REFUSED, _LOGOUT, _login_response("ctx-2"), _response(200, b"QUJD\n")]
        assert sm.download("/backup") == "QUJD\n"
        assert self._sent(sm)[-1][0] == "https://192.0.2.1/backup?context=ctx-2"

    def test_upload_resends_with_the_new_context(self, sm: SessionManager) -> None:
        sm.session.send.side_effect = [_REFUSED, _LOGOUT, _login_response("ctx-2"), _response(200)]
        sm.upload("/restore", "restore", "internetbox.cfg", b"QUJD\n")
        assert b'name="context"\r\n\r\nctx-2\r\n' in sm.session.send.call_args.args[0].body

    def test_threads_log_in_once(self) -> None:
        sm = SessionManager(hostname="192.0.2.1", ssl_verify=False)
        logging_in, finish_login = threading.Event(), threading.Event()

        def slow_login() -> None:
            logging_in.set()
            finish_login.wait(5)
            sm.context_id = "ctx-1"

        with patch.object(sm, "_login", side_effect=slow_login) as login:
            first = threading.Thread(target=sm._ensure_authenticated)
            first.start()
            logging_in.wait(5)
            second = threading.Thread(target=sm._ensure_authenticated)
            second.start()
            time.sleep(0.1)  # the second thread waits for the first one's login
            finish_login.set()
            first.join(5)
            second.join(5)
        assert login.call_count == 1


class TestRouterErrors:
    """The router explains most refusals in an "errors" list, e.g. which parameters it didn't accept."""

    @pytest.fixture()
    def sm(self) -> SessionManager:
        sm = SessionManager(hostname="192.0.2.1", ssl_verify=False)
        sm.context_id = "ctx-1"
        sm.session.send = MagicMock()
        return sm

    def test_reasons_are_in_the_message(self, sm: SessionManager) -> None:
        body = (
            b'{"status": null, "errors": [{"error": 1114117, "description": "Invalid port-range", "info": "InternalPort, ExternalPort"}]}'
        )
        sm.session.send.return_value = _response(500, body)
        with pytest.raises(requests.HTTPError) as raised:
            sm.post("/sysbus/Firewall:setPortForwarding")
        assert str(raised.value).startswith("500 Server Error")
        assert str(raised.value).endswith("\nRouter says: Invalid port-range (InternalPort, ExternalPort)")
        assert raised.value.response.status_code == 500

    def test_several_reasons(self, sm: SessionManager) -> None:
        body = b'{"errors": [{"description": "Invalid value", "info": "SSID"}, {"description": "Missing", "info": "mibs"}]}'
        sm.session.send.return_value = _response(500, body)
        with pytest.raises(requests.HTTPError, match=r"Router says: Invalid value \(SSID\); Missing \(mibs\)$"):
            sm.post("/sysbus/NeMo/Intf/wl0:setWLANConfig")

    @pytest.mark.parametrize("body", [b"<html>Internal error</html>", b'{"status": null}', b'{"errors": []}', b"[]"])
    def test_without_reasons(self, sm: SessionManager, body: bytes) -> None:
        sm.session.send.return_value = _response(500, body)
        with pytest.raises(requests.HTTPError) as raised:
            sm.post("/sysbus/Firewall:setPortForwarding")
        assert "Router says" not in str(raised.value)


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

        client.download("/backup")
        mock_session_manager.download.assert_called_once_with("/backup")

        client.upload("/restore", "restore", "internetbox.cfg", b"QUJD")
        mock_session_manager.upload.assert_called_once_with("/restore", "restore", "internetbox.cfg", b"QUJD")

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
