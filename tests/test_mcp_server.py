"""Tests for the MCP server: which tools it offers, what they send to the router, confirmations, secrets and metrics.

The tools run through an in-process MCP client against a fake router, so the router's answers here are made up.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
import requests
from mcp import Client
from mcp.types import ElicitResult

from internetbox_client import InternetBoxClient
from internetbox_client.mcp_server import server as mcp_server
from internetbox_client.mcp_server.server import MAX_CHARS, Options, build_server

READ_TOOLS = {
    "router_overview",
    "list_devices",
    "wifi_overview",
    "internet_status",
    "firewall_overview",
    "dns_settings",
    "lan_settings",
    "parental_controls",
    "remote_access",
    "speed_test_results",
    "list_router_functions",
    "call_router_function",
}
WRITE_TOOLS = {
    "rename_device",
    "set_device_internet_access",
    "set_device_schedule",
    "wake_device",
    "forget_device",
    "set_port_forward",
    "delete_port_forward",
    "set_fixed_ip",
    "delete_fixed_ip",
    "set_dns_servers",
    "flush_dns_cache",
    "run_speed_test",
    "change_router_setting",
}
DISRUPTIVE_TOOLS = {"set_wifi_enabled", "set_guest_wifi", "set_wifi_network", "set_wifi_channel", "reboot_router"}

READ_ONLY = Options()
WRITES = Options(allow_writes=True)
DISRUPTIVE = Options(allow_disruptive=True)

DEVICES = [
    {"Key": "AA:BB:CC:00:00:01", "Name": "laptop", "IPAddress": "192.168.1.20", "Active": True, "InterfaceName": "ETH1"},
    {
        "Key": "AA:BB:CC:00:00:02",
        "Name": "Tim's phone",
        "IPAddress": "192.168.1.21",
        "Active": True,
        "InterfaceName": "wl0",
        "OperatingFrequencyBand": "5GHz",
        "SignalStrength": -50,
    },
    {"Key": "AA:BB:CC:00:00:03", "Name": "Anna's phone", "IPAddress": "192.168.1.22", "Active": False, "InterfaceName": "wl1"},
    {"Key": "AA:BB:CC:00:00:04", "Name": "printer", "IPAddress": "", "Active": False, "InterfaceName": "ETH2"},
]

ACCESS_POINT = {
    "Band": "5GHz",
    "SSID": "Home",
    "Security": {"KeyPassPhrase": "Secret-passphrase-1", "ModeEnabled": "WPA2-Personal"},
    "VAPStatus": "Up",
    "SSIDAdvertisementEnabled": True,
    "Channel": 36,
}

ANSWERS: dict[str, Any] = {
    "Devices:get": {"status": DEVICES},
    "/sysbus/DeviceInfo:get": {"status": {"ModelName": "IB4-00", "SoftwareVersion": "15.21.36", "UpTime": 93784}},
    "/sysbus/NMC:getWANStatus": {
        "status": True,
        "data": {"LinkType": "gpon", "LinkState": "up", "ConnectionState": "Bound", "IPAddress": "203.0.113.7", "IPv6Address": ""},
    },
    "/sysbus/NMC:get": {"status": {"ActiveWANInterface": "XGS-PON"}},
    "/sysbus/NMC/Wifi:get": {"status": {"Enable": True, "ConfigurationMode": False, "WPSEnable": False}},
    "/sysbus/NMC/Guest:get": {"status": None, "data": {"Enable": False, "ActivationTimeout": 0, "BandwidthLimitation": 200}},
    "/sysbus/Firewall:get": {"status": {"AdvancedLevel": "High", "AdvancedIPv6Level": "Medium", "UpnpPortForwardingEnable": False}},
    "/sysbus/Firewall:getPortForwarding": {
        "status": {
            "webui_game": {
                "Id": "webui_game",
                "Description": "game",
                "Origin": "webui",
                "Enable": True,
                "Status": "Enabled",
                "Protocol": "6,17",
                "ExternalPort": "25565",
                "InternalPort": "25565",
                "DestinationIPAddress": "192.168.1.20",
                "SourcePrefix": "",
            }
        }
    },
    "/sysbus/Firewall:getDMZ": {"status": {}},
    "/sysbus/Scheduler:getSchedule": {"status": False},
    "/sysbus/Scheduler:getCompleteSchedules": {
        "status": True,
        "data": {
            "scheduleInfo": [
                {
                    "ID": "AA:BB:CC:00:00:02",
                    "enable": True,
                    "value": "Disable",
                    "override": "Disable",
                    "temporaryOverride": False,
                    "schedule": [{"state": "Disable", "begin": 79200, "end": 111600}, {"state": "Enable", "begin": 0, "end": 10}],
                }
            ]
        },
    },
    "/sysbus/ToD:listMST": {"status": None, "data": {"ids": ["aabbcc000002"]}},
    "/sysbus/ToD:getMST": {
        "status": None,
        "data": {"subject": "MAC:AA:BB:CC:00:00:02", "enable": True, "allowedTime": dict.fromkeys(("Mon", "Tue", "Sun"), 120)},
    },
    "/sysbus/DHCPv4/Server/Pool/default:getStaticLeases": {"status": [{"MACAddress": "aa:bb:cc:00:00:01", "IPAddress": "192.168.1.20"}]},
    "/sysbus/DHCPv4/Server/Pool/guest:getStaticLeases": {"status": [{"MACAddress": "aa:bb:cc:00:00:09", "IPAddress": "10.128.0.20"}]},
    "/sysbus/NMC:getLANIP": {"status": None, "data": {"Address": "192.168.1.1"}},
    "/sysbus/NMC/DHCPv4/DNSServers/User:get": {"status": {"DNSServers": "1.1.1.1,9.9.9.9"}},
    "/sysbus/NMC/DHCPv6/DNSServers/User:get": {"status": {"DNSServers": ""}},
    "/sysbus/DNS/Server/Route:get": {"status": {"webuidns1": {"Status": "Enabled", "DNS": "192.168.1.53"}}},
    "/sysbus/DynDNS:getHosts": {"status": [{"hostname": "home.example.org", "username": "me", "password": "dyndns-password"}]},
    "/sysbus/WireGuard:_get": {"status": {"WireGuard.": {"Enable": True, "Status": "Enabled"}}},
    "/sysbus/WireGuard/Server:_get": {"status": {"WireGuard.Server.1.": {"Status": "Disabled"}, "WireGuard.Server.": {}}},
    "/sysbus/WireGuard/Server/default/Client:_get": {
        "status": {"WireGuard.Server.1.Client.1.": {"Alias": "phone", "PreSharedKey": "psk-secret"}, "WireGuard.Server.1.Client.": {}}
    },
    "/sysbus/Sysbus:get": {"status": {"Name": "veip0"}},
    "/sysbus/NeMo/Intf/veip0:get": {
        "status": {"Name": "veip0", "PonMode": "XGS-PON", "SignalRxPower": -17670, "SignalTxPower": 6805, "DownstreamMaxRate": 9953280}
    },
    "/sysbus/NeMo/Intf/veip0:getNetDevStats": {"status": {"RxBytes": 2_500_000_000, "TxBytes": 1_000_000_000, "RxErrors": 1}},
}


class FakeRouter:
    """Answers the client's requests by endpoint, or by "service:method" for /ws, and records them."""

    def __init__(self) -> None:
        self.answers = dict(ANSWERS)
        self.requests: list[tuple[str, Any]] = []

    def post(self, endpoint: str, data: Any = None, auth_required: bool = True) -> str:
        key = f"{data['service']}:{data['method']}" if endpoint == "/ws" else endpoint
        self.requests.append((key, data))
        answer = self.answers.get(key, {"status": True})
        if isinstance(answer, list):  # answered in turn, the last one again and again
            answer = answer.pop(0) if len(answer) > 1 else answer[0]
        if isinstance(answer, Exception):
            raise answer
        return answer if isinstance(answer, str) else json.dumps(answer)

    def changes(self) -> list[tuple[str, Any]]:
        """The requests that weren't reads."""
        return [(key, data) for key, data in self.requests if not key.rsplit(":", 1)[-1].lower().startswith(("get", "_get", "list"))]


@pytest.fixture()
def router() -> FakeRouter:
    return FakeRouter()


@pytest.fixture()
def client(router: FakeRouter) -> InternetBoxClient:
    sm = MagicMock()
    sm.base_url = "https://192.168.1.1"
    sm.post.side_effect = router.post
    with patch("internetbox_client.client.SessionManager", return_value=sm):
        return InternetBoxClient(password="test")


class Events:
    """Stands in for MetricsSender."""

    def __init__(self) -> None:
        self.sent: list[dict] = []

    def send(self, event: dict) -> None:
        self.sent.append(event)


def _yes(context: Any, params: Any) -> ElicitResult:
    return ElicitResult(action="accept", content={"confirm": True})


class _Asked:
    """An elicitation callback that records the questions and gives a fixed answer."""

    def __init__(self, answer: ElicitResult) -> None:
        self.answer = answer
        self.questions: list[str] = []

    async def __call__(self, context: Any, params: Any) -> ElicitResult:
        self.questions.append(params.message)
        return self.answer


def call(server: Any, tool: str, arguments: dict | None = None, **client_options: Any) -> tuple[bool, str]:
    """Call a tool through an in-process MCP client: (whether it failed, its text)."""
    client_options.setdefault("mode", "legacy")

    async def main() -> tuple[bool, str]:
        async with Client(server, **client_options) as mcp_client:
            result = await mcp_client.call_tool(tool, arguments or {})
            return result.is_error, result.content[0].text

    return asyncio.run(main())


def tool_names(server: Any) -> set[str]:
    async def main() -> set[str]:
        async with Client(server, mode="legacy") as mcp_client:
            return {tool.name for tool in (await mcp_client.list_tools()).tools}

    return asyncio.run(main())


def tools(server: Any) -> dict[str, Any]:
    async def main() -> dict[str, Any]:
        async with Client(server, mode="legacy") as mcp_client:
            return {tool.name: tool for tool in (await mcp_client.list_tools()).tools}

    return asyncio.run(main())


# ── Which tools are offered ─────────────────────────────────────────────


@pytest.mark.parametrize(
    "options,expected",
    [(READ_ONLY, READ_TOOLS), (WRITES, READ_TOOLS | WRITE_TOOLS), (DISRUPTIVE, READ_TOOLS | WRITE_TOOLS | DISRUPTIVE_TOOLS)],
)
def test_flags_decide_the_tools(client: InternetBoxClient, options: Options, expected: set[str]) -> None:
    assert tool_names(build_server(client, options)) == expected


def test_tool_hints(client: InternetBoxClient) -> None:
    offered = tools(build_server(client, DISRUPTIVE))
    for name, tool in offered.items():
        assert tool.annotations.read_only_hint is (name in READ_TOOLS), name
        assert tool.annotations.open_world_hint is False
        assert tool.description and "\n" not in tool.description.split("\n\n")[0]
    assert offered["reboot_router"].annotations.destructive_hint is True
    assert offered["rename_device"].annotations.destructive_hint is False


def test_confirmations_arent_arguments(client: InternetBoxClient) -> None:
    offered = tools(build_server(client, DISRUPTIVE))
    assert set(offered["set_wifi_enabled"].input_schema["properties"]) == {"enable"}
    assert set(offered["change_router_setting"].input_schema["properties"]) == {"function", "arguments"}
    assert "device" in offered["rename_device"].input_schema["properties"]
    assert "name, MAC address or IP address" in offered["rename_device"].input_schema["properties"]["device"]["description"]


@pytest.mark.parametrize(
    "options,says",
    [(READ_ONLY, "--allow-writes"), (WRITES, "--allow-disruptive"), (DISRUPTIVE, "confirm"), (Options(show_secrets=True), "are shown")],
)
def test_instructions(client: InternetBoxClient, options: Options, says: str) -> None:
    assert says in build_server(client, options).instructions


def test_disruptive_implies_writes() -> None:
    assert Options(allow_disruptive=True).actions == {"read", "write", "disruptive"}
    assert Options(allow_writes=True).actions == {"read", "write"}
    assert Options().actions == {"read"}


# ── Reads ───────────────────────────────────────────────────────────────


def test_router_overview(client: InternetBoxClient) -> None:
    failed, text = call(build_server(client), "router_overview")
    overview = json.loads(text)
    assert not failed
    assert overview["router"]["model"] == "IB4-00"
    assert overview["router"]["uptime"] == "1 d 2 h 3 min"
    assert overview["internet"]["public_ipv4"] == "203.0.113.7"
    assert overview["internet"]["interface"] == "XGS-PON"
    assert overview["wifi"] == {"wifi_enabled": True, "guest_wifi_enabled": False}
    assert overview["devices"] == {"connected": 2, "known": 4}
    assert overview["firewall"] == {"ipv4_level": "High", "ipv6_level": "Medium"}


def test_a_failing_part_shows_its_error(client: InternetBoxClient, router: FakeRouter) -> None:
    router.answers["/sysbus/DeviceInfo:get"] = requests.ConnectionError("no route")
    failed, text = call(build_server(client), "router_overview")
    overview = json.loads(text)
    assert not failed
    assert "Could not connect to the router at https://192.168.1.1" in overview["router"]["error"]
    assert overview["devices"]["known"] == 4


def test_list_devices(client: InternetBoxClient) -> None:
    devices = json.loads(call(build_server(client), "list_devices")[1])
    assert [d["name"] for d in devices] == ["laptop", "Tim's phone", "Anna's phone", "printer"]
    connected = json.loads(call(build_server(client), "list_devices", {"connected_only": True})[1])
    assert [d["name"] for d in connected] == ["laptop", "Tim's phone"]
    assert connected[1]["signal_dbm"] == -50


def test_wifi_overview_hides_passwords(client: InternetBoxClient) -> None:
    with patch.object(client.wifi, "summary", return_value=json.dumps({"networks": [{"ssid": "Home", "password": "Secret-1"}]})):
        overview = json.loads(call(build_server(client), "wifi_overview")[1])
        shown = json.loads(call(build_server(client, Options(show_secrets=True)), "wifi_overview")[1])
    assert overview["wifi"]["networks"][0] == {"ssid": "Home", "password": "<hidden>"}
    assert shown["wifi"]["networks"][0]["password"] == "Secret-1"
    assert overview["guest"] == {"enabled": False, "turns_off_after_hours": None, "bandwidth_limit": 200}
    assert overview["schedule"] == "none"


def test_wifi_overview_schedule(client: InternetBoxClient, router: FakeRouter) -> None:
    router.answers["/sysbus/Scheduler:getSchedule"] = {
        "status": {"enable": True, "value": "Enable", "schedule": [{"begin": 82800, "end": 111600, "state": "Disable"}]}
    }
    with patch.object(client.wifi, "summary", return_value="{}"):
        overview = json.loads(call(build_server(client), "wifi_overview")[1])
    assert overview["schedule"] == {"enabled": True, "wifi_off_now": False, "off_periods": ["Mon 23:00 to Tue 07:00"]}


def test_internet_status(client: InternetBoxClient) -> None:
    status = json.loads(call(build_server(client), "internet_status")[1])
    assert status["connection"]["IPAddress"] == "203.0.113.7"
    assert status["fiber"]["signal_rx_dbm"] == -17.67
    assert status["fiber"]["downstream_max_mbps"] == 9953.28
    assert status["traffic"] == {"received_gb": 2.5, "sent_gb": 1.0, "errors": 1}


def test_firewall_overview(client: InternetBoxClient) -> None:
    with (
        patch.object(client.firewall, "custom_rules", return_value="[]"),
        patch.object(client.firewall, "custom_policy", return_value='{"ipv4": "allow"}'),
    ):
        overview = json.loads(call(build_server(client), "firewall_overview")[1])
    assert overview["levels"] == {"ipv4": "High", "ipv6": "Medium", "upnp_port_forwarding": False}
    forward = overview["port_forwards"][0]
    assert (forward["name"], forward["protocol"], forward["destination_ip"], forward["allowed_sources"]) == (
        "game",
        "both",
        "192.168.1.20",
        "any",
    )
    assert overview["dmz"] == "none"
    assert overview["custom_policy"] == {"ipv4": "allow"}


def test_dns_settings(client: InternetBoxClient) -> None:
    dns = json.loads(call(build_server(client), "dns_settings")[1])
    assert dns["devices_get_ipv4"] == ["1.1.1.1", "9.9.9.9"]
    assert dns["devices_get_ipv6"] == "the router"
    assert dns["router_asks"] == {"webuidns1": {"server": "192.168.1.53", "status": "Enabled"}}


def test_lan_settings(client: InternetBoxClient) -> None:
    lan = json.loads(call(build_server(client), "lan_settings")[1])
    assert lan["lan"] == {"Address": "192.168.1.1"}
    assert lan["fixed_ips"] == [{"device": "laptop", "mac": "AA:BB:CC:00:00:01", "ip": "192.168.1.20"}]
    assert lan["guest_fixed_ips"] == [{"device": None, "mac": "AA:BB:CC:00:00:09", "ip": "10.128.0.20"}]


def test_parental_controls(client: InternetBoxClient) -> None:
    controls = json.loads(call(build_server(client), "parental_controls")[1])
    assert controls["access_schedules"] == [
        {
            "device": "Tim's phone",
            "mac": "AA:BB:CC:00:00:02",
            "enabled": True,
            "blocked_now": True,
            "override": "block",
            "blocked_periods": ["Mon 22:00 to Tue 07:00"],
        }
    ]
    assert controls["daily_time_limits"] == [{"device": "Tim's phone", "mac": "AA:BB:CC:00:00:02", "enabled": True, "minutes_per_day": 120}]


@pytest.mark.parametrize(
    "schedule,expected",
    [
        ({"override": "", "temporaryOverride": False, "value": "Disable"}, None),
        ({"override": "Enable", "temporaryOverride": False, "value": "Enable"}, "allow"),
        ({"override": "", "temporaryOverride": True, "value": "Enable"}, "allow until the schedule next changes"),
        ({"override": "", "temporaryOverride": True, "value": "Disable"}, "block until the schedule next changes"),
        ({}, None),
    ],
)
def test_override(schedule: dict, expected: str | None) -> None:
    assert mcp_server._override(schedule) == expected


def test_remote_access_hides_secrets(client: InternetBoxClient) -> None:
    access = json.loads(call(build_server(client), "remote_access")[1])
    assert access["dyndns_hosts"][0]["password"] == "<hidden>"
    assert access["wireguard"] == {"Enable": True, "Status": "Enabled"}
    assert access["wireguard_server"] == [{"Status": "Disabled"}]
    assert access["wireguard_clients"] == [{"Alias": "phone", "PreSharedKey": "<hidden>"}]


SPEED_TEST = "com.vestiacom.speedtest/com/vestiacom/speedtest.com.vestiacom.speedtest"
# As the router reported them during a test, every 2 seconds.
SPEED_TEST_STATUSES = [
    {"event": "PROGRESS_PING", "origin": "webui", "progress": 1, "time_remaining": 20, "current_value": 1.541},
    {"event": "PROGRESS_DOWNLOAD", "origin": "webui", "progress": 7, "time_remaining": 18.9, "current_value": 7809.79},
    {"event": "DOWNLOAD_DONE", "origin": "webui", "progress": 51, "time_remaining": 10, "average": 8005.82, "max": 8005.82},
    {"event": "PROGRESS_UPLOAD", "origin": "webui", "progress": 57, "time_remaining": 8.7, "current_value": 7977.57},
    {"event": "UPLOAD_DONE", "origin": "webui", "progress": 100, "time_remaining": 0, "average": 7662.22, "max": 7662.22},
    {"event": "IDLE"},
]


@pytest.fixture()
def fast_speed_test(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mcp_server, "SPEED_TEST_POLL_SECONDS", 0)


def _speed_test(router: FakeRouter, statuses: list[dict], start: Any = None) -> None:
    router.answers[f"{SPEED_TEST}:TestStatus"] = [{"status": status} for status in statuses]
    router.answers[f"{SPEED_TEST}:TestStart"] = start or {"status": {"status": "SUCCESS", "downloadDuration": 10000}}


def test_run_speed_test(client: InternetBoxClient, router: FakeRouter, fast_speed_test: None) -> None:
    _speed_test(router, [{"event": "IDLE"}, {"event": "IDLE"}, *SPEED_TEST_STATUSES])
    server = build_server(client, WRITES)
    assert json.loads(call(server, "speed_test_results")[1]) == {"running_now": False, "last_result": "none since the server started"}
    failed, text = call(server, "run_speed_test")
    result = json.loads(text)
    assert not failed
    assert (result["ping_ms"], result["download_mbps"], result["upload_mbps"]) == (1.5, 8005.8, 7662.2)
    assert "note" not in result
    status, start = f"{SPEED_TEST}:TestStatus", f"{SPEED_TEST}:TestStart"
    assert [key for key, _ in router.changes()] == [status, status, start] + [status] * len(SPEED_TEST_STATUSES)
    assert json.loads(call(server, "speed_test_results")[1]) == {"running_now": False, "last_result": result}


def test_speed_test_results_while_one_runs(client: InternetBoxClient, router: FakeRouter) -> None:
    _speed_test(router, SPEED_TEST_STATUSES[1:2])
    assert json.loads(call(build_server(client), "speed_test_results")[1])["running_now"]["event"] == "PROGRESS_DOWNLOAD"


def test_run_speed_test_waits_for_a_running_one(client: InternetBoxClient, router: FakeRouter, fast_speed_test: None) -> None:
    _speed_test(router, [SPEED_TEST_STATUSES[0], SPEED_TEST_STATUSES[1], SPEED_TEST_STATUSES[3], {"event": "IDLE"}])
    result = json.loads(call(build_server(client, WRITES), "run_speed_test")[1])
    assert f"{SPEED_TEST}:TestStart" not in [key for key, _ in router.requests]
    assert (result["ping_ms"], result["download_mbps"], result["upload_mbps"]) == (1.5, 7809.8, 7977.6)
    assert result["note"].startswith("The speeds are the last ones measured")


@pytest.mark.parametrize(
    "statuses,start,settings,message",
    [
        (
            [{"event": "IDLE"}],
            {"status": {"status": "FAILURE"}},
            {},
            'The router didn\'t start the speed test. Its answer: {"status":"FAILURE"}',
        ),
        ([{"event": "IDLE"}], None, {"SPEED_TEST_START_SECONDS": 0}, "the router's speed test stays idle"),
        ([{"event": "IDLE"}, *SPEED_TEST_STATUSES], None, {"SPEED_TEST_TIMEOUT_SECONDS": 0}, "didn't finish within 0 seconds"),
        ([{"event": "IDLE"}, {"event": "SOMETHING_ELSE"}, {"event": "IDLE"}], None, {}, "ended without a result"),
    ],
)
def test_run_speed_test_fails(
    client: InternetBoxClient,
    router: FakeRouter,
    monkeypatch: pytest.MonkeyPatch,
    fast_speed_test: None,
    statuses: list,
    start: Any,
    settings: dict,
    message: str,
) -> None:
    for name, value in settings.items():
        monkeypatch.setattr(mcp_server, name, value)
    _speed_test(router, statuses, start)
    failed, text = call(build_server(client, WRITES), "run_speed_test")
    assert failed
    assert message in text


# ── The general tools ───────────────────────────────────────────────────


def test_list_router_functions(client: InternetBoxClient) -> None:
    listing = json.loads(call(build_server(client), "list_router_functions")[1])
    assert "summary" in listing["wifi"]["functions"]
    assert "set_enabled" not in listing["wifi"]["functions"]
    assert not {"voice", "dect", "phonebook", "carddav"} & set(listing)
    assert "restore" not in listing["nmc"]["functions"]
    with_writes = json.loads(call(build_server(client, WRITES), "list_router_functions")[1])
    assert "set_upnp_enabled" in with_writes["firewall"]["functions"]
    assert "set_enabled" not in with_writes["wifi"]["functions"]


def test_list_router_functions_of_a_group(client: InternetBoxClient) -> None:
    listing = json.loads(call(build_server(client, DISRUPTIVE), "list_router_functions", {"group": "wifi"})[1])
    channel = next(f for f in listing if f["function"].startswith("wifi.set_channel("))
    assert channel["action"] == "disruptive"
    assert "band: Literal['2.4GHz', '5GHz']" in channel["function"]
    secret = json.loads(call(build_server(client, WRITES), "list_router_functions", {"group": "wireguard"})[1])
    assert next(f for f in secret if f["function"].startswith("wireguard.add_client("))["description"].endswith("The result is a secret.")
    failed, text = call(build_server(client), "list_router_functions", {"group": "voice"})
    assert failed and "No group 'voice'" in text


def test_call_router_function(client: InternetBoxClient, router: FakeRouter) -> None:
    router.answers["/sysbus/NeMo/Intf/wifi0:get"] = {"status": {"Channel": 36}}
    with patch.object(client.wifi, "radio", wraps=client.wifi.radio) as radio:
        failed, text = call(build_server(client), "call_router_function", {"function": "wifi.radio", "arguments": {"id": "0"}})
    assert not failed
    radio.assert_called_once_with(id=0)  # converted to the annotated type


@pytest.mark.parametrize(
    "arguments,message",
    [
        ({"function": "nmc.restore", "arguments": {"path": "backup"}}, "No function 'nmc.restore'. list_router_functions(group='nmc')"),
        ({"function": "voice.call_list"}, "No function 'voice.call_list'. list_router_functions lists"),
        ({"function": "wifi.radio"}, "wifi.radio needs id"),
        ({"function": "wifi.radio", "arguments": {"idx": 0}}, "wifi.radio has no argument idx. Its arguments: id."),
        ({"function": "wifi.radio", "arguments": {"id": "zero"}}, "Invalid id for wifi.radio"),
        ({"function": "wifi.set_enabled", "arguments": {"enable": False}}, "must be started with --allow-disruptive"),
        ({"function": "firewall.set_upnp_enabled", "arguments": {"enable": False}}, "must be started with --allow-writes"),
    ],
)
def test_call_router_function_refuses(client: InternetBoxClient, router: FakeRouter, arguments: dict, message: str) -> None:
    failed, text = call(build_server(client), "call_router_function", arguments)
    assert failed
    assert message in text
    assert router.changes() == []


def test_call_router_function_points_to_change_router_setting(client: InternetBoxClient) -> None:
    arguments = {"function": "firewall.set_upnp_enabled", "arguments": {"enable": False}}
    assert call(build_server(client, WRITES), "call_router_function", arguments) == (
        True,
        "Error executing tool call_router_function: firewall.set_upnp_enabled changes settings: use change_router_setting.",
    )


def test_long_answers_are_cut_off(client: InternetBoxClient) -> None:
    with patch.object(client.devices, "get", return_value=json.dumps({"status": "x" * (MAX_CHARS * 2)})):
        failed, text = call(build_server(client), "call_router_function", {"function": "devices.get"})
    assert not failed
    assert len(text) < MAX_CHARS + 200
    assert text.endswith(
        f"[Cut off after {MAX_CHARS} of {MAX_CHARS * 2 + 13} characters. Ask for less, e.g. with a function that returns a summary.]"
    )


def test_secrets_are_hidden_in_general_answers(client: InternetBoxClient, router: FakeRouter) -> None:
    assert (
        json.loads(call(build_server(client), "call_router_function", {"function": "dyndns.hosts"})[1])["status"][0]["password"]
        == "<hidden>"
    )
    shown = call(build_server(client, Options(show_secrets=True)), "call_router_function", {"function": "dyndns.hosts"})[1]
    assert json.loads(shown)["status"][0]["password"] == "dyndns-password"


def test_secret_results_are_hidden(client: InternetBoxClient) -> None:
    arguments = {"function": "wireguard.add_client", "arguments": {"name": "phone"}}
    with patch.object(client.wireguard, "add_client", return_value='{"status": "[Interface]\\nPrivateKey = abc"}'):
        hidden = call(build_server(client, WRITES), "change_router_setting", arguments)[1]
        shown = call(build_server(client, Options(allow_writes=True, show_secrets=True)), "change_router_setting", arguments)[1]
    assert "PrivateKey" not in hidden
    assert "--show-secrets" in hidden
    assert "PrivateKey = abc" in shown


# ── Writes ──────────────────────────────────────────────────────────────


@pytest.mark.parametrize("device", ["laptop", "LAPTOP", "aa-bb-cc-00-00-01", "192.168.1.20", "lap"])
def test_devices_by_name_mac_or_ip(client: InternetBoxClient, router: FakeRouter, device: str) -> None:
    failed, text = call(build_server(client, WRITES), "rename_device", {"device": device, "new_name": "work laptop"})
    assert not failed
    assert text.startswith("Renamed laptop (AA:BB:CC:00:00:01) to 'work laptop'.")
    assert router.changes() == [
        (
            "Devices.Device.AA:BB:CC:00:00:01:set",
            {"service": "Devices.Device.AA:BB:CC:00:00:01", "method": "set", "parameters": {"parameters": {"Name": "work laptop"}}},
        )
    ]


def test_an_exact_name_beats_a_partial_one(client: InternetBoxClient, router: FakeRouter) -> None:
    router.answers["Devices:get"] = {"status": [*DEVICES, {"Key": "AA:BB:CC:00:00:05", "Name": "laptop 2"}]}
    assert call(build_server(client, WRITES), "wake_device", {"device": "laptop"})[1].startswith(
        "Sent a Wake-on-LAN packet to laptop (AA:BB"
    )


def test_an_unknown_mac_is_used_as_it_is(client: InternetBoxClient, router: FakeRouter) -> None:
    failed, text = call(build_server(client, WRITES), "wake_device", {"device": "aabbcc0000ff"})
    assert text.startswith("Sent a Wake-on-LAN packet to AA:BB:CC:00:00:FF.")
    assert router.changes()[0][1]["parameters"]["hostID"] == "AA:BB:CC:00:00:FF"


@pytest.mark.parametrize(
    "device,message",
    [
        (
            "phone",
            "'phone' matches several devices: Tim's phone (AA:BB:CC:00:00:02, 192.168.1.21); Anna's phone (AA:BB:CC:00:00:03, 192.168.1.22)",
        ),
        ("tablet", "No device matches 'tablet'. list_devices shows"),
    ],
)
def test_unclear_devices(client: InternetBoxClient, router: FakeRouter, device: str, message: str) -> None:
    failed, text = call(build_server(client, WRITES), "rename_device", {"device": device, "new_name": "x"})
    assert failed
    assert message in text
    assert router.changes() == []


@pytest.mark.parametrize("allowed,method", [(False, "block"), (True, "unblock")])
def test_set_device_internet_access(client: InternetBoxClient, allowed: bool, method: str) -> None:
    with patch.object(client.devices, method, return_value='{"status": true}') as changed:
        failed, text = call(build_server(client, WRITES), "set_device_internet_access", {"device": "Tim's phone", "allowed": allowed})
    changed.assert_called_once_with("AA:BB:CC:00:00:02")
    assert text.startswith(f"{'Allowed' if allowed else 'Blocked'} internet access for Tim's phone (AA:BB:CC:00:00:02).")


def test_set_device_schedule(client: InternetBoxClient) -> None:
    periods = [{"begin": "Sun 21:00", "end": "Mon 07:00"}]
    with patch.object(client.scheduler, "set_device_schedule", return_value='{"status": true}') as schedule:
        call(build_server(client, WRITES), "set_device_schedule", {"device": "laptop", "blocked_periods": periods})
    schedule.assert_called_once_with("AA:BB:CC:00:00:01", periods, True)


def test_forget_device(client: InternetBoxClient) -> None:
    with patch.object(client.devices, "remove", return_value='{"status": true}') as remove:
        text = call(build_server(client, WRITES), "forget_device", {"device": "printer"})[1]
    remove.assert_called_once_with("AA:BB:CC:00:00:04")
    assert text == 'Removed printer (AA:BB:CC:00:00:04) from the device list.\nRouter\'s answer: {"status":true}'


@pytest.mark.parametrize(
    "device,ip,target",
    [("laptop", "192.168.1.20", "laptop (AA:BB:CC:00:00:01) at 192.168.1.20"), ("192.168.1.99", "192.168.1.99", "192.168.1.99")],
)
def test_set_port_forward(client: InternetBoxClient, device: str, ip: str, target: str) -> None:
    with patch.object(client.firewall, "set_port_forwarding", return_value='{"status": true}') as forward:
        text = call(build_server(client, WRITES), "set_port_forward", {"name": "game", "device": device, "external_port": "25565"})[1]
    forward.assert_called_once_with("game", ip, "25565", None, "both", True)
    assert text.startswith(f"Port forwarding rule 'game': both port 25565 to {target}.")


def test_set_port_forward_needs_an_ip_address(client: InternetBoxClient, router: FakeRouter) -> None:
    failed, text = call(build_server(client, WRITES), "set_port_forward", {"name": "print", "device": "printer", "external_port": "631"})
    assert failed and "printer (AA:BB:CC:00:00:04) has no IP address" in text
    assert router.changes() == []


def test_delete_port_forward(client: InternetBoxClient) -> None:
    with patch.object(client.firewall, "delete_port_forwarding", return_value='{"status": true}') as delete:
        call(build_server(client, WRITES), "delete_port_forward", {"name": "game"})
    delete.assert_called_once_with("game")


def test_fixed_ips(client: InternetBoxClient) -> None:
    with (
        patch.object(client.dhcp, "add_static_lease", return_value='{"status": true}') as add,
        patch.object(client.dhcp, "delete_static_lease", return_value='{"status": true}') as delete,
    ):
        call(build_server(client, WRITES), "set_fixed_ip", {"device": "Tim's phone", "ip": "192.168.1.50"})
        call(build_server(client, WRITES), "delete_fixed_ip", {"device": "Tim's phone"})
    add.assert_called_once_with("AA:BB:CC:00:00:02", "192.168.1.50")
    delete.assert_called_once_with("AA:BB:CC:00:00:02")


def test_set_dns_servers(client: InternetBoxClient, router: FakeRouter) -> None:
    text = call(build_server(client, WRITES), "set_dns_servers", {"ipv4": ["192.168.1.53"], "ipv6": []})[1]
    assert router.changes() == [
        ("/sysbus/NMC/DHCPv4/DNSServers/User:set", {"parameters": {"DNSServers": "192.168.1.53"}}),
        ("/sysbus/NMC/DHCPv6/DNSServers/User:set", {"parameters": {"DNSServers": ""}}),
    ]
    assert "IPv4 DNS servers for devices: 192.168.1.53." in text
    assert "IPv6 DNS servers for devices: the router." in text
    failed, text = call(build_server(client, WRITES), "set_dns_servers", {})
    assert failed and "Nothing to change" in text


def test_flush_dns_cache(client: InternetBoxClient, router: FakeRouter) -> None:
    call(build_server(client, WRITES), "flush_dns_cache")
    assert [key for key, _ in router.changes()] == ["/sysbus/DNS/Server/Cache:flush"]


def test_change_router_setting(client: InternetBoxClient, router: FakeRouter) -> None:
    asked = _Asked(ElicitResult(action="accept", content={"confirm": True}))
    arguments = {"function": "firewall.set_upnp_enabled", "arguments": {"enable": False}}
    failed, text = call(build_server(client, WRITES), "change_router_setting", arguments, elicitation_callback=asked)
    assert not failed
    assert asked.questions == []  # a write that doesn't disrupt anything goes ahead
    assert router.changes() == [("/sysbus/Firewall:set", {"parameters": {"UpnpPortForwardingEnable": False}})]


@pytest.mark.parametrize(
    "options,arguments,message",
    [
        (WRITES, {"function": "wifi.set_enabled", "arguments": {"enable": False}}, "must be started with --allow-disruptive"),
        (WRITES, {"function": "wifi.summary"}, "wifi.summary only reads: use call_router_function."),
        (WRITES, {"function": "nmc.restore", "arguments": {"path": "x"}}, "No function 'nmc.restore'"),
        (DISRUPTIVE, {"function": "wifi.set_enabled", "arguments": {}}, "wifi.set_enabled needs enable"),
    ],
)
def test_change_router_setting_refuses(
    client: InternetBoxClient, router: FakeRouter, options: Options, arguments: dict, message: str
) -> None:
    asked = _Asked(ElicitResult(action="accept", content={"confirm": True}))
    failed, text = call(build_server(client, options), "change_router_setting", arguments, elicitation_callback=asked)
    assert failed
    assert message in text
    assert asked.questions == []
    assert router.changes() == []


# ── Confirmations ───────────────────────────────────────────────────────


@pytest.mark.parametrize("mode", ["legacy", "auto"])
def test_disruptive_changes_ask_first(client: InternetBoxClient, router: FakeRouter, mode: str) -> None:
    asked = _Asked(ElicitResult(action="accept", content={"confirm": True}))
    failed, text = call(build_server(client, DISRUPTIVE), "set_wifi_enabled", {"enable": False}, elicitation_callback=asked, mode=mode)
    assert not failed
    assert text.startswith("Turned Wi-Fi off.")
    assert asked.questions == [
        "Turn off all Wi-Fi networks? Every wireless device will lose its connection, including this computer if it's on Wi-Fi.\n\nenable: false"
    ]
    assert router.changes() == [("/sysbus/NMC/Wifi:set", {"parameters": {"Enable": False, "Status": False, "ConfigurationMode": False}})]


@pytest.mark.parametrize("mode", ["legacy", "auto"])
@pytest.mark.parametrize(
    "answer", [ElicitResult(action="decline"), ElicitResult(action="cancel"), ElicitResult(action="accept", content={"confirm": False})]
)
def test_no_means_no(client: InternetBoxClient, router: FakeRouter, mode: str, answer: ElicitResult) -> None:
    failed, text = call(build_server(client, DISRUPTIVE), "reboot_router", elicitation_callback=_Asked(answer), mode=mode)
    assert (failed, text) == (False, "Not done: the user said no.")
    assert router.changes() == []


@pytest.mark.parametrize("mode", ["legacy", "auto"])
def test_refused_when_the_app_cant_ask(client: InternetBoxClient, router: FakeRouter, mode: str) -> None:
    failed, text = call(build_server(client, DISRUPTIVE), "reboot_router", mode=mode)
    assert failed
    assert "this app can't ask for it" in text
    assert router.changes() == []


def test_no_question_when_nothing_is_disrupted(client: InternetBoxClient, router: FakeRouter) -> None:
    asked = _Asked(ElicitResult(action="decline"))
    failed, text = call(build_server(client, DISRUPTIVE), "set_wifi_enabled", {"enable": True}, elicitation_callback=asked)
    assert text.startswith("Turned Wi-Fi on.")
    assert asked.questions == []
    # Without the app being able to ask, too.
    assert call(build_server(client, DISRUPTIVE), "set_guest_wifi", {"enable": True, "hours": 2})[1].startswith(
        "Turned the guest Wi-Fi on for 2 hours."
    )


def test_questions_hide_passwords(client: InternetBoxClient) -> None:
    asked = _Asked(ElicitResult(action="decline"))
    call(build_server(client, DISRUPTIVE), "set_wifi_network", {"ssid": "Home", "password": "New-passphrase-1"}, elicitation_callback=asked)
    assert asked.questions[0].endswith('network: "main", ssid: "Home", password: "<hidden>"')
    assert "New-passphrase-1" not in asked.questions[0]


def test_change_router_setting_asks_for_disruptive_functions(client: InternetBoxClient, router: FakeRouter) -> None:
    asked = _Asked(ElicitResult(action="decline"))
    arguments = {"function": "wifi.set_channel", "arguments": {"band": "5GHz", "channel": 36}}
    assert call(build_server(client, DISRUPTIVE), "change_router_setting", arguments, elicitation_callback=asked) == (
        False,
        "Not done: the user said no.",
    )
    assert asked.questions[0].startswith("Change the Wi-Fi channel?")
    assert router.changes() == []


@pytest.mark.parametrize(
    "tool,arguments,method,expected",
    [
        ("set_guest_wifi", {"enable": False}, "set_guest_enabled", (False, 0)),
        ("set_wifi_network", {"network": "guest", "ssid": "Guests"}, "set_guest_network", ("Guests", None)),
        ("set_wifi_network", {"visible": False, "band": "5GHz"}, "set_network", (None, None, False, "5GHz")),
        ("set_wifi_channel", {"band": "2.4GHz", "channel": "auto"}, "set_channel", ("2.4GHz", "auto", None)),
    ],
)
def test_disruptive_tools(client: InternetBoxClient, tool: str, arguments: dict, method: str, expected: tuple) -> None:
    with patch.object(client.wifi, method, return_value='{"status": true}') as changed:
        failed, text = call(build_server(client, DISRUPTIVE), tool, arguments, elicitation_callback=_yes_async)
    assert not failed, text
    changed.assert_called_once_with(*expected)


def test_guest_network_has_no_visibility(client: InternetBoxClient) -> None:
    failed, text = call(
        build_server(client, DISRUPTIVE), "set_wifi_network", {"network": "guest", "visible": False}, elicitation_callback=_yes_async
    )
    assert failed and "give only ssid and password" in text


async def _yes_async(context: Any, params: Any) -> ElicitResult:
    return _yes(context, params)


# ── Errors and metrics ──────────────────────────────────────────────────


def _http_error(status: int) -> requests.HTTPError:
    response = requests.Response()
    response.status_code = status
    return requests.HTTPError(f"{status} Client Error", response=response)


@pytest.mark.parametrize(
    "error,message",
    [
        (requests.exceptions.SSLError("bad certificate"), "SSL error talking to the router at https://192.168.1.1: bad certificate"),
        (requests.exceptions.ReadTimeout(), "accepted the connection but didn't answer in time"),
        (requests.ConnectionError("refused"), "Could not connect to the router at https://192.168.1.1: refused"),
        (_http_error(500), "The router rejected the request: 500 Client Error"),
        (_http_error(401), "the router password (IB_PASSWORD) is wrong"),
        (ValueError("Invalid MAC"), "Invalid MAC"),
        (KeyError("status"), "KeyError: 'status'"),
    ],
)
def test_errors_reach_the_model(client: InternetBoxClient, router: FakeRouter, error: Exception, message: str) -> None:
    router.answers["/sysbus/NMC/Wifi:get"] = error
    failed, text = call(build_server(client), "call_router_function", {"function": "wifi.status"})
    assert failed
    assert message in text


def test_metrics(client: InternetBoxClient, router: FakeRouter) -> None:
    events = Events()
    server = build_server(client, DISRUPTIVE, events)  # type: ignore[arg-type]
    call(server, "list_devices")
    call(server, "call_router_function", {"function": "wifi.status"})
    call(server, "call_router_function", {"function": "nope"})
    call(server, "change_router_setting", {"function": "wifi.set_enabled", "arguments": {"enable": False}})
    call(server, "reboot_router", elicitation_callback=_Asked(ElicitResult(action="decline")))
    assert [(e["tool"], e["function"], e["action"], e["outcome"], e["client"]) for e in events.sent] == [
        ("list_devices", "devices.summary", "read", "ok", "mcp"),
        ("call_router_function", "wifi.status", "read", "ok", "mcp"),
        ("call_router_function", "", "read", "error", "mcp"),
        ("change_router_setting", "wifi.set_enabled", "disruptive", "refused", "mcp"),
        ("reboot_router", "nmc.reboot", "disruptive", "declined", "mcp"),
    ]
    assert all(e["duration_seconds"] >= 0 and e["server_version"] for e in events.sent)
    assert all(set(e) == {"tool", "function", "action", "outcome", "duration_seconds", "client", "server_version"} for e in events.sent)


# ── Helpers ─────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "seconds,text", [(0, "Mon 00:00"), (79200, "Mon 22:00"), (111600, "Tue 07:00"), (604800, "Sun 24:00"), (608400, "Mon 01:00")]
)
def test_week_time(seconds: int, text: str) -> None:
    assert mcp_server._week_time(seconds) == text


@pytest.mark.parametrize(
    "raw,body",
    [
        ('{"status": {"a": 1}}', {"a": 1}),
        ('{"status": true, "data": {"a": 1}}', {"a": 1}),
        ('{"status": false}', False),
        ('{"status": null, "errors": [1]}', {"status": None, "errors": [1]}),
        ("not json", "not json"),
    ],
)
def test_body(raw: str, body: Any) -> None:
    assert mcp_server._body(raw) == body


def test_duration() -> None:
    assert mcp_server._duration(3 * 3600 + 120) == "3 h 2 min"
    assert mcp_server._duration(2 * 86400 + 60) == "2 d 0 h 1 min"


# ── Catalog ─────────────────────────────────────────────────────────────


def test_catalog_leaves_out_telephony_and_restore(client: InternetBoxClient) -> None:
    from internetbox_client.mcp_server.catalog import EXCLUDED_FUNCTIONS, EXCLUDED_GROUPS, functions

    offered = functions(client)
    assert not {f.group for f in offered.values()} & EXCLUDED_GROUPS
    assert not set(offered) & EXCLUDED_FUNCTIONS
    assert "nmc.reboot" in offered and offered["nmc.reboot"].action == "disruptive"
    assert offered["devices.get"].summary == "Get devices."
    # The exclusions name real functions, so none of them stops working after a rename.
    for name in EXCLUDED_FUNCTIONS:
        group, method = name.split(".")
        assert callable(getattr(getattr(client, group), method)), name
    assert all(hasattr(client, group) for group in EXCLUDED_GROUPS)
