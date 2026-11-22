"""Tests for the read/write/disruptive labels on resource methods."""

from __future__ import annotations

import collections.abc
import inspect
import re
import typing
from unittest.mock import MagicMock

import pytest

import internetbox_client.resources as resources
from internetbox_client import InternetBoxClient
from internetbox_client.utils.APIClient import APIClient, SessionManager
from internetbox_client.utils.labels import action, disruptive, has_secret_result, secret_result, write


def _methods() -> list[tuple[type, str]]:
    """Every public resource method, e.g. (Wifi, "set_network"). Devices.get counts: it replaces APIClient.get."""
    found = []
    for class_name in resources.__all__:
        cls = getattr(resources, class_name)
        for name, _ in inspect.getmembers(cls, inspect.isfunction):
            if not name.startswith("_") and (name not in APIClient.__dict__ or name in cls.__dict__):
                found.append((cls, name))
    return found


def _example(annotation: object) -> object:
    """A value for a required argument that the methods accept without contacting the router."""
    if typing.get_origin(annotation) is typing.Literal:
        return typing.get_args(annotation)[0]
    origin = typing.get_origin(annotation) or annotation
    if origin in (list, collections.abc.Sequence):
        return []
    return {str: "AA:BB:CC:DD:EE:FF", int: 0, float: 0.0, bool: True}[origin]


# Router functions that only read, e.g. getMIBs, listTrunks, statsMST, readLogs, or the event channels' get_events.
_READS = re.compile(r"_?(get|list|stats|read|next|has|topology|open_channel|subscribe|unsubscribe|teststatus)", re.IGNORECASE)


def _function(call: tuple) -> str | None:
    """The router function a recorded SessionManager call runs, e.g. "getMIBs"; None for downloads and GET requests."""
    name, args, kwargs = call
    if name in ("get", "download"):
        return None
    if name == "upload":
        return "upload"
    endpoint, data = args[0], args[1] if len(args) > 1 else kwargs.get("data")
    return data["method"] if endpoint == "/ws" else endpoint.rsplit(":", 1)[-1]


@pytest.mark.parametrize(
    ("cls", "name"), [m for m in _methods() if action(getattr(m[0], m[1])) == "read"], ids=lambda v: getattr(v, "__name__", v)
)
def test_methods_without_a_label_only_read(cls: type, name: str) -> None:
    """A method that changes something must be labelled @write or @disruptive, or it would count as read-only."""
    sm = MagicMock(spec=SessionManager)
    sm.get.return_value = sm.post.return_value = sm.download.return_value = '{"status": {}}'
    resource = cls(sm)
    method = getattr(resource, name)
    parameters = inspect.signature(method, eval_str=True).parameters.values()
    method(**{p.name: _example(p.annotation) for p in parameters if p.default is inspect.Parameter.empty})
    functions = [_function(call) for call in sm.method_calls]
    assert functions, "made no request"
    assert all(function is None or _READS.match(function) for function in functions), functions


@pytest.mark.parametrize(
    ("method", "expected"),
    [
        ("devices.get", "read"),
        ("devices.summary", "read"),
        ("wifi.status", "read"),
        ("devices.block", "write"),
        ("firewall.set_port_forwarding", "write"),
        ("speedtest.start", "write"),
        ("wifi.start_wps_pairing", "write"),
        ("nmc.reboot", "disruptive"),
        ("nmc.restore", "disruptive"),
        ("wifi.set_enabled", "disruptive"),
        ("wifi.set_network", "disruptive"),
        ("wifi.set_guest_network", "disruptive"),
        ("wifi.set_guest_enabled", "disruptive"),
        ("wifi.set_channel", "disruptive"),
        ("wifi.search_channel", "disruptive"),
        ("firewall.custom_rules", "read"),
        ("firewall.custom_policy", "read"),
        ("firewall.set_custom_rule", "write"),
        ("firewall.enable_custom_rule", "write"),
        ("firewall.delete_custom_rule", "write"),
        ("firewall.set_custom_policy", "disruptive"),
        ("dyndns.set_host", "write"),
        ("dyndns.delete_host", "write"),
        ("nmc.set_static_route", "write"),
        ("nmc.delete_static_route", "write"),
        ("scheduler.wifi_schedule", "read"),
        ("scheduler.set_wifi_schedule", "disruptive"),
        ("scheduler.enable_wifi_schedule", "disruptive"),
        ("scheduler.remove_wifi_schedule", "write"),
        ("power_management.set_wifi_6ghz_power_saving", "write"),
        ("wireguard.add_client", "write"),
        ("wireguard.set_client", "write"),
        ("wireguard.delete_client", "write"),
        ("wireguard.set_server_enabled", "disruptive"),
        ("dns.metrics", "read"),
        ("dns.set_cache_enabled", "write"),
        ("dns.set_upstream_servers", "disruptive"),
        ("devices.reset_name", "write"),
        ("devices.set_type", "write"),
        ("devices.set_dns_name", "write"),
        ("devices.remove_dns_name", "write"),
        ("devices.reset_traffic_counters", "write"),
        ("devices.clear_traffic_history", "write"),
        ("debug.save_log_file", "write"),
        ("debug.save_wifi_logs", "write"),
        ("firewall.delete_all_port_forwarding", "write"),
        ("firewall.respond_to_ping", "read"),
        ("firewall.set_respond_to_ping", "write"),
        ("firewall.protocol_forwarding", "read"),
        ("firewall.set_protocol_forwarding", "write"),
        ("firewall.delete_protocol_forwarding", "write"),
        ("firewall.ipv6_pinholes", "read"),
        ("firewall.set_ipv6_pinhole", "write"),
        ("firewall.delete_ipv6_pinhole", "write"),
        ("wifi.set_steering_enabled", "disruptive"),
        ("wifi.set_wlan_box_sync", "write"),
        ("wifi.set_standard", "disruptive"),
        ("wifi.set_device_steering", "write"),
        ("dhcp.static_leases", "read"),
        ("dhcp.add_static_lease", "write"),
        ("dhcp.ipv6_server_status", "read"),
        ("dyndns.set_enabled", "write"),
        ("firewall.upnp_description", "read"),
        ("scheduler.override_device_schedule", "write"),
        ("wireguard.set_enabled", "disruptive"),
        ("nmc.wan_mtu", "read"),
        ("nmc.reboot_info", "read"),
        ("nmc.reboot_history", "read"),
    ],
)
def test_labels(method: str, expected: str) -> None:
    client = InternetBoxClient(hostname="192.0.2.1", ssl_verify=False)
    group, name = method.split(".")
    assert action(getattr(getattr(client, group), name)) == expected  # bound methods have their function's label


def test_secret_results() -> None:
    assert {f"{cls.__name__}.{name}" for cls, name in _methods() if has_secret_result(getattr(cls, name))} == {
        "DECT.pin",
        "NMC.backup",
        "Wireguard.add_client",
    }


def test_decorators_return_the_method() -> None:
    def method() -> str:
        return "ok"

    assert write(method) is method and action(method) == "write"
    assert disruptive(method) is method and action(method) == "disruptive"
    assert secret_result(method) is method and has_secret_result(method)
    assert action(lambda: None) == "read" and not has_secret_result(lambda: None)
