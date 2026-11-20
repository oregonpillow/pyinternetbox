from typing import Literal

from internetbox_client.utils.APIClient import APIClient
from internetbox_client.utils.labels import write

_PROTOCOLS = {"tcp": "6", "udp": "17", "both": "6,17"}


class Firewall(APIClient):
    """Firewall rules, DMZ, and port-forwarding settings."""

    def status(self) -> str:
        """Get firewall status, including whether UPnP port forwarding is on (UpnpPortForwardingEnable)"""
        data = {"parameters": {}}
        return self.post("/sysbus/Firewall:get", data)

    @write
    def set_upnp_enabled(self, enable: bool) -> str:
        """Turn UPnP port forwarding on or off, like the UPnP switch in the web UI's port forwarding settings.

        With UPnP on, devices such as game consoles open ports to the internet themselves.

        Args:
            enable (bool): True to turn UPnP on, False to turn it off.

        Returns:
            str: response content

        """
        data = {"parameters": {"UpnpPortForwardingEnable": enable}}
        return self.post("/sysbus/Firewall:set", data)

    def dmz(self) -> str:
        """Get DMZ status"""
        data = {"parameters": {}}
        return self.post("/sysbus/Firewall:getDMZ", data)

    @write
    def set_dmz(self, destination_ip: str) -> str:
        """Expose a device to the internet (DMZ host).

        Incoming connections that no port forwarding rule matches go to this device instead of being blocked.
        Only use it for a device that is safe to expose directly to the internet.

        Args:
            destination_ip (str): LAN IP address of the device, e.g. "192.168.1.20".

        Returns:
            str: response content

        """
        data = {"parameters": {"id": "webui", "sourceInterface": "data", "destinationIPAddress": destination_ip, "enable": True}}
        return self.post("/sysbus/Firewall:setDMZ", data)

    @write
    def delete_dmz(self) -> str:
        """Remove the DMZ host set in the web UI or with set_dmz."""
        data = {"parameters": {"id": "webui"}}
        return self.post("/sysbus/Firewall:deleteDMZ", data)

    def level(self) -> str:
        """Get IPv4 firewall level"""
        data = {"parameters": {}}
        return self.post("/sysbus/Firewall:getFirewallLevel", data)

    @write
    def set_level(self, level: Literal["Low", "Medium", "High", "Custom"]) -> str:
        """Set the IPv4 firewall level.

        Args:
            level (str): "Low" (Off in the web UI), "Medium" (Balanced), "High" (Strict) or "Custom" (custom rules).

        Returns:
            str: response content

        """
        data = {"parameters": {"level": level}}
        return self.post("/sysbus/Firewall:setFirewallLevel", data)

    def ipv6_level(self) -> str:
        """Get IPv6 firewall level"""
        data = {"parameters": {}}
        return self.post("/sysbus/Firewall:getFirewallIPv6Level", data)

    @write
    def set_ipv6_level(self, level: Literal["Off", "Medium", "High", "Custom"]) -> str:
        """Set the IPv6 firewall level.

        Args:
            level (str): "Off", "Medium" (Balanced in the web UI), "High" (Strict) or "Custom" (custom rules).

        Returns:
            str: response content

        """
        data = {"parameters": {"level": level}}
        return self.post("/sysbus/Firewall:setFirewallIPv6Level", data)

    def port_forwarding(self) -> str:
        """Get port forwarding rules"""
        data = {"parameters": {}}
        return self.post("/sysbus/Firewall:getPortForwarding", data)

    @write
    def set_port_forwarding(
        self,
        name: str,
        destination_ip: str,
        external_port: str,
        internal_port: str | None = None,
        protocol: Literal["tcp", "udp", "both"] = "both",
        enabled: bool = True,
    ) -> str:
        """Add a port forwarding rule, or update the rule with this name.

        The rule shows up in the web UI like rules created there, with the ID "webui_<name>".

        Args:
            name (str): rule name, e.g. "minecraft".
            destination_ip (str): LAN IP address of the device to forward to, e.g. "192.168.1.20".
            external_port (str): port on the internet side, e.g. "25565", or a range such as "8000-8010".
            internal_port (str | None): port on the device. Default is the same as external_port. For a range of
                external ports, give the same range, or a single port to send the whole range to it.
            protocol (str): "tcp", "udp" or "both". Default is "both".
            enabled (bool): whether the rule is active. Default is True.

        Returns:
            str: response content, including the stored rule

        """
        if protocol not in _PROTOCOLS:
            raise ValueError(f"protocol must be one of {list(_PROTOCOLS)}, got {protocol!r}")
        external_port, internal_port = str(external_port), str(internal_port or external_port)
        if "-" in internal_port and internal_port != external_port:
            raise ValueError(f"internal_port must be a single port or the same range as external_port, got {internal_port!r}")
        data = {
            "parameters": {
                "id": name,
                "description": name,
                "persistent": True,
                "origin": "webui",
                "sourceInterface": "data",
                "sourcePrefix": "",
                "enable": enabled,
                "protocol": _PROTOCOLS[protocol],
                "destinationIPAddress": destination_ip,
                "externalPort": external_port,
                "internalPort": internal_port,
            }
        }
        result = self.post("/sysbus/Firewall:setPortForwarding", data)
        self._commit()
        return result

    @write
    def delete_port_forwarding(self, name: str) -> str:
        """Delete a port forwarding rule created in the web UI or with set_port_forwarding.

        Args:
            name (str): rule name, or its ID as listed by port_forwarding() (e.g. "webui_minecraft").

        Returns:
            str: response content

        """
        data = {"parameters": {"id": name, "origin": "webui"}}
        result = self.post("/sysbus/Firewall:deletePortForwarding", data)
        self._commit()
        return result

    def custom_rule(self) -> str:
        """Get custom firewall rules"""
        data = {"parameters": {}}
        return self.post("/sysbus/Firewall:getCustomRule", data)

    def _commit(self) -> None:
        """Apply saved port forwarding changes, as the web UI does after every change."""
        self.post("/sysbus/Firewall:commit", {"parameters": {}})
