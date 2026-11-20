from __future__ import annotations

import json

from internetbox_client.resources.dhcp import DHCP
from internetbox_client.resources.mst import MST, _mst_id
from internetbox_client.resources.scheduler import WEEK, Scheduler
from internetbox_client.utils.APIClient import APIClient
from internetbox_client.utils.helpers import normalize_mac
from internetbox_client.utils.labels import write


def _device_key(key: str) -> str:
    """Network devices are keyed by their MAC address in upper case; other keys pass unchanged."""
    try:
        return normalize_mac(key)
    except ValueError:
        return key


def _has_time_limit(mst: MST, mac: str) -> bool:
    return _mst_id(mac) in (json.loads(mst.get()).get("data") or {}).get("ids", [])


def _connection(device: dict) -> str | None:
    """How a device connects, or last connected, e.g. "Ethernet (ETH4)", "Wi-Fi 5GHz" or "guest Wi-Fi 2.4GHz"."""
    interface = device.get("InterfaceName") or ""
    if interface.upper().startswith("ETH"):
        return f"Ethernet ({interface})"
    if interface.lower().startswith("wl"):
        network = "guest Wi-Fi" if "guest" in interface.lower() else "Wi-Fi"
        band = device.get("OperatingFrequencyBand")
        return f"{network} {band}" if band else network
    return interface or None


def _device_summary(device: dict) -> dict:
    summary = {
        "name": device.get("Name"),
        "mac": device.get("Key"),
        "ip": device.get("IPAddress") or None,
        "type": device.get("DeviceType") or None,
        "manufacturer": device.get("Manufacturer") or device.get("MACVendor") or None,
        "connected": bool(device.get("Active")),
        "connection": _connection(device),
        "last_connection": device.get("LastConnection"),
    }
    if summary["connected"] and "Wi-Fi" in (summary["connection"] or "") and device.get("SignalStrength"):
        summary["signal_dbm"] = device["SignalStrength"]
    return summary


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

    def summary(self) -> str:
        """A short list of the devices on the home network: name, addresses, type, and whether and how they're connected.

        A short version of get(): 5 KB instead of 130 KB for 25 devices, with the manufacturer and the last connection
        time too. The connection is the current or last one, e.g. "Ethernet (ETH4)" or "Wi-Fi 5GHz". Connected Wi-Fi
        devices also have their signal strength in dBm.

        Returns:
            str: a JSON list, e.g. [{"name": "iPhone", "mac": "AA:BB:CC:DD:EE:FF", "ip": "192.168.1.20", ...}]

        """
        devices = json.loads(self.get(expression="lan and not self"))["status"]
        return json.dumps([_device_summary(device) for device in devices], ensure_ascii=False)

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

    @write
    def rename(self, key: str, name: str) -> str:
        """Rename a device, as shown in the web UI and in get(). The new name shows up within a second or so.

        Args:
            key (str): device key: the MAC address for network devices (the "Key" field in get()).
            name (str): new name.

        Returns:
            str: response content

        """
        data = {"service": f"Devices.Device.{_device_key(key)}", "method": "set", "parameters": {"parameters": {"Name": name}}}
        return self.post("/ws", data)

    @write
    def remove(self, mac: str) -> str:
        """Remove an offline device from the device list, like the delete button in the web UI.

        As in the web UI, this also deletes the device's IP address reservation, internet access schedule and daily
        time limit. If the device connects again, it shows up as a new device.

        Args:
            mac (str): device MAC address.

        Returns:
            str: response content

        Raises:
            ValueError: if the device is connected. It would reappear straight away, without its settings.

        """
        mac = normalize_mac(mac)
        device = json.loads(self.post("/ws", {"service": f"Devices.Device.{mac}", "method": "get", "parameters": {}}))
        if (device.get("status") or {}).get("Active"):
            raise ValueError(f"{mac} is connected. Only offline devices can be removed; a connected one would reappear straight away.")
        # The reservation goes first: deleting it after the device brings the device back.
        dhcp = DHCP(self._sm)
        if any(lease["MACAddress"].upper() == mac for lease in json.loads(dhcp.static_leases())["status"]):
            dhcp.delete_static_lease(mac)
        Scheduler(self._sm).remove_device_schedule(mac)
        mst = MST(self._sm)
        if _has_time_limit(mst, mac):
            mst.delete(mac)
        data = {"service": "Devices", "method": "destroyDevice", "parameters": {"key": mac}}
        return self.post("/ws", data)

    @write
    def wake_on_lan(self, mac: str) -> str:
        """Wake up a device with Wake-on-LAN. The device must support it and have it turned on.

        Args:
            mac (str): device MAC address.

        Returns:
            str: response content

        """
        data = {"parameters": {"hostID": normalize_mac(mac), "broadcast": True, "retries": 3, "interval": 60000}}
        return self.post("/sysbus/WOL:sendWakeOnLan", data)

    @write
    def block(self, mac: str) -> str:
        """Block a device's internet access, like the web UI's "Internet access blocked" switch.

        This turns the device's parental controls on. A device without an access schedule gets one that blocks it all
        week. A device with a schedule (see scheduler.set_device_schedule) is only blocked when that schedule says so.
        Its daily time limit (see mst.set) is turned on too.

        Args:
            mac (str): device MAC address.

        Returns:
            str: the device's schedule, as from scheduler.device_schedule. "value" is "Disable" while it is blocked.

        """
        return self._set_parental_controls(mac, True)

    @write
    def unblock(self, mac: str) -> str:
        """Restore a device's internet access, like turning off the web UI's "Internet access blocked" switch.

        This turns off the device's access schedule and daily time limit. Both are kept, so block() brings them back.

        Args:
            mac (str): device MAC address.

        Returns:
            str: the device's schedule, as from scheduler.device_schedule ({"status": false} if it has none).

        """
        return self._set_parental_controls(mac, False)

    def _set_parental_controls(self, mac: str, enable: bool) -> str:
        mac = normalize_mac(mac)
        scheduler, mst = Scheduler(self._sm), MST(self._sm)
        if json.loads(scheduler.device_schedule(mac)).get("status"):
            scheduler.enable_device_schedule(mac, enable)
        elif enable:
            scheduler.set_device_schedule(mac, [{"begin": 0, "end": WEEK}])
        # Unblocking leaves devices without a time limit alone instead of creating a disabled one.
        if enable or _has_time_limit(mst, mac):
            mst.set(mac, enable=enable)
        return scheduler.device_schedule(mac)
