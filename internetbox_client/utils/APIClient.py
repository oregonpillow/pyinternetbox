from __future__ import annotations

import ipaddress
import logging
import os
from types import TracebackType
from typing import Any, Mapping
from urllib.parse import urljoin, urlsplit

import requests
import urllib3  # deptry: ignore[DEP003]

logger = logging.getLogger(__name__)

# (connect, read) seconds. The short connect timeout makes an unreachable host fail fast
# instead of hanging; the read timeout leaves room for slow router endpoints.
DEFAULT_TIMEOUT: tuple[float, float] = (5, 30)
# Configuration backups and restores take longer: the web UI waits up to 200 s for a backup.
TRANSFER_TIMEOUT: tuple[float, float] = (5, 200)

_NO_AUTH_HEADERS = {
    "Authorization": "X-Sah null",
    "X-Context": "null",
    "Content-Type": "application/x-sah-ws-4-call+json",
    "Accept": "application/json, text/javascript, */*; q=0.01",
}


def normalize_hostname(hostname: str) -> str:
    """Return ``https://host[:port]`` for any user-supplied hostname.

    Adds a missing scheme, upgrades ``http://`` to ``https://`` (the gateway
    does not serve the API over plain HTTP) and drops any path, query or
    trailing slash.
    """
    raw = hostname.strip()
    if "://" not in raw:
        raw = f"https://{raw}"
    parts = urlsplit(raw)
    scheme = parts.scheme.lower()
    host = parts.hostname or ""
    if ":" in host:
        host = f"[{host}]"
    port = parts.port

    if scheme == "http":
        logger.warning("The Internet Box API is only served over HTTPS; using https:// instead of http://.")
        scheme = "https"
        if port == 80:
            port = None
    elif scheme != "https":
        raise ValueError(f"Unsupported URL scheme {parts.scheme!r} in hostname {hostname!r}; use https://.")

    if not host:
        raise ValueError(f"Invalid hostname {hostname!r}.")
    return f"{scheme}://{host}:{port}" if port else f"{scheme}://{host}"


def _is_ip_address(base_url: str) -> bool:
    try:
        ipaddress.ip_address(urlsplit(base_url).hostname or "")
    except ValueError:
        return False
    return True


def _resolve_ssl_verify(base_url: str, ssl_verify: bool | None) -> bool:
    """Decide whether to verify TLS certificates.

    Priority: explicit argument, then ``IB_SSL_VERIFY``, then auto-detect.
    The gateway's certificate is issued for ``internetbox.swisscom.ch``, so
    verification can never succeed when connecting by IP address.
    """
    if ssl_verify is not None:
        return ssl_verify
    env = os.getenv("IB_SSL_VERIFY")
    if env is not None:
        return env.lower() != "false"
    if _is_ip_address(base_url):
        logger.warning(
            "Connecting by IP address: SSL certificate verification disabled (the certificate is only valid for "
            "internetbox.swisscom.ch). Pass --insecure / -k (or set IB_SSL_VERIFY=false) to hide this warning."
        )
        return False
    return True


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
        ssl_verify: bool | None = None,
        timeout: float | tuple[float, float] = DEFAULT_TIMEOUT,
    ) -> None:
        self.base_url = normalize_hostname(hostname)
        self.timeout = timeout
        ssl_verify = _resolve_ssl_verify(self.base_url, ssl_verify)
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

        login_response = self.session.post(url=self.auth_url, json=login_data, timeout=self.timeout)
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
            self.session.post(url=self.auth_url, json=logout_data, timeout=self.timeout)
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
        response = self.session.get(url=url, headers=headers, timeout=self.timeout)
        response.raise_for_status()
        return response.text

    def post(self, endpoint: str | None = None, data: Mapping[str, Any] | None = None, auth_required: bool = True) -> str:
        """Send an HTTP POST request to the gateway."""
        if auth_required:
            self._ensure_authenticated()
        headers = _NO_AUTH_HEADERS if not auth_required else {}
        url = urljoin(self.base_url, endpoint) if endpoint else self.base_url
        response = self.session.post(url=url, json=data, headers=headers, timeout=self.timeout)
        response.raise_for_status()
        return response.text

    def download(self, endpoint: str) -> str:
        """Download a file the way the web UI does: a GET request with the session's context ID as a query parameter."""
        self._ensure_authenticated()
        url = urljoin(self.base_url, endpoint)
        response = self.session.get(url=url, params={"context": self.context_id}, timeout=TRANSFER_TIMEOUT)
        response.raise_for_status()
        return response.text

    def upload(self, endpoint: str, field: str, filename: str, content: bytes) -> str:
        """Upload a file the way the web UI's forms do: multipart/form-data, with the session's context ID first."""
        self._ensure_authenticated()
        url = urljoin(self.base_url, endpoint)
        response = self.session.post(
            url=url,
            data={"context": self.context_id},
            files={field: (filename, content, "application/octet-stream")},
            headers={"Content-Type": None},  # drops the session's JSON content type, so requests sets the multipart one
            timeout=TRANSFER_TIMEOUT,
        )
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

    def download(self, endpoint: str) -> str:
        return self._sm.download(endpoint)

    def upload(self, endpoint: str, field: str, filename: str, content: bytes) -> str:
        return self._sm.upload(endpoint, field, filename, content)
