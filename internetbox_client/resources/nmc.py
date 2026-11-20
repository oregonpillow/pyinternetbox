import base64
import binascii
import contextlib
import ipaddress
import json
import random
from pathlib import Path

import requests

from internetbox_client.utils.APIClient import APIClient
from internetbox_client.utils.labels import disruptive, secret_result, write

_PRIVATE = [ipaddress.IPv4Network(network) for network in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16")]
# Networks the router uses itself, besides the LAN and WireGuard's.
_ROUTER_NETWORKS = {
    "the guest Wi-Fi": ipaddress.IPv4Network("10.128.0.0/16"),
    "the router's apbridge network": ipaddress.IPv4Network("10.129.0.0/16"),
}
_MAX_ROUTES = 10  # the web UI's limit


def _route_network(destination: str) -> ipaddress.IPv4Network:
    """The destination of a static route, checked like the web UI does."""
    try:
        network = ipaddress.IPv4Network(destination.strip(), strict=False)
    except ValueError:
        network = None
    if network is None or "/" not in destination:
        raise ValueError(f'destination must be a network such as "192.168.10.0/24", got {destination!r}')
    if not 16 <= network.prefixlen <= 28:
        raise ValueError(f"The destination network must have a prefix length from /16 to /28, got {destination!r}")
    if network.network_address != ipaddress.IPv4Address(destination.split("/")[0].strip()):
        raise ValueError(f"{destination} isn't the address of its network: did you mean {network}?")
    if not any(network.subnet_of(private) for private in _PRIVATE):
        raise ValueError(f"{network} isn't a private network (in 10.0.0.0/8, 172.16.0.0/12 or 192.168.0.0/16).")
    return network


def _route_destination(route: dict) -> ipaddress.IPv4Network:
    return ipaddress.IPv4Network(f"{route.get('Dst')}/{route.get('DstLen')}", strict=False)


def _address_in(address: object, network: ipaddress.IPv4Network) -> bool:
    try:
        return ipaddress.IPv4Address(str(address)) in network
    except ValueError:
        return False


def _read_backup(path: str) -> bytes:
    """The content of a configuration backup file, with the router's line endings (files saved on Windows have \\r\\n)."""
    content = Path(path).read_bytes().replace(b"\r\n", b"\n")
    try:
        is_backup = bool(base64.b64decode(b"".join(content.split()), validate=True))
    except binascii.Error:
        is_backup = False
    if not is_backup:
        raise ValueError(f"{path} isn't a configuration backup. Use a file saved with nmc backup or the web interface.")
    return content


class NMC(APIClient):
    """Query the Network Management Controller for WAN, LAN, and system status."""

    def status(self) -> str:
        """Get NMC status"""
        data = {"parameters": {}}
        return self.post("/sysbus/NMC:get", data, auth_required=False)

    def ip_conflicts(self) -> str:
        """Get IP conflicts"""
        data = {"parameters": {}}
        return self.post("/sysbus/NMC:getIPConflicts", data, auth_required=False)

    def wan_status(self) -> str:
        """Get WAN status"""
        data = {"parameters": {}}
        return self.post("/sysbus/NMC:getWANStatus", data, auth_required=False)

    def orientation(self) -> str:
        """Get device orientation"""
        data = {"parameters": {}}
        return self.post("/sysbus/NMC/Orientation:get", data, auth_required=False)

    def lan_ip(self) -> str:
        """Get LAN IP address"""
        data = {"parameters": {}}
        return self.post("/sysbus/NMC:getLANIP", data)

    @disruptive
    def reboot(self, reason: str = "pyinternetbox") -> str:
        """Restart the router. Internet, Wi-Fi and phone are down for a few minutes.

        Args:
            reason (str): reason sent to the router (the web UI sends "WebUI"). Default is "pyinternetbox".

        Returns:
            str: response content

        """
        data = {"parameters": {"reason": reason}}
        return self.post("/sysbus/NMC:reboot", data)

    @secret_result
    def backup(self) -> str:
        """Download a backup of all settings, e.g. ibox nmc backup > internetbox.cfg

        This is the file the web UI's "Save Current Configuration" button saves; restore() loads it back. The phone book
        isn't included. The router keeps the dates of the last two backups (History.backup_entries()).

        Returns:
            str: content of the backup file

        """
        return self.download("/backup")

    @disruptive
    def restore(self, path: str) -> str:
        """Replace all settings with a backup file. The router restarts: internet, Wi-Fi and phone are down for a few minutes.

        The phone book isn't in the file and stays as it is.

        Args:
            path (str): backup file saved with backup() or the web UI.

        Returns:
            str: response content

        Raises:
            ValueError: if the file isn't a configuration backup or the router doesn't confirm the restore.

        """
        content = _read_backup(path)
        # Sent under the name the router gives its backups: the web UI only uploads .cfg files.
        response = self.upload("/restore", "restore", "internetbox.cfg", content)
        # The answer is a page that passes the result to the web UI: ...fire('sah:models:System:state', 'restore-success')
        if "restore-success" not in response:
            raise ValueError(f"The router didn't confirm the restore. It answered: {response[:300]}")
        return response

    @write
    def backup_to_swisscom(self) -> str:
        """Upload a backup of the settings to Swisscom, as the web UI does when settings are saved.

        Only if backup to Swisscom is turned on for this router; the web UI has no setting for it. The router answers
        straight away and uploads in the background, which takes about a minute: network_config() shows Saving,
        Uploading, then Uploaded, and History.backup_entries() lists the upload.

        Returns:
            str: response content

        Raises:
            ValueError: if backup to Swisscom isn't turned on. Nothing is uploaded.

        """
        status = (json.loads(self.network_config()).get("status") or {}).get("Status")
        # Like the web UI, which uploads unless the status is "Disabled".
        if status in (None, "Disabled"):
            raise ValueError(
                f"Backup to Swisscom isn't turned on for this router (status: {status}), so nothing was uploaded. "
                "The web interface has no setting for it."
            )
        data = {"parameters": {}}
        return self.post("/sysbus/NMC/NetworkConfig:launchNetworkBackup", data)

    def phonebook_backup(self) -> str:
        """Get phonebook backup status"""
        data = {"parameters": {}}
        return self.post("/sysbus/NMC/PhonebookBackup:get", data)

    def static_routes(self) -> str:
        """Get LAN static routes"""
        data = {"parameters": {}}
        return self.post("/sysbus/NMC/LAN:getStaticRoutes", data)

    @write
    def set_static_route(self, destination: str, gateway: str) -> str:
        """Add a static route, or change the gateway of the route to this network, like the web UI's static routes.

        The router then sends traffic for the destination network to the gateway: a device in your network, such as a
        second router with that network behind it. Give the gateway a fixed IP address (dhcp.add_static_lease()), as
        the web UI suggests, so the route keeps working.

        Args:
            destination (str): a private network with a prefix length from /16 to /28, e.g. "192.168.10.0/24".
            gateway (str): IP address of a device in your network, e.g. "192.168.1.2".

        Returns:
            str: response content

        Raises:
            ValueError: if the web UI would refuse the route: for instance a public network, one that overlaps your
                network, the guest Wi-Fi, the WireGuard clients or another route, a gateway outside your network, or an
                11th route.

        """
        network = _route_network(destination)
        try:
            next_hop = ipaddress.IPv4Address(gateway.strip())
        except ValueError:
            raise ValueError(f'gateway must be an IP address such as "192.168.1.2", got {gateway!r}') from None
        lan_settings = json.loads(self.lan_ip()).get("data") or {}
        lan = ipaddress.IPv4Interface(f"{lan_settings.get('Address')}/{lan_settings.get('Netmask')}")
        if next_hop == lan.ip:
            raise ValueError(f"The gateway can't be the router itself ({lan.ip}).")
        if next_hop not in lan.network or next_hop in (lan.network.network_address, lan.network.broadcast_address):
            raise ValueError(f"The gateway must be a device in your network ({lan.network}), got {gateway!r}")
        routes = json.loads(self.static_routes()).get("status") or {}
        current = next((name for name, route in routes.items() if _route_destination(route) == network), None)
        used = {"your network": lan.network, **_ROUTER_NETWORKS}
        wireguard = self._wireguard_network()
        if wireguard:
            used["the WireGuard clients' network"] = wireguard
        used |= {f"the static route {name!r}": _route_destination(route) for name, route in routes.items() if name != current}
        for what, other in used.items():
            if network.overlaps(other):
                raise ValueError(f"{network} overlaps {what} ({other}).")
        settings = {"Dst": str(network.network_address), "DstLen": network.prefixlen, "Gateway": str(next_hop), "Enable": True}
        if current:
            return self.post(f"/sysbus/NMC/LAN/IPv4Route/{current}:set", {"parameters": settings})
        if len(routes) >= _MAX_ROUTES:
            raise ValueError(f"There are {len(routes)} static routes already, the most the web UI allows. Delete one first.")
        name = f"webui_{random.randrange(1_000_000)}"  # like the web UI
        while name in routes:
            name = f"webui_{random.randrange(1_000_000)}"
        return self.post("/sysbus/NMC/LAN:addStaticRoute", {"parameters": {"Name": name, **settings}})

    @write
    def delete_static_route(self, route: str) -> str:
        """Delete a static route, and the port forwarding rules to devices behind it, like the web UI.

        The port forwarding rules made in the web UI or with firewall.set_port_forwarding() for addresses in the
        route's network only reach their devices through the route, so the web UI deletes them too.

        Args:
            route (str): the route's destination network, e.g. "192.168.10.0/24", or its name in static_routes().

        Returns:
            str: response content

        """
        routes = json.loads(self.static_routes()).get("status") or {}
        name = route if route in routes else None
        if name is None and "/" in route:
            with contextlib.suppress(ValueError):
                network = ipaddress.IPv4Network(route.strip(), strict=False)
                name = next((name for name, found in routes.items() if _route_destination(found) == network), None)
        if name is None:
            known = ", ".join(f"{_route_destination(found)} ({name})" for name, found in routes.items()) or "none"
            raise ValueError(f"There's no static route {route!r}. The routes are: {known}.")
        network = _route_destination(routes[name])
        result = self.post("/sysbus/NMC/LAN:deleteStaticRoute", {"parameters": {"Name": name}})
        rules = json.loads(self.post("/sysbus/Firewall:getPortForwarding", {"parameters": {}})).get("status") or {}
        behind_route = [
            rule_id
            for rule_id, rule in rules.items()
            if rule.get("Origin") == "webui" and _address_in(rule.get("DestinationIPAddress"), network)
        ]
        for rule_id in behind_route:
            self.post("/sysbus/Firewall:deletePortForwarding", {"parameters": {"id": rule_id, "origin": "webui"}})
        if behind_route:
            self.post("/sysbus/Firewall:commit", {"parameters": {}})
        return result

    def _wireguard_network(self) -> ipaddress.IPv4Network | None:
        """The network of the WireGuard clients, e.g. 10.0.1.0/24, or None on routers without WireGuard."""
        with contextlib.suppress(requests.HTTPError, ValueError):
            servers = json.loads(self.post("/sysbus/WireGuard/Server:_get", {"parameters": {}})).get("status") or {}
            subnet = next((server["SubnetIPv4"] for server in servers.values() if (server or {}).get("SubnetIPv4")), None)
            return ipaddress.IPv4Network(subnet, strict=False) if subnet else None
        return None

    def network_config(self) -> str:
        """Get the status of backup to Swisscom: Enabled, or Saving, Uploading and Uploaded during an upload. Disabled means it's off."""
        data = {"parameters": {}}
        return self.post("/sysbus/NMC/NetworkConfig:get", data)

    def bdd(self) -> str:
        """Get NMC BDD (Broadband Device Database) information"""
        data = {"service": "NMC.BDD", "method": "get", "parameters": {}}
        return self.post("/ws", data)
