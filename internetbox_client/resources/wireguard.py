import contextlib
import json
import re

import requests

from internetbox_client.utils.APIClient import APIClient
from internetbox_client.utils.labels import disruptive, secret_result, write

_ENDPOINT = re.compile(r"[A-Za-z0-9]([A-Za-z0-9.-]{0,251}[A-Za-z0-9])?")


class Wireguard(APIClient):
    """WireGuard VPN server and its clients."""

    def app_status(self) -> str:
        """Get Wireguard application status"""
        data = {"parameters": {}}
        return self.post("/sysbus/WireGuard:_get", data)

    def server_status(self) -> str:
        """Get Wireguard server status"""
        data = {"parameters": {}}
        return self.post("/sysbus/WireGuard/Server:_get", data)

    def clients(self) -> str:
        """Get configured Wireguard clients"""
        data = {"parameters": {}}
        return self.post("/sysbus/WireGuard/Server/default/Client:_get", data)

    def client_status(self, alias: str) -> str:
        """Get specific Wireguard client stats
        Such as connection status, data transferred, etc.
        Args:
            alias (str): client alias name
        """
        data = {"parameters": {}}
        return self.post(f"/sysbus/WireGuard/Server/default/Client/{alias}/InfoStats:_get", data)

    @disruptive
    def set_server_enabled(self, enable: bool) -> str:
        """Turn the WireGuard VPN server on or off, like the WireGuard switch in the web UI's VPN settings.

        While it's on, the router accepts WireGuard connections from the internet on port 51820 (ListenPort in
        server_status()). Turning it off disconnects the VPN clients.

        Args:
            enable (bool): True to turn the server on, False to turn it off.

        Returns:
            str: response content

        """
        self._check_available()
        data = {"parameters": {"parameters": {"Enable": enable}}}
        return self.post("/sysbus/WireGuard/Server/default:_set", data)

    @write
    @secret_result
    def add_client(self, name: str, endpoint: str | None = None, intranet_access: bool = True) -> str:
        """Add a WireGuard VPN client and get its configuration, like adding a WireGuard account in the web UI.

        Import the configuration into the WireGuard app on the phone or computer, as a file or as a QR code (e.g.
        qrencode -t ansiutf8 < client.conf). Keep it safe: it contains the client's private key, which the router
        doesn't keep. The client can only connect while the server is on (see set_server_enabled()): unlike the web
        UI, this doesn't turn the server on.

        Args:
            name (str): 3 to 16 letters, digits, - or _, starting with a letter, e.g. "phone".
            endpoint (str | None): where the client finds the router: its public IP address, or a DynDNS host name
                pointing to it (see dyndns.hosts()). Default: the current public IPv4 address, which may change.
            intranet_access (bool): whether the client may reach the devices in your network, not only the internet.
                Default is True.

        Returns:
            str: response content, with the client's configuration as "status", e.g. {"status": "[Interface]\\n..."}

        Raises:
            ValueError: if the name is invalid or taken, there's no endpoint, or the router doesn't return the
                configuration. A client added before the error is deleted again.

        """
        if not re.fullmatch(r"[a-zA-Z][a-zA-Z0-9_-]{2,15}", name):
            raise ValueError(f"The client name must be 3 to 16 letters, digits, - or _, starting with a letter, got {name!r}")
        if endpoint is not None and not _ENDPOINT.fullmatch(endpoint):
            raise ValueError(f'endpoint must be an IPv4 address or a host name such as "myhome.ddns.net", got {endpoint!r}')
        self._check_available()
        if name in self._clients():
            raise ValueError(f"There's already a WireGuard client named {name!r}.")
        lan_ip = (json.loads(self.post("/sysbus/NMC:getLANIP", {"parameters": {}})).get("data") or {}).get("Address")
        if endpoint is None:
            endpoint = (json.loads(self.post("/sysbus/NMC:getWANStatus", {"parameters": {}})).get("data") or {}).get("IPAddress")
            if not endpoint or endpoint == "0.0.0.0":
                raise ValueError("The router has no public IPv4 address. Give an endpoint, e.g. a DynDNS host name.")
        # The web UI keeps the endpoint and the router's LAN address in ExtraData, and warns when the endpoint changes.
        self.post(
            "/sysbus/WireGuard/Server/default/Client:_add",
            {"parameters": {"parameters": {"Alias": name, "ExtraData": f"{endpoint};{lan_ip}"}}},
        )
        try:
            data = {"parameters": {"parameters": {"Enable": True, "IntranetAccess": intranet_access}}}
            self.post(f"/sysbus/WireGuard/Server/default/Client/{name}:_set", data)
            answer = json.loads(
                self.post(f"/sysbus/WireGuard/Server/default/Client/{name}:GeneratePrivateKeyAndGetQRConfig", {"parameters": {}})
            )
            if not isinstance(answer.get("status"), str) or "[Interface]" not in answer["status"]:
                raise ValueError("The router didn't return the client's configuration.")
        except Exception:
            with contextlib.suppress(requests.RequestException):
                self.post(f"/sysbus/WireGuard/Server/default/Client/{name}:_del", {"parameters": {}})
            raise
        # The router writes its public IPv4 address as the endpoint; the web UI puts the chosen one in its place.
        answer["status"] = re.sub(r"Endpoint = \d+\.\d+\.\d+\.\d+", lambda _: f"Endpoint = {endpoint}", answer["status"], count=1)
        return json.dumps(answer)

    @write
    def set_client(self, name: str, enabled: bool | None = None, intranet_access: bool | None = None) -> str:
        """Turn a WireGuard client on or off, or change whether it may reach the devices in your network.

        Args:
            name (str): client name (Alias in clients()).
            enabled (bool | None): False stops the client from connecting. Default: unchanged.
            intranet_access (bool | None): whether the client may reach the devices in your network, not only the
                internet. Default: unchanged.

        Returns:
            str: response content

        """
        changes = {key: value for key, value in (("Enable", enabled), ("IntranetAccess", intranet_access)) if value is not None}
        if not changes:
            raise ValueError("Nothing to change: give enabled or intranet_access.")
        self._client(name)
        data = {"parameters": {"parameters": changes}}
        return self.post(f"/sysbus/WireGuard/Server/default/Client/{name}:_set", data)

    @write
    def delete_client(self, name: str) -> str:
        """Delete a WireGuard client. Its configuration stops working.

        Args:
            name (str): client name (Alias in clients()).

        Returns:
            str: response content

        """
        self._client(name)
        data = {"parameters": {}}
        return self.post(f"/sysbus/WireGuard/Server/default/Client/{name}:_del", data)

    def _clients(self) -> dict[str, dict]:
        """The clients by name."""
        found = json.loads(self.clients()).get("status") or {}
        return {client["Alias"]: client for client in found.values() if (client or {}).get("Alias")}

    def _client(self, name: str) -> dict:
        clients = self._clients()
        if name not in clients:
            names = ", ".join(map(repr, clients)) or "none"
            raise ValueError(f"There's no WireGuard client named {name!r}. The clients are: {names}.")
        return clients[name]

    def _check_available(self) -> None:
        """Raise if WireGuard is turned off on this router: the web UI then doesn't offer it."""
        status = json.loads(self.app_status()).get("status") or {}
        if not any((app or {}).get("Enable") for app in status.values()):
            raise ValueError("WireGuard isn't available on this router (Enable is false in app_status()).")
