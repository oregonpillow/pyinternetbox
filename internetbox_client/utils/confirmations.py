"""The questions to ask before running disruptive methods, shared by the CLI and the MCP server."""

from __future__ import annotations

from collections.abc import Callable, Mapping

# (resource, method): the question, and whether to ask, given all of the method's arguments (defaults included).
QUESTIONS: dict[tuple[str, str], tuple[str, Callable[[Mapping[str, object]], bool]]] = {
    ("nmc", "reboot"): ("Restart the router? Internet, Wi-Fi and phone will be down for a few minutes.", lambda args: True),
    ("nmc", "restore"): (
        "Replace all settings with this backup? The router then restarts: internet, Wi-Fi and phone will be down for a few minutes.",
        lambda args: True,
    ),
    ("wifi", "set_enabled"): (
        "Turn off all Wi-Fi networks? Every wireless device will lose its connection, including this computer if it's on Wi-Fi.",
        lambda args: not args["enable"],
    ),
    ("wifi", "set_network"): (
        "Change the Wi-Fi settings? Wireless devices lose their connection and must reconnect, with the new password if it changed.",
        lambda args: True,
    ),
    ("wifi", "set_guest_network"): (
        "Change the guest Wi-Fi settings? Devices on the guest network must reconnect, with the new password if it changed.",
        lambda args: True,
    ),
    ("wifi", "set_guest_enabled"): ("Turn off the guest Wi-Fi? Devices on it will lose their connection.", lambda args: not args["enable"]),
    ("wifi", "set_channel"): (
        "Change the Wi-Fi channel? Devices on this band lose their connection for a moment, and for about a minute on 5 GHz "
        "channels 52 to 112, where the router first listens for radar.",
        lambda args: True,
    ),
    ("wifi", "search_channel"): (
        "Let the router choose a new Wi-Fi channel now? If it changes, devices on this band lose their connection for a moment.",
        lambda args: True,
    ),
    ("wifi", "set_steering_enabled"): (
        "Turn band steering on? The router then moves wireless devices between bands, and they lose their connection for a "
        "moment when it does.",
        lambda args: bool(args["enable"]),
    ),
    ("wifi", "set_standard"): (
        "Change the Wi-Fi standard? Devices on this band may lose their connection for a moment.",
        lambda args: True,
    ),
    ("dns", "set_upstream_servers"): (
        "Change the DNS servers the router asks? If they don't answer, devices on the home network can't look up names, so "
        "the internet seems down.",
        lambda args: True,
    ),
    ("scheduler", "set_wifi_schedule"): (
        "Turn Wi-Fi off on a schedule? During the off periods, every wireless device loses its connection, including this "
        "computer if it's on Wi-Fi.",
        lambda args: bool(args["enable"]) and bool(args["off_periods"]),
    ),
    ("scheduler", "enable_wifi_schedule"): (
        "Turn on the Wi-Fi schedule? During its off periods, every wireless device loses its connection, including this "
        "computer if it's on Wi-Fi.",
        lambda args: bool(args["enable"]),
    ),
    ("firewall", "set_custom_policy"): (
        "Block all outgoing traffic that no custom rule allows? While the firewall level is Custom, devices then lose "
        "internet access except for the ports that rules allow.",
        lambda args: args["action"] == "block" and args["direction"] == "outbound",
    ),
    ("wireguard", "set_server_enabled"): (
        "Turn off the WireGuard VPN server? Connected VPN clients lose their connection.",
        lambda args: not args["enable"],
    ),
    ("voice", "clear_call_list"): ("Delete all calls from the call list? They can't be brought back.", lambda args: True),
    ("firewall", "delete_all_port_forwarding"): (
        "Delete all port forwarding rules? They can't be brought back. Ports that devices opened themselves with UPnP stay open.",
        lambda args: True,
    ),
    ("devices", "reset_traffic_counters"): (
        "Set every device's traffic counters for the last day, week and month to 0? The old counts can't be brought back.",
        lambda args: True,
    ),
}


def question(resource: str, method: str, args: Mapping[str, object]) -> str | None:
    """The question to ask before resource.method runs with these arguments, or None if it needs none.

    Args:
        resource (str): resource name, e.g. "wifi".
        method (str): method name, e.g. "set_enabled".
        args (Mapping): all of the method's arguments, defaults included.
    """
    entry = QUESTIONS.get((resource, method))
    return entry[0] if entry and entry[1](args) else None
