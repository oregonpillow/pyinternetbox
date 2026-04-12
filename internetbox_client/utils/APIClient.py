from __future__ import annotations

import os
from types import TracebackType
from typing import Any, Mapping
from urllib.parse import urljoin

import requests
import urllib3  # deptry: ignore[DEP003]

_NO_AUTH_HEADERS = {
    "Authorization": "X-Sah null",
    "X-Context": "null",
    "Content-Type": "application/x-sah-ws-4-call+json",
    "Accept": "application/json, text/javascript, */*; q=0.01",
}


class SessionManager:
    """Manages a single authenticated session to the Internet Box.

    Handles authentication via the SoftAtHome web services API (``/ws``
    endpoint). A session is created by calling ``createContext`` on the
    ``sah.Device.Information`` service. The resulting context ID and
    session cookie are stored and sent with every subsequent request.

    Supports the context-manager protocol so sessions are automatically
    closed on exit.
    """

    def __init__(
        self,
        hostname: str = os.getenv("IB_HOSTNAME", "https://internetbox.swisscom.ch"),
        password: str = os.getenv("IB_PASSWORD", ""),
        username: str = os.getenv("IB_USERNAME", "admin"),
        application_name: str = "webui",
        ssl_verify: bool = os.getenv("IB_SSL_VERIFY", "true").lower() != "false",
    ) -> None:
        self.base_url = hostname
        self.application_name = application_name
        self._username = username
        self._password = password
        self.session = requests.Session()
        self.session.verify = ssl_verify
        if not ssl_verify:
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        self.context_id: str | None = None
        self.auth_url = urljoin(self.base_url, "ws")

    def _ensure_authenticated(self) -> None:
        """Authenticate lazily on the first request that requires auth."""
        if self.context_id is not None:
            return

        self.session.headers.update({"Content-Type": "application/x-sah-ws-4-call+json", "Authorization": "X-Sah-Login"})

        login_data = {
            "service": "sah.Device.Information",
            "method": "createContext",
            "parameters": {"applicationName": self.application_name, "username": self._username, "password": self._password},
        }

        login_response = self.session.post(url=self.auth_url, json=login_data)
        login_response.raise_for_status()

        self.context_id = login_response.json()["data"]["contextID"]
        self.session.headers.update({"Authorization": f"X-Sah {self.context_id}"})

    def close(self) -> None:
        """Log out and close the underlying HTTP session.

        Sends a ``releaseContext`` RPC to invalidate the session token
        on the gateway, then closes the underlying ``requests.Session``.
        """
        if self.context_id is None:
            return

        self.session.headers.update({"Authorization": f"X-Sah-Logout {self.context_id}"})

        logout_data = {
            "service": "sah.Device.Information",
            "method": "releaseContext",
            "parameters": {"applicationName": self.application_name},
        }

        try:
            self.session.post(url=self.auth_url, json=logout_data)
        finally:
            self.context_id = None
            self.session.close()

    def __enter__(self) -> SessionManager:
        return self

    def __exit__(self, exc_type: type[BaseException] | None, exc_val: BaseException | None, exc_tb: TracebackType | None) -> bool:
        self.close()
        return False

    def get(self, endpoint: str | None = None, auth_required: bool = True) -> str:
        """Send an HTTP GET request to the gateway."""
        if auth_required:
            self._ensure_authenticated()
        headers = _NO_AUTH_HEADERS if not auth_required else {}
        url = urljoin(self.base_url, endpoint) if endpoint else self.base_url
        response = self.session.get(url=url, headers=headers)
        response.raise_for_status()
        return response.text

    def post(self, endpoint: str | None = None, data: Mapping[str, Any] | None = None, auth_required: bool = True) -> str:
        """Send an HTTP POST request to the gateway."""
        if auth_required:
            self._ensure_authenticated()
        headers = _NO_AUTH_HEADERS if not auth_required else {}
        url = urljoin(self.base_url, endpoint) if endpoint else self.base_url
        response = self.session.post(url=url, json=data, headers=headers)
        response.raise_for_status()
        return response.text


class APIClient:
    """Base class for Internet Box API resource groups.

    Each resource class (e.g. ``Wifi``, ``Devices``) inherits from this
    class and gains ``get()`` / ``post()`` helpers that delegate to a
    shared :class:`SessionManager`.
    """

    def __init__(
        self,
        session_manager: SessionManager | None = None,
        *,
        hostname: str = "https://internetbox.swisscom.ch",
        password: str = "",
        username: str = "admin",
        application_name: str = "webui",
    ) -> None:
        if session_manager is not None:
            self._sm = session_manager
            self._owns_session = False
        else:
            self._sm = SessionManager(hostname=hostname, password=password, username=username, application_name=application_name)
            self._owns_session = True

    @property
    def base_url(self) -> str:
        return self._sm.base_url

    @property
    def session(self) -> requests.Session:
        return self._sm.session

    def close_session(self) -> None:
        if self._owns_session:
            self._sm.close()

    def get(self, endpoint: str | None = None, auth_required: bool = True) -> str:
        return self._sm.get(endpoint, auth_required)

    def post(self, endpoint: str | None = None, data: Mapping[str, Any] | None = None, auth_required: bool = True) -> str:
        return self._sm.post(endpoint, data, auth_required)
