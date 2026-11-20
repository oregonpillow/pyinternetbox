"""Tests for the auto-generated CLI: argument types, parsing and error messages."""

from __future__ import annotations

import inspect
import operator
from collections.abc import Mapping, Sequence
from typing import Any, Literal
from unittest.mock import MagicMock, patch

import pytest
import requests
from typer.testing import CliRunner

from internetbox_client import InternetBoxClient, cli
from internetbox_client.utils.labels import action

runner = CliRunner()

_COMMANDS = [
    ("wifi", "set_enabled"),
    ("wifi", "set_guest_enabled"),
    ("wifi", "set_network"),
    ("wifi", "set_guest_network"),
    ("mst", "set"),
    ("firewall", "set_port_forwarding"),
    ("scheduler", "set_device_schedule"),
    ("nmc", "reboot"),
    ("nmc", "restore"),
    ("voice", "clear_call_list"),
    ("dns", "set_device_servers"),
    ("wifi", "set_channel"),
    ("wifi", "search_channel"),
    ("scheduler", "set_wifi_schedule"),
    ("scheduler", "enable_wifi_schedule"),
    ("firewall", "set_custom_rule"),
    ("firewall", "set_custom_policy"),
    ("wireguard", "set_server_enabled"),
]


@pytest.fixture()
def client() -> MagicMock:
    """Patch the CLI's client factory with a mock whose methods all return a JSON string."""
    mock = MagicMock()
    mock.configure_mock(**{f"{group}.{method}.return_value": '{"status": true}' for group, method in _COMMANDS})
    factory = MagicMock()
    factory.return_value.__enter__.return_value = mock
    with patch.object(cli, "_make_client", factory):
        yield mock


@pytest.mark.parametrize(
    "annotation,expected",
    [
        (str, str),
        (str | None, str),
        (int | None, int),
        (bool, bool),
        (dict, dict),
        (dict | None, dict),
        (dict[str, int], dict),
        (list, list),
        (list[dict], list),
        (Sequence[Mapping[str, Any]], list),
        (Literal["a", "b"] | None, Literal["a", "b"]),
    ],
)
def test_base_type(annotation: object, expected: object) -> None:
    assert cli._base_type(annotation) == expected


@pytest.mark.parametrize(
    "value,annotation,expected",
    [
        ('{"Sat": 240}', dict | None, {"Sat": 240}),
        ('[{"begin": 0}]', list, [{"begin": 0}]),
        ("a, b", list, ["a", "b"]),
        ("5", list, ["5"]),
        ("7", int, 7),
        ("tcp", Literal["tcp", "udp"], "tcp"),
        ("6", Literal[4, 6], 6),
        ("text", str, "text"),
        ("52", int | Literal["auto"], 52),
        ("auto", int | Literal["auto"], "auto"),
        ("auto", int | Literal["auto"] | None, "auto"),
    ],
)
def test_coerce_value(value: str, annotation: object, expected: object) -> None:
    assert cli._coerce_value(value, annotation) == expected


@pytest.mark.parametrize("value", ["Auto", "x", "5.5", ""])
def test_coerce_union_rejects_other_values(value: str) -> None:
    with pytest.raises(ValueError, match=f"Expected a whole number or 'auto', got {value!r}"):
        cli._coerce_value(value, int | Literal["auto"])


def test_union_argument(client: MagicMock) -> None:
    assert runner.invoke(cli.app, ["wifi", "set-channel", "2.4GHz", "auto", "--bandwidth", "20MHz", "--yes"]).exit_code == 0
    client.wifi.set_channel.assert_called_once_with(band="2.4GHz", channel="auto", bandwidth="20MHz")


def test_union_argument_rejects_other_values(client: MagicMock) -> None:
    result = runner.invoke(cli.app, ["wifi", "set-channel", "5GHz", "fast", "--yes"])
    assert result.exit_code == 2
    assert "Expected a whole number or 'auto', got 'fast'" in result.output
    client.wifi.set_channel.assert_not_called()


def test_union_argument_help_shows_values() -> None:
    assert "Channel (a whole number or 'auto')" in runner.invoke(cli.app, ["wifi", "set-channel", "--help"]).output


def test_int_choice_option(client: MagicMock) -> None:
    args = [
        "firewall",
        "set-custom-rule",
        "SSH",
        "22",
        "allow",
        "--ip-version",
        "6",
        "--direction",
        "inbound",
        "--device",
        "02:00:00:00:00:01",
    ]
    assert runner.invoke(cli.app, args).exit_code == 0
    client.firewall.set_custom_rule.assert_called_once_with(
        name="SSH", port="22", action="allow", ip_version=6, direction="inbound", protocol="both", device="02:00:00:00:00:01", enabled=True
    )


@pytest.mark.parametrize("value,expected", [("false", False), ("true", True)])
def test_bool_argument(client: MagicMock, value: str, expected: bool) -> None:
    result = runner.invoke(cli.app, ["wifi", "set-enabled", value, "--yes"])
    assert result.exit_code == 0
    client.wifi.set_enabled.assert_called_once_with(enable=expected)


def test_bool_argument_rejects_other_values(client: MagicMock) -> None:
    assert runner.invoke(cli.app, ["wifi", "set-enabled", "maybe"]).exit_code == 2
    client.wifi.set_enabled.assert_not_called()


def test_bool_argument_help_shows_values() -> None:
    assert "Enable (true or false)" in runner.invoke(cli.app, ["wifi", "set-enabled", "--help"]).output


def test_bool_option_with_true_default_can_be_turned_off(client: MagicMock) -> None:
    result = runner.invoke(cli.app, ["firewall", "set-port-forwarding", "mc", "192.168.1.5", "25565", "--no-enabled"])
    assert result.exit_code == 0
    assert client.firewall.set_port_forwarding.call_args.kwargs["enabled"] is False


def test_bool_option_default(client: MagicMock) -> None:
    runner.invoke(cli.app, ["firewall", "set-port-forwarding", "mc", "192.168.1.5", "25565"])
    assert client.firewall.set_port_forwarding.call_args.kwargs["enabled"] is True


def test_optional_int_and_dict_options(client: MagicMock) -> None:
    args = ["mst", "set", "aa:bb:cc:dd:ee:ff", "--minutes-per-day", "90", "--allowed-time", '{"Sat": 240}']
    assert runner.invoke(cli.app, args).exit_code == 0
    client.mst.set.assert_called_once_with(mac="aa:bb:cc:dd:ee:ff", enable=True, minutes_per_day=90, allowed_time={"Sat": 240})


def test_list_argument_from_json(client: MagicMock) -> None:
    args = ["scheduler", "set-device-schedule", "aa:bb:cc:dd:ee:ff", '[{"begin": "Mon 22:00", "end": "Tue 07:00"}]']
    assert runner.invoke(cli.app, args).exit_code == 0
    assert client.scheduler.set_device_schedule.call_args.kwargs["blocked_periods"] == [{"begin": "Mon 22:00", "end": "Tue 07:00"}]


@pytest.mark.parametrize("value,expected", [("1.1.1.1,9.9.9.9", ["1.1.1.1", "9.9.9.9"]), ("", [])])
def test_list_argument_comma_separated_or_empty(client: MagicMock, value: str, expected: list) -> None:
    assert runner.invoke(cli.app, ["dns", "set-device-servers", value]).exit_code == 0
    client.dns.set_device_servers.assert_called_once_with(servers=expected)


def test_invalid_json_is_a_usage_error(client: MagicMock) -> None:
    result = runner.invoke(cli.app, ["mst", "set", "aa:bb:cc:dd:ee:ff", "--allowed-time", "{bad"])
    assert result.exit_code == 2
    assert "allowed_time" in result.output
    client.mst.set.assert_not_called()


def test_invalid_input_shows_message_instead_of_traceback() -> None:
    """Validation errors raised by resource methods are reported without contacting the router."""
    with patch.object(cli, "_make_client", lambda: InternetBoxClient(hostname="192.0.2.1", ssl_verify=False)):
        result = runner.invoke(cli.app, ["mst", "set", "not-a-mac"])
    assert result.exit_code == 1
    assert "Not a MAC address: 'not-a-mac'" in result.output


def test_missing_file_shows_message_instead_of_traceback(tmp_path) -> None:
    missing = tmp_path / "missing.cfg"
    with patch.object(cli, "_make_client", lambda: InternetBoxClient(hostname="192.0.2.1", ssl_verify=False)):
        result = runner.invoke(cli.app, ["nmc", "restore", str(missing), "--yes"])
    assert result.exit_code == 1
    assert f"No such file or directory: '{missing}'" in result.output


def test_text_is_printed_as_it_is(client: MagicMock) -> None:
    """A backup redirected to a file is the router's file, without an extra newline."""
    client.nmc.backup.return_value = "QUJD\nRUZH\n"
    result = runner.invoke(cli.app, ["nmc", "backup"])
    assert result.exit_code == 0
    assert result.stdout == "QUJD\nRUZH\n"


def test_router_errors_are_shown(client: MagicMock) -> None:
    """The library adds the router's reasons to the message (see test_api_client)."""
    response = requests.Response()
    response.status_code = 500
    client.firewall.set_port_forwarding.side_effect = requests.HTTPError(
        "500 Server Error: Internal Server Error\nRouter says: Invalid port-range (InternalPort, ExternalPort)", response=response
    )
    result = runner.invoke(cli.app, ["firewall", "set-port-forwarding", "mc", "192.168.1.5", "25565"])
    assert result.exit_code == 1
    assert "The router rejected the request: 500 Server Error" in result.output
    assert "Router says: Invalid port-range (InternalPort, ExternalPort)" in result.output


# Commands that ask for confirmation: CLI arguments, the question, and the call they make.
_CONFIRMED = [
    (["nmc", "reboot", "--reason", "maintenance"], "Restart the router?", "nmc.reboot", {"reason": "maintenance"}),
    (["nmc", "restore", "internetbox.cfg"], "Replace all settings with this backup?", "nmc.restore", {"path": "internetbox.cfg"}),
    (["wifi", "set-enabled", "false"], "Turn off all Wi-Fi networks?", "wifi.set_enabled", {"enable": False}),
    (["wifi", "set-guest-enabled", "false"], "Turn off the guest Wi-Fi?", "wifi.set_guest_enabled", {"enable": False, "hours": 0}),
    (
        ["wifi", "set-network", "--ssid", "Home", "--no-visible", "--band", "5GHz"],
        "Change the Wi-Fi settings?",
        "wifi.set_network",
        {"ssid": "Home", "password": None, "visible": False, "band": "5GHz"},
    ),
    # The command's own --password, not the router password option of the same name.
    (
        ["wifi", "set-guest-network", "--password", "Guest-Password-1"],
        "Change the guest Wi-Fi settings?",
        "wifi.set_guest_network",
        {"ssid": None, "password": "Guest-Password-1"},
    ),
    (["voice", "clear-call-list"], "Delete all calls from the call list?", "voice.clear_call_list", {}),
    (
        ["wifi", "set-channel", "5GHz", "52"],
        "Change the Wi-Fi channel?",
        "wifi.set_channel",
        {"band": "5GHz", "channel": 52, "bandwidth": None},
    ),
    (["wifi", "search-channel", "2.4GHz"], "Let the router choose a new Wi-Fi channel now?", "wifi.search_channel", {"band": "2.4GHz"}),
    (
        ["scheduler", "set-wifi-schedule", '[{"begin": "Mon 01:00", "end": "Mon 06:00"}]'],
        "Turn Wi-Fi off on a schedule?",
        "scheduler.set_wifi_schedule",
        {"off_periods": [{"begin": "Mon 01:00", "end": "Mon 06:00"}], "enable": True},
    ),
    (["scheduler", "enable-wifi-schedule"], "Turn on the Wi-Fi schedule?", "scheduler.enable_wifi_schedule", {"enable": True}),
    (
        ["firewall", "set-custom-policy", "block"],
        "Block all outgoing traffic that no custom rule allows?",
        "firewall.set_custom_policy",
        {"action": "block", "ip_version": 4, "direction": "outbound"},
    ),
    (["wireguard", "set-server-enabled", "false"], "Turn off the WireGuard VPN server?", "wireguard.set_server_enabled", {"enable": False}),
]


@pytest.mark.parametrize("answer", ["n\n", "\n"])
@pytest.mark.parametrize("args,question,method,kwargs", _CONFIRMED)
def test_asks_first(args: list[str], question: str, method: str, kwargs: dict, answer: str) -> None:
    factory = MagicMock()
    with patch.object(cli, "_make_client", factory):
        result = runner.invoke(cli.app, args, input=answer)
    assert result.exit_code == 1
    assert question in result.output
    factory.assert_not_called()  # declined before logging in


@pytest.mark.parametrize("args,question,method,kwargs", _CONFIRMED)
def test_runs_after_confirmation(client: MagicMock, args: list[str], question: str, method: str, kwargs: dict) -> None:
    result = runner.invoke(cli.app, args, input="y\n")
    assert result.exit_code == 0
    operator.attrgetter(method)(client).assert_called_once_with(**kwargs)


@pytest.mark.parametrize("flag", ["--yes", "-y"])
@pytest.mark.parametrize("args,question,method,kwargs", _CONFIRMED)
def test_yes_skips_question(client: MagicMock, args: list[str], question: str, method: str, kwargs: dict, flag: str) -> None:
    result = runner.invoke(cli.app, [*args, flag])
    assert result.exit_code == 0
    assert question not in result.output
    operator.attrgetter(method)(client).assert_called_once_with(**kwargs)


@pytest.mark.parametrize(
    ("args", "method"), [(["wifi", "set-enabled", "true"], "set_enabled"), (["wifi", "set-guest-enabled", "true"], "set_guest_enabled")]
)
def test_turning_wifi_on_doesnt_ask(client: MagicMock, args: list[str], method: str) -> None:
    result = runner.invoke(cli.app, args)
    assert result.exit_code == 0
    assert "Turn off" not in result.output
    getattr(client.wifi, method).assert_called_once()


@pytest.mark.parametrize(
    "args,method",
    [
        (["scheduler", "set-wifi-schedule", '[{"begin": "Mon 01:00", "end": "Mon 06:00"}]', "--no-enable"], "scheduler.set_wifi_schedule"),
        (["scheduler", "set-wifi-schedule", "[]"], "scheduler.set_wifi_schedule"),
        (["scheduler", "enable-wifi-schedule", "--no-enable"], "scheduler.enable_wifi_schedule"),
        (["firewall", "set-custom-policy", "allow"], "firewall.set_custom_policy"),
        (["firewall", "set-custom-policy", "block", "--ip-version", "6", "--direction", "inbound"], "firewall.set_custom_policy"),
        (["wireguard", "set-server-enabled", "true"], "wireguard.set_server_enabled"),
    ],
)
def test_harmless_variants_dont_ask(client: MagicMock, args: list[str], method: str) -> None:
    """Wi-Fi stays on, blocking inbound traffic doesn't cut anyone off the internet, and the VPN server goes on."""
    result = runner.invoke(cli.app, args)
    assert result.exit_code == 0
    assert "?" not in result.output
    operator.attrgetter(method)(client).assert_called_once()


def test_disruptive_commands_ask_first() -> None:
    """Every method labelled disruptive has a confirmation question, at least for its disruptive arguments."""
    client = InternetBoxClient(hostname="192.0.2.1", ssl_verify=False)
    disruptive = {
        (group, name)
        for group, resource in vars(client).items()
        if not group.startswith("_")
        for name, method in inspect.getmembers(resource, inspect.ismethod)
        if action(method) == "disruptive"
    }
    assert disruptive
    assert disruptive <= set(cli._CONFIRM)
