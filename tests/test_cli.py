"""Tests for the auto-generated CLI: argument types, parsing and error messages."""

from __future__ import annotations

import operator
from collections.abc import Mapping, Sequence
from typing import Any, Literal
from unittest.mock import MagicMock, patch

import pytest
import requests
from typer.testing import CliRunner

from internetbox_client import InternetBoxClient, cli

runner = CliRunner()

_COMMANDS = [
    ("wifi", "set_enabled"),
    ("mst", "set"),
    ("firewall", "set_port_forwarding"),
    ("scheduler", "set_device_schedule"),
    ("nmc", "reboot"),
    ("nmc", "restore"),
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
        ("text", str, "text"),
    ],
)
def test_coerce_value(value: str, annotation: object, expected: object) -> None:
    assert cli._coerce_value(value, annotation) == expected


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


def _http_error(body: bytes) -> requests.HTTPError:
    response = requests.Response()
    response.status_code, response._content = 500, body
    return requests.HTTPError("500 Server Error: Internal Server Error", response=response)


def test_router_error_reasons_are_shown(client: MagicMock) -> None:
    client.firewall.set_port_forwarding.side_effect = _http_error(
        b'{"status": null, "errors": [{"error": 1114117, "description": "Invalid port-range", "info": "InternalPort, ExternalPort"}]}'
    )
    result = runner.invoke(cli.app, ["firewall", "set-port-forwarding", "mc", "192.168.1.5", "25565"])
    assert result.exit_code == 1
    assert "The router rejected the request: 500 Server Error" in result.output
    assert "Router says: Invalid port-range (InternalPort, ExternalPort)" in result.output


@pytest.mark.parametrize("body", [b"<html>Internal error</html>", b'{"status": null}', b'{"errors": []}'])
def test_router_error_without_reasons(client: MagicMock, body: bytes) -> None:
    client.firewall.set_port_forwarding.side_effect = _http_error(body)
    result = runner.invoke(cli.app, ["firewall", "set-port-forwarding", "mc", "192.168.1.5", "25565"])
    assert result.exit_code == 1
    assert "The router rejected the request: 500 Server Error" in result.output
    assert "Router says" not in result.output


# Commands that ask for confirmation: CLI arguments, the question, and the call they make.
_CONFIRMED = [
    (["nmc", "reboot", "--reason", "maintenance"], "Restart the router?", "nmc.reboot", {"reason": "maintenance"}),
    (["nmc", "restore", "internetbox.cfg"], "Replace all settings with this backup?", "nmc.restore", {"path": "internetbox.cfg"}),
    (["wifi", "set-enabled", "false"], "Turn off all Wi-Fi networks?", "wifi.set_enabled", {"enable": False}),
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


def test_turning_wifi_on_doesnt_ask(client: MagicMock) -> None:
    result = runner.invoke(cli.app, ["wifi", "set-enabled", "true"])
    assert result.exit_code == 0
    assert "Turn off" not in result.output
    client.wifi.set_enabled.assert_called_once_with(enable=True)
