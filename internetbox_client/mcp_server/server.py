"""The MCP server behind `ibox mcp`: tools for an AI app to look at the router and, when allowed, change its settings.

Reads are always offered. Changes need --allow-writes, and changes that cut the Wi-Fi or internet for others need
--allow-disruptive. Those ask the user first, in the app, and are refused in apps that can't ask.

This module needs the optional `mcp` dependency: pip install "pyinternetbox[mcp]".
"""

# No `from __future__ import annotations` here: the SDK reads the tools' annotations, which name resolvers defined
# inside build_server(), so they must be evaluated where they are written.

import contextlib
import functools
import inspect
import ipaddress
import json
import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated, Any, Literal

import requests
from mcp.server.mcpserver import AcceptedElicitation, Context, Elicit, ElicitationResult, MCPServer, Resolve
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import BaseModel, Field

from internetbox_client import InternetBoxClient, __version__
from internetbox_client.mcp_server.catalog import Function, functions, groups
from internetbox_client.mcp_server.metrics import MetricsSender
from internetbox_client.resources.scheduler import WEEK
from internetbox_client.utils.confirmations import question
from internetbox_client.utils.helpers import hide_secrets, normalize_mac
from internetbox_client.utils.labels import Action

# Longer answers are cut off: they would fill the model's context. devices.get() alone is 130 KB.
MAX_CHARS = 25_000
# The speed test takes about 50 s. Its results only show while it runs: the router doesn't keep them.
SPEED_TEST_POLL_SECONDS = 1.0
SPEED_TEST_TIMEOUT_SECONDS = 180.0
SPEED_TEST_START_SECONDS = 15.0
_SPEED_TEST_RESULTS = {"ping": "ping_ms", "download": "download_mbps", "upload": "upload_mbps"}

_DAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
_PROTOCOLS = {"6": "tcp", "17": "udp", "6,17": "both"}

# What the confirmation resolvers return instead of asking.
_NOT_NEEDED = "not needed"
_CANT_ASK = "can't ask"


@dataclass(frozen=True)
class Options:
    """What `ibox mcp` allows, from its flags."""

    allow_writes: bool = False
    allow_disruptive: bool = False  # implies allow_writes
    show_secrets: bool = False

    @property
    def actions(self) -> frozenset[Action]:
        """What the tools may do to the router."""
        if self.allow_disruptive:
            return frozenset({"read", "write", "disruptive"})
        return frozenset({"read", "write"}) if self.allow_writes else frozenset({"read"})


class Confirmation(BaseModel):
    """The form shown to the user before a disruptive change."""

    confirm: bool = Field(default=True, title="Go ahead", description="Untick or decline to cancel.")


class TimePeriod(BaseModel):
    """A period of the week, e.g. Monday 22:00 to Tuesday 07:00."""

    begin: str | int = Field(description='A day and time, e.g. "Mon 22:00", or seconds since Monday 00:00.')
    end: str | int = Field(description='A day and time, e.g. "Tue 07:00". "Sun 24:00" is the end of the week.')


class _Refused(ToolError):
    """A change the server doesn't allow, e.g. without --allow-disruptive."""


Device = Annotated[str, Field(description="The device's name, MAC address or IP address, as list_devices shows them.")]


# ── Helpers ──────────────────────────────────────────────────────────────


def _decode(raw: Any) -> Any:
    if not isinstance(raw, str):
        return raw
    try:
        return json.loads(raw)
    except ValueError:
        return raw


def _body(raw: Any) -> Any:
    """The useful part of a response: {"status": X} gives X, and {"status": true, "data": X} gives X."""
    data = _decode(raw)
    if isinstance(data, dict) and data and set(data) <= {"status", "data"}:
        return data["data"] if "data" in data else data["status"]
    return data


def _text(data: Any) -> str:
    """Compact JSON for the model, cut off at MAX_CHARS."""
    text = data if isinstance(data, str) else json.dumps(data, ensure_ascii=False, separators=(",", ":"), default=str)
    if len(text) > MAX_CHARS:
        text = (
            f"{text[:MAX_CHARS]}\n[Cut off after {MAX_CHARS} of {len(text)} characters. "
            "Ask for less, e.g. with a function that returns a summary.]"
        )
    return text


def _week_time(seconds: int) -> str:
    """Seconds since Monday 00:00 as e.g. "Tue 07:30". The end of the week is "Sun 24:00"."""
    if seconds and seconds % WEEK == 0:
        return "Sun 24:00"
    day, rest = divmod(int(seconds) % WEEK, 86400)
    return f"{_DAYS[day]} {rest // 3600:02d}:{rest % 3600 // 60:02d}"


def _duration(seconds: int) -> str:
    days, rest = divmod(int(seconds), 86400)
    hours, rest = divmod(rest, 3600)
    return f"{days} d {hours} h {rest // 60} min" if days else f"{hours} h {rest // 60} min"


def _note_speed(event: dict, result: dict[str, float], finished: set[str]) -> None:
    """Add a speed test status to the result, e.g. {"event": "DOWNLOAD_DONE", "average": 940.5} as download_mbps."""
    name = str(event.get("event") or "").lower()
    phase = next((phase for phase in _SPEED_TEST_RESULTS if phase in name), None)
    if phase is None or phase in finished:
        return
    value = event.get("average") if name.endswith("_done") else event.get("current_value")
    if isinstance(value, int | float):
        result[_SPEED_TEST_RESULTS[phase]] = round(value, 1)
    if name.endswith("_done"):
        finished.add(phase)


def _friendly(exc: Exception, host: str) -> str:
    """What went wrong, for the model, like the CLI's error messages."""
    if isinstance(exc, requests.exceptions.SSLError):
        return f"SSL error talking to the router at {host}: {exc}"
    if isinstance(exc, requests.exceptions.ReadTimeout):
        return f"The router at {host} accepted the connection but didn't answer in time."
    if isinstance(exc, requests.exceptions.ConnectionError):
        return f"Could not connect to the router at {host}: {exc}"
    if isinstance(exc, requests.exceptions.HTTPError):
        message = f"The router rejected the request: {exc}"
        if exc.response is not None and exc.response.status_code == 401:
            message += "\nIf every request fails like this, the router password (IB_PASSWORD) is wrong."
        return message
    if isinstance(exc, ValueError):  # invalid input caught by the library, e.g. a malformed MAC address
        return str(exc)
    return f"{type(exc).__name__}: {exc}"


def _client_name(ctx: Context) -> str:
    """The AI app's name from the MCP handshake, e.g. "opencode"."""
    with contextlib.suppress(Exception):
        return ctx.session.client_params.client_info.name or "unknown"
    return "unknown"


def _can_ask(ctx: Context) -> bool:
    """Whether the app can show the user a form (MCP elicitation)."""
    capabilities = ctx.client_capabilities
    elicitation = capabilities.elicitation if capabilities is not None else None
    return elicitation is not None and (elicitation.form is not None or elicitation.url is None)


def _confirmation(ctx: Context, text: str | None, details: dict[str, Any]) -> Any:
    """A resolver's answer: ask the question in *text*, if there is one and the app can ask."""
    if text is None:
        return _NOT_NEEDED
    if not _can_ask(ctx):
        return _CANT_ASK
    shown = {name: value for name, value in hide_secrets(details).items() if value is not None}
    if shown:
        text += "\n\n" + ", ".join(f"{name}: {json.dumps(value, ensure_ascii=False, default=str)}" for name, value in shown.items())
    return Elicit(text, Confirmation)


def _confirmed(confirmation: Any) -> bool:
    """Whether a tool may go ahead. Raises _Refused if it needed the user's answer and the app couldn't ask."""
    if not isinstance(confirmation, AcceptedElicitation):
        return False  # declined or cancelled
    if confirmation.data == _CANT_ASK:
        raise _Refused(
            "Not done: this change needs the user's confirmation, and this app can't ask for it (MCP elicitation). "
            "The user can make the change with the ibox command line tool or the router's web interface."
        )
    return confirmation.data == _NOT_NEEDED or (isinstance(confirmation.data, Confirmation) and confirmation.data.confirm)


def _instrument(
    fn: Callable[..., str], action: Action, function: str | None, catalog: dict[str, Function], metrics: MetricsSender | None, host: str
) -> Callable[..., str]:
    """Wrap a tool: handle its confirmation, turn errors into messages for the model and send a usage event.

    Args:
        function (str | None): the library function the tool calls, e.g. "wifi.set_enabled"; None for the general tools,
            which call the one in their "function" argument.
    """
    signature = inspect.signature(fn)

    @functools.wraps(fn)
    def tool(*args: Any, **kwargs: Any) -> str:
        arguments = signature.bind(*args, **kwargs).arguments
        called, called_action = function or "", action
        if function is None and arguments.get("function") in catalog:
            called, called_action = arguments["function"], catalog[arguments["function"]].action
        started, outcome = time.monotonic(), "error"
        try:
            if "confirmation" in arguments and not _confirmed(arguments["confirmation"]):
                outcome = "declined"
                return "Not done: the user said no."
            result = fn(*args, **kwargs)
            outcome = "ok"
            return result
        except _Refused:
            outcome = "refused"
            raise
        except ToolError:
            raise
        except Exception as exc:  # noqa: BLE001 - the SDK would hide the message: the model needs it to correct itself
            raise ToolError(_friendly(exc, host)) from exc
        finally:
            if metrics is not None:
                metrics.send(
                    {
                        "tool": fn.__name__,
                        "function": called,
                        "action": called_action,
                        "outcome": outcome,
                        "duration_seconds": round(time.monotonic() - started, 4),
                        "client": _client_name(arguments["ctx"]),
                        "server_version": __version__,
                    }
                )

    return tool


def _instructions(options: Options) -> str:
    if options.allow_disruptive:
        changes = (
            "Changes are allowed. Those that cut the Wi-Fi or internet for others, e.g. a restart, ask the user to confirm "
            "in the app first, and are refused in apps that can't ask."
        )
    elif options.allow_writes:
        changes = (
            "Changes are allowed, except those that cut the Wi-Fi or internet for others, e.g. turning Wi-Fi off, new "
            "Wi-Fi settings or a restart: those need the server to be started with --allow-disruptive."
        )
    else:
        changes = "The server is read-only: changing settings needs it to be started with --allow-writes."
    secrets = (
        "Passwords and keys are shown."
        if options.show_secrets
        else 'Passwords and keys show as "<hidden>": the server must be started with --show-secrets to show them.'
    )
    return (
        "Tools for the user's Internet Box router (Swisscom, Wingo) on their home network. Devices can be given by "
        f"name, MAC address or IP address, as list_devices shows them. {changes} {secrets} For anything the other tools "
        "don't cover, use list_router_functions, then call_router_function to read"
        + (" or change_router_setting to change a setting." if "write" in options.actions else ".")
    )


# ── The server ───────────────────────────────────────────────────────────


def build_server(client: InternetBoxClient, options: Options | None = None, metrics: MetricsSender | None = None) -> MCPServer:
    """The MCP server for a client, with the tools *options* allow."""
    options = options or Options()
    catalog = functions(client)
    resources = groups(client)
    host = client._sm.base_url
    server = MCPServer(name="ibox", title="Internet Box", instructions=_instructions(options), version=__version__, log_level="WARNING")

    def add(
        fn: Callable[..., str], action: Action, function: str | None = "", *, destructive: bool = False, idempotent: bool = True
    ) -> None:
        if action not in options.actions:
            return
        hints = ToolAnnotations(
            read_only_hint=action == "read", destructive_hint=destructive, idempotent_hint=idempotent, open_world_hint=False
        )
        # The model gets docstrings as flowing text, without their line breaks.
        description = re.sub(r"(?<!\n)\n(?!\n)", " ", inspect.cleandoc(fn.__doc__ or ""))
        tool = _instrument(fn, action, function, catalog, metrics, host)
        server.add_tool(tool, description=description, annotations=hints, structured_output=False)

    last_speed_test: dict[str, Any] = {}

    def shown(data: Any) -> str:
        return _text(data if options.show_secrets else hide_secrets(data))

    def device_list() -> list[dict]:
        return json.loads(client.devices.summary())

    def find_device(query: str) -> dict:
        """The device with this name, MAC address or IP address, from devices.summary()."""
        query = query.strip()
        devices = device_list()
        with contextlib.suppress(ValueError):
            mac = normalize_mac(query)
            return next((d for d in devices if (d.get("mac") or "").upper() == mac), {"name": None, "mac": mac, "ip": None})
        folded = query.casefold()
        matches = (
            [d for d in devices if d.get("ip") == query]
            or [d for d in devices if (d.get("name") or "").casefold() == folded]
            or [d for d in devices if folded in (d.get("name") or "").casefold()]
        )
        if not matches:
            raise ToolError(f"No device matches {query!r}. list_devices shows the devices' names, MAC and IP addresses.")
        if len(matches) > 1:
            found = "; ".join(f"{d.get('name')} ({d.get('mac')}, {d.get('ip') or 'no IP'})" for d in matches)
            raise ToolError(f"{query!r} matches several devices: {found}. Give the MAC address instead.")
        return matches[0]

    def label(device: dict) -> str:
        return f"{device['name']} ({device['mac']})" if device.get("name") else device["mac"]

    def names() -> dict[str, str]:
        """Device names by MAC address, upper case."""
        with contextlib.suppress(Exception):
            return {(d.get("mac") or "").upper(): d.get("name") for d in device_list()}
        return {}

    def done(message: str, raw: Any) -> str:
        return f"{message}\nRouter's answer: {shown(_decode(raw))}"

    def part(read: Callable[[], Any]) -> Any:
        """One part of a combined answer: a failing part shows its error instead of failing the whole answer."""
        try:
            return read()
        except Exception as exc:  # noqa: BLE001
            return {"error": _friendly(exc, host)}

    # ── Reads ────────────────────────────────────────────────────────────

    def router_overview(ctx: Context) -> str:
        """An overview of the router: model, firmware, uptime, internet connection and public IP addresses, whether
        Wi-Fi and guest Wi-Fi are on, how many devices are connected and the firewall level. Start here."""

        def router() -> dict:
            info = _body(client.devices.info())
            return {
                "model": info.get("ModelName"),
                "manufacturer": info.get("Manufacturer"),
                "firmware": info.get("SoftwareVersion"),
                "hardware": info.get("HardwareVersion"),
                "uptime": _duration(info.get("UpTime") or 0),
                "status": info.get("DeviceStatus"),
            }

        def internet() -> dict:
            wan = _body(client.nmc.wan_status(details=True))
            return {
                "link": wan.get("LinkType"),
                "link_state": wan.get("LinkState"),
                "connection_state": wan.get("ConnectionState"),
                "interface": part(lambda: _body(client.nmc.status()).get("ActiveWANInterface")),
                "public_ipv4": wan.get("IPAddress") or None,
                "public_ipv6": wan.get("IPv6Address") or None,
            }

        def wifi() -> dict:
            return {
                "wifi_enabled": _body(client.wifi.status()).get("Enable"),
                "guest_wifi_enabled": _body(client.wifi.guest()).get("Enable"),
            }

        def devices() -> dict:
            found = device_list()
            return {"connected": sum(1 for d in found if d.get("connected")), "known": len(found)}

        def firewall() -> dict:
            status = _body(client.firewall.status())
            return {"ipv4_level": status.get("AdvancedLevel"), "ipv6_level": status.get("AdvancedIPv6Level")}

        return shown(
            {"router": part(router), "internet": part(internet), "wifi": part(wifi), "devices": part(devices), "firewall": part(firewall)}
        )

    add(router_overview, "read")

    def list_devices(ctx: Context, connected_only: Annotated[bool, Field(description="Only the devices connected now.")] = False) -> str:
        """The devices on the home network: name, MAC and IP address, type, manufacturer, whether and how they're
        connected (e.g. "Ethernet (ETH4)" or "Wi-Fi 5GHz"), when they last connected, and the Wi-Fi signal in dBm."""
        devices = device_list()
        return shown([d for d in devices if d.get("connected")] if connected_only else devices)

    add(list_devices, "read", "devices.summary")

    def wifi_overview(ctx: Context) -> str:
        """The Wi-Fi networks: name, password, encryption, channel and connected devices of each band, whether Wi-Fi and
        WPS are on, the guest network (on or off, its automatic turn-off) and the Wi-Fi schedule."""
        guest = part(lambda: _body(client.wifi.guest()))
        if isinstance(guest, dict) and "Enable" in guest:
            guest = {
                "enabled": guest.get("Enable"),
                "turns_off_after_hours": guest.get("ActivationTimeout") or None,
                "bandwidth_limit": guest.get("BandwidthLimitation"),
            }
        schedule = part(lambda: _body(client.scheduler.wifi_schedule()))
        if isinstance(schedule, dict) and "schedule" in schedule:
            schedule = {
                "enabled": schedule.get("enable"),
                "wifi_off_now": schedule.get("value") == "Disable",
                "off_periods": [f"{_week_time(p['begin'])} to {_week_time(p['end'])}" for p in schedule.get("schedule") or []],
            }
        elif schedule is False:
            schedule = "none"
        return shown({"wifi": part(lambda: json.loads(client.wifi.summary())), "guest": guest, "schedule": schedule})

    add(wifi_overview, "read", "wifi.summary")

    def internet_status(ctx: Context) -> str:
        """The internet connection: link type and state, public IPv4 and IPv6 addresses, gateway and provider DNS
        servers, and for fiber the optical signal, line rates and traffic since the router started."""
        wan = _body(client.nmc.wan_status(details=True))
        status: dict[str, Any] = {"connection": wan, "interface": part(lambda: _body(client.nmc.status()).get("ActiveWANInterface"))}
        if isinstance(wan, dict) and wan.get("LinkType") == "gpon":
            veip = part(lambda: _body(client.sysbus.veip()))
            if isinstance(veip, dict) and "SignalRxPower" in veip:
                status["fiber"] = {
                    "pon_mode": veip.get("PonMode"),
                    "signal_rx_dbm": veip["SignalRxPower"] / 1000,
                    "signal_tx_dbm": (veip.get("SignalTxPower") or 0) / 1000,
                    "downstream_max_mbps": (veip.get("DownstreamMaxRate") or 0) / 1000,
                    "upstream_max_mbps": (veip.get("UpstreamMaxRate") or 0) / 1000,
                }
                stats = part(lambda: _body(client.sysbus.net_dev_stats(veip.get("Name") or "veip0")))
                if isinstance(stats, dict) and "RxBytes" in stats:
                    status["traffic"] = {
                        "received_gb": round(stats["RxBytes"] / 1e9, 2),
                        "sent_gb": round(stats.get("TxBytes", 0) / 1e9, 2),
                        "errors": stats.get("RxErrors", 0) + stats.get("TxErrors", 0),
                    }
            else:
                status["fiber"] = veip
        return shown(status)

    add(internet_status, "read", "nmc.wan_status")

    def firewall_overview(ctx: Context) -> str:
        """The firewall: IPv4 and IPv6 levels, UPnP, port forwarding rules, DMZ, and the custom rules and policy that
        apply while a level is "Custom"."""

        def levels() -> dict:
            status = _body(client.firewall.status())
            return {
                "ipv4": status.get("AdvancedLevel"),
                "ipv6": status.get("AdvancedIPv6Level"),
                "upnp_port_forwarding": status.get("UpnpPortForwardingEnable"),
            }

        def port_forwards() -> list[dict]:
            rules = _body(client.firewall.port_forwarding()) or {}
            return [
                {
                    "id": rule.get("Id"),
                    "name": rule.get("Description"),
                    "origin": rule.get("Origin"),
                    "enabled": rule.get("Enable"),
                    "status": rule.get("Status"),
                    "protocol": _PROTOCOLS.get(str(rule.get("Protocol")), rule.get("Protocol")),
                    "external_port": rule.get("ExternalPort"),
                    "internal_port": rule.get("InternalPort"),
                    "destination_ip": rule.get("DestinationIPAddress"),
                    "allowed_sources": rule.get("SourcePrefix") or "any",
                }
                for rule in rules.values()
            ]

        return shown(
            {
                "levels": part(levels),
                "port_forwards": part(port_forwards),
                "dmz": part(lambda: _body(client.firewall.dmz()) or "none"),
                "custom_rules": part(lambda: json.loads(client.firewall.custom_rules())),
                "custom_policy": part(lambda: json.loads(client.firewall.custom_policy())),
            }
        )

    add(firewall_overview, "read", "firewall.status")

    def dns_settings(ctx: Context) -> str:
        """DNS: the servers the router gives devices on the home network (by default itself), the servers the router
        asks, and its DNS cache."""

        def servers(raw: str) -> Any:
            return [s for s in str((_body(raw) or {}).get("DNSServers") or "").split(",") if s] or "the router"

        def upstream() -> dict:
            routes = _body(client.dns.settings()) or {}
            return {name: {"server": route.get("DNS"), "status": route.get("Status")} for name, route in routes.items()}

        return shown(
            {
                "devices_get_ipv4": part(lambda: servers(client.dns.user())),
                "devices_get_ipv6": part(lambda: servers(client.dns.user_ipv6())),
                "router_asks": part(upstream),
                "router_mode": part(lambda: _body(client.dns.mode())),
                "cache": part(lambda: _body(client.dns.cache())),
            }
        )

    add(dns_settings, "read", "dns.user")

    def lan_settings(ctx: Context) -> str:
        """The home network: the router's address, the range of addresses it gives out (DHCP), fixed IP addresses
        reserved for devices, and static routes."""
        known = names()

        def fixed_ips() -> list[dict]:
            leases = _body(client.dhcp.static_leases()) or []
            return [
                {"device": known.get(lease["MACAddress"].upper()), "mac": lease["MACAddress"].upper(), "ip": lease["IPAddress"]}
                for lease in leases
            ]

        return shown(
            {
                "lan": part(lambda: _body(client.nmc.lan_ip())),
                "fixed_ips": part(fixed_ips),
                "static_routes": part(lambda: _body(client.nmc.static_routes()) or []),
            }
        )

    add(lan_settings, "read", "nmc.lan_ip")

    def parental_controls(ctx: Context) -> str:
        """Parental controls: each device's internet access schedule (when it's blocked, and whether it's blocked now)
        and daily internet time limits."""
        known = names()

        def schedules() -> list[dict]:
            found = (_body(client.scheduler.complete_schedules("ToD")) or {}).get("scheduleInfo") or []
            return [
                {
                    "device": known.get(str(s.get("ID")).upper()),
                    "mac": s.get("ID"),
                    "enabled": s.get("enable"),
                    "blocked_now": bool(s.get("enable")) and s.get("value") == "Disable",
                    "blocked_periods": [
                        f"{_week_time(p['begin'])} to {_week_time(p['end'])}"
                        for p in s.get("schedule") or []
                        if p.get("state") == "Disable"
                    ],
                }
                for s in found
            ]

        def time_limits() -> list[dict]:
            limits = []
            for mst_id in (_body(client.mst.get()) or {}).get("ids") or []:
                config = _body(client.mst.config(mst_id)) or {}
                mac = str(config.get("subject") or "").removeprefix("MAC:")
                minutes = config.get("allowedTime") or {}
                same = set(minutes.values())
                limits.append(
                    {
                        "device": known.get(mac.upper()),
                        "mac": mac,
                        "enabled": config.get("enable"),
                        "minutes_per_day": same.pop() if len(same) == 1 else minutes,
                    }
                )
            return limits

        return shown({"access_schedules": part(schedules), "daily_time_limits": part(time_limits)})

    add(parental_controls, "read", "scheduler.complete_schedules")

    def remote_access(ctx: Context) -> str:
        """Access from outside: DynDNS host names, and the WireGuard VPN server and its clients."""

        def wireguard_server() -> Any:
            servers = _body(client.wireguard.server_status()) or {}
            return [server for server in servers.values() if server] or "none"

        def wireguard() -> Any:
            app = _body(client.wireguard.app_status()) or {}
            return next((status for status in app.values() if status), app) if isinstance(app, dict) else app

        return shown(
            {
                "dyndns_enabled": part(lambda: _body(client.dyndns.global_enable())),
                "dyndns_hosts": part(lambda: _body(client.dyndns.hosts())),
                "wireguard": part(wireguard),
                "wireguard_server": part(wireguard_server),
                "wireguard_clients": part(lambda: [c for c in (_body(client.wireguard.clients()) or {}).values() if c]),
            }
        )

    add(remote_access, "read", "dyndns.hosts")

    def speed_test_results(ctx: Context) -> str:
        """The speed test running now, if any, and the result of the last test run_speed_test ran. The router doesn't
        keep results of tests run elsewhere, e.g. in the web interface."""
        state = _body(client.speedtest.status()) or {}
        running = isinstance(state, dict) and state.get("event") not in (None, "IDLE")
        return shown({"running_now": state if running else False, "last_result": last_speed_test or "none since the server started"})

    add(speed_test_results, "read", "speedtest.status")

    def list_router_functions(ctx: Context, group: Annotated[str | None, Field(description='A group, e.g. "wifi".')] = None) -> str:
        """The router functions for what the other tools don't cover. Without a group: the groups, e.g. "wifi" or
        "firewall", and their functions. With a group: each function's arguments and description. Then use
        call_router_function to read, or change_router_setting to change a setting."""
        offered = {name: f for name, f in catalog.items() if f.action in options.actions}
        if group is None:
            listing = {}
            for name, resource in resources.items():
                members = [f.method for f in offered.values() if f.group == name]
                if members:
                    listing[name] = {"about": (type(resource).__doc__ or "").strip().split("\n")[0], "functions": members}
            return _text(listing)
        if group not in resources:
            raise ToolError(f"No group {group!r}. The groups: {', '.join(resources)}.")
        return _text(
            [
                {"function": f.usage, "action": f.action, "description": f.doc + (" The result is a secret." if f.secret_result else "")}
                for f in offered.values()
                if f.group == group
            ]
        )

    add(list_router_functions, "read", None)

    def lookup(function: str) -> Function:
        if function not in catalog:
            group = function.split(".", 1)[0]
            hint = f"list_router_functions(group={group!r})" if group in resources else "list_router_functions"
            raise ToolError(f"No function {function!r}. {hint} lists the functions.")
        return catalog[function]

    def call(found: Function, arguments: dict[str, Any] | None) -> str:
        checked = found.arguments(arguments)
        raw = getattr(resources[found.group], found.method)(**checked)
        if found.secret_result and not options.show_secrets:
            return (
                f"Done. The result of {found.name} is a secret, so it's hidden: the server must be started with --show-secrets to show it."
            )
        return shown(_decode(raw))

    def call_router_function(
        ctx: Context,
        function: Annotated[str, Field(description='Group and function, e.g. "wifi.station_stats".')],
        arguments: Annotated[dict[str, Any] | None, Field(description='The function\'s arguments by name, e.g. {"id": 0}.')] = None,
    ) -> str:
        """Call one of the router functions list_router_functions lists, to read something the other tools don't cover."""
        found = lookup(function)
        if found.action != "read":
            raise _Refused(
                f"{function} changes settings: use change_router_setting."
                if found.action in options.actions
                else f"{function} changes settings, and the server doesn't allow that: it must be started with "
                + ("--allow-disruptive." if found.action == "disruptive" else "--allow-writes.")
            )
        return call(found, arguments)

    add(call_router_function, "read", None)

    # ── Writes ───────────────────────────────────────────────────────────

    def rename_device(ctx: Context, device: Device, new_name: Annotated[str, Field(description="The new name.")]) -> str:
        """Rename a device, as shown in the web interface and list_devices."""
        found = find_device(device)
        return done(f"Renamed {label(found)} to {new_name!r}.", client.devices.rename(found["mac"], new_name))

    add(rename_device, "write", "devices.rename")

    def set_device_internet_access(
        ctx: Context, device: Device, allowed: Annotated[bool, Field(description="False blocks the device, True allows it again.")]
    ) -> str:
        """Block or allow a device's internet access, like the web interface's "Internet access blocked" switch.
        Blocking turns the device's parental controls on: a device without an access schedule is blocked all week, one
        with a schedule only when the schedule says so. Allowing turns them off, and keeps the schedule."""
        found = find_device(device)
        raw = client.devices.unblock(found["mac"]) if allowed else client.devices.block(found["mac"])
        return done(f"{'Allowed' if allowed else 'Blocked'} internet access for {label(found)}.", raw)

    add(set_device_internet_access, "write", "devices.block")

    def set_device_schedule(
        ctx: Context,
        device: Device,
        blocked_periods: Annotated[
            list[TimePeriod], Field(description='When it\'s blocked, e.g. [{"begin": "Sun 21:00", "end": "Mon 07:00"}]. [] never blocks.')
        ],
        enabled: Annotated[bool, Field(description="Whether the schedule is on.")] = True,
    ) -> str:
        """Set when a device's internet access is blocked each week (parental controls). Replaces its schedule."""
        found = find_device(device)
        periods = [period.model_dump() for period in blocked_periods]
        return done(
            f"Set the internet access schedule of {label(found)}.", client.scheduler.set_device_schedule(found["mac"], periods, enabled)
        )

    add(set_device_schedule, "write", "scheduler.set_device_schedule")

    def wake_device(ctx: Context, device: Device) -> str:
        """Wake up a device with Wake-on-LAN. The device must support it and have it turned on."""
        found = find_device(device)
        return done(f"Sent a Wake-on-LAN packet to {label(found)}.", client.devices.wake_on_lan(found["mac"]))

    add(wake_device, "write", "devices.wake_on_lan", idempotent=False)

    def forget_device(ctx: Context, device: Device) -> str:
        """Remove an offline device from the device list, with its fixed IP address, schedule and time limit."""
        found = find_device(device)
        return done(f"Removed {label(found)} from the device list.", client.devices.remove(found["mac"]))

    add(forget_device, "write", "devices.remove", destructive=True)

    def set_port_forward(
        ctx: Context,
        name: Annotated[str, Field(description='The rule\'s name, e.g. "minecraft".')],
        device: Annotated[str, Field(description="The device to forward to: its name, MAC address or LAN IP address.")],
        external_port: Annotated[str, Field(description='The port on the internet side, e.g. "25565", or a range, e.g. "8000-8010".')],
        internal_port: Annotated[str | None, Field(description="The port on the device. Default: the same as external_port.")] = None,
        protocol: Literal["tcp", "udp", "both"] = "both",
        enabled: Annotated[bool, Field(description="Whether the rule is on.")] = True,
    ) -> str:
        """Add a port forwarding rule, or change the rule with this name. The device should have a fixed IP address
        (set_fixed_ip), or the rule stops working when its address changes."""
        try:
            ip = target = str(ipaddress.IPv4Address(device.strip()))
        except ValueError:
            found = find_device(device)
            if not found.get("ip"):
                raise ToolError(f"{label(found)} has no IP address. Give its IP address instead.") from None
            ip, target = found["ip"], f"{label(found)} at {found['ip']}"
        raw = client.firewall.set_port_forwarding(name, ip, external_port, internal_port, protocol, enabled)
        return done(f"Port forwarding rule {name!r}: {protocol} port {external_port} to {target}.", raw)

    add(set_port_forward, "write", "firewall.set_port_forwarding")

    def delete_port_forward(
        ctx: Context, name: Annotated[str, Field(description="The rule's name or ID, as firewall_overview shows it.")]
    ) -> str:
        """Delete a port forwarding rule."""
        return done(f"Deleted port forwarding rule {name!r}.", client.firewall.delete_port_forwarding(name))

    add(delete_port_forward, "write", "firewall.delete_port_forwarding", destructive=True)

    def set_fixed_ip(
        ctx: Context, device: Device, ip: Annotated[str, Field(description='An IPv4 address in the home network, e.g. "192.168.1.20".')]
    ) -> str:
        """Reserve an IP address for a device, so it always gets the same one. It gets it when it next reconnects."""
        found = find_device(device)
        return done(f"Reserved {ip} for {label(found)}.", client.dhcp.add_static_lease(found["mac"], ip))

    add(set_fixed_ip, "write", "dhcp.add_static_lease")

    def delete_fixed_ip(ctx: Context, device: Device) -> str:
        """Remove a device's reserved IP address."""
        found = find_device(device)
        return done(f"Removed the reserved IP address of {label(found)}.", client.dhcp.delete_static_lease(found["mac"]))

    add(delete_fixed_ip, "write", "dhcp.delete_static_lease", destructive=True)

    def set_dns_servers(
        ctx: Context,
        ipv4: Annotated[
            list[str] | None,
            Field(
                description='Up to 2 IPv4 addresses, e.g. ["1.1.1.1", "9.9.9.9"]. [] gives devices the router again. Default: unchanged.'
            ),
        ] = None,
        ipv6: Annotated[
            list[str] | None, Field(description="Up to 2 IPv6 addresses. [] gives devices the router again. Default: unchanged.")
        ] = None,
    ) -> str:
        """Set the DNS servers the router gives devices on the home network, e.g. a Pi-hole. Devices use them once they
        renew their address, e.g. when they reconnect."""
        if ipv4 is None and ipv6 is None:
            raise ToolError("Nothing to change: give ipv4, ipv6 or both.")
        answers = []
        if ipv4 is not None:
            answers.append(done(f"IPv4 DNS servers for devices: {', '.join(ipv4) or 'the router'}.", client.dns.set_device_servers(ipv4)))
        if ipv6 is not None:
            answers.append(
                done(f"IPv6 DNS servers for devices: {', '.join(ipv6) or 'the router'}.", client.dns.set_device_servers_ipv6(ipv6))
            )
        return "\n".join(answers)

    add(set_dns_servers, "write", "dns.set_device_servers")

    def flush_dns_cache(ctx: Context) -> str:
        """Empty the router's DNS cache, so names are looked up again. Only matters while the cache is on."""
        return done("Emptied the DNS cache.", client.dns.flush_cache())

    add(flush_dns_cache, "write", "dns.flush_cache", idempotent=False)

    def run_speed_test(ctx: Context) -> str:
        """Run the router's speed test and wait for the result: ping in ms, and download and upload speed in Mbit/s.
        It takes about a minute and uses the whole connection meanwhile, which slows down everyone's internet."""
        started_at = time.monotonic()
        result: dict[str, float] = {}
        finished: set[str] = set()
        state = _body(client.speedtest.status()) or {}
        seen_running = isinstance(state, dict) and state.get("event") not in (None, "IDLE")
        if seen_running:  # one is running already, e.g. from the web interface: wait for it
            _note_speed(state, result, finished)
        else:
            started = _body(client.speedtest.start())
            if not isinstance(started, dict) or started.get("status") != "SUCCESS":
                raise ToolError(f"The router didn't start the speed test. Its answer: {_text(started)}")
        while time.monotonic() - started_at < SPEED_TEST_TIMEOUT_SECONDS:
            state = _body(client.speedtest.status()) or {}
            if not isinstance(state, dict) or state.get("event") in (None, "IDLE"):
                if seen_running:
                    break
                if time.monotonic() - started_at > SPEED_TEST_START_SECONDS:
                    raise ToolError("The speed test didn't start: the router's speed test stays idle.")
            else:
                seen_running = True
                _note_speed(state, result, finished)
            time.sleep(SPEED_TEST_POLL_SECONDS)
        else:
            raise ToolError(
                f"The speed test didn't finish within {SPEED_TEST_TIMEOUT_SECONDS:.0f} seconds. Partial result: {_text(result)}"
            )
        if not result:
            raise ToolError("The speed test ended without a result.")
        last_speed_test.clear()
        last_speed_test.update(result, finished_at=time.strftime("%Y-%m-%dT%H:%M:%S%z"))
        if not {"download", "upload"} <= finished:
            last_speed_test["note"] = "The speeds are the last ones measured during the test: its final averages weren't seen."
        return _text(last_speed_test)

    add(run_speed_test, "write", "speedtest.start", idempotent=False)

    def ask_change(ctx: Context, function: str, arguments: dict[str, Any] | None) -> Any:
        found = catalog.get(function)
        if found is None or found.action == "read" or found.action not in options.actions:
            return _NOT_NEEDED  # the tool refuses it
        try:
            checked = found.arguments(arguments)
        except ValueError:
            return _NOT_NEEDED  # the tool reports the error
        return _confirmation(ctx, question(found.group, found.method, checked), arguments or {})

    def change_router_setting(
        ctx: Context,
        confirmation: Annotated[ElicitationResult[Confirmation], Resolve(ask_change)],
        function: Annotated[str, Field(description='Group and function, e.g. "firewall.set_upnp_enabled".')],
        arguments: Annotated[dict[str, Any] | None, Field(description='The function\'s arguments by name, e.g. {"enable": false}.')] = None,
    ) -> str:
        """Call one of the router functions list_router_functions lists, to change a setting the other tools don't
        cover. Changes that disrupt the network ask the user first."""
        found = lookup(function)
        if found.action == "read":
            raise _Refused(f"{function} only reads: use call_router_function.")
        if found.action not in options.actions:
            raise _Refused(
                f"{function} disrupts the network, and the server doesn't allow that: it must be started with --allow-disruptive."
            )
        return call(found, arguments)

    add(change_router_setting, "write", None, destructive=True, idempotent=False)

    # ── Disruptive ───────────────────────────────────────────────────────

    def ask_wifi_enabled(ctx: Context, enable: bool) -> Any:
        return _confirmation(ctx, question("wifi", "set_enabled", {"enable": enable}), {"enable": enable})

    def set_wifi_enabled(
        ctx: Context,
        confirmation: Annotated[ElicitationResult[Confirmation], Resolve(ask_wifi_enabled)],
        enable: Annotated[bool, Field(description="True turns Wi-Fi on, False turns it off.")],
    ) -> str:
        """Turn all Wi-Fi networks on or off. Off disconnects every wireless device. The guest network stays off when
        Wi-Fi comes back on: see set_guest_wifi."""
        return done(f"Turned Wi-Fi {'on' if enable else 'off'}.", client.wifi.set_enabled(enable))

    add(set_wifi_enabled, "disruptive", "wifi.set_enabled", destructive=True)

    def ask_guest_wifi(ctx: Context, enable: bool, hours: int) -> Any:
        details = {"enable": enable, "hours": hours}
        return _confirmation(ctx, question("wifi", "set_guest_enabled", details), details)

    def set_guest_wifi(
        ctx: Context,
        confirmation: Annotated[ElicitationResult[Confirmation], Resolve(ask_guest_wifi)],
        enable: Annotated[bool, Field(description="True turns the guest Wi-Fi on, False turns it off.")],
        hours: Annotated[int, Field(ge=0, description="When turning it on, turn it off again after this many hours. 0: stay on.")] = 0,
    ) -> str:
        """Turn the guest Wi-Fi on or off."""
        after = f" for {hours} hours" if enable and hours else ""
        return done(f"Turned the guest Wi-Fi {'on' if enable else 'off'}{after}.", client.wifi.set_guest_enabled(enable, hours))

    add(set_guest_wifi, "disruptive", "wifi.set_guest_enabled", destructive=True)

    def ask_wifi_network(ctx: Context, network: str, ssid: str | None, password: str | None, visible: bool | None, band: str | None) -> Any:
        details = {"network": network, "ssid": ssid, "password": password, "visible": visible, "band": band}
        return _confirmation(ctx, question("wifi", "set_guest_network" if network == "guest" else "set_network", details), details)

    def set_wifi_network(
        ctx: Context,
        confirmation: Annotated[ElicitationResult[Confirmation], Resolve(ask_wifi_network)],
        network: Literal["main", "guest"] = "main",
        ssid: Annotated[str | None, Field(description="The network name, 2 to 32 characters.")] = None,
        password: Annotated[
            str | None, Field(description="12 to 63 characters, with a lower-case and an upper-case letter, a digit and a symbol.")
        ] = None,
        visible: Annotated[bool | None, Field(description="False hides the network name. Main network only.")] = None,
        band: Annotated[
            Literal["2.4GHz", "5GHz"] | None,
            Field(description="Change one band only, when the bands have separate settings. Main network only."),
        ] = None,
    ) -> str:
        """Change a Wi-Fi network's name, password or visibility. Settings left out stay as they are. Wireless devices
        lose their connection and must reconnect, with the new password if it changed."""
        if network == "guest":
            if visible is not None or band is not None:
                raise ToolError("The guest network's visibility and bands can't be changed: give only ssid and password.")
            raw = client.wifi.set_guest_network(ssid, password)
        else:
            raw = client.wifi.set_network(ssid, password, visible, band)
        return done(f"Changed the {'guest ' if network == 'guest' else ''}Wi-Fi settings.", raw)

    add(set_wifi_network, "disruptive", "wifi.set_network", destructive=True)

    def ask_wifi_channel(ctx: Context, band: str, channel: int | str, bandwidth: str | None) -> Any:
        details = {"band": band, "channel": channel, "bandwidth": bandwidth}
        return _confirmation(ctx, question("wifi", "set_channel", details), details)

    def set_wifi_channel(
        ctx: Context,
        confirmation: Annotated[ElicitationResult[Confirmation], Resolve(ask_wifi_channel)],
        band: Literal["2.4GHz", "5GHz"],
        channel: Annotated[
            int | Literal["auto"], Field(description='A channel, or "auto". 2.4 GHz: usually 1 to 13. 5 GHz: 36 to 64 or 100 to 112.')
        ],
        bandwidth: Annotated[
            str | None, Field(description='2.4 GHz: "20MHz" or "40MHz". 5 GHz: "80MHz", or "Auto" for 80 or 160 MHz. Default: unchanged.')
        ] = None,
    ) -> str:
        """Set a band's Wi-Fi channel, or let the router choose it. Devices on the band lose their connection for a
        moment, and for about a minute on 5 GHz channels 52 to 112."""
        return done(f"Set the {band} channel to {channel}.", client.wifi.set_channel(band, channel, bandwidth))

    add(set_wifi_channel, "disruptive", "wifi.set_channel", destructive=True)

    def ask_reboot(ctx: Context) -> Any:
        return _confirmation(ctx, question("nmc", "reboot", {}), {})

    def reboot_router(ctx: Context, confirmation: Annotated[ElicitationResult[Confirmation], Resolve(ask_reboot)]) -> str:
        """Restart the router. Internet and Wi-Fi are down for a few minutes, for everyone."""
        return done("The router is restarting. It's back in a few minutes.", client.nmc.reboot())

    add(reboot_router, "disruptive", "nmc.reboot", destructive=True, idempotent=False)

    return server
