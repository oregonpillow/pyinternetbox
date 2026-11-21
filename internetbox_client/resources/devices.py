from __future__ import annotations

import json
import re

import requests

from internetbox_client.resources.dhcp import DHCP
from internetbox_client.resources.mst import MST, _mst_id
from internetbox_client.resources.scheduler import WEEK, Scheduler
from internetbox_client.utils.APIClient import APIClient
from internetbox_client.utils.helpers import normalize_mac
from internetbox_client.utils.labels import write

# The device types the web UI offers for its device icons, from its settings (/static/settings/application.json).
DEVICE_TYPES = (
    "generic", "computer", "laptop", "tv", "storage", "dect", "smartphone", "tablette", "ipad", "gameconsole", "printer", "avplayer",
    "chromecast", "wlan box", "starwifi5", "starwifi5pro", "imaging", "liveradio", "speaker", "sonos-speaker", "generic-speaker",
    "wireless repeater", "miscellaneous", "tv box", "tv box ip1800", "tv box ip2000", "tv box ip2300", "apple-tv", "dect repeater",
    "ethernet switch", "circle-camera", "camera", "video-camera", "homeplug", "swisscom smart switch", "ha-switch", "bulb", "lamp-1",
    "lamp-2", "lamp-3", "lamp-4", "lamp-5", "led-strip", "xmas-tree", "ule", "small-button", "netatmo-outdoor", "netatmo-additional",
    "netatmo-indoor", "coffee-maker", "fan", "gigaset", "motion-sensor", "heating", "smart-watch", "remote-control", "white-goods",
    "irobot", "square", "circle", "triangle",
)  # fmt: skip
# The GenLog topics the web UI clears to reset a device's traffic history. The Internet-Box 4 only keeps "network".
_TRAFFIC_LOGS = ("network", "network_persistent")


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
    def reset_name(self, key: str) -> str:
        """Remove the name given to a device in the web UI or with rename(), so it gets the name it was found with
        again, e.g. the one it gives the router when it connects.

        Args:
            key (str): device key: the MAC address for network devices (the "Key" field in get()).

        Returns:
            str: response content

        """
        data = {"service": f"Devices.Device.{_device_key(key)}", "method": "removeName", "parameters": {"source": "webui"}}
        return self.post("/ws", data)

    @write
    def set_type(self, key: str, device_type: str) -> str:
        """Set a device's type, which picks its icon, like the device settings in the web UI.

        Args:
            key (str): device key: the MAC address for network devices (the "Key" field in get()).
            device_type (str): one of the types the web UI offers (DEVICE_TYPES), e.g. "computer", "laptop",
                "smartphone", "tablette" (a tablet), "tv", "printer", "gameconsole", "camera", "ha-switch" (a smart
                plug), "bulb", "speaker" or "miscellaneous".

        Returns:
            str: response content

        Raises:
            ValueError: if the web UI doesn't offer the type.

        """
        if device_type not in DEVICE_TYPES:
            raise ValueError(f"device_type must be one of the web UI's types: {', '.join(DEVICE_TYPES)}. Got {device_type!r}")
        parameters = {"parameters": {"DeviceType": device_type}}
        return self.post("/ws", {"service": f"Devices.Device.{_device_key(key)}", "method": "set", "parameters": parameters})

    @write
    def set_dns_name(self, key: str, name: str) -> str:
        """Give a device a different name in the router's DNS than the one the web UI shows (see rename()).

        The name works straight away, also with the router's local domain (e.g. "nas.home"), and replaces the
        displayed name in DNS until remove_dns_name(). The web UI keeps showing the displayed name.

        Args:
            key (str): device key: the MAC address for network devices (the "Key" field in get()).
            name (str): 1 to 63 letters, digits and hyphens, not starting or ending with a hyphen, e.g. "nas".

        Returns:
            str: response content

        """
        if not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?", name):
            raise ValueError(
                f"The DNS name must be 1 to 63 letters, digits and hyphens, not starting or ending with a hyphen, got {name!r}"
            )
        data = {"service": f"Devices.Device.{_device_key(key)}", "method": "setName", "parameters": {"name": name, "source": "dns"}}
        return self.post("/ws", data)

    @write
    def remove_dns_name(self, key: str) -> str:
        """Remove the DNS name given to a device with set_dns_name(), so its displayed name works in DNS again.

        Args:
            key (str): device key: the MAC address for network devices (the "Key" field in get()).

        Returns:
            str: response content

        """
        data = {"service": f"Devices.Device.{_device_key(key)}", "method": "removeName", "parameters": {"source": "dns"}}
        return self.post("/ws", data)

    @write
    def reset_traffic_counters(self) -> str:
        """Set every device's traffic counters to 0, like the reset button on the web UI's bandwidth page.

        The counters are the "Bandwidth" field in get(): what each device received and sent over the last day, week
        and month. The exporter's device traffic gauges start again from 0. The old counts can't be brought back.

        Returns:
            str: response content

        """
        data = {"service": "Devices.Config.bandwidth", "method": "set", "parameters": {"Reset": 1}}
        return self.post("/ws", data)

    @write
    def clear_traffic_history(self, mac: str) -> str:
        """Delete a Wi-Fi device's recent traffic history, like the web UI's reset button for a device's data usage.

        The history is the device's traffic and Wi-Fi signal readings, one every 15 seconds for about the last 25
        minutes, from which the web UI draws its graphs. It can't be brought back; the next reading starts a new one.
        The data the device used today, this week and this month (the "Bandwidth" field in get()) stays, and so do
        its hourly snapshots (getEventLog type "network_persistent"): only reset_traffic_counters() resets those, for
        every device. Wired devices have no history.

        Args:
            mac (str): device MAC address.

        Returns:
            str: response content

        Raises:
            ValueError: if the router has no traffic history for the device, e.g. because it's wired or never connected.

        """
        source = f"Devices.Device.{normalize_mac(mac)}"
        results = []
        for topic in _TRAFFIC_LOGS:
            try:
                results.append(self.post("/sysbus/GenLog:clearLogs", {"parameters": {"topic": topic, "source": source}}))
            except requests.HTTPError as error:
                # Like the web UI, also try "network_persistent", although the Internet-Box 4 doesn't keep it here.
                if "Topic does not exist" not in str(error):
                    raise
        if not results:
            raise ValueError(f"The router has no traffic history for {mac}, e.g. because it's wired or never connected")
        return results[-1]

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
