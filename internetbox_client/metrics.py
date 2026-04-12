"""User-defined Prometheus metrics for the Internet Box exporter.

Add your own metrics here.  Each metric is a function decorated with
``@collector.register_collector`` (or registered via
``collector.register_collector(fn)``).  The function receives the
:class:`~internetbox_client.exporter.InternetBoxCollector` instance as its
only argument and calls ``col.update_gauge(...)`` to publish values.

``register_metrics(collector, client)`` is called automatically by the CLI
``export`` command.  Add new collectors inside that function following the
same pattern as the examples already there.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from internetbox_client import InternetBoxClient
    from internetbox_client.exporter import InternetBoxCollector

logger = logging.getLogger(__name__)


def register_metrics(collector: InternetBoxCollector, client: InternetBoxClient) -> None:
    """Register all metric collectors with *collector*.

    Called once by the CLI before the HTTP server starts.  Add new
    ``@collector.register_collector`` functions here.
    """

    # ── Default labels (attached to every metric) ─────────────────
    try:
        devices_data = json.loads(client.devices.get())
        ibox = next((d for d in devices_data.get("status", []) if d["Name"] == "internetbox"), None)
        if ibox:
            collector.default_labels = {"internetbox_model": ibox.get("ModelName", ""), "internetbox_serial": ibox.get("SerialNumber", "")}
    except Exception:
        logger.warning("Could not fetch default labels (ModelName/SerialNumber); they will be empty.")

    # ── Devices ───────────────────────────────────────────

    @collector.register_collector
    def collect_devices(col: InternetBoxCollector) -> None:
        data = json.loads(client.devices.get())
        for device in data.get("status", []):
            if device["Name"] == "internetbox":
                ibox_labels = {
                    "Name": device["Name"],
                    "Key": device["Key"],
                    "public_ipv4": device["ConnectionIPv4Address"],
                    "public_ipv6": device["ConnectionIPv6Address"],
                    "RemoteGateway": device["RemoteGateway"],
                    # these fields are already included as default labels
                    # "ModelName": device["ModelName"],
                    # "SerialNumber": device["SerialNumber"],
                    "FirewallLevel": device["FirewallLevel"],
                    "SoftwareVersion": device["SoftwareVersion"],
                    "Manufacturer": device["Manufacturer"],
                    "LinkType": device["LinkType"],
                }
                col.update_gauge(
                    name="internetbox_device_internetbox_gpon_up_state",
                    value=1 if device["LinkState"] == "up" else 0,
                    labels=ibox_labels,
                    description="GPON up state of the Internet Box (1 for Up, 0 for Down)",
                )
                col.update_gauge(
                    name="internetbox_device_internetbox_internet_enabled",
                    value=1 if device["Internet"] else 0,
                    labels=ibox_labels,
                    description="Internet enabled state of the Internet Box (1 for Enabled, 0 for Disabled)",
                )
                col.update_gauge(
                    name="internetbox_device_internetbox_iptv_enabled",
                    value=1 if device["IPTV"] else 0,
                    labels=ibox_labels,
                    description="IPTV enabled state of the Internet Box (1 for Enabled, 0 for Disabled)",
                )
                col.update_gauge(
                    name="internetbox_device_internetbox_telephony_enabled",
                    value=1 if device["Telephony"] else 0,
                    labels=ibox_labels,
                    description="Telephony enabled state of the Internet Box (1 for Enabled, 0 for Disabled)",
                )
                continue  # skip the Internet Box itself
            labels = {"Name": device["Name"], "Key": device["Key"]}
            if "IPAddress" in device:
                labels.update({"IP": device["IPAddress"]})
            if "Manufacturer" in device:
                labels.update({"Manufacturer": device["Manufacturer"]})
            if "ModelName" in device:
                labels.update({"ModelName": device["ModelName"]})
            if "PhysAddress" in device:
                labels.update({"MAC": device["PhysAddress"]})
            # only wireless devices have these fields
            if "DiscoveredDeviceName" in device:
                labels.update({"DiscoveredDeviceName": device["DiscoveredDeviceName"]})
            if "DiscoveredDeviceType" in device:
                labels.update({"DiscoveredDeviceType": device["DiscoveredDeviceType"]})

            # only wireless devices have these fields
            if "SignalStrength" in device:
                col.update_gauge(
                    name="internetbox_device_signal_strength",
                    value=device["SignalStrength"],
                    labels=labels,
                    description="Signal strength of connected device in dBm",
                )
            if "SignalNoiseRatio" in device:
                col.update_gauge(
                    name="internetbox_device_signal_noise_ratio_db",
                    value=device["SignalNoiseRatio"],
                    labels=labels,
                    description="Signal-to-noise ratio of connected device in dB",
                )

            for bandwidth_type in device.get("Bandwidth", {}):
                if bandwidth_type["Id"] == "Last1Day":
                    col.update_gauge(
                        name="internetbox_device_rx_bandwidth_lastday_bytes",
                        value=bandwidth_type["RxBytes"],
                        labels={**labels, "Id": "Last1Day"},
                        description="Bandwidth received from device in bytes over the last day",
                    )
                    col.update_gauge(
                        name="internetbox_device_tx_bandwidth_lastday_bytes",
                        value=bandwidth_type["TxBytes"],
                        labels={**labels, "Id": "Last1Day"},
                        description="Bandwidth transmitted by device in bytes over the last day",
                    )
                elif bandwidth_type["Id"] == "Last1Week":
                    col.update_gauge(
                        name="internetbox_device_rx_bandwidth_lastweek_bytes",
                        value=bandwidth_type["RxBytes"],
                        labels={**labels, "Id": "Last1Week"},
                        description="Bandwidth received from device in bytes over the last week",
                    )
                    col.update_gauge(
                        name="internetbox_device_tx_bandwidth_lastweek_bytes",
                        value=bandwidth_type["TxBytes"],
                        labels={**labels, "Id": "Last1Week"},
                        description="Bandwidth transmitted by device in bytes over the last week",
                    )
                elif bandwidth_type["Id"] == "Last1Month":
                    col.update_gauge(
                        name="internetbox_device_rx_bandwidth_lastmonth_bytes",
                        value=bandwidth_type["RxBytes"],
                        labels={**labels, "Id": "Last1Month"},
                        description="Bandwidth received from device in bytes over the last month",
                    )
                    col.update_gauge(
                        name="internetbox_device_tx_bandwidth_lastmonth_bytes",
                        value=bandwidth_type["TxBytes"],
                        labels={**labels, "Id": "Last1Month"},
                        description="Bandwidth transmitted by device in bytes over the last month",
                    )

            for user_agent in device.get("UserAgents", []):
                col.update_gauge(
                    name="internetbox_device_user_agent_count",
                    value=len(device.get("UserAgents", [])),
                    labels={**labels, "Type": user_agent["Type"]},
                    description="Number of connections from device with this user agent string and type",
                )

    # ── Temperature sensors ──────────────────────────────────────────
    @collector.register_collector
    def collect_temperature(col: InternetBoxCollector) -> None:
        data = json.loads(client.temperature.sensor())
        for sensor_name, sensor in data.get("status", {}).items():
            col.update_gauge(
                name="internetbox_temperature_celsius",
                value=sensor["Value"],
                labels={"sensor": sensor_name, "status": sensor["Status"]},
                description="Hardware temperature sensor reading in °C",
            )

    # ── Wi-Fi signal strength ───────────────────────────────────────
    @collector.register_collector
    def collect_wifi_signal(col: InternetBoxCollector) -> None:
        for radio_id in range(2):
            data = json.loads(client.wifi.latest_power(radio_id))
            for antenna, value in data.get("status", {}).items():
                col.update_gauge(
                    name="internetbox_wifi_signal_dbm",
                    value=value,
                    labels={"antenna": antenna, "radio_id": str(radio_id)},
                    description="Wi-Fi signal strength in dBm",
                )

    # ── Wi-Fi radio settings ─────────────────────────────────────────
    @collector.register_collector
    def collect_wifi_radio(col: InternetBoxCollector) -> None:
        for radio_id in range(2):
            data = json.loads(client.wifi.radio(radio_id))
            status = data.get("status", {})
            labels = {"name": status["Name"], "radio_id": str(radio_id)}
            col.update_gauge(
                name="internetbox_wifi_noise_dbm", value=status["Noise"], labels=labels, description="Wi-Fi noise level in dBm"
            )
            col.update_gauge(name="internetbox_wifi_channel", value=status["Channel"], labels=labels, description="Wi-Fi channel")
            col.update_gauge(
                name="internetbox_wifi_status",
                value=1 if status["RadioStatus"] == "Up" else 0,
                labels=labels,
                description="Wi-Fi radio up (1) or down (0)",
            )
            col.update_gauge(
                name="internetbox_wifi_channel_load", value=status["ChannelLoad"], labels=labels, description="Wi-Fi channel load in %"
            )
            col.update_gauge(
                name="internetbox_wifi_interference", value=status["Interference"], labels=labels, description="Wi-Fi interference in %"
            )

    # ── Wi-Fi Spectrum Info ───────────────────────────────────────
    @collector.register_collector
    def collect_wifi_spectrum(col: InternetBoxCollector) -> None:
        for radio_id in range(2):
            data = json.loads(client.wifi.spectrum_info(radio_id))
            for channel in data.get("status", []):
                labels = {
                    "radio_id": str(radio_id),
                    "isBanned": str(channel["isBanned"]),
                    "bandwidth": str(channel["bandwidth"]),
                    "channel": str(channel["channel"]),
                }
                col.update_gauge(
                    name="internetbox_wifi_spectrum_availability",
                    value=channel["availability"],
                    labels=labels,
                    description="Wi-Fi spectrum availability in %",
                )
                col.update_gauge(
                    name="internetbox_wifi_spectrum_noise_dbm",
                    value=channel["noiselevel"],
                    labels=labels,
                    description="Wi-Fi spectrum noise level in dBm",
                )

    # ── DNS status ───────────────────────────────────────────
    @collector.register_collector
    def collect_dns_status(col: InternetBoxCollector) -> None:
        data = json.loads(client.dns.settings())
        for name, setting in data.get("status", {}).items():
            col.update_gauge(
                name="internetbox_dns_server_enabled",
                value=1 if setting["Status"] == "Enabled" else 0,
                labels={"setting": name, "dns": setting["DNS"]},
                description="DNS server enabled (1) or disabled (0)",
            )

    # ── Crash Reports ───────────────────────────────────────────
    @collector.register_collector
    def collect_crash_reports(col: InternetBoxCollector) -> None:
        data = json.loads(client.oops_tracker.status())
        col.update_gauge(
            name="internetbox_crash_report_count",
            value=data["status"]["Count"],
            labels=None,
            description="Number of crash reports collected by the Internet Box",
        )

    # ── Port Forwarding Rules ───────────────────────────────────────────
    @collector.register_collector
    def collect_port_forwarding(col: InternetBoxCollector) -> None:
        data = json.loads(client.firewall.port_forwarding())
        col.update_gauge(
            name="internetbox_firewall_port_forwarding_rules_count",
            value=len(data.get("status", [])),
            labels=None,
            description="Number of port forwarding rules",
        )
        for rule in data.get("status", {}).values():
            col.update_gauge(
                name="internetbox_firewall_port_forwarding_rule_enabled",
                value=1 if rule["Status"] == "Enabled" else 0,
                labels={
                    "Id": rule["Id"].replace("webui_", ""),  # remove "webui_" prefix from rule ID for cleaner labels
                    "ExternalPort": rule["ExternalPort"],
                    "InternalPort": rule["InternalPort"],
                    "DestinationIPAddress": rule["DestinationIPAddress"],
                },
                description="Port forwarding rule enabled (1) or disabled (0)",
            )

    # ── LAN Ports ───────────────────────────────────────────
    @collector.register_collector
    def collect_lan_ports(col: InternetBoxCollector) -> None:
        for port_id in range(5):
            data = json.loads(client.lan.ethernet_port(port=port_id))
            port = data.get("status", {})
            labels = {
                "Name": port["Name"],
                "MaxBitRateSupported": str(port["MaxBitRateSupported"]),
                "PortState": port["PortState"],
                "CurrentDuplexMode": port["CurrentDuplexMode"],
            }
            col.update_gauge(
                name="internetbox_lan_port_active",
                value=1 if port["Active"] else 0,
                labels=labels,
                description="LAN port link status (1 for Up, 0 for Down)",
            )
            col.update_gauge(
                name="internetbox_lan_port_current_bitrate_mbps",
                value=port["CurrentBitRate"],
                labels=labels,
                description="LAN port current link speed in Mbps",
            )

    # ── VPN ───────────────────────────────────────────
    @collector.register_collector
    def collect_vpn(col: InternetBoxCollector) -> None:
        data = json.loads(client.vpn.servers_config())
        for server in data.get("data", {}).get("config", {}).get("Server", []):
            labels = {"server": server["Name"]}
            col.update_gauge(
                name="internetbox_vpn_server_enabled",
                value=1 if server["Enable"] else 0,
                labels=labels,
                description="VPN server enabled (1) or disabled (0)",
            )
            clients = server.get("Client", [])
            col.update_gauge(
                name="internetbox_vpn_clients_enabled_count",
                value=sum(1 for c in clients if c["Enable"]),
                labels=labels,
                description="Number of enabled VPN client accounts",
            )
            col.update_gauge(
                name="internetbox_vpn_clients_disabled_count",
                value=sum(1 for c in clients if not c["Enable"]),
                labels=labels,
                description="Number of disabled VPN client accounts",
            )
            col.update_gauge(
                name="internetbox_vpn_clients_connected_count",
                value=sum(1 for c in clients if c["Connected"]),
                labels=labels,
                description="Number of currently connected VPN clients",
            )

    # ── WireGuard ───────────────────────────────────────────
    @collector.register_collector
    def collect_wireguard(col: InternetBoxCollector) -> None:
        data = json.loads(client.wireguard.server_status())
        for key, server in data.get("status", {}).items():
            if not server:  # skip empty entries like "WireGuard.Server."
                continue
            alias = server.get("Alias", key)
            col.update_gauge(
                name="internetbox_wireguard_server_enabled",
                value=1 if server["Enable"] else 0,
                labels={"alias": alias, "listen_port": str(server["ListenPort"])},
                description="WireGuard server enabled (1) or disabled (0)",
            )

        data = json.loads(client.wireguard.clients())
        # Group clients by server ID (e.g. "WireGuard.Server.1.Client.2." → server "1")
        servers: dict[str, list[dict]] = {}
        for key, client_obj in data.get("status", {}).items():
            if not client_obj:
                continue
            # key format: "WireGuard.Server.<id>.Client.<id>."
            parts = key.split(".")
            server_id = parts[2] if len(parts) > 2 else "unknown"
            servers.setdefault(server_id, []).append(client_obj)

        for server_id, clients in servers.items():
            labels = {"server_id": server_id}
            col.update_gauge(
                name="internetbox_wireguard_clients_enabled_count",
                value=sum(1 for c in clients if c["Enable"]),
                labels=labels,
                description="Number of enabled WireGuard clients",
            )
            col.update_gauge(
                name="internetbox_wireguard_clients_disabled_count",
                value=sum(1 for c in clients if not c["Enable"]),
                labels=labels,
                description="Number of disabled WireGuard clients",
            )

    # ── VEIP (XGS-PON optical interface) ────────────────────────────
    @collector.register_collector
    def collect_veip(col: InternetBoxCollector) -> None:
        data = json.loads(client.sysbus.veip())
        veip = data.get("status", {})
        if not veip:
            return
        labels = {"name": veip["Name"], "pon_mode": veip["PonMode"], "serial_number": veip["SerialNumber"]}
        col.update_gauge(
            name="internetbox_veip_enabled",
            value=1 if veip["Enable"] else 0,
            labels=labels,
            description="VEIP interface enabled (1) or disabled (0)",
        )
        col.update_gauge(
            name="internetbox_veip_signal_rx_power_dBm",
            value=veip["SignalRxPower"] / 1000,
            labels=labels,
            description="VEIP optical receive power in dBm",
        )
        col.update_gauge(
            name="internetbox_veip_signal_tx_power_dBm",
            value=veip["SignalTxPower"] / 1000,
            labels=labels,
            description="VEIP optical transmit power in dBm",
        )
        col.update_gauge(
            name="internetbox_veip_downstream_max_rate_kbps",
            value=veip["DownstreamMaxRate"],
            labels=labels,
            description="VEIP downstream maximum rate in kbps",
        )
        col.update_gauge(
            name="internetbox_veip_upstream_max_rate_kbps",
            value=veip["UpstreamMaxRate"],
            labels=labels,
            description="VEIP upstream maximum rate in kbps",
        )
        col.update_gauge(
            name="internetbox_veip_downstream_curr_rate_kbps",
            value=veip["DownstreamCurrRate"],
            labels=labels,
            description="VEIP downstream current rate in kbps",
        )
        col.update_gauge(
            name="internetbox_veip_upstream_curr_rate_kbps",
            value=veip["UpstreamCurrRate"],
            labels=labels,
            description="VEIP upstream current rate in kbps",
        )
