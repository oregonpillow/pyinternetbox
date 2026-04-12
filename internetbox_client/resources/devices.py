from __future__ import annotations

from internetbox_client.utils.APIClient import APIClient


class Devices(APIClient):
    """Information about connected devices, network topology, and hardware."""

    def info(self) -> str:
        """Device information such as model name, serial number, firmware version, uptime, etc."""
        data = {"parameters": {}}
        return self.post("/sysbus/DeviceInfo:get", data, auth_required=False)

    def get(self, expression: str | None = None, flags: str | None = None) -> str:
        """Get devices.

        Powerful method to get detailed information about devices connected to the router: user agents, DNS records,
        network interfaces, hardware identifiers, bandwidth usage, and more. The expression and flags parameters allow
        filtering and customization of the response.

        Args:
            expression (str | None): expression to search for, separated by "||" for multiple tags.
                Default is None to include all main device tags.
            flags (str | None): additional flags for the search.
                Default is None to exclude actions from the response.

        Expression examples:
            "self || not self || lan || eth || nemo || interface || events || usb || sysbus"
            "lan and not self and not interface"

        Flags examples:
            "no_actions" - do not include actions in the response
            "full_links" - include full links information in the response

        Returns:
            str: response content

        """

        data = {"service": "Devices", "method": "get", "parameters": {"expression": expression, "flags": flags}}
        return self.post("/ws", data=data)

    def usb(self) -> str:
        """USB information."""
        data = {"parameters": {}}
        return self.post("/sysbus/USBHosts:getDevices", data)

    def topology(self) -> str:
        """Detailed device and network topology information.

        Includes public IP addresses, connected devices, network interfaces, and more.
        """
        data = {
            "service": "Devices.Device.HGW",
            "method": "topology",
            "parameters": {"expression": "", "traverse": "down", "flags": "no_actions"},
        }
        return self.post("/ws", data)

    def network_xt(self) -> str:
        """Network information from the extended network topology."""
        data = {"service": "Devices.Device.HGW", "method": "getEventLog", "parameters": {"type": "network_xt"}}
        return self.post("/ws", data)

    def memory_status(self) -> str:
        """Device memory status."""
        data = {"parameters": {}}
        return self.post("/sysbus/DeviceInfo/MemoryStatus:get", data)
