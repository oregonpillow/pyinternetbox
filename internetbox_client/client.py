"""Unified InternetBoxClient bundling all resource groups."""

from __future__ import annotations

from types import TracebackType
from typing import Any

from internetbox_client.resources import *  # noqa: F403
from internetbox_client.utils.APIClient import SessionManager


class InternetBoxClient:
    """Unified client for the Internet Box API.

    Initializes a single authenticated session and exposes all resource
    groups as attributes. Use as a context manager for automatic cleanup::

        with InternetBoxClient(password="secret") as client:
            print(client.devices.info())
            print(client.vpn.status())

    Connection parameters fall back to the ``IB_HOSTNAME``, ``IB_PASSWORD``,
    and ``IB_USERNAME`` environment variables when not provided explicitly.
    """

    def __init__(
        self, hostname: str | None = None, password: str | None = None, username: str | None = None, ssl_verify: bool | None = None
    ) -> None:
        kwargs: dict[str, Any] = {}
        if hostname is not None:
            kwargs["hostname"] = hostname
        if password is not None:
            kwargs["password"] = password
        if username is not None:
            kwargs["username"] = username
        if ssl_verify is not None:
            kwargs["ssl_verify"] = ssl_verify
        self._sm = SessionManager(**kwargs)

        self.devices = Devices(session_manager=self._sm)
        self.sysbus = Sysbus(session_manager=self._sm)
        self.mitigation = Mitigation(session_manager=self._sm)
        self.nmc = NMC(session_manager=self._sm)
        self.voice = Voice(session_manager=self._sm)
        self.password_recovery = PasswordRecovery(session_manager=self._sm)
        self.dns = DNS(session_manager=self._sm)
        self.wifi = Wifi(session_manager=self._sm)
        self.lan = LAN(session_manager=self._sm)
        self.events = Events(session_manager=self._sm)
        self.wwan = WWAN(session_manager=self._sm)
        self.static = Static(session_manager=self._sm)
        self.wireguard = Wireguard(session_manager=self._sm)
        self.firewall = Firewall(session_manager=self._sm)
        self.security = Security(session_manager=self._sm)
        self.debug = Debug(session_manager=self._sm)
        self.led = LED(session_manager=self._sm)
        self.dect = DECT(session_manager=self._sm)
        self.dhcp = DHCP(session_manager=self._sm)
        self.dyndns = DynDNS(session_manager=self._sm)
        self.carddav = CardDav(session_manager=self._sm)
        self.genlog = GenLog(session_manager=self._sm)
        self.http_service = HTTPService(session_manager=self._sm)
        self.history = History(session_manager=self._sm)
        self.phonebook = Phonebook(session_manager=self._sm)
        self.power_management = PowerManagement(session_manager=self._sm)
        self.scheduler = Scheduler(session_manager=self._sm)
        self.temperature = Temperature(session_manager=self._sm)
        self.mst = MST(session_manager=self._sm)
        self.oops_tracker = OopsTracker(session_manager=self._sm)
        self.user_management = UserManagement(session_manager=self._sm)
        self.vpn = VPN(session_manager=self._sm)
        self.webui = WebUI(session_manager=self._sm)
        self.speedtest = SpeedTest(session_manager=self._sm)
        self.ap_services = APServices(session_manager=self._sm)

    def close(self) -> None:
        """Log out and close the session."""
        self._sm.close()

    def __enter__(self) -> InternetBoxClient:
        return self

    def __exit__(self, exc_type: type[BaseException] | None, exc_val: BaseException | None, exc_tb: TracebackType | None) -> bool:
        self.close()
        return False
