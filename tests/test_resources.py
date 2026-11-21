"""Tests for resource classes.

Each resource is tested by verifying it calls the correct endpoint with the
expected payload via the mocked SessionManager.
"""

from __future__ import annotations

import json
import pathlib
import re
from unittest.mock import MagicMock, patch

import pytest
import requests

import internetbox_client.resources as resources
from internetbox_client.resources.ap_services import APServices
from internetbox_client.resources.carddav import CardDav
from internetbox_client.resources.debug import Debug
from internetbox_client.resources.dect import DECT
from internetbox_client.resources.devices import Devices
from internetbox_client.resources.dhcp import DHCP
from internetbox_client.resources.dns import DNS
from internetbox_client.resources.dyndns import DynDNS
from internetbox_client.resources.events import Events
from internetbox_client.resources.firewall import Firewall
from internetbox_client.resources.genlog import GenLog
from internetbox_client.resources.history import History
from internetbox_client.resources.http_service import HTTPService
from internetbox_client.resources.lan import LAN
from internetbox_client.resources.led import LED
from internetbox_client.resources.mitigation import Mitigation
from internetbox_client.resources.mst import MST
from internetbox_client.resources.nmc import NMC
from internetbox_client.resources.oops_tracker import OopsTracker
from internetbox_client.resources.password_recovery import PasswordRecovery
from internetbox_client.resources.phonebook import Phonebook
from internetbox_client.resources.power_management import PowerManagement
from internetbox_client.resources.scheduler import Scheduler
from internetbox_client.resources.security import Security
from internetbox_client.resources.speedtest import SpeedTest
from internetbox_client.resources.static import Static
from internetbox_client.resources.sysbus import Sysbus
from internetbox_client.resources.temperature import Temperature
from internetbox_client.resources.user_management import UserManagement
from internetbox_client.resources.voice import Voice
from internetbox_client.resources.vpn import VPN
from internetbox_client.resources.webui import WebUI
from internetbox_client.resources.wifi import Wifi
from internetbox_client.resources.wireguard import Wireguard
from internetbox_client.resources.wwan import WWAN
from internetbox_client.utils.helpers import decode_nested_json


def _make_resource(cls: type, sm: MagicMock):
    """Instantiate a resource class backed by a mock SessionManager."""
    obj = object.__new__(cls)
    obj._sm = sm
    obj._owns_session = False
    return obj


def _answering(sm: MagicMock, answers: dict[str, object], default: str = '{"status": true}') -> None:
    """Let the mock router answer by endpoint. A list is answered in turn; an exception is raised."""

    def post(endpoint: str, data: dict | None = None, auth_required: bool = True) -> str:
        answer = answers.get(endpoint, default)
        if isinstance(answer, list):
            answer = answer.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer

    sm.post.side_effect = post


def _sent(sm: MagicMock, reads: tuple[str, ...] = (":get", ":_get")) -> list[tuple]:
    """The (endpoint, data) of each request, except to functions ending with one of *reads*."""
    return [c[0][:2] for c in sm.post.call_args_list if not c[0][0].endswith(reads)]


def _http_error(status: int) -> requests.HTTPError:
    response = requests.Response()
    response.status_code = status
    return requests.HTTPError(f"{status} Server Error", response=response)


def test_sysbus_paths_use_slashes() -> None:
    """The router drops the connection for a path like /sysbus/VoiceService.VoiceApplication:listTrunks."""
    source = "".join(path.read_text() for path in pathlib.Path(resources.__file__).parent.glob("*.py"))
    objects = re.findall(r"[\"']/sysbus/([^\"':{]*)", source)
    assert len(objects) > 100
    assert [obj for obj in objects if "." in obj] == []


# ── APServices ────────────────────────────────────────────────────────


class TestAPServices:
    def test_info(self, mock_session_manager: MagicMock) -> None:
        svc = _make_resource(APServices, mock_session_manager)
        svc.info()
        mock_session_manager.post.assert_called_once()
        args = mock_session_manager.post.call_args
        assert args[0][0] == "/ws"
        data = args[0][1]
        assert data["service"] == "com.swisscom.apsm/apservicesinfo.com.swisscom.apsm.apservicesinfo"
        assert data["method"] == "Get"


# ── CardDav ───────────────────────────────────────────────────────────


class TestCardDav:
    def test_status(self, mock_session_manager: MagicMock) -> None:
        svc = _make_resource(CardDav, mock_session_manager)
        svc.status()
        mock_session_manager.post.assert_called_once()
        assert "/sysbus/CardDav:get" in mock_session_manager.post.call_args[0][0]


# ── Debug ─────────────────────────────────────────────────────────────


class TestDebug:
    def test_status(self, mock_session_manager: MagicMock) -> None:
        svc = _make_resource(Debug, mock_session_manager)
        svc.status()
        assert "/sysbus/NMC/Debug/DebugFile:get" in mock_session_manager.post.call_args[0][0]

    def test_wifi_driver_stats(self, mock_session_manager: MagicMock) -> None:
        svc = _make_resource(Debug, mock_session_manager)
        svc.wifi_driver_stats()
        assert "/sysbus/NMC/Debug:getWifiDriverStats" in mock_session_manager.post.call_args[0][0]

    @pytest.mark.parametrize(
        "method,request_",
        [
            ("save_log_file", ("/sysbus/NMC/Debug/DebugFile:set", {"parameters": {"GenerateFile": True}})),
            ("save_wifi_logs", ("/sysbus/NMC/Debug:generateWiFiLogs", {"parameters": {}})),
        ],
    )
    def test_save_logs(self, mock_session_manager: MagicMock, method: str, request_: tuple) -> None:
        svc = _make_resource(Debug, mock_session_manager)
        getattr(svc, method)()
        assert _sent(mock_session_manager) == [request_]


# ── DECT ──────────────────────────────────────────────────────────────


class TestDECT:
    @pytest.mark.parametrize(
        "method,endpoint",
        [
            ("base_state", "/sysbus/DECT:getBaseState"),
            ("nemo_state", "/sysbus/DECT:getNEMoState"),
            ("rfpi", "/sysbus/DECT:getRFPI"),
            ("pin", "/sysbus/DECT:getPIN"),
            ("version", "/sysbus/DECT:getVersion"),
            ("dspg", "/sysbus/DSPGDECT:get"),
            ("radio_state", "/sysbus/DECT:getRadioState"),
            ("pairing_status", "/sysbus/DECT:getPairingStatus"),
            ("standard_version", "/sysbus/DECT:getStandardVersion"),
            ("name", "/sysbus/DECT:getName"),
            ("ringtone", "/sysbus/VoiceService/VoiceApplication:getRingtone"),
        ],
    )
    def test_endpoints(self, mock_session_manager: MagicMock, method: str, endpoint: str) -> None:
        svc = _make_resource(DECT, mock_session_manager)
        getattr(svc, method)()
        assert mock_session_manager.post.call_args[0][0] == endpoint


# ── Devices ───────────────────────────────────────────────────────────


class TestDevices:
    def test_info_no_auth(self, mock_session_manager: MagicMock) -> None:
        svc = _make_resource(Devices, mock_session_manager)
        svc.info()
        args = mock_session_manager.post.call_args
        assert args[0][0] == "/sysbus/DeviceInfo:get"
        assert args[0][2] is False  # auth_required

    def test_get_default(self, mock_session_manager: MagicMock) -> None:
        svc = _make_resource(Devices, mock_session_manager)
        svc.get()
        data = mock_session_manager.post.call_args[0][1]
        assert data["service"] == "Devices"
        assert data["parameters"]["expression"] is None

    def test_get_with_expression(self, mock_session_manager: MagicMock) -> None:
        svc = _make_resource(Devices, mock_session_manager)
        svc.get(expression="lan and not self")
        data = mock_session_manager.post.call_args[0][1]
        assert data["parameters"]["expression"] == "lan and not self"

    def test_topology(self, mock_session_manager: MagicMock) -> None:
        svc = _make_resource(Devices, mock_session_manager)
        svc.topology()
        data = mock_session_manager.post.call_args[0][1]
        assert data["method"] == "topology"

    def test_usb(self, mock_session_manager: MagicMock) -> None:
        svc = _make_resource(Devices, mock_session_manager)
        svc.usb()
        assert mock_session_manager.post.call_args[0][0] == "/sysbus/USBHosts:getDevices"

    def test_memory_status(self, mock_session_manager: MagicMock) -> None:
        svc = _make_resource(Devices, mock_session_manager)
        svc.memory_status()
        assert mock_session_manager.post.call_args[0][0] == "/sysbus/DeviceInfo/MemoryStatus:get"

    @pytest.mark.parametrize("key,service", [("aa-bb-cc-dd-ee-ff", "Devices.Device.AA:BB:CC:DD:EE:FF"), ("HGW", "Devices.Device.HGW")])
    def test_rename(self, mock_session_manager: MagicMock, key: str, service: str) -> None:
        """Keys are case-sensitive: MAC addresses are normalised to the router's upper case, other keys pass unchanged."""
        svc = _make_resource(Devices, mock_session_manager)
        svc.rename(key, "Laptop")
        assert mock_session_manager.post.call_args[0][:2] == (
            "/ws",
            {"service": service, "method": "set", "parameters": {"parameters": {"Name": "Laptop"}}},
        )

    @pytest.mark.parametrize(
        "call,method,parameters",
        [
            (lambda svc: svc.reset_name("aa-bb-cc-dd-ee-ff"), "removeName", {"source": "webui"}),
            (lambda svc: svc.set_type("aa:bb:cc:dd:ee:ff", "tv box"), "set", {"parameters": {"DeviceType": "tv box"}}),
            (lambda svc: svc.set_dns_name("aa:bb:cc:dd:ee:ff", "nas-2"), "setName", {"name": "nas-2", "source": "dns"}),
            (lambda svc: svc.remove_dns_name("AA:BB:CC:DD:EE:FF"), "removeName", {"source": "dns"}),
        ],
    )
    def test_names_and_type(self, mock_session_manager: MagicMock, call, method: str, parameters: dict) -> None:
        svc = _make_resource(Devices, mock_session_manager)
        call(svc)
        assert _sent(mock_session_manager) == [
            ("/ws", {"service": "Devices.Device.AA:BB:CC:DD:EE:FF", "method": method, "parameters": parameters})
        ]

    def test_set_type_needs_a_web_ui_type(self, mock_session_manager: MagicMock) -> None:
        svc = _make_resource(Devices, mock_session_manager)
        with pytest.raises(ValueError, match=r"device_type must be one of the web UI's types: generic, computer, .*Got 'Computer'"):
            svc.set_type("aa:bb:cc:dd:ee:ff", "Computer")
        mock_session_manager.post.assert_not_called()

    @pytest.mark.parametrize("name", ["", "-nas", "nas-", "my nas", "nas.lan", "nås", "a" * 64])
    def test_set_dns_name_checks_the_name(self, mock_session_manager: MagicMock, name: str) -> None:
        svc = _make_resource(Devices, mock_session_manager)
        with pytest.raises(ValueError, match="1 to 63 letters, digits and hyphens"):
            svc.set_dns_name("aa:bb:cc:dd:ee:ff", name)
        mock_session_manager.post.assert_not_called()

    def test_reset_traffic_counters(self, mock_session_manager: MagicMock) -> None:
        """Like the web UI: the parameters aren't wrapped in "parameters", as they are for Devices.Device.{key}:set."""
        svc = _make_resource(Devices, mock_session_manager)
        svc.reset_traffic_counters()
        assert _sent(mock_session_manager) == [
            ("/ws", {"service": "Devices.Config.bandwidth", "method": "set", "parameters": {"Reset": 1}})
        ]

    def test_clear_traffic_history(self, mock_session_manager: MagicMock) -> None:
        svc = _make_resource(Devices, mock_session_manager)
        svc.clear_traffic_history("aa-bb-cc-dd-ee-ff")
        assert _sent(mock_session_manager) == [
            ("/sysbus/GenLog:clearLogs", {"parameters": {"topic": topic, "source": "Devices.Device.AA:BB:CC:DD:EE:FF"}})
            for topic in ("network", "network_persistent")
        ]

    _NO_TOPIC = (
        "500 Server Error\nRouter says: Topic does not exist for source (Devices.Device.AA:BB:CC:DD:EE:FF); Function execution failed"
    )

    def test_clear_traffic_history_without_network_persistent(self, mock_session_manager: MagicMock) -> None:
        """The Internet-Box 4 only keeps a Wi-Fi device's recent readings ("network") in GenLog, like on 15.21.36."""
        _answering(mock_session_manager, {"/sysbus/GenLog:clearLogs": ['{"status": true}', requests.HTTPError(self._NO_TOPIC)]})
        svc = _make_resource(Devices, mock_session_manager)
        assert svc.clear_traffic_history("aa:bb:cc:dd:ee:ff") == '{"status": true}'
        assert mock_session_manager.post.call_count == 2

    def test_clear_traffic_history_without_a_history(self, mock_session_manager: MagicMock) -> None:
        _answering(mock_session_manager, {"/sysbus/GenLog:clearLogs": requests.HTTPError(self._NO_TOPIC)})
        svc = _make_resource(Devices, mock_session_manager)
        with pytest.raises(ValueError, match="The router has no traffic history for aa:bb:cc:dd:ee:ff, e.g. because it's wired or never"):
            svc.clear_traffic_history("aa:bb:cc:dd:ee:ff")

    def test_clear_traffic_history_other_errors(self, mock_session_manager: MagicMock) -> None:
        _answering(
            mock_session_manager, {"/sysbus/GenLog:clearLogs": requests.HTTPError("500 Server Error\nRouter says: Permission denied")}
        )
        svc = _make_resource(Devices, mock_session_manager)
        with pytest.raises(requests.HTTPError, match="Permission denied"):
            svc.clear_traffic_history("aa:bb:cc:dd:ee:ff")

    def test_wake_on_lan(self, mock_session_manager: MagicMock) -> None:
        svc = _make_resource(Devices, mock_session_manager)
        svc.wake_on_lan("aa:bb:cc:dd:ee:ff")
        assert mock_session_manager.post.call_args[0][:2] == (
            "/sysbus/WOL:sendWakeOnLan",
            {"parameters": {"hostID": "AA:BB:CC:DD:EE:FF", "broadcast": True, "retries": 3, "interval": 60000}},
        )

    def test_summary(self, mock_session_manager: MagicMock) -> None:
        devices = [
            {
                "Key": "AA:BB:CC:DD:EE:01",
                "Name": "iPhone",
                "DeviceType": "iPhone",
                "Manufacturer": "Apple",
                "IPAddress": "192.168.1.20",
                "Active": True,
                "InterfaceName": "wl0",
                "OperatingFrequencyBand": "5GHz",
                "SignalStrength": -45,
                "LastConnection": "2026-11-19T20:18:29Z",
                "Actions": [{"Function": "setName"}],
            },
            {
                "Key": "AA:BB:CC:DD:EE:02",
                "Name": "NAS",
                "DeviceType": "Computer",
                "Manufacturer": "",
                "MACVendor": "Synology",
                "IPAddress": "192.168.1.5",
                "Active": True,
                "InterfaceName": "ETH4",
                "LastConnection": "2026-11-19T20:15:47Z",
            },
            {
                "Key": "AA:BB:CC:DD:EE:03",
                "Name": "Tablet",
                "Active": False,
                "InterfaceName": "wlguest2",
                "SignalStrength": -70,
                "IPAddress": "",
            },
            {"Key": "AA:BB:CC:DD:EE:04", "Name": "Printer", "Active": False, "InterfaceName": "", "LastConnection": "2026-10-01T08:00:00Z"},
        ]
        mock_session_manager.post.return_value = json.dumps({"status": devices})
        svc = _make_resource(Devices, mock_session_manager)
        assert json.loads(svc.summary()) == [
            {
                "name": "iPhone",
                "mac": "AA:BB:CC:DD:EE:01",
                "ip": "192.168.1.20",
                "type": "iPhone",
                "manufacturer": "Apple",
                "connected": True,
                "connection": "Wi-Fi 5GHz",
                "last_connection": "2026-11-19T20:18:29Z",
                "signal_dbm": -45,
            },
            {
                "name": "NAS",
                "mac": "AA:BB:CC:DD:EE:02",
                "ip": "192.168.1.5",
                "type": "Computer",
                "manufacturer": "Synology",
                "connected": True,
                "connection": "Ethernet (ETH4)",
                "last_connection": "2026-11-19T20:15:47Z",
            },
            # Signal strengths of devices that aren't connected are old.
            {
                "name": "Tablet",
                "mac": "AA:BB:CC:DD:EE:03",
                "ip": None,
                "type": None,
                "manufacturer": None,
                "connected": False,
                "connection": "guest Wi-Fi",
                "last_connection": None,
            },
            {
                "name": "Printer",
                "mac": "AA:BB:CC:DD:EE:04",
                "ip": None,
                "type": None,
                "manufacturer": None,
                "connected": False,
                "connection": None,
                "last_connection": "2026-10-01T08:00:00Z",
            },
        ]
        assert mock_session_manager.post.call_args[0][1]["parameters"]["expression"] == "lan and not self"


class TestDevicesRemove:
    """remove() deletes the device's settings first, like the web UI, then the device entry."""

    MAC = "AA:BB:CC:DD:EE:FF"
    OFFLINE = '{"status": {"Key": "AA:BB:CC:DD:EE:FF", "Active": false}}'

    @staticmethod
    def _calls(sm: MagicMock) -> list[str]:
        """Each call as "Service:method", whether it went to /sysbus/... or to /ws."""
        return [
            f"{c[0][1]['service']}:{c[0][1]['method']}" if c[0][0] == "/ws" else c[0][0].removeprefix("/sysbus/")
            for c in sm.post.call_args_list
        ]

    def test_remove_deletes_settings_then_device(self, mock_session_manager: MagicMock) -> None:
        mock_session_manager.post.side_effect = [
            self.OFFLINE,
            '{"status": [{"MACAddress": "AA:BB:CC:DD:EE:FF", "IPAddress": "192.168.1.20"}]}',
            '{"status": null}',
            '{"status": true, "data": {"scheduleInfo": {"enable": true}}}',
            '{"status": true}',
            '{"status": true}',
            '{"status": null, "data": {"ids": ["aabbccddeeff"]}}',
            '{"status": null}',
            '{"status": true}',
        ]
        result = _make_resource(Devices, mock_session_manager).remove("aa:bb:cc:dd:ee:ff")
        assert self._calls(mock_session_manager) == [
            f"Devices.Device.{self.MAC}:get",
            "DHCPv4/Server/Pool/default:getStaticLeases",
            "DHCPv4/Server/Pool/default:deleteStaticLease",
            "Scheduler:getSchedule",
            "Scheduler:enableSchedule",
            "Scheduler:removeSchedules",
            "ToD:listMST",
            "ToD:deleteMST",
            "Devices:destroyDevice",
        ]
        assert mock_session_manager.post.call_args[0][1]["parameters"] == {"key": self.MAC}
        assert result == '{"status": true}'

    def test_remove_skips_missing_reservation_and_time_limit(self, mock_session_manager: MagicMock) -> None:
        """Deleting a reservation or time limit that doesn't exist fails with HTTP 404, so those calls are skipped."""
        mock_session_manager.post.side_effect = [
            self.OFFLINE,
            '{"status": [{"MACAddress": "11:22:33:44:55:66", "IPAddress": "192.168.1.20"}]}',
            '{"status": false}',
            '{"status": true}',
            '{"status": null, "data": {"ids": []}}',
            '{"status": true}',
        ]
        _make_resource(Devices, mock_session_manager).remove(self.MAC)
        assert self._calls(mock_session_manager) == [
            f"Devices.Device.{self.MAC}:get",
            "DHCPv4/Server/Pool/default:getStaticLeases",
            "Scheduler:getSchedule",
            "Scheduler:removeSchedules",
            "ToD:listMST",
            "Devices:destroyDevice",
        ]

    def test_remove_refuses_connected_device(self, mock_session_manager: MagicMock) -> None:
        mock_session_manager.post.return_value = '{"status": {"Key": "AA:BB:CC:DD:EE:FF", "Active": true}}'
        with pytest.raises(ValueError, match="is connected"):
            _make_resource(Devices, mock_session_manager).remove(self.MAC)
        assert self._calls(mock_session_manager) == [f"Devices.Device.{self.MAC}:get"]


class TestDevicesParentalControls:
    """block/unblock combine schedule and time-limit calls, like the web UI's "Internet access blocked" switch."""

    MAC = "AA:BB:CC:DD:EE:FF"
    NO_SCHEDULE = '{"status": false}'
    SCHEDULE = '{"status": true, "data": {"scheduleInfo": {"ID": "AA:BB:CC:DD:EE:FF", "enable": true, "value": "Disable"}}}'

    @staticmethod
    def _endpoints(sm: MagicMock) -> list[str]:
        return [c[0][0].removeprefix("/sysbus/") for c in sm.post.call_args_list]

    @staticmethod
    def _payload(sm: MagicMock, endpoint: str) -> dict:
        return next(c[0][1]["parameters"] for c in sm.post.call_args_list if c[0][0] == f"/sysbus/{endpoint}")

    def test_block_without_schedule_creates_all_week_block(self, mock_session_manager: MagicMock) -> None:
        mock_session_manager.post.side_effect = [self.NO_SCHEDULE, '{"status": true}', '{"status": null}', self.SCHEDULE]
        result = _make_resource(Devices, mock_session_manager).block("aa-bb-cc-dd-ee-ff")
        assert self._endpoints(mock_session_manager) == [
            "Scheduler:getSchedule",
            "Scheduler:addSchedule",
            "ToD:setMST",
            "Scheduler:getSchedule",
        ]
        info = self._payload(mock_session_manager, "Scheduler:addSchedule")["info"]
        assert (info["ID"], info["enable"], info["schedule"]) == (self.MAC, True, [{"begin": 0, "end": 604800, "state": "Disable"}])
        assert self._payload(mock_session_manager, "ToD:setMST") == {"id": "aabbccddeeff", "subject": f"MAC:{self.MAC}", "enable": True}
        assert result == self.SCHEDULE

    def test_block_with_schedule_enables_it(self, mock_session_manager: MagicMock) -> None:
        mock_session_manager.post.side_effect = [self.SCHEDULE, '{"status": true}', '{"status": null}', self.SCHEDULE]
        _make_resource(Devices, mock_session_manager).block(self.MAC)
        assert self._endpoints(mock_session_manager) == [
            "Scheduler:getSchedule",
            "Scheduler:enableSchedule",
            "ToD:setMST",
            "Scheduler:getSchedule",
        ]
        assert self._payload(mock_session_manager, "Scheduler:enableSchedule") == {"type": "ToD", "ID": self.MAC, "enable": True}

    def test_unblock_turns_off_schedule_and_time_limit(self, mock_session_manager: MagicMock) -> None:
        mock_session_manager.post.side_effect = [
            self.SCHEDULE,
            '{"status": true}',
            '{"status": null, "data": {"ids": ["aabbccddeeff"]}}',
            '{"status": null}',
            self.SCHEDULE,
        ]
        _make_resource(Devices, mock_session_manager).unblock(self.MAC)
        assert self._endpoints(mock_session_manager) == [
            "Scheduler:getSchedule",
            "Scheduler:enableSchedule",
            "ToD:listMST",
            "ToD:setMST",
            "Scheduler:getSchedule",
        ]
        assert self._payload(mock_session_manager, "Scheduler:enableSchedule")["enable"] is False
        assert self._payload(mock_session_manager, "ToD:setMST")["enable"] is False

    def test_unblock_without_parental_controls_creates_nothing(self, mock_session_manager: MagicMock) -> None:
        mock_session_manager.post.side_effect = [self.NO_SCHEDULE, '{"status": null, "data": {"ids": ["112233445566"]}}', self.NO_SCHEDULE]
        result = _make_resource(Devices, mock_session_manager).unblock(self.MAC)
        assert self._endpoints(mock_session_manager) == ["Scheduler:getSchedule", "ToD:listMST", "Scheduler:getSchedule"]
        assert result == self.NO_SCHEDULE


# ── DHCP ──────────────────────────────────────────────────────────────


class TestDHCP:
    @pytest.mark.parametrize(
        "method,endpoint",
        [
            ("static_leases", "/sysbus/DHCPv4/Server/Pool/default:getStaticLeases"),
            ("server_pool", "/sysbus/DHCPv4/Server:getDHCPServerPool"),
            ("ipv6_prefix_information", "/sysbus/DHCPv6/Server:getPrefixInformation"),
        ],
    )
    def test_endpoints(self, mock_session_manager: MagicMock, method: str, endpoint: str) -> None:
        svc = _make_resource(DHCP, mock_session_manager)
        getattr(svc, method)()
        assert mock_session_manager.post.call_args[0][0] == endpoint

    def test_add_static_lease_normalises_mac(self, mock_session_manager: MagicMock) -> None:
        svc = _make_resource(DHCP, mock_session_manager)
        svc.add_static_lease("aa-bb-cc-dd-ee-ff", "192.168.1.20")
        assert mock_session_manager.post.call_args[0][:2] == (
            "/sysbus/DHCPv4/Server/Pool/default:addStaticLease",
            {"parameters": {"MACAddress": "AA:BB:CC:DD:EE:FF", "IPAddress": "192.168.1.20"}},
        )

    def test_delete_static_lease(self, mock_session_manager: MagicMock) -> None:
        svc = _make_resource(DHCP, mock_session_manager)
        svc.delete_static_lease("aa:bb:cc:dd:ee:ff")
        assert mock_session_manager.post.call_args[0][:2] == (
            "/sysbus/DHCPv4/Server/Pool/default:deleteStaticLease",
            {"parameters": {"MACAddress": "AA:BB:CC:DD:EE:FF"}},
        )

    def test_static_lease_rejects_invalid_mac(self, mock_session_manager: MagicMock) -> None:
        svc = _make_resource(DHCP, mock_session_manager)
        with pytest.raises(ValueError, match="Not a MAC address"):
            svc.add_static_lease("printer", "192.168.1.20")
        mock_session_manager.post.assert_not_called()


# ── DNS ───────────────────────────────────────────────────────────────


class TestDNS:
    def test_status_no_auth(self, mock_session_manager: MagicMock) -> None:
        svc = _make_resource(DNS, mock_session_manager)
        svc.status()
        assert mock_session_manager.post.call_args[0][2] is False  # auth_required

    @pytest.mark.parametrize(
        "method,endpoint",
        [
            ("mode", "/sysbus/DNS:get"),
            ("settings", "/sysbus/DNS/Server/Route:get"),
            ("user", "/sysbus/NMC/DHCPv4/DNSServers/User:get"),
            ("user_ipv6", "/sysbus/NMC/DHCPv6/DNSServers/User:get"),
            ("cache", "/sysbus/DNS/Server/Cache:get"),
        ],
    )
    def test_endpoints(self, mock_session_manager: MagicMock, method: str, endpoint: str) -> None:
        svc = _make_resource(DNS, mock_session_manager)
        getattr(svc, method)()
        assert mock_session_manager.post.call_args[0][0] == endpoint

    @pytest.mark.parametrize(
        "method,endpoint,servers,stored",
        [
            ("set_device_servers", "/sysbus/NMC/DHCPv4/DNSServers/User:set", ["1.1.1.1", " 9.9.9.9 "], "1.1.1.1,9.9.9.9"),
            ("set_device_servers", "/sysbus/NMC/DHCPv4/DNSServers/User:set", [], ""),
            ("set_device_servers_ipv6", "/sysbus/NMC/DHCPv6/DNSServers/User:set", ["2606:4700:4700:0::1111"], "2606:4700:4700::1111"),
            ("set_device_servers_ipv6", "/sysbus/NMC/DHCPv6/DNSServers/User:set", [], ""),
        ],
    )
    def test_set_device_servers(self, mock_session_manager: MagicMock, method: str, endpoint: str, servers: list, stored: str) -> None:
        svc = _make_resource(DNS, mock_session_manager)
        getattr(svc, method)(servers)
        assert mock_session_manager.post.call_args[0][:2] == (endpoint, {"parameters": {"DNSServers": stored}})

    @pytest.mark.parametrize(
        "method,servers,message",
        [
            ("set_device_servers", ["1.1.1.1", "1.0.0.1", "9.9.9.9"], "at most 2 DNS servers, got 3"),
            ("set_device_servers", ["dns.google"], "'dns.google' isn't an IPv4 address"),
            ("set_device_servers", ["2606:4700:4700::1111"], "isn't an IPv4 address"),
            ("set_device_servers_ipv6", ["1.1.1.1"], "'1.1.1.1' isn't an IPv6 address"),
        ],
    )
    def test_set_device_servers_checks_addresses(self, mock_session_manager: MagicMock, method: str, servers: list, message: str) -> None:
        svc = _make_resource(DNS, mock_session_manager)
        with pytest.raises(ValueError, match=message):
            getattr(svc, method)(servers)
        mock_session_manager.post.assert_not_called()

    def test_flush_cache(self, mock_session_manager: MagicMock) -> None:
        svc = _make_resource(DNS, mock_session_manager)
        svc.flush_cache()
        assert mock_session_manager.post.call_args[0][:2] == ("/sysbus/DNS/Server/Cache:flush", {"parameters": {}})

    def test_metrics(self, mock_session_manager: MagicMock) -> None:
        svc = _make_resource(DNS, mock_session_manager)
        svc.metrics()
        assert mock_session_manager.post.call_args[0][:2] == ("/sysbus/DNS/Server:getMetrics", {"parameters": {}})

    @pytest.mark.parametrize("enable", [True, False])
    def test_set_cache_enabled_empties_the_cache(self, mock_session_manager: MagicMock, enable: bool) -> None:
        svc = _make_resource(DNS, mock_session_manager)
        svc.set_cache_enabled(enable)
        assert _sent(mock_session_manager) == [
            ("/sysbus/DNS/Server:configureCache", {"parameters": {"enable": enable, "commit": True}}),
            ("/sysbus/DNS/Server/Cache:flush", {"parameters": {}}),
        ]


_ROUTES = json.dumps(
    {"status": {"webuidns1": {"Status": "Enabled", "DNS": "192.168.1.53"}, "dataV4_1": {"Status": "Disabled", "DNS": "193.247.204.23"}}}
)
_LAN_IP = json.dumps({"status": True, "data": {"Address": "192.168.1.1", "Netmask": "255.255.255.0"}})


class TestDNSUpstreamServers:
    """set_upstream_servers(), against a router that asks one server set in the web UI, 192.168.1.53."""

    READS = (":get", ":getLANIP")

    @staticmethod
    def _router(sm: MagicMock) -> DNS:
        _answering(sm, {"/sysbus/DNS/Server/Route:get": _ROUTES, "/sysbus/NMC:getLANIP": _LAN_IP})
        return _make_resource(DNS, sm)

    @pytest.mark.parametrize(
        "servers,saved,mode",
        [
            ([" 1.1.1.1", "192.168.1.53"], [("webuidns1", "1.1.1.1"), ("webuidns2", "192.168.1.53")], "Custom"),
            (["9.9.9.9", "9.9.9.9"], [("webuidns1", "9.9.9.9"), ("webuidns2", "9.9.9.9")], "Custom"),
            (["9.9.9.9"], [("webuidns1", "9.9.9.9")], "Custom"),
            ([], [], "All"),
        ],
    )
    def test_replaces_the_servers_like_the_web_ui(self, mock_session_manager: MagicMock, servers: list, saved: list, mode: str) -> None:
        self._router(mock_session_manager).set_upstream_servers(servers)
        assert _sent(mock_session_manager, self.READS) == [
            ("/sysbus/DNS/Server:deleteRoute", {"parameters": {"id": "webuidns1", "dns": "192.168.1.53", "commit": True}}),
            *[("/sysbus/DNS/Server:setRoute", {"parameters": {"id": route, "dns": dns, "commit": True}}) for route, dns in saved],
            ("/sysbus/DNS:setMode", {"parameters": {"mode": mode}}),
        ]

    @pytest.mark.parametrize(
        "servers,message",
        [
            (["1.1.1.1", "1.0.0.1", "9.9.9.9"], "at most 2 DNS servers, got 3"),
            (["dns.google"], "'dns.google' isn't an IPv4 address"),
            (["2606:4700:4700::1111"], "isn't an IPv4 address"),
            (["0.0.0.0"], "'0.0.0.0' can't be a DNS server"),
            (["224.0.0.251"], "reserved or multicast"),
            (["255.255.255.255"], "reserved or multicast"),
            (["10.0.0.53"], r"'10.0.0.53' isn't a device in your network \(192.168.1.0/24\)"),
            (["1.1.1.1", "172.16.0.53"], "'172.16.0.53' isn't a device in your network"),
            (["192.168.1.0"], "isn't a device in your network"),
            (["192.168.1.255"], "isn't a device in your network"),
        ],
    )
    def test_checks_the_servers_like_the_web_ui(self, mock_session_manager: MagicMock, servers: list, message: str) -> None:
        with pytest.raises(ValueError, match=message):
            self._router(mock_session_manager).set_upstream_servers(servers)
        assert _sent(mock_session_manager, self.READS) == []


# ── DynDNS ────────────────────────────────────────────────────────────


class TestDynDNS:
    @pytest.mark.parametrize(
        "method,endpoint",
        [
            ("global_enable", "/sysbus/DynDNS:getGlobalEnable"),
            ("hosts", "/sysbus/DynDNS:getHosts"),
            ("services", "/sysbus/DynDNS:getServices"),
        ],
    )
    def test_endpoints(self, mock_session_manager: MagicMock, method: str, endpoint: str) -> None:
        svc = _make_resource(DynDNS, mock_session_manager)
        getattr(svc, method)()
        assert mock_session_manager.post.call_args[0][0] == endpoint


class TestDynDNSHosts:
    """set_host() and delete_host(), against a router with Swisscom's own host."""

    SWISSCOM = {"service": "Swisscom", "hostname": "home.swisscom.example", "username": "sc", "password": "swisscom-secret", "enable": True}
    NO_IP = {"service": "No-IP", "hostname": "old.ddns.net", "username": "me", "password": "Old-password-1", "enable": True}
    NEW = {"service": "No-IP", "hostname": "myhome.ddns.net", "username": "me", "password": "New-password-2", "enable": True}
    READS = (":getHosts", ":getServices")

    @staticmethod
    def _dyndns(sm: MagicMock, hosts: list[dict], add: object = '{"status": true}') -> DynDNS:
        services = json.dumps({"status": ["Swisscom", "dyndns", "No-IP"]})
        _answering(
            sm,
            {
                "/sysbus/DynDNS:getHosts": json.dumps({"status": hosts}),
                "/sysbus/DynDNS:getServices": services,
                "/sysbus/DynDNS:addHost": add,
            },
        )
        return _make_resource(DynDNS, sm)

    def test_set_host_keeps_the_others(self, mock_session_manager: MagicMock) -> None:
        svc = self._dyndns(mock_session_manager, [self.SWISSCOM])
        assert svc.set_host("No-IP", "myhome.ddns.net", "me", "New-password-2") == '{"status": true}'
        assert _sent(mock_session_manager, self.READS) == [("/sysbus/DynDNS:addHost", {"parameters": self.NEW})]

    def test_set_host_replaces_same_service_and_same_hostname(self, mock_session_manager: MagicMock) -> None:
        same_name = {**self.NO_IP, "service": "dyndns", "hostname": "MyHome.ddns.net"}
        svc = self._dyndns(mock_session_manager, [self.SWISSCOM, self.NO_IP, same_name])
        svc.set_host("No-IP", "myhome.ddns.net", "me", "New-password-2", enable=False)
        assert _sent(mock_session_manager, self.READS) == [
            ("/sysbus/DynDNS:delHost", {"parameters": {"hostname": "old.ddns.net"}}),
            ("/sysbus/DynDNS:delHost", {"parameters": {"hostname": "MyHome.ddns.net"}}),
            ("/sysbus/DynDNS:addHost", {"parameters": {**self.NEW, "enable": False}}),
        ]

    @pytest.mark.parametrize("add", [[_http_error(500), '{"status": true}'], ['{"status": false}', '{"status": true}']])
    def test_set_host_puts_the_old_host_back_when_the_router_refuses(self, mock_session_manager: MagicMock, add: list) -> None:
        old = {**self.NO_IP, "status": "UPDATED", "last_update": "2026-11-20T10:00:00Z"}
        svc = self._dyndns(mock_session_manager, [old], add=add)
        with pytest.raises((requests.HTTPError, ValueError)):
            svc.set_host("No-IP", "myhome.ddns.net", "me", "New-password-2")
        assert _sent(mock_session_manager, self.READS) == [
            ("/sysbus/DynDNS:delHost", {"parameters": {"hostname": "old.ddns.net"}}),
            ("/sysbus/DynDNS:addHost", {"parameters": self.NEW}),
            ("/sysbus/DynDNS:addHost", {"parameters": self.NO_IP}),
        ]

    @pytest.mark.parametrize(
        "kwargs,message",
        [
            ({"service": "Swisscom"}, "set up by Swisscom"),
            ({"service": "Unknown"}, r"service must be one of \['dyndns', 'No-IP'\]"),
            ({"hostname": "home.swisscom.example"}, "is Swisscom's DynDNS host"),
            ({"hostname": "ab"}, "hostname must be a host name of 3 to 63"),
            ({"hostname": "myhome"}, "hostname must be"),
            ({"hostname": "1home.ddns.net"}, "hostname must be"),
            ({"hostname": "my_home.ddns.net"}, "hostname must be"),
            ({"hostname": "x" * 60 + ".net"}, "hostname must be"),
            ({"username": ""}, "username must be 1 to 63"),
            ({"username": "Jürg"}, "username must be"),
            ({"password": "Short-1"}, "password must be 12 to 63"),
            ({"password": "Pässword-long-1"}, "password must be"),
        ],
    )
    def test_set_host_refuses(self, mock_session_manager: MagicMock, kwargs: dict, message: str) -> None:
        svc = self._dyndns(mock_session_manager, [self.SWISSCOM])
        arguments = {"service": "No-IP", "hostname": "myhome.ddns.net", "username": "me", "password": "New-password-2", **kwargs}
        with pytest.raises(ValueError, match=message) as error:
            svc.set_host(**arguments)
        assert arguments["password"] not in str(error.value)
        assert _sent(mock_session_manager, self.READS) == []

    def test_delete_host(self, mock_session_manager: MagicMock) -> None:
        svc = self._dyndns(mock_session_manager, [self.SWISSCOM, self.NO_IP])
        svc.delete_host("OLD.ddns.net")
        assert _sent(mock_session_manager, self.READS) == [("/sysbus/DynDNS:delHost", {"parameters": {"hostname": "old.ddns.net"}})]

    @pytest.mark.parametrize(
        "hostname,message",
        [
            ("home.swisscom.example", "is Swisscom's DynDNS host"),
            ("other.ddns.net", "no DynDNS host 'other.ddns.net'. The hosts are: 'home"),
        ],
    )
    def test_delete_host_refuses(self, mock_session_manager: MagicMock, hostname: str, message: str) -> None:
        svc = self._dyndns(mock_session_manager, [self.SWISSCOM])
        with pytest.raises(ValueError, match=message):
            svc.delete_host(hostname)
        assert _sent(mock_session_manager, self.READS) == []


# ── Events ────────────────────────────────────────────────────────────


class TestEvents:
    def test_service_default(self, mock_session_manager: MagicMock) -> None:
        svc = _make_resource(Events, mock_session_manager)
        svc.service()
        data = mock_session_manager.post.call_args[0][1]
        assert data["service"] == "eventmanager"
        assert data["method"] == "get_events"

    def test_handler_builds_events(self, mock_session_manager: MagicMock) -> None:
        svc = _make_resource(Events, mock_session_manager)
        svc.handler(handler=["NMC.Wifi", "NMC.Guest"], id=5)
        data = mock_session_manager.post.call_args[0][1]
        assert len(data["parameters"]["events"]) == 2
        assert data["parameters"]["events"][0]["handler"] == "NMC.Wifi"

    def test_log_uppercases_mac(self, mock_session_manager: MagicMock) -> None:
        svc = _make_resource(Events, mock_session_manager)
        svc.log(mac="aa:bb:cc:dd:ee:ff")
        data = mock_session_manager.post.call_args[0][1]
        assert data["service"] == "Devices.Device.AA:BB:CC:DD:EE:FF"

    def test_open_channel(self, mock_session_manager: MagicMock) -> None:
        svc = _make_resource(Events, mock_session_manager)
        events = [{"handler": "NMC.Wifi"}]
        svc.open_channel(events=events)
        data = mock_session_manager.post.call_args[0][1]
        assert data["method"] == "open_channel"
        assert data["parameters"]["events"] == events

    def test_subscribe(self, mock_session_manager: MagicMock) -> None:
        svc = _make_resource(Events, mock_session_manager)
        svc.subscribe(events=[{"handler": "NMC.Wifi"}], id=1)
        data = mock_session_manager.post.call_args[0][1]
        assert data["method"] == "subscribe"
        assert data["parameters"]["channelid"] == 1

    def test_unsubscribe(self, mock_session_manager: MagicMock) -> None:
        svc = _make_resource(Events, mock_session_manager)
        svc.unsubscribe(events=[{"handler": "NMC.Wifi"}], id=1)
        data = mock_session_manager.post.call_args[0][1]
        assert data["method"] == "unsubscribe"

    def test_poll(self, mock_session_manager: MagicMock) -> None:
        svc = _make_resource(Events, mock_session_manager)
        svc.poll(id=7)
        data = mock_session_manager.post.call_args[0][1]
        assert data["parameters"]["channelid"] == 7

    def test_device_network(self, mock_session_manager: MagicMock) -> None:
        svc = _make_resource(Events, mock_session_manager)
        svc.device_network(macs=["aa:bb:cc:dd:ee:ff"])
        data = mock_session_manager.post.call_args[0][1]
        assert data["parameters"]["events"][0]["service"] == "Devices.Device.AA:BB:CC:DD:EE:FF"

    def test_ethernet_ports_default(self, mock_session_manager: MagicMock) -> None:
        svc = _make_resource(Events, mock_session_manager)
        svc.ethernet_ports()
        data = mock_session_manager.post.call_args[0][1]
        # 1 eth_device_updated + 5 port events
        assert len(data["parameters"]["events"]) == 6

    def test_ethernet_ports_custom(self, mock_session_manager: MagicMock) -> None:
        svc = _make_resource(Events, mock_session_manager)
        svc.ethernet_ports(ports=["ETH0", "ETH1"])
        data = mock_session_manager.post.call_args[0][1]
        assert len(data["parameters"]["events"]) == 3


# ── Firewall ──────────────────────────────────────────────────────────


class TestFirewall:
    @pytest.mark.parametrize(
        "method,endpoint",
        [
            ("dmz", "/sysbus/Firewall:getDMZ"),
            ("level", "/sysbus/Firewall:getFirewallLevel"),
            ("ipv6_level", "/sysbus/Firewall:getFirewallIPv6Level"),
            ("port_forwarding", "/sysbus/Firewall:getPortForwarding"),
            ("custom_rule", "/sysbus/Firewall:getCustomRule"),
            ("delete_dmz", "/sysbus/Firewall:deleteDMZ"),
            ("status", "/sysbus/Firewall:get"),
        ],
    )
    def test_endpoints(self, mock_session_manager: MagicMock, method: str, endpoint: str) -> None:
        svc = _make_resource(Firewall, mock_session_manager)
        getattr(svc, method)()
        assert mock_session_manager.post.call_args[0][0] == endpoint

    def test_set_upnp_enabled(self, mock_session_manager: MagicMock) -> None:
        svc = _make_resource(Firewall, mock_session_manager)
        svc.set_upnp_enabled(True)
        mock_session_manager.post.assert_called_once_with("/sysbus/Firewall:set", {"parameters": {"UpnpPortForwardingEnable": True}}, True)

    @pytest.mark.parametrize(
        "method,endpoint,level",
        [("set_level", "/sysbus/Firewall:setFirewallLevel", "Low"), ("set_ipv6_level", "/sysbus/Firewall:setFirewallIPv6Level", "Off")],
    )
    def test_set_levels(self, mock_session_manager: MagicMock, method: str, endpoint: str, level: str) -> None:
        svc = _make_resource(Firewall, mock_session_manager)
        getattr(svc, method)(level)
        assert mock_session_manager.post.call_args[0][:2] == (endpoint, {"parameters": {"level": level}})

    def test_set_port_forwarding_payload_then_commit(self, mock_session_manager: MagicMock) -> None:
        mock_session_manager.post.side_effect = ['{"status": "webui_minecraft"}', '{"status": true}']
        svc = _make_resource(Firewall, mock_session_manager)
        result = svc.set_port_forwarding("minecraft", "192.168.1.20", 25565)
        (set_call, commit_call) = mock_session_manager.post.call_args_list
        assert set_call[0][0] == "/sysbus/Firewall:setPortForwarding"
        assert set_call[0][1] == {
            "parameters": {
                "id": "minecraft",
                "description": "minecraft",
                "persistent": True,
                "origin": "webui",
                "sourceInterface": "data",
                "sourcePrefix": "",
                "enable": True,
                "protocol": "6,17",
                "destinationIPAddress": "192.168.1.20",
                "externalPort": "25565",
                "internalPort": "25565",
            }
        }
        assert commit_call[0][:2] == ("/sysbus/Firewall:commit", {"parameters": {}})
        assert result == '{"status": "webui_minecraft"}'

    @pytest.mark.parametrize("protocol,code", [("tcp", "6"), ("udp", "17"), ("both", "6,17")])
    def test_set_port_forwarding_options(self, mock_session_manager: MagicMock, protocol: str, code: str) -> None:
        svc = _make_resource(Firewall, mock_session_manager)
        svc.set_port_forwarding("web", "192.168.1.20", "8000-8010", "9000", protocol=protocol, enabled=False)
        params = mock_session_manager.post.call_args_list[0][0][1]["parameters"]
        assert (params["protocol"], params["externalPort"], params["internalPort"], params["enable"]) == (code, "8000-8010", "9000", False)

    @pytest.mark.parametrize("external,internal", [("8000-8010", None), ("8000-8010", "8000-8010"), ("80", "8080")])
    def test_set_port_forwarding_accepted_port_combinations(
        self, mock_session_manager: MagicMock, external: str, internal: str | None
    ) -> None:
        svc = _make_resource(Firewall, mock_session_manager)
        svc.set_port_forwarding("web", "192.168.1.20", external, internal)
        params = mock_session_manager.post.call_args_list[0][0][1]["parameters"]
        assert (params["externalPort"], params["internalPort"]) == (external, internal or external)

    @pytest.mark.parametrize("external,internal", [("8000-8010", "9000-9010"), ("80", "8080-8081")])
    def test_set_port_forwarding_rejects_other_internal_range(self, mock_session_manager: MagicMock, external: str, internal: str) -> None:
        """The router only forwards a range to the same range or to a single port ("Invalid port-range" otherwise)."""
        svc = _make_resource(Firewall, mock_session_manager)
        with pytest.raises(ValueError, match="same range"):
            svc.set_port_forwarding("web", "192.168.1.20", external, internal)
        mock_session_manager.post.assert_not_called()

    def test_set_port_forwarding_rejects_unknown_protocol(self, mock_session_manager: MagicMock) -> None:
        svc = _make_resource(Firewall, mock_session_manager)
        with pytest.raises(ValueError, match="protocol"):
            svc.set_port_forwarding("web", "192.168.1.20", "80", protocol="icmp")
        mock_session_manager.post.assert_not_called()

    def test_delete_port_forwarding_then_commit(self, mock_session_manager: MagicMock) -> None:
        svc = _make_resource(Firewall, mock_session_manager)
        svc.delete_port_forwarding("webui_minecraft")
        (delete_call, commit_call) = mock_session_manager.post.call_args_list
        assert delete_call[0][:2] == ("/sysbus/Firewall:deletePortForwarding", {"parameters": {"id": "webui_minecraft", "origin": "webui"}})
        assert commit_call[0][0] == "/sysbus/Firewall:commit"

    def test_set_dmz(self, mock_session_manager: MagicMock) -> None:
        svc = _make_resource(Firewall, mock_session_manager)
        svc.set_dmz("192.168.1.20")
        assert mock_session_manager.post.call_args[0][:2] == (
            "/sysbus/Firewall:setDMZ",
            {"parameters": {"id": "webui", "sourceInterface": "data", "destinationIPAddress": "192.168.1.20", "enable": True}},
        )

    def test_delete_all_port_forwarding_then_commit(self, mock_session_manager: MagicMock) -> None:
        """Without an ID, the router deletes all rules of the origin: those made in the web UI, not by UPnP."""
        svc = _make_resource(Firewall, mock_session_manager)
        svc.delete_all_port_forwarding()
        assert _sent(mock_session_manager) == [
            ("/sysbus/Firewall:deletePortForwarding", {"parameters": {"origin": "webui"}}),
            ("/sysbus/Firewall:commit", {"parameters": {}}),
        ]

    def test_respond_to_ping(self, mock_session_manager: MagicMock) -> None:
        svc = _make_resource(Firewall, mock_session_manager)
        svc.respond_to_ping()
        assert _sent(mock_session_manager) == [("/sysbus/Firewall:getRespondToPing", {"parameters": {"sourceInterface": "data"}})]

    @pytest.mark.parametrize(
        "args,service",
        [
            ((False,), {"enableIPv4": False, "enableIPv6": False}),
            ((True,), {"enableIPv4": True, "enableIPv6": True}),
            ((False, 4), {"enableIPv4": False, "enableIPv6": True}),
            ((False, 6), {"enableIPv4": True, "enableIPv6": False}),
        ],
    )
    def test_set_respond_to_ping_keeps_the_other_ip_version(self, mock_session_manager: MagicMock, args: tuple, service: dict) -> None:
        _answering(mock_session_manager, {"/sysbus/Firewall:getRespondToPing": '{"status": {"enableIPv4": true, "enableIPv6": true}}'})
        svc = _make_resource(Firewall, mock_session_manager)
        svc.set_respond_to_ping(*args)
        assert _sent(mock_session_manager, (":getRespondToPing",)) == [
            ("/sysbus/Firewall:setRespondToPing", {"parameters": {"sourceInterface": "data", "service_enable": service}})
        ]

    def test_set_respond_to_ping_checks_the_ip_version(self, mock_session_manager: MagicMock) -> None:
        svc = _make_resource(Firewall, mock_session_manager)
        with pytest.raises(ValueError, match="ip_version must be 4 or 6, got 5"):
            svc.set_respond_to_ping(False, 5)  # type: ignore[arg-type]
        mock_session_manager.post.assert_not_called()

    @pytest.mark.parametrize("method,endpoint", [("protocol_forwarding", "getProtocolForwarding"), ("ipv6_pinholes", "getPinhole")])
    def test_reads(self, mock_session_manager: MagicMock, method: str, endpoint: str) -> None:
        svc = _make_resource(Firewall, mock_session_manager)
        getattr(svc, method)()
        assert _sent(mock_session_manager) == [(f"/sysbus/Firewall:{endpoint}", {"parameters": {}})]

    @pytest.mark.parametrize("protocol,stored", [("gre", "47"), (" ESP , ah", "50,51"), ("47", "47"), ("0,255", "0,255")])
    def test_set_protocol_forwarding_then_commit(self, mock_session_manager: MagicMock, protocol: str, stored: str) -> None:
        svc = _make_resource(Firewall, mock_session_manager)
        svc.set_protocol_forwarding("vpn", "192.168.1.20", protocol, enabled=False)
        parameters = {
            "id": "vpn",
            "description": "vpn",
            "persistent": True,
            "sourceInterface": "data",
            "enable": False,
            "protocol": stored,
            "destinationIPAddress": "192.168.1.20",
        }
        assert _sent(mock_session_manager) == [
            ("/sysbus/Firewall:setProtocolForwarding", {"parameters": parameters}),
            ("/sysbus/Firewall:commit", {"parameters": {}}),
        ]

    @pytest.mark.parametrize("protocol", ["", "icmp", "256", "-1", "47,", "4.7"])
    def test_set_protocol_forwarding_checks_the_protocol(self, mock_session_manager: MagicMock, protocol: str) -> None:
        svc = _make_resource(Firewall, mock_session_manager)
        with pytest.raises(ValueError, match="protocol must be numbers from 0 to 255"):
            svc.set_protocol_forwarding("vpn", "192.168.1.20", protocol)
        mock_session_manager.post.assert_not_called()

    def test_delete_protocol_forwarding_then_commit(self, mock_session_manager: MagicMock) -> None:
        svc = _make_resource(Firewall, mock_session_manager)
        svc.delete_protocol_forwarding("vpn")
        assert _sent(mock_session_manager) == [
            ("/sysbus/Firewall:deleteProtocolForwarding", {"parameters": {"id": "vpn"}}),
            ("/sysbus/Firewall:commit", {"parameters": {}}),
        ]

    @pytest.mark.parametrize("port,protocol,stored", [("25565", "both", ("25565", "6,17")), ("8000 - 8010", "udp", ("8000-8010", "17"))])
    def test_set_ipv6_pinhole_then_commit(self, mock_session_manager: MagicMock, port: str, protocol: str, stored: tuple) -> None:
        svc = _make_resource(Firewall, mock_session_manager)
        svc.set_ipv6_pinhole("minecraft", "2001:DB8:0::20", port, protocol)  # type: ignore[arg-type]
        parameters = {
            "id": "minecraft",
            "description": "minecraft",
            "origin": "webui",
            "sourceInterface": "data",
            "sourcePort": "",
            "sourcePrefix": "",
            "destinationPort": stored[0],
            "destinationIPAddress": "2001:db8::20",
            "destinationMACAddress": "",
            "protocol": stored[1],
            "ipversion": 6,
            "enable": True,
            "persistent": True,
        }
        assert _sent(mock_session_manager) == [
            ("/sysbus/Firewall:setPinhole", {"parameters": parameters}),
            ("/sysbus/Firewall:commit", {"parameters": {}}),
        ]

    @pytest.mark.parametrize(
        "args,message",
        [
            (("192.168.1.20", "80"), "destination_ip must be an IPv6 address, got '192.168.1.20'"),
            (("2001:db8::20", "0"), "Ports must be between 1 and 65535"),
            (("2001:db8::20", "http"), "port must be a port such as 443"),
            (("2001:db8::20", "80", "icmp"), "protocol must be one of"),
        ],
    )
    def test_set_ipv6_pinhole_checks_the_values(self, mock_session_manager: MagicMock, args: tuple, message: str) -> None:
        svc = _make_resource(Firewall, mock_session_manager)
        with pytest.raises(ValueError, match=message):
            svc.set_ipv6_pinhole("web", *args)
        mock_session_manager.post.assert_not_called()

    def test_delete_ipv6_pinhole_then_commit(self, mock_session_manager: MagicMock) -> None:
        svc = _make_resource(Firewall, mock_session_manager)
        svc.delete_ipv6_pinhole("minecraft")
        assert _sent(mock_session_manager) == [
            ("/sysbus/Firewall:deletePinhole", {"parameters": {"id": "minecraft", "origin": "webui"}}),
            ("/sysbus/Firewall:commit", {"parameters": {}}),
        ]


def _custom_rule(rule_id: str, name: str, port: str, target: str = "Drop", protocol: str = "6", mac: str = "", **fields: object) -> dict:
    """A custom rule as the router stores it. Inbound IPv6 rules use DestinationMACAddress instead."""
    rule = {"Id": rule_id, "Target": target, "Status": "Disabled", "Class": "Forward", "IPVersion": 4, "Protocol": protocol}
    rule |= {"DestinationPort": port, "SourcePort": "", "DestinationMACAddress": "", "SourceMACAddress": mac, "DestinationPrefix": ""}
    return rule | {"SourcePrefix": "", "TargetChain": "", "Description": name, "Enable": True, **fields}


class TestFirewallCustomRules:
    """Custom rules and chain policies, against a router with an IPv4 rule blocking Telnet."""

    TELNET = _custom_rule("1700000000000_1", "Telnet", "23")
    STAMP = 1763600000.123  # time.time() for new rule IDs: 1763600000123_1
    READS = (":getCustomRule", ":getChainPolicy")

    @staticmethod
    def _firewall(sm: MagicMock, rules: dict[str, dict] | None = None, policies: dict[str, str] | None = None) -> Firewall:
        policies = {"Custom": "Accept", "Custom_V6Out": "Accept", "Custom_V6In": "Drop", **(policies or {})}

        def post(endpoint: str, data: dict | None = None, auth_required: bool = True) -> str:
            parameters = (data or {}).get("parameters") or {}
            if endpoint.endswith(":getCustomRule"):
                return json.dumps({"status": (rules or {}).get(parameters.get("chain", "Custom"), {})})
            if endpoint.endswith(":getChainPolicy"):
                return json.dumps({"status": policies[parameters["chain"]]})
            if endpoint.endswith(":setCustomRule"):
                return json.dumps({"status": parameters["id"]})
            return '{"status": true}'

        sm.post.side_effect = post
        return _make_resource(Firewall, sm)

    @staticmethod
    def _rule(rule_id: str, chain: str, name: str, port: str, action: str, protocol: str = "6,17", version: int = 4, **mac: str) -> dict:
        """The setCustomRule parameters for a rule."""
        mac = mac or {"destinationMAC" if chain == "Custom_V6In" else "sourceMAC": ""}
        parameters = {"id": rule_id, "chain": chain, "description": name, "action": action, "ipversion": version, "protocol": protocol}
        return {"parameters": {**parameters, "destinationPort": port, **mac, "enable": True, "persistent": True}}

    def test_custom_rule_of_a_chain(self, mock_session_manager: MagicMock) -> None:
        svc = _make_resource(Firewall, mock_session_manager)
        svc.custom_rule("Custom_V6In")
        assert mock_session_manager.post.call_args[0][:2] == ("/sysbus/Firewall:getCustomRule", {"parameters": {"chain": "Custom_V6In"}})

    def test_custom_rules(self, mock_session_manager: MagicMock) -> None:
        ssh = _custom_rule(
            "1700000000000_2", "SSH", "22-23", target="Accept", protocol="6,17", IPVersion=6, DestinationMACAddress="AA:BB:CC:DD:EE:FF"
        )
        unnamed = _custom_rule("old-rule", "", "5000", protocol="17", mac="11:22:33:44:55:66", Enable=False)
        svc = self._firewall(
            mock_session_manager, {"Custom": {"1700000000000_1": self.TELNET, "old-rule": unnamed}, "Custom_V6In": {"1700000000000_2": ssh}}
        )
        common = {"ip_version": 4, "direction": "outbound", "chain": "Custom"}
        assert json.loads(svc.custom_rules()) == [
            {
                "name": "Telnet",
                "port": "23",
                "action": "block",
                "protocol": "tcp",
                "device": None,
                "enabled": True,
                "id": "1700000000000_1",
                **common,
            },
            {
                "name": "old-rule",
                "port": "5000",
                "action": "block",
                "protocol": "udp",
                "device": "11:22:33:44:55:66",
                "enabled": False,
                "id": "old-rule",
                **common,
            },
            {
                "name": "SSH",
                "port": "22-23",
                "action": "allow",
                "ip_version": 6,
                "direction": "inbound",
                "protocol": "both",
                "device": "AA:BB:CC:DD:EE:FF",
                "enabled": True,
                "id": "1700000000000_2",
                "chain": "Custom_V6In",
            },
        ]

    def test_add_rule(self, mock_session_manager: MagicMock) -> None:
        svc = self._firewall(mock_session_manager, {"Custom": {"1700000000000_1": self.TELNET}})
        with patch("internetbox_client.resources.firewall.time.time", return_value=self.STAMP):
            result = svc.set_custom_rule("Games", "27000-27050", "allow", protocol="udp", device="02-00-00-00-00-01", enabled=False)
        expected = self._rule("1763600000123_1", "Custom", "Games", "27000-27050", "Accept", protocol="17", sourceMAC="02:00:00:00:00:01")
        expected["parameters"]["enable"] = False
        assert _sent(mock_session_manager, self.READS) == [
            ("/sysbus/Firewall:setCustomRule", expected),
            ("/sysbus/Firewall:commit", {"parameters": {}}),
        ]
        assert result == '{"status": "1763600000123_1"}'

    @pytest.mark.parametrize(
        "direction,chain,mac",
        [
            ("outbound", "Custom_V6Out", {"sourceMAC": "02:00:00:00:00:01"}),
            ("inbound", "Custom_V6In", {"destinationMAC": "02:00:00:00:00:01"}),
        ],
    )
    def test_ipv6_rules(self, mock_session_manager: MagicMock, direction: str, chain: str, mac: dict) -> None:
        svc = self._firewall(mock_session_manager)
        with patch("internetbox_client.resources.firewall.time.time", return_value=self.STAMP):
            svc.set_custom_rule("SSH", 22, "allow", ip_version=6, direction=direction, device="02:00:00:00:00:01")
        assert _sent(mock_session_manager, self.READS)[0] == (
            "/sysbus/Firewall:setCustomRule",
            self._rule("1763600000123_1", chain, "SSH", "22", "Accept", version=6, **mac),
        )

    def test_new_id_differs_from_existing_ids(self, mock_session_manager: MagicMock) -> None:
        taken = _custom_rule("1763600000123_1", "Other", "80")
        svc = self._firewall(mock_session_manager, {"Custom": {"1763600000123_1": taken}})
        with patch("internetbox_client.resources.firewall.time.time", return_value=self.STAMP):
            svc.set_custom_rule("Games", "27000", "block", protocol="udp")
        assert _sent(mock_session_manager, self.READS)[0][1]["parameters"]["id"] == "1763600000123_2"

    @pytest.mark.parametrize(
        "kwargs,chain,version", [({}, "Custom", 4), ({"ip_version": 6}, "Custom_V6Out", 6)], ids=["same chain", "another chain"]
    )
    def test_changing_a_rule_replaces_it(self, mock_session_manager: MagicMock, kwargs: dict, chain: str, version: int) -> None:
        """Like the web UI. The new rule comes first, so the old one stays if it fails. It doesn't overlap the old one."""
        svc = self._firewall(mock_session_manager, {"Custom": {"1700000000000_1": self.TELNET}})
        with patch("internetbox_client.resources.firewall.time.time", return_value=self.STAMP):
            result = svc.set_custom_rule("Telnet", "23-24", "block", **kwargs)
        assert _sent(mock_session_manager, self.READS) == [
            ("/sysbus/Firewall:setCustomRule", self._rule("1763600000123_1", chain, "Telnet", "23-24", "Drop", version=version)),
            ("/sysbus/Firewall:deleteCustomRule", {"parameters": {"id": "1700000000000_1", "chain": "Custom"}}),
            ("/sysbus/Firewall:commit", {"parameters": {}}),
        ]
        assert result == '{"status": "1763600000123_1"}'

    def test_changing_a_rule_that_the_router_refuses_keeps_the_old_one(self, mock_session_manager: MagicMock) -> None:
        svc = self._firewall(mock_session_manager, {"Custom": {"1700000000000_1": self.TELNET}})
        answer = mock_session_manager.post.side_effect

        def post(endpoint: str, *args: object) -> str:
            if endpoint.endswith(":setCustomRule"):
                raise _http_error(500)
            return answer(endpoint, *args)

        mock_session_manager.post.side_effect = post
        with pytest.raises(requests.HTTPError):
            svc.set_custom_rule("Telnet", "23-24", "block")
        assert [endpoint for endpoint, _ in _sent(mock_session_manager, self.READS)] == ["/sysbus/Firewall:setCustomRule"]

    @pytest.mark.parametrize(
        "kwargs",
        [
            {"port": "23", "protocol": "udp"},  # other protocol
            {"port": "24"},  # other port
            {"port": "23", "ip_version": 6},  # other chain
            {"port": "23", "device": "02:00:00:00:00:02"},  # other device than the rule's
        ],
    )
    def test_rules_that_dont_overlap(self, mock_session_manager: MagicMock, kwargs: dict) -> None:
        telnet = _custom_rule("1700000000000_1", "Telnet", "23", mac="02:00:00:00:00:01")
        svc = self._firewall(mock_session_manager, {"Custom": {"1700000000000_1": telnet}})
        svc.set_custom_rule("New", action="block", **kwargs)
        assert _sent(mock_session_manager, self.READS)[-1] == ("/sysbus/Firewall:commit", {"parameters": {}})

    @pytest.mark.parametrize(
        "kwargs,message",
        [
            ({"port": "20-30"}, "overlaps the custom rule 'Telnet' \\(port 23\\)"),
            ({"port": "23", "action": "allow", "protocol": "tcp"}, "contradicts the custom rule 'Telnet'"),
            ({"port": "23", "device": "02:00:00:00:00:01"}, "overlaps"),  # the Telnet rule is for all devices
            ({"port": "1-65535", "action": "block", "protocol": "udp"}, "same action as the basic action"),
            ({"port": "80", "direction": "inbound"}, "IPv4 custom rules are outbound only"),
            ({"port": "80", "ip_version": 5}, "ip_version must be 4 or 6"),
            ({"port": "80", "direction": "both"}, 'direction must be "outbound" or "inbound"'),
            ({"port": "80", "action": "deny"}, 'action must be "allow" or "block"'),
            ({"port": "80", "protocol": "icmp"}, "protocol must be one of"),
            ({"port": "80", "name": ""}, "name must be 1 to 40"),
            ({"port": "80", "name": " "}, "name must be 1 to 40"),
            ({"port": "80", "name": "x" * 41}, "name must be 1 to 40"),
            ({"port": "80", "name": "Café"}, "name must be 1 to 40"),
            ({"port": "0"}, "between 1 and 65535"),
            ({"port": "65536"}, "between 1 and 65535"),
            ({"port": "8010-8000"}, "from a lower to a higher port"),
            ({"port": "80-80"}, "from a lower to a higher port"),
            ({"port": "http"}, "port must be a port such as 443"),
            ({"port": "80", "device": "phone"}, "Not a MAC address"),
        ],
    )
    def test_refuses(self, mock_session_manager: MagicMock, kwargs: dict, message: str) -> None:
        svc = self._firewall(mock_session_manager, {"Custom": {"1700000000000_1": self.TELNET}})
        with pytest.raises(ValueError, match=message):
            svc.set_custom_rule(**{"name": "New", "action": "block", **kwargs})
        assert _sent(mock_session_manager, self.READS) == []

    @pytest.mark.parametrize("policy,action", [("Accept", "allow"), ("Drop", "block")])
    def test_all_ports_with_the_basic_action(self, mock_session_manager: MagicMock, policy: str, action: str) -> None:
        svc = self._firewall(mock_session_manager, policies={"Custom_V6Out": policy})
        svc.set_custom_rule("All", "1-65535", action, ip_version=6)
        assert _sent(mock_session_manager, self.READS)[0][1]["parameters"]["destinationPort"] == "1-65535"

    def test_enable_custom_rule_keeps_its_settings(self, mock_session_manager: MagicMock) -> None:
        """Including settings the web UI can't make, e.g. a source prefix."""
        rule = _custom_rule(
            "1700000000000_2",
            "Mail",
            "25",
            protocol="6",
            IPVersion=6,
            SourcePrefix="2001:db8::/64",
            DestinationMACAddress="02:00:00:00:00:01",
        )
        svc = self._firewall(mock_session_manager, {"Custom_V6In": {"1700000000000_2": rule}})
        svc.enable_custom_rule("Mail", False)
        expected = self._rule(
            "1700000000000_2", "Custom_V6In", "Mail", "25", "Drop", protocol="6", version=6, destinationMAC="02:00:00:00:00:01"
        )
        expected["parameters"] |= {"enable": False, "sourcePrefix": "2001:db8::/64"}
        assert _sent(mock_session_manager, self.READS) == [
            ("/sysbus/Firewall:setCustomRule", expected),
            ("/sysbus/Firewall:commit", {"parameters": {}}),
        ]

    def test_delete_custom_rule(self, mock_session_manager: MagicMock) -> None:
        svc = self._firewall(mock_session_manager, {"Custom": {"1700000000000_1": self.TELNET}})
        svc.delete_custom_rule("Telnet")
        assert _sent(mock_session_manager, self.READS) == [
            ("/sysbus/Firewall:deleteCustomRule", {"parameters": {"id": "1700000000000_1", "chain": "Custom"}}),
            ("/sysbus/Firewall:commit", {"parameters": {}}),
        ]

    @pytest.mark.parametrize("method", ["enable_custom_rule", "delete_custom_rule"])
    def test_unknown_rule(self, mock_session_manager: MagicMock, method: str) -> None:
        svc = self._firewall(mock_session_manager, {"Custom": {"1700000000000_1": self.TELNET}})
        with pytest.raises(ValueError, match="no custom firewall rule named 'SSH'. The rules are: 'Telnet'"):
            getattr(svc, method)("SSH")
        assert _sent(mock_session_manager, self.READS) == []

    @pytest.mark.parametrize("ipv4", ["Drop", "None", ""])
    def test_custom_policy(self, mock_session_manager: MagicMock, ipv4: str) -> None:
        """Like the web UI, a chain without a policy allows."""
        svc = self._firewall(mock_session_manager, policies={"Custom": ipv4})
        expected = {"ipv4": "block" if ipv4 == "Drop" else "allow", "ipv6_outbound": "allow", "ipv6_inbound": "block"}
        assert json.loads(svc.custom_policy()) == expected

    def test_set_custom_policy(self, mock_session_manager: MagicMock) -> None:
        svc = _make_resource(Firewall, mock_session_manager)
        svc.set_custom_policy("block", ip_version=6, direction="inbound")
        assert mock_session_manager.post.call_args[0][:2] == (
            "/sysbus/Firewall:setChainPolicy",
            {"parameters": {"chain": "Custom_V6In", "policy": "Drop"}},
        )

    @pytest.mark.parametrize("kwargs", [{"action": "deny"}, {"action": "block", "direction": "inbound"}])
    def test_set_custom_policy_refuses(self, mock_session_manager: MagicMock, kwargs: dict) -> None:
        with pytest.raises(ValueError):
            _make_resource(Firewall, mock_session_manager).set_custom_policy(**kwargs)
        mock_session_manager.post.assert_not_called()


# ── GenLog ────────────────────────────────────────────────────────────


class TestGenLog:
    def test_next_logs(self, mock_session_manager: MagicMock) -> None:
        svc = _make_resource(GenLog, mock_session_manager)
        svc.next_logs(stream="cpu", nrecords=10)
        mock_session_manager.post.assert_called_once()


# ── History ───────────────────────────────────────────────────────────


class TestHistory:
    @pytest.mark.parametrize(
        "method,endpoint",
        [("backup_entries", "/sysbus/History/Backup/Entry:get"), ("upgrade_entries", "/sysbus/History/Upgrade/Entry:get")],
    )
    def test_endpoints(self, mock_session_manager: MagicMock, method: str, endpoint: str) -> None:
        svc = _make_resource(History, mock_session_manager)
        getattr(svc, method)()
        assert mock_session_manager.post.call_args[0][0] == endpoint


# ── HTTPService ───────────────────────────────────────────────────────


class TestHTTPService:
    def test_current_user(self, mock_session_manager: MagicMock) -> None:
        svc = _make_resource(HTTPService, mock_session_manager)
        svc.current_user()
        assert mock_session_manager.post.call_args[0][0] == "/sysbus/HTTPService:getCurrentUser"


# ── LAN ───────────────────────────────────────────────────────────────


class TestLAN:
    def test_mac(self, mock_session_manager: MagicMock) -> None:
        svc = _make_resource(LAN, mock_session_manager)
        svc.mac()
        data = mock_session_manager.post.call_args[0][1]
        assert data["parameters"]["name"] == "LLAddress"

    def test_ethernet_port_default(self, mock_session_manager: MagicMock) -> None:
        svc = _make_resource(LAN, mock_session_manager)
        svc.ethernet_port()
        data = mock_session_manager.post.call_args[0][1]
        assert data["service"] == "Devices.Device.ETH4"

    def test_ethernet_port_specific(self, mock_session_manager: MagicMock) -> None:
        svc = _make_resource(LAN, mock_session_manager)
        svc.ethernet_port(port=2)
        data = mock_session_manager.post.call_args[0][1]
        assert data["service"] == "Devices.Device.ETH2"

    def test_mac_lookup_uppercases(self, mock_session_manager: MagicMock) -> None:
        svc = _make_resource(LAN, mock_session_manager)
        svc.mac_lookup(mac="ab:cd:ef:12:34:56")
        data = mock_session_manager.post.call_args[0][1]
        assert data["service"] == "Devices.Device.AB:CD:EF:12:34:56.UDevice"


# ── LED ───────────────────────────────────────────────────────────────


class TestLED:
    def test_status(self, mock_session_manager: MagicMock) -> None:
        svc = _make_resource(LED, mock_session_manager)
        svc.status(type="Status")
        assert "/sysbus/LEDs/LED/Status:get" in mock_session_manager.post.call_args[0][0]

    def test_set_brightness(self, mock_session_manager: MagicMock) -> None:
        svc = _make_resource(LED, mock_session_manager)
        svc.set(type="Wireless", brightness=50)
        data = mock_session_manager.post.call_args[0][1]
        assert data["parameters"]["Brightness"] == 50

    def test_nmc_status(self, mock_session_manager: MagicMock) -> None:
        svc = _make_resource(LED, mock_session_manager)
        svc.nmc_status(type="Status")
        assert "/sysbus/NMC/LEDs/LED/Status:get" in mock_session_manager.post.call_args[0][0]

    def test_party_time_on(self, mock_session_manager: MagicMock) -> None:
        svc = _make_resource(LED, mock_session_manager)
        with patch("internetbox_client.resources.led.time.sleep"):
            result = svc.party_time(mode="on", flashes=2)
        assert isinstance(result, str)
        # 2 flashes × 4 set calls + 2 restore calls = 10
        assert mock_session_manager.post.call_count == 10

    def test_party_time_off(self, mock_session_manager: MagicMock) -> None:
        svc = _make_resource(LED, mock_session_manager)
        result = svc.party_time(mode="off")
        assert isinstance(result, str)
        # Restores Status and Wireless to 100
        assert mock_session_manager.post.call_count == 2

    def test_morse_code_returns_string(self, mock_session_manager: MagicMock) -> None:
        svc = _make_resource(LED, mock_session_manager)
        with patch("internetbox_client.resources.led.time.sleep"):
            result = svc.morse_code(message="SOS", led="Status")
        assert isinstance(result, str)
        assert "SOS" in result

    def test_morse_code_led_endpoint(self, mock_session_manager: MagicMock) -> None:
        svc = _make_resource(LED, mock_session_manager)
        with patch("internetbox_client.resources.led.time.sleep"):
            svc.morse_code(message="E", led="Wireless")
        # Every set call should target the Wireless LED endpoint
        for call in mock_session_manager.post.call_args_list:
            endpoint = call[0][0]
            if "LEDs" in endpoint:
                assert "Wireless" in endpoint


# ── Mitigation ────────────────────────────────────────────────────────


class TestMitigation:
    def test_status_no_auth(self, mock_session_manager: MagicMock) -> None:
        svc = _make_resource(Mitigation, mock_session_manager)
        svc.status()
        assert mock_session_manager.post.call_args[0][2] is False  # auth_required


# ── NMC ───────────────────────────────────────────────────────────────

# The router's answer to a restore (HTTP 200): a page that passes the result to the web UI.
_RESTORE_SUCCESS = (
    "<html><head><script language=\"javascript\">window.parent.document.fire('sah:models:System:state', 'restore-success');"
    "</script></head><body></body></html>\n"
)
# The web UI treats any other state as a failure. Only success has been seen on a router, so this state is made up.
_RESTORE_FAILURE = _RESTORE_SUCCESS.replace("restore-success", "restore-error")


class TestNMC:
    @pytest.mark.parametrize(
        "method,no_auth",
        [
            ("status", True),
            ("ip_conflicts", True),
            ("wan_status", True),
            ("orientation", True),
            ("lan_ip", False),
            ("phonebook_backup", False),
        ],
    )
    def test_auth_required(self, mock_session_manager: MagicMock, method: str, no_auth: bool) -> None:
        svc = _make_resource(NMC, mock_session_manager)
        getattr(svc, method)()
        auth_val = mock_session_manager.post.call_args[0][2]
        if no_auth:
            assert auth_val is False
        else:
            assert auth_val is True

    def test_wan_status_details_need_the_password(self, mock_session_manager: MagicMock) -> None:
        svc = _make_resource(NMC, mock_session_manager)
        svc.wan_status(details=True)
        assert mock_session_manager.post.call_args[0] == ("/sysbus/NMC:getWANStatus", {"parameters": {}}, True)

    def test_bdd_uses_ws(self, mock_session_manager: MagicMock) -> None:
        svc = _make_resource(NMC, mock_session_manager)
        svc.bdd()
        data = mock_session_manager.post.call_args[0][1]
        assert data["service"] == "NMC.BDD"

    def test_reboot(self, mock_session_manager: MagicMock) -> None:
        svc = _make_resource(NMC, mock_session_manager)
        svc.reboot()
        assert mock_session_manager.post.call_args[0][:2] == ("/sysbus/NMC:reboot", {"parameters": {"reason": "pyinternetbox"}})

    def test_backup(self, mock_session_manager: MagicMock) -> None:
        mock_session_manager.download.return_value = "QUJD\n"
        assert _make_resource(NMC, mock_session_manager).backup() == "QUJD\n"
        mock_session_manager.download.assert_called_once_with("/backup")

    @pytest.mark.parametrize("content", [b"QUJD\nRUZH\n", b"QUJD\r\nRUZH\r\n"])  # saved on Linux/macOS, or on Windows
    def test_restore_uploads_the_backup(self, mock_session_manager: MagicMock, tmp_path, content: bytes) -> None:
        backup = tmp_path / "my backup.cfg"
        backup.write_bytes(content)
        mock_session_manager.upload.return_value = _RESTORE_SUCCESS
        assert _make_resource(NMC, mock_session_manager).restore(str(backup)) == _RESTORE_SUCCESS
        mock_session_manager.upload.assert_called_once_with("/restore", "restore", "internetbox.cfg", b"QUJD\nRUZH\n")

    @pytest.mark.parametrize("content", [b"", b"\n", b'{"status": true}', b"QUJD!\n", b"QUJ\n", "Bäckup".encode()])
    def test_restore_refuses_other_files(self, mock_session_manager: MagicMock, tmp_path, content: bytes) -> None:
        other = tmp_path / "other.cfg"
        other.write_bytes(content)
        with pytest.raises(ValueError, match="other.cfg isn't a configuration backup"):
            _make_resource(NMC, mock_session_manager).restore(str(other))
        mock_session_manager.upload.assert_not_called()

    def test_restore_missing_file(self, mock_session_manager: MagicMock, tmp_path) -> None:
        with pytest.raises(FileNotFoundError):
            _make_resource(NMC, mock_session_manager).restore(str(tmp_path / "missing.cfg"))
        mock_session_manager.upload.assert_not_called()

    def test_restore_not_confirmed(self, mock_session_manager: MagicMock, tmp_path) -> None:
        backup = tmp_path / "internetbox.cfg"
        backup.write_bytes(b"QUJD\n")
        mock_session_manager.upload.return_value = _RESTORE_FAILURE
        with pytest.raises(ValueError, match="The router didn't confirm the restore. It answered: .*'restore-error'"):
            _make_resource(NMC, mock_session_manager).restore(str(backup))

    @pytest.mark.parametrize("status", ["Enabled", "Uploaded"])
    def test_backup_to_swisscom(self, mock_session_manager: MagicMock, status: str) -> None:
        mock_session_manager.post.side_effect = [json.dumps({"status": {"Status": status}}), '{"status": null}']
        assert _make_resource(NMC, mock_session_manager).backup_to_swisscom() == '{"status": null}'
        assert [c[0][:2] for c in mock_session_manager.post.call_args_list] == [
            ("/sysbus/NMC/NetworkConfig:get", {"parameters": {}}),
            ("/sysbus/NMC/NetworkConfig:launchNetworkBackup", {"parameters": {}}),
        ]

    @pytest.mark.parametrize("response", ['{"status": {"Status": "Disabled"}}', '{"status": {}}'])
    def test_backup_to_swisscom_turned_off(self, mock_session_manager: MagicMock, response: str) -> None:
        mock_session_manager.post.return_value = response
        with pytest.raises(ValueError, match="Backup to Swisscom isn't turned on for this router"):
            _make_resource(NMC, mock_session_manager).backup_to_swisscom()
        mock_session_manager.post.assert_called_once()  # the status, but no upload


class TestStaticRoutes:
    """set_static_route() and delete_static_route(), on a router with the LAN 192.168.1.0/24 and WireGuard clients in
    10.0.1.0/24."""

    LAB = {"Enable": True, "Status": "Enabled", "DstLen": 24, "Dst": "192.168.10.0", "Priority": 0, "Gateway": "192.168.1.2", "MTU": 0}
    READS = (":getLANIP", ":getStaticRoutes", ":_get", ":getPortForwarding")

    @staticmethod
    def _nmc(sm: MagicMock, routes: dict[str, dict] | None = None, wireguard: object = None, forwards: dict | None = None) -> NMC:
        servers = {"WireGuard.Server.1.": {"SubnetIPv4": "10.0.1.0/24", "Enable": False}, "WireGuard.Server.": {}}
        _answering(
            sm,
            {
                "/sysbus/NMC:getLANIP": json.dumps({"status": None, "data": {"Address": "192.168.1.1", "Netmask": "255.255.255.0"}}),
                "/sysbus/NMC/LAN:getStaticRoutes": json.dumps({"status": routes or {}}),
                "/sysbus/WireGuard/Server:_get": wireguard if wireguard is not None else json.dumps({"status": servers}),
                "/sysbus/Firewall:getPortForwarding": json.dumps({"status": forwards or {}}),
            },
            default='{"status": null}',
        )
        return _make_resource(NMC, sm)

    def test_add_route(self, mock_session_manager: MagicMock) -> None:
        svc = self._nmc(mock_session_manager)
        with patch("internetbox_client.resources.nmc.random.randrange", return_value=123456):
            assert svc.set_static_route(" 192.168.10.0/24", "192.168.1.2 ") == '{"status": null}'
        settings = {"Name": "webui_123456", "Dst": "192.168.10.0", "DstLen": 24, "Gateway": "192.168.1.2", "Enable": True}
        assert _sent(mock_session_manager, self.READS) == [("/sysbus/NMC/LAN:addStaticRoute", {"parameters": settings})]

    def test_new_name_differs_from_existing_names(self, mock_session_manager: MagicMock) -> None:
        svc = self._nmc(mock_session_manager, {"webui_1": self.LAB})
        with patch("internetbox_client.resources.nmc.random.randrange", side_effect=[1, 2]):
            svc.set_static_route("172.16.0.0/16", "192.168.1.3")
        assert _sent(mock_session_manager, self.READS)[0][1]["parameters"]["Name"] == "webui_2"

    def test_changing_the_gateway_keeps_the_route(self, mock_session_manager: MagicMock) -> None:
        """The route to the same network doesn't overlap itself."""
        svc = self._nmc(mock_session_manager, {"webui_1": self.LAB})
        svc.set_static_route("192.168.10.0/24", "192.168.1.3")
        settings = {"Dst": "192.168.10.0", "DstLen": 24, "Gateway": "192.168.1.3", "Enable": True}
        assert _sent(mock_session_manager, self.READS) == [("/sysbus/NMC/LAN/IPv4Route/webui_1:set", {"parameters": settings})]

    def test_without_wireguard(self, mock_session_manager: MagicMock) -> None:
        """Routers without WireGuard answer with an error: the WireGuard clients' network then isn't checked."""
        svc = self._nmc(mock_session_manager, wireguard=_http_error(500))
        svc.set_static_route("10.0.1.0/24", "192.168.1.2")
        assert _sent(mock_session_manager, self.READS)[0][0] == "/sysbus/NMC/LAN:addStaticRoute"

    @pytest.mark.parametrize(
        "destination,gateway,message",
        [
            ("192.168.10.0", "192.168.1.2", 'destination must be a network such as "192.168.10.0/24"'),
            ("192.168.10.0/33", "192.168.1.2", "destination must be a network"),
            ("lab", "192.168.1.2", "destination must be a network"),
            ("10.0.0.0/8", "192.168.1.2", "prefix length from /16 to /28"),
            ("192.168.10.0/29", "192.168.1.2", "prefix length from /16 to /28"),
            ("192.168.10.5/24", "192.168.1.2", "isn't the address of its network: did you mean 192.168.10.0/24"),
            ("8.8.0.0/16", "192.168.1.2", "isn't a private network"),
            ("192.168.1.0/24", "192.168.1.2", r"overlaps your network \(192.168.1.0/24\)"),
            ("192.168.0.0/16", "192.168.1.2", "overlaps your network"),
            ("10.128.5.0/24", "192.168.1.2", "overlaps the guest Wi-Fi"),
            ("10.129.0.0/16", "192.168.1.2", "overlaps the router's apbridge network"),
            ("10.0.1.0/24", "192.168.1.2", r"overlaps the WireGuard clients' network \(10.0.1.0/24\)"),
            ("192.168.10.128/25", "192.168.1.2", r"overlaps the static route 'webui_1' \(192.168.10.0/24\)"),
            ("172.16.0.0/16", "router", "gateway must be an IP address"),
            ("172.16.0.0/16", "192.168.1.1", r"can't be the router itself \(192.168.1.1\)"),
            ("172.16.0.0/16", "192.168.2.2", r"must be a device in your network \(192.168.1.0/24\)"),
            ("172.16.0.0/16", "192.168.1.0", "must be a device in your network"),
            ("172.16.0.0/16", "192.168.1.255", "must be a device in your network"),
        ],
    )
    def test_refuses(self, mock_session_manager: MagicMock, destination: str, gateway: str, message: str) -> None:
        svc = self._nmc(mock_session_manager, {"webui_1": self.LAB})
        with pytest.raises(ValueError, match=message):
            svc.set_static_route(destination, gateway)
        assert _sent(mock_session_manager, self.READS) == []

    def test_refuses_an_11th_route(self, mock_session_manager: MagicMock) -> None:
        routes = {f"webui_{n}": {**self.LAB, "Dst": f"172.16.{n}.0"} for n in range(10)}
        svc = self._nmc(mock_session_manager, routes)
        with pytest.raises(ValueError, match="There are 10 static routes already"):
            svc.set_static_route("172.17.0.0/24", "192.168.1.2")
        svc.set_static_route("172.16.3.0/24", "192.168.1.3")  # changing one is fine
        assert _sent(mock_session_manager, self.READS)[0][0] == "/sysbus/NMC/LAN/IPv4Route/webui_3:set"

    @pytest.mark.parametrize("route", ["webui_1", "192.168.10.0/24", "192.168.10.7/24"])
    def test_delete_route_and_the_port_forwarding_behind_it(self, mock_session_manager: MagicMock, route: str) -> None:
        forwards = {
            "webui_nas": {"Origin": "webui", "DestinationIPAddress": "192.168.10.20"},
            "webui_pc": {"Origin": "webui", "DestinationIPAddress": "192.168.1.20"},  # not behind the route
            "upnp_1": {"Origin": "upnp", "DestinationIPAddress": "192.168.10.21"},  # not made in the web UI
            "webui_odd": {"Origin": "webui", "DestinationIPAddress": ""},
        }
        svc = self._nmc(
            mock_session_manager, {"webui_1": self.LAB, "webui_2": {**self.LAB, "Dst": "172.16.0.0", "DstLen": 16}}, forwards=forwards
        )
        svc.delete_static_route(route)
        assert _sent(mock_session_manager, self.READS) == [
            ("/sysbus/NMC/LAN:deleteStaticRoute", {"parameters": {"Name": "webui_1"}}),
            ("/sysbus/Firewall:deletePortForwarding", {"parameters": {"id": "webui_nas", "origin": "webui"}}),
            ("/sysbus/Firewall:commit", {"parameters": {}}),
        ]

    def test_delete_route_without_port_forwarding_doesnt_commit(self, mock_session_manager: MagicMock) -> None:
        svc = self._nmc(mock_session_manager, {"webui_1": self.LAB})
        assert svc.delete_static_route("webui_1") == '{"status": null}'
        assert _sent(mock_session_manager, self.READS) == [("/sysbus/NMC/LAN:deleteStaticRoute", {"parameters": {"Name": "webui_1"}})]

    @pytest.mark.parametrize("route", ["webui_9", "192.168.11.0/24", "lab/24"])
    def test_delete_unknown_route(self, mock_session_manager: MagicMock, route: str) -> None:
        svc = self._nmc(mock_session_manager, {"webui_1": self.LAB})
        with pytest.raises(ValueError, match=r"no static route .*The routes are: 192.168.10.0/24 \(webui_1\)"):
            svc.delete_static_route(route)
        assert _sent(mock_session_manager, self.READS) == []


# ── Simple resource classes ───────────────────────────────────────────


@pytest.mark.parametrize(
    "cls,method,endpoint",
    [
        (OopsTracker, "status", "/sysbus/OopsTracker:get"),
        (OopsTracker, "oopses", "/sysbus/OopsTracker:getOopses"),
        (PasswordRecovery, "status", "/sysbus/PasswordRecovery:getStatus"),
        (Phonebook, "all_contacts", "/sysbus/Phonebook:getAllContacts"),
        (Phonebook, "get_contact", "/sysbus/Phonebook:getContactByUniqueID"),  # id param tested separately
        (PowerManagement, "profiles", "/sysbus/PowerManagement:getProfiles"),
        (Scheduler, "complete_schedules", "/sysbus/Scheduler:getCompleteSchedules"),
        (Temperature, "sensor", "/sysbus/Temperature/Sensor:get"),
        (UserManagement, "user_log", "/sysbus/UserManagement:getUserLog"),
        (VPN, "status", "/sysbus/VPN:get"),
        (VPN, "servers_config", "/sysbus/VPN:getServersConfig"),
        (WebUI, "status", "/sysbus/WebuiupgradeService:get"),
        (WebUI, "release_notes", "/sysbus/WebuiupgradeService:getReleaseNotes"),
        (Wireguard, "app_status", "/sysbus/WireGuard:_get"),
        (Wireguard, "server_status", "/sysbus/WireGuard/Server:_get"),
        (Wireguard, "clients", "/sysbus/WireGuard/Server/default/Client:_get"),
    ],
)
def test_simple_resource_endpoints(mock_session_manager: MagicMock, cls: type, method: str, endpoint: str) -> None:
    svc = _make_resource(cls, mock_session_manager)
    # get_contact requires an id argument
    kwargs = {"id": "123"} if method == "get_contact" else {}
    getattr(svc, method)(**kwargs)
    assert mock_session_manager.post.call_args[0][0] == endpoint


# ── Phonebook ─────────────────────────────────────────────────────────


class TestPhonebook:
    def test_get_contact_passes_unique_id(self, mock_session_manager: MagicMock) -> None:
        svc = _make_resource(Phonebook, mock_session_manager)
        svc.get_contact(id="abc-123")
        data = mock_session_manager.post.call_args[0][1]
        assert data["parameters"]["uniqueID"] == "abc-123"

    def test_add_contact_passes_contact(self, mock_session_manager: MagicMock) -> None:
        svc = _make_resource(Phonebook, mock_session_manager)
        contact = {"name": "N:Test", "formattedName": "Test", "telephoneNumbers": []}
        svc.add_contact(contact=contact)
        data = mock_session_manager.post.call_args[0][1]
        assert data["parameters"]["contact"] == contact
        assert mock_session_manager.post.call_args[0][0] == "/sysbus/Phonebook:addContactAndGenUUID"

    def test_modify_contact(self, mock_session_manager: MagicMock) -> None:
        svc = _make_resource(Phonebook, mock_session_manager)
        contact = {"name": "N:Test", "formattedName": "Test", "telephoneNumbers": []}
        svc.modify_contact("abc-123", contact)
        assert mock_session_manager.post.call_args[0][:2] == (
            "/sysbus/Phonebook:modifyContactByUniqueID",
            {"parameters": {"uniqueID": "abc-123", "contact": contact}},
        )

    def test_delete_contact(self, mock_session_manager: MagicMock) -> None:
        svc = _make_resource(Phonebook, mock_session_manager)
        svc.delete_contact("abc-123")
        assert mock_session_manager.post.call_args[0][:2] == (
            "/sysbus/Phonebook:removeContactByUniqueID",
            {"parameters": {"uniqueID": "abc-123"}},
        )


# ── Security ──────────────────────────────────────────────────────────


class TestSecurity:
    @pytest.mark.parametrize(
        "method,endpoint",
        [
            ("home_security_status", "/sysbus/RouterSecurityAgent:get"),
            ("user_exposure_status", "/sysbus/NMC/Security:get"),
            ("package_management_status", "/sysbus/PackageManager/Package/security:_get"),
        ],
    )
    def test_endpoints(self, mock_session_manager: MagicMock, method: str, endpoint: str) -> None:
        svc = _make_resource(Security, mock_session_manager)
        getattr(svc, method)()
        assert mock_session_manager.post.call_args[0][0] == endpoint


# ── SpeedTest ─────────────────────────────────────────────────────────


class TestSpeedTest:
    def test_decode_nested_json_dict(self) -> None:
        raw = {"status": '{"event": "IDLE"}'}
        result = decode_nested_json(raw)
        assert result == {"status": {"event": "IDLE"}}

    def test_decode_nested_json_list(self) -> None:
        raw = ['{"a": 1}', "plain"]
        result = decode_nested_json(raw)
        assert result == [{"a": 1}, "plain"]

    def test_decode_nested_json_plain_string(self) -> None:
        assert decode_nested_json("hello") == "hello"

    def test_decode_nested_json_int(self) -> None:
        assert decode_nested_json(42) == 42

    def test_decode_nested_json_deeply_nested(self) -> None:
        raw = {"outer": '{"inner": "{\\"deep\\": true}"}'}
        result = decode_nested_json(raw)
        assert result == {"outer": {"inner": {"deep": True}}}

    def test_clean_valid_json(self, mock_session_manager: MagicMock) -> None:
        svc = _make_resource(SpeedTest, mock_session_manager)
        raw = '{"status": "{\\"event\\": \\"IDLE\\"}"}'
        result = svc._clean(raw)
        parsed = json.loads(result)
        assert parsed["status"]["event"] == "IDLE"

    def test_clean_invalid_json(self, mock_session_manager: MagicMock) -> None:
        svc = _make_resource(SpeedTest, mock_session_manager)
        assert svc._clean("not json") == "not json"

    def test_start(self, mock_session_manager: MagicMock) -> None:
        mock_session_manager.post.return_value = '{"status": "ok"}'
        svc = _make_resource(SpeedTest, mock_session_manager)
        svc.start(origin="test", wait_for_lan_result=True)
        data = mock_session_manager.post.call_args[0][1]
        assert data["method"] == "TestStart"
        assert data["parameters"]["waitforlanresult"] == "true"

    def test_status(self, mock_session_manager: MagicMock) -> None:
        mock_session_manager.post.return_value = '{"status": "ok"}'
        svc = _make_resource(SpeedTest, mock_session_manager)
        svc.status()
        data = mock_session_manager.post.call_args[0][1]
        assert data["method"] == "TestStatus"


# ── Static ────────────────────────────────────────────────────────────


class TestStatic:
    def test_settings_uses_get(self, mock_session_manager: MagicMock) -> None:
        svc = _make_resource(Static, mock_session_manager)
        svc.settings()
        mock_session_manager.get.assert_called_once()
        assert mock_session_manager.get.call_args[0][0] == "/static/settings/application.json"

    def test_translations_default_en(self, mock_session_manager: MagicMock) -> None:
        svc = _make_resource(Static, mock_session_manager)
        svc.translations()
        assert "/stargatev4/en.json" in mock_session_manager.get.call_args[0][0]

    def test_translations_language(self, mock_session_manager: MagicMock) -> None:
        svc = _make_resource(Static, mock_session_manager)
        svc.translations(language="de")
        assert "/stargatev4/de.json" in mock_session_manager.get.call_args[0][0]


# ── Sysbus ────────────────────────────────────────────────────────────


class TestSysbus:
    def test_gpio_no_auth(self, mock_session_manager: MagicMock) -> None:
        svc = _make_resource(Sysbus, mock_session_manager)
        svc.gpio()
        assert mock_session_manager.post.call_args[0][2] is False  # auth_required

    def test_mibs_default_flag(self, mock_session_manager: MagicMock) -> None:
        svc = _make_resource(Sysbus, mock_session_manager)
        svc.mibs()
        data = mock_session_manager.post.call_args[0][1]
        assert "dslline" in data["parameters"]["flag"]

    def test_mibs_custom_flag(self, mock_session_manager: MagicMock) -> None:
        svc = _make_resource(Sysbus, mock_session_manager)
        svc.mibs(flag="eth && wan")
        data = mock_session_manager.post.call_args[0][1]
        assert data["parameters"]["flag"] == "eth && wan"

    def test_net_dev_stats_default_interface(self, mock_session_manager: MagicMock) -> None:
        svc = _make_resource(Sysbus, mock_session_manager)
        svc.net_dev_stats()
        assert mock_session_manager.post.call_args[0][0] == "/sysbus/NeMo/Intf/veip0:getNetDevStats"

    def test_net_dev_stats_custom_interface(self, mock_session_manager: MagicMock) -> None:
        svc = _make_resource(Sysbus, mock_session_manager)
        svc.net_dev_stats("bridge")
        assert mock_session_manager.post.call_args[0][0] == "/sysbus/NeMo/Intf/bridge:getNetDevStats"


# ── Scheduler ─────────────────────────────────────────────────────────


class TestScheduler:
    MAC = "AA:BB:CC:DD:EE:FF"

    def test_device_schedule(self, mock_session_manager: MagicMock) -> None:
        svc = _make_resource(Scheduler, mock_session_manager)
        svc.device_schedule("aa:bb:cc:dd:ee:ff")
        assert mock_session_manager.post.call_args[0][:2] == (
            "/sysbus/Scheduler:getSchedule",
            {"parameters": {"type": "ToD", "ID": self.MAC}},
        )

    def test_remove_device_schedule_never_sends_empty_id(self, mock_session_manager: MagicMock) -> None:
        """removeSchedules without an ID would delete every device's schedule."""
        svc = _make_resource(Scheduler, mock_session_manager)
        with pytest.raises(ValueError):
            svc.remove_device_schedule("")
        mock_session_manager.post.assert_not_called()

    def test_remove_device_schedule_turns_it_off_first(self, mock_session_manager: MagicMock) -> None:
        """The router ignores the removal of a schedule turned on with enableSchedule until it's turned off again."""
        mock_session_manager.post.side_effect = [
            '{"status": true, "data": {"scheduleInfo": {"enable": true}}}',
            '{"status": true}',
            '{"status": true}',
        ]
        svc = _make_resource(Scheduler, mock_session_manager)
        assert svc.remove_device_schedule("aa:bb:cc:dd:ee:ff") == '{"status": true}'
        assert [c[0][:2] for c in mock_session_manager.post.call_args_list] == [
            ("/sysbus/Scheduler:getSchedule", {"parameters": {"type": "ToD", "ID": self.MAC}}),
            ("/sysbus/Scheduler:enableSchedule", {"parameters": {"type": "ToD", "ID": self.MAC, "enable": False}}),
            ("/sysbus/Scheduler:removeSchedules", {"parameters": {"type": "ToD", "ID": self.MAC}}),
        ]

    def test_remove_device_schedule_without_schedule(self, mock_session_manager: MagicMock) -> None:
        mock_session_manager.post.side_effect = ['{"status": false}', '{"status": true}']
        _make_resource(Scheduler, mock_session_manager).remove_device_schedule(self.MAC)
        assert [c[0][0] for c in mock_session_manager.post.call_args_list] == [
            "/sysbus/Scheduler:getSchedule",
            "/sysbus/Scheduler:removeSchedules",
        ]

    def test_enable_device_schedule(self, mock_session_manager: MagicMock) -> None:
        svc = _make_resource(Scheduler, mock_session_manager)
        svc.enable_device_schedule(self.MAC, False)
        assert mock_session_manager.post.call_args[0][:2] == (
            "/sysbus/Scheduler:enableSchedule",
            {"parameters": {"type": "ToD", "ID": self.MAC, "enable": False}},
        )

    def test_set_device_schedule_payload(self, mock_session_manager: MagicMock) -> None:
        svc = _make_resource(Scheduler, mock_session_manager)
        svc.set_device_schedule(self.MAC, [{"begin": "Mon 22:00", "end": "Tue 07:00"}], enable=False)
        assert mock_session_manager.post.call_args[0][:2] == (
            "/sysbus/Scheduler:addSchedule",
            {
                "parameters": {
                    "type": "ToD",
                    "info": {
                        "ID": self.MAC,
                        "enable": False,
                        "base": "Weekly",
                        "def": "Enable",
                        "override": "",
                        "schedule": [{"begin": 79200, "end": 111600, "state": "Disable"}],
                    },
                }
            },
        )

    @pytest.mark.parametrize(
        "periods,expected",
        [
            ([], []),
            ([{"begin": "Mon 00:00", "end": "Sun 24:00"}], [(0, 604800)]),
            ([{"begin": "saturday 9:30", "end": "Sat 12:00"}], [(466200, 475200)]),
            ([{"begin": "Sun 22:00", "end": "Mon 07:00"}], [(0, 25200), (597600, 604800)]),  # wraps past Sunday midnight
            ([{"begin": 3600, "end": 7200}, {"begin": "Mon 01:30", "end": "Mon 03:00"}], [(3600, 10800)]),  # overlap
            ([{"begin": "7200", "end": 10800}, {"begin": 0, "end": 7200}], [(0, 10800)]),  # adjacent, unsorted
            ([{"begin": 100, "end": 100}], []),  # empty
        ],
    )
    def test_blocked_periods(self, mock_session_manager: MagicMock, periods: list, expected: list) -> None:
        svc = _make_resource(Scheduler, mock_session_manager)
        svc.set_device_schedule(self.MAC, periods)
        schedule = mock_session_manager.post.call_args[0][1]["parameters"]["info"]["schedule"]
        assert [(p["begin"], p["end"]) for p in schedule] == expected
        assert all(p["state"] == "Disable" for p in schedule)

    @pytest.mark.parametrize("bad", ["Mon", "Funday 10:00", "Mon 24:30", "Mon 10:60", -1, 604801])
    def test_invalid_times_raise(self, mock_session_manager: MagicMock, bad: object) -> None:
        svc = _make_resource(Scheduler, mock_session_manager)
        with pytest.raises(ValueError):
            svc.set_device_schedule(self.MAC, [{"begin": bad, "end": 604800}])
        mock_session_manager.post.assert_not_called()


class TestWifiSchedule:
    """The Wi-Fi schedule of the web UI's power settings: type WLAN, ID wl0."""

    NIGHT = [{"begin": 3600, "end": 21600, "state": "Disable"}]  # Monday 01:00 to 06:00
    SCHEDULE = json.dumps({"status": True, "data": {"scheduleInfo": {"ID": "wl0", "enable": False, "schedule": NIGHT, "value": "Enable"}}})

    @staticmethod
    def _add(schedule: list, enable: bool) -> tuple:
        info = {"ID": "wl0", "enable": enable, "base": "Weekly", "def": "Enable", "override": "", "schedule": schedule}
        return ("/sysbus/Scheduler:addSchedule", {"parameters": {"type": "WLAN", "info": info}})

    def test_wifi_schedule(self, mock_session_manager: MagicMock) -> None:
        _make_resource(Scheduler, mock_session_manager).wifi_schedule()
        assert mock_session_manager.post.call_args[0][:2] == (
            "/sysbus/Scheduler:getSchedule",
            {"parameters": {"type": "WLAN", "ID": "wl0"}},
        )

    @pytest.mark.parametrize("enable", [True, False])
    def test_set_wifi_schedule(self, mock_session_manager: MagicMock, enable: bool) -> None:
        svc = _make_resource(Scheduler, mock_session_manager)
        svc.set_wifi_schedule([{"begin": "Mon 01:00", "end": "Mon 06:00"}], enable=enable)
        assert [c[0][:2] for c in mock_session_manager.post.call_args_list] == [self._add(self.NIGHT, enable)]

    def test_set_wifi_schedule_without_periods_is_saved_off(self, mock_session_manager: MagicMock) -> None:
        """Like the web UI: a schedule that never turns Wi-Fi off can't be on."""
        _make_resource(Scheduler, mock_session_manager).set_wifi_schedule([])
        assert [c[0][:2] for c in mock_session_manager.post.call_args_list] == [self._add([], False)]

    @pytest.mark.parametrize(
        "periods",
        [[{"begin": "Mon 00:00", "end": "Sun 24:00"}], [{"begin": "Wed 12:00", "end": "Sun 24:00"}, {"begin": 0, "end": "Wed 12:00"}]],
    )
    def test_set_wifi_schedule_refuses_all_week(self, mock_session_manager: MagicMock, periods: list) -> None:
        with pytest.raises(ValueError, match=r"off all week. To turn Wi-Fi off, use wifi.set_enabled\(False\)"):
            _make_resource(Scheduler, mock_session_manager).set_wifi_schedule(periods)
        mock_session_manager.post.assert_not_called()

    @pytest.mark.parametrize("enable", [True, False])
    def test_enable_wifi_schedule_keeps_the_periods(self, mock_session_manager: MagicMock, enable: bool) -> None:
        mock_session_manager.post.side_effect = [self.SCHEDULE, '{"status": true}']
        assert _make_resource(Scheduler, mock_session_manager).enable_wifi_schedule(enable) == '{"status": true}'
        assert mock_session_manager.post.call_args[0][:2] == self._add(self.NIGHT, enable)

    def test_enable_wifi_schedule_without_schedule(self, mock_session_manager: MagicMock) -> None:
        mock_session_manager.post.return_value = '{"status": false}'
        with pytest.raises(ValueError, match="There's no Wi-Fi schedule. Create one with set_wifi_schedule"):
            _make_resource(Scheduler, mock_session_manager).enable_wifi_schedule()
        mock_session_manager.post.assert_called_once()

    def test_enable_wifi_schedule_without_periods(self, mock_session_manager: MagicMock) -> None:
        empty = json.dumps({"status": True, "data": {"scheduleInfo": {"ID": "wl0", "enable": False, "schedule": []}}})
        mock_session_manager.post.side_effect = [empty, empty, '{"status": true}']
        svc = _make_resource(Scheduler, mock_session_manager)
        with pytest.raises(ValueError, match="has no off periods, so it can't be turned on"):
            svc.enable_wifi_schedule()
        svc.enable_wifi_schedule(False)  # turning it off is fine
        assert mock_session_manager.post.call_args[0][:2] == self._add([], False)

    def test_remove_wifi_schedule_turns_it_off_first(self, mock_session_manager: MagicMock) -> None:
        mock_session_manager.post.side_effect = [self.SCHEDULE, '{"status": true}', '{"status": true}']
        assert _make_resource(Scheduler, mock_session_manager).remove_wifi_schedule() == '{"status": true}'
        assert [c[0][:2] for c in mock_session_manager.post.call_args_list] == [
            ("/sysbus/Scheduler:getSchedule", {"parameters": {"type": "WLAN", "ID": "wl0"}}),
            ("/sysbus/Scheduler:enableSchedule", {"parameters": {"type": "WLAN", "ID": "wl0", "enable": False}}),
            ("/sysbus/Scheduler:removeSchedules", {"parameters": {"type": "WLAN", "ID": "wl0"}}),
        ]

    def test_remove_wifi_schedule_without_schedule(self, mock_session_manager: MagicMock) -> None:
        mock_session_manager.post.side_effect = ['{"status": false}', '{"status": true}']
        _make_resource(Scheduler, mock_session_manager).remove_wifi_schedule()
        assert [c[0][0] for c in mock_session_manager.post.call_args_list] == [
            "/sysbus/Scheduler:getSchedule",
            "/sysbus/Scheduler:removeSchedules",
        ]


class TestPowerManagement:
    @pytest.mark.parametrize("enable", [True, False])
    def test_set_wifi_6ghz_power_saving(self, mock_session_manager: MagicMock, enable: bool) -> None:
        _make_resource(PowerManagement, mock_session_manager).set_wifi_6ghz_power_saving(enable)
        assert mock_session_manager.post.call_args[0][:2] == (
            "/sysbus/PowerManagement:setTriggeredProfiles",
            {"parameters": {"profiles": [{"profile": "ECO_6G_SCS", "activate": enable}]}},
        )


# ── MST ───────────────────────────────────────────────────────────────


class TestMST:
    DAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")

    @pytest.mark.parametrize("method,endpoint", [("status", "/sysbus/ToD/MaxSurfTime:get"), ("get", "/sysbus/ToD:listMST")])
    def test_endpoints(self, mock_session_manager: MagicMock, method: str, endpoint: str) -> None:
        svc = _make_resource(MST, mock_session_manager)
        getattr(svc, method)()
        assert mock_session_manager.post.call_args[0][0] == endpoint

    def test_config(self, mock_session_manager: MagicMock) -> None:
        svc = _make_resource(MST, mock_session_manager)
        svc.config(id="abc123")
        assert mock_session_manager.post.call_args[0][0] == "/sysbus/ToD:getMST"

    def test_stats(self, mock_session_manager: MagicMock) -> None:
        svc = _make_resource(MST, mock_session_manager)
        svc.stats(id="abc123")
        assert mock_session_manager.post.call_args[0][0] == "/sysbus/ToD:statsMST"

    def test_set_minutes_per_day(self, mock_session_manager: MagicMock) -> None:
        svc = _make_resource(MST, mock_session_manager)
        svc.set("aa:bb:cc:dd:ee:ff", minutes_per_day=90)
        assert mock_session_manager.post.call_args[0][:2] == (
            "/sysbus/ToD:setMST",
            {
                "parameters": {
                    "id": "aabbccddeeff",
                    "subject": "MAC:AA:BB:CC:DD:EE:FF",
                    "enable": True,
                    "allowedTime": dict.fromkeys(self.DAYS, 90),
                }
            },
        )

    def test_set_allowed_time_overrides_given_days(self, mock_session_manager: MagicMock) -> None:
        svc = _make_resource(MST, mock_session_manager)
        svc.set("AA:BB:CC:DD:EE:FF", minutes_per_day=60, allowed_time={"saturday": 240, "Sun": 240})
        allowed = mock_session_manager.post.call_args[0][1]["parameters"]["allowedTime"]
        assert allowed == {**dict.fromkeys(self.DAYS, 60), "Sat": 240, "Sun": 240}

    def test_set_without_times_keeps_current_limit(self, mock_session_manager: MagicMock) -> None:
        svc = _make_resource(MST, mock_session_manager)
        svc.set("aabbccddeeff", enable=False)  # an MST entry ID works too
        params = mock_session_manager.post.call_args[0][1]["parameters"]
        assert params == {"id": "aabbccddeeff", "subject": "MAC:AA:BB:CC:DD:EE:FF", "enable": False}

    @pytest.mark.parametrize(
        "kwargs,error",
        [({"minutes_per_day": 1441}, "1440"), ({"minutes_per_day": -1}, "1440"), ({"allowed_time": {"Funday": 10}}, "Unknown day")],
    )
    def test_set_rejects_invalid_limits(self, mock_session_manager: MagicMock, kwargs: dict, error: str) -> None:
        svc = _make_resource(MST, mock_session_manager)
        with pytest.raises(ValueError, match=error):
            svc.set("aa:bb:cc:dd:ee:ff", **kwargs)
        mock_session_manager.post.assert_not_called()

    def test_delete(self, mock_session_manager: MagicMock) -> None:
        svc = _make_resource(MST, mock_session_manager)
        svc.delete("AA:BB:CC:DD:EE:FF")
        assert mock_session_manager.post.call_args[0][:2] == ("/sysbus/ToD:deleteMST", {"parameters": {"id": "aabbccddeeff"}})


# ── Voice ─────────────────────────────────────────────────────────────


class TestVoice:
    def test_status_no_auth(self, mock_session_manager: MagicMock) -> None:
        svc = _make_resource(Voice, mock_session_manager)
        svc.status()
        assert mock_session_manager.post.call_args[0][2] is False  # auth_required

    def test_trunks_no_auth(self, mock_session_manager: MagicMock) -> None:
        svc = _make_resource(Voice, mock_session_manager)
        svc.trunks()
        assert mock_session_manager.post.call_args[0][2] is False  # auth_required

    def test_delete_call(self, mock_session_manager: MagicMock) -> None:
        svc = _make_resource(Voice, mock_session_manager)
        svc.delete_call("42")
        assert mock_session_manager.post.call_args[0][:2] == (
            "/sysbus/VoiceService/VoiceApplication:clearCallList",
            {"parameters": {"callId": "42"}},
        )

    def test_clear_call_list(self, mock_session_manager: MagicMock) -> None:
        svc = _make_resource(Voice, mock_session_manager)
        svc.clear_call_list()
        assert mock_session_manager.post.call_args[0][:2] == ("/sysbus/VoiceService/VoiceApplication:clearCallList", {"parameters": {}})


# ── Wifi ──────────────────────────────────────────────────────────────


class TestWifi:
    def test_status_no_auth(self, mock_session_manager: MagicMock) -> None:
        svc = _make_resource(Wifi, mock_session_manager)
        svc.status()
        assert mock_session_manager.post.call_args[0][2] is False  # auth_required

    def test_radio_uses_id(self, mock_session_manager: MagicMock) -> None:
        svc = _make_resource(Wifi, mock_session_manager)
        svc.radio(id=2)
        assert mock_session_manager.post.call_args[0][0] == "/sysbus/NeMo/Intf/wifi2_bcm:get"

    def test_power_sets_transmit(self, mock_session_manager: MagicMock) -> None:
        svc = _make_resource(Wifi, mock_session_manager)
        svc.power(id=0, power=50)
        data = mock_session_manager.post.call_args[0][1]
        radio_cfg = data["parameters"]["mibs"]["wlanradio"]["wifi0_bcm"]
        assert radio_cfg["TransmitPower"] == 50
        assert radio_cfg["PersistentEnable"] is True

    def test_scan(self, mock_session_manager: MagicMock) -> None:
        svc = _make_resource(Wifi, mock_session_manager)
        svc.scan(id=1)
        assert mock_session_manager.post.call_args[0][0] == "/sysbus/NeMo/Intf/wifi1_bcm:scan"

    def test_station_stats(self, mock_session_manager: MagicMock) -> None:
        svc = _make_resource(Wifi, mock_session_manager)
        svc.station_stats(id=0)
        assert mock_session_manager.post.call_args[0][0] == "/sysbus/NeMo/Intf/wl0:getStationStats"

    def test_set_enabled_keeps_configuration_mode(self, mock_session_manager: MagicMock) -> None:
        mock_session_manager.post.side_effect = [
            '{"status": null, "data": {"Enable": true, "Status": true, "ConfigurationMode": true}}',
            '{"status": true}',
        ]
        svc = _make_resource(Wifi, mock_session_manager)
        assert svc.set_enabled(False) == '{"status": true}'
        assert mock_session_manager.post.call_args[0][:2] == (
            "/sysbus/NMC/Wifi:set",
            {"parameters": {"Enable": False, "Status": False, "ConfigurationMode": True}},
        )

    def test_set_enabled_without_configuration_mode(self, mock_session_manager: MagicMock) -> None:
        svc = _make_resource(Wifi, mock_session_manager)
        svc.set_enabled(True)
        assert mock_session_manager.post.call_args[0][1] == {"parameters": {"Enable": True, "Status": True}}

    def test_set_guest_enabled_sets_timer(self, mock_session_manager: MagicMock) -> None:
        svc = _make_resource(Wifi, mock_session_manager)
        svc.set_guest_enabled(True, hours=4)
        assert [c[0][:2] for c in mock_session_manager.post.call_args_list] == [
            ("/sysbus/NMC/Guest:set", {"parameters": {"Enable": True}}),
            ("/sysbus/NMC/WlanTimer:setActivationTimer", {"parameters": {"InterfaceName": "guest", "Timeout": 4}}),
        ]

    def test_set_guest_disabled_skips_timer(self, mock_session_manager: MagicMock) -> None:
        svc = _make_resource(Wifi, mock_session_manager)
        svc.set_guest_enabled(False)
        mock_session_manager.post.assert_called_once_with("/sysbus/NMC/Guest:set", {"parameters": {"Enable": False}}, True)

    def test_set_wps_enabled(self, mock_session_manager: MagicMock) -> None:
        svc = _make_resource(Wifi, mock_session_manager)
        svc.set_wps_enabled(False)
        mock_session_manager.post.assert_called_once_with("/sysbus/NMC/Wifi:setWPSEnable", {"parameters": {"enable": False}}, True)

    def test_start_wps_pairing(self, mock_session_manager: MagicMock) -> None:
        mock_session_manager.post.side_effect = ['{"status": null, "data": {"WPSEnable": true}}', '{"status": true}']
        svc = _make_resource(Wifi, mock_session_manager)
        assert svc.start_wps_pairing() == '{"status": true}'
        assert mock_session_manager.post.call_args[0][:2] == ("/sysbus/NMC/Wifi:startPairing", {"parameters": {}})

    def test_start_wps_pairing_needs_wps(self, mock_session_manager: MagicMock) -> None:
        mock_session_manager.post.return_value = '{"status": null, "data": {"WPSEnable": false}}'
        svc = _make_resource(Wifi, mock_session_manager)
        with pytest.raises(ValueError, match=r"WPS is turned off.*set_wps_enabled\(True\)"):
            svc.start_wps_pairing()
        mock_session_manager.post.assert_called_once()  # only the status

    def test_stop_wps_pairing(self, mock_session_manager: MagicMock) -> None:
        svc = _make_resource(Wifi, mock_session_manager)
        svc.stop_wps_pairing()
        assert mock_session_manager.post.call_args[0][:2] == ("/sysbus/NMC/Wifi:stopPairing", {"parameters": {}})


def _wlan_mibs(access_points: dict[str, tuple[str, str, str, str]], mode: str = "WPA2-WPA3-Personal") -> str:
    """A getMIBs answer for access points given as name: (radio, band, SSID, password). Like the router's, the access
    points' RadioReference is empty: their radio is in "base"."""
    return json.dumps(
        {
            "status": {
                "wlanvap": {
                    name: {
                        "SSID": ssid,
                        "SSIDAdvertisementEnabled": True,
                        "RadioReference": "",
                        "Security": {"KeyPassPhrase": password, "WEPKey": "", "ModeEnabled": mode},
                        "VAPStatus": "Up",
                        "ActiveAssociatedDeviceNumberOfEntries": 2,
                    }
                    for name, (_, _, ssid, password) in access_points.items()
                },
                "wlanradio": {
                    radio: {"OperatingFrequencyBand": band, "Channel": 36 if band == "5GHz" else 6}
                    for radio, band, _, _ in access_points.values()
                },
                "base": {name: {"LLIntf": {radio: {"Name": radio}}} for name, (radio, *_) in access_points.items()},
            }
        }
    )


_WL0 = ("wifi0_bcm", "5GHz", "Home", "Old-Password-1")
_WL1 = ("wifi1_bcm", "2.4GHz", "Home", "Old-Password-1")
_WLGUEST2 = ("wifi1_bcm", "2.4GHz", "Visitors", "Guest-Password-1")
_SSW_SSIDS = json.dumps(
    {
        "status": {
            "priv5g": {"Band": "5", "PersistentEnable": True},
            "priv6g": {"Band": "6", "PersistentEnable": True},
            "guest6g": {"Band": "6", "PersistentEnable": False},
        }
    }
)


class TestWifiNetwork:
    """set_network() and set_guest_network(), against a router with 5 and 2.4 GHz and a 2.4 GHz guest network."""

    @staticmethod
    def _router(sm: MagicMock, lan: str | None = None, combined: bool = False, answers: dict | None = None) -> Wifi:
        responses = {
            "/sysbus/NeMo/Intf/lan:getMIBs": lan or _wlan_mibs({"wl0": _WL0, "wl1": _WL1}),
            # The guest interface also lists the 5 GHz access point.
            "/sysbus/NeMo/Intf/guest:getMIBs": _wlan_mibs({"wlguest2": _WLGUEST2, "wl0": _WL0}),
            "/sysbus/NMC/Wifi:get": json.dumps(
                {"status": None, "data": {"Enable": True, "ConfigurationMode": combined, "WPSEnable": True}}
            ),
            "/sysbus/SSW/DataElements/Network/SSID:get": _SSW_SSIDS,
            **(answers or {}),
        }

        def post(endpoint: str, data: dict | None = None, auth_required: bool = True) -> str:
            answer = responses.get(endpoint, '{"status": null}')
            if isinstance(answer, Exception):
                raise answer
            return answer

        sm.post.side_effect = post
        return _make_resource(Wifi, sm)

    @staticmethod
    def _writes(sm: MagicMock) -> list[tuple]:
        return [c[0][:2] for c in sm.post.call_args_list if not c[0][0].endswith((":get", ":getMIBs"))]

    @staticmethod
    def _vap(name: str, ssid: str, password: str, visible: bool = True) -> tuple:
        security = {"KeyPassPhrase": password, "WEPKey": "", "ModeEnabled": "WPA2-WPA3-Personal"}
        settings = {"SSID": ssid, "SSIDAdvertisementEnabled": visible, "Security": security}
        return f"/sysbus/NeMo/Intf/{name}:setWLANConfig", {"parameters": {"mibs": {"wlanvap": {name: settings}}}}

    def test_summary(self, mock_session_manager: MagicMock) -> None:
        svc = self._router(mock_session_manager)

        def network(name: str, band: str, ssid: str, password: str, channel: int) -> dict:
            return {
                "network": name,
                "band": band,
                "ssid": ssid,
                "password": password,
                "encryption": "WPA2-WPA3-Personal",
                "up": True,
                "visible": True,
                "channel": channel,
                "connected_devices": 2,
            }

        assert json.loads(svc.summary()) == {
            "enabled": True,
            "bands_share_settings": False,
            "wps": True,
            "networks": [
                network("Wi-Fi", "5GHz", "Home", "Old-Password-1", 36),
                network("Wi-Fi", "2.4GHz", "Home", "Old-Password-1", 6),
                network("guest Wi-Fi", "2.4GHz", "Visitors", "Guest-Password-1", 6),
            ],
        }
        assert self._writes(mock_session_manager) == []

    def test_changes_all_bands_and_copies_5ghz_to_6ghz(self, mock_session_manager: MagicMock) -> None:
        svc = self._router(mock_session_manager)
        assert svc.set_network(password="New-Password-2") == '{"status": null}'
        mirrored = {
            "Enable": True,
            "PersistentEnable": True,
            "SSID": "Home",
            "SSIDAdvertisementEnabled": True,
            "PassPhrase": "New-Password-2",
        }
        assert self._writes(mock_session_manager) == [
            self._vap("wl0", "Home", "New-Password-2"),
            ("/sysbus/SSW/DataElements/Network/SSID/priv6g:set", {"parameters": mirrored}),
            self._vap("wl1", "Home", "New-Password-2"),
        ]

    def test_one_band_keeps_the_other(self, mock_session_manager: MagicMock) -> None:
        svc = self._router(mock_session_manager)
        svc.set_network(ssid="Home 2G", visible=False, band="2.4GHz")
        assert self._writes(mock_session_manager) == [self._vap("wl1", "Home 2G", "Old-Password-1", visible=False)]

    def test_writing_current_values_back_skips_checks(self, mock_session_manager: MagicMock) -> None:
        """A password the web UI would refuse today, e.g. set before the rules got stricter, can be written back."""
        weak = ("wifi1_bcm", "2.4GHz", "Home", "weak")
        svc = self._router(mock_session_manager, lan=_wlan_mibs({"wl0": (*_WL0[:3], "weak"), "wl1": weak}))
        svc.set_network(ssid="Home", password="weak")
        assert [endpoint for endpoint, _ in self._writes(mock_session_manager) if endpoint.endswith(":setWLANConfig")] == [
            "/sysbus/NeMo/Intf/wl0:setWLANConfig",
            "/sysbus/NeMo/Intf/wl1:setWLANConfig",
        ]

    def test_6ghz_errors_are_ignored(self, mock_session_manager: MagicMock) -> None:
        error = requests.HTTPError("500 Server Error")
        svc = self._router(mock_session_manager, answers={"/sysbus/SSW/DataElements/Network/SSID/priv6g:set": error})
        svc.set_network(visible=False, band="5GHz")
        assert self._writes(mock_session_manager)[0] == self._vap("wl0", "Home", "Old-Password-1", visible=False)

    def test_without_6ghz_network(self, mock_session_manager: MagicMock) -> None:
        no_6ghz = json.dumps({"status": {"priv5g": {"Band": "5", "PersistentEnable": True}}})
        svc = self._router(mock_session_manager, answers={"/sysbus/SSW/DataElements/Network/SSID:get": no_6ghz})
        svc.set_network(visible=False, band="5GHz")
        assert self._writes(mock_session_manager) == [self._vap("wl0", "Home", "Old-Password-1", visible=False)]

    def test_band_the_router_doesnt_have(self, mock_session_manager: MagicMock) -> None:
        svc = self._router(mock_session_manager, lan=_wlan_mibs({"wl1": _WL1}))
        with pytest.raises(ValueError, match="no 5GHz Wi-Fi network"):
            svc.set_network(visible=False, band="5GHz")
        assert self._writes(mock_session_manager) == []

    @pytest.mark.parametrize(
        "kwargs,message",
        [
            ({}, "Nothing to change"),
            ({"visible": False, "band": "6GHz"}, 'band must be "2.4GHz" or "5GHz"'),
            ({"ssid": "x"}, "must be 2 to 32"),
            ({"ssid": "a" * 33}, "must be 2 to 32"),
            ({"ssid": "Café"}, "must be 2 to 32"),
            ({"ssid": " Home"}, "must not start or end with a space"),
            ({"ssid": "Visitors"}, "must be different from the guest Wi-Fi name"),
            ({"password": "Short-1"}, "must be 12 to 63"),
            ({"password": "no-upper-case-1"}, "must contain a lower-case letter, an upper-case letter, a digit and a symbol"),
            ({"password": "NoSymbolsHere1"}, "must contain a lower-case letter"),
            ({"password": "Guest-Password-1"}, "must be different from the guest Wi-Fi password"),
            ({"password": "New-Password-2", "band": "5GHz"}, "5GHz and 2.4GHz networks would have the same name but different passwords"),
        ],
    )
    def test_refuses_before_changing_anything(self, mock_session_manager: MagicMock, kwargs: dict, message: str) -> None:
        svc = self._router(mock_session_manager)
        with pytest.raises(ValueError, match=message) as error:
            svc.set_network(**kwargs)
        if "password" in kwargs:
            assert kwargs["password"] not in str(error.value)
        assert self._writes(mock_session_manager) == []

    def test_band_needs_separate_mode(self, mock_session_manager: MagicMock) -> None:
        svc = self._router(mock_session_manager, combined=True)
        with pytest.raises(ValueError, match="combined mode"):
            svc.set_network(visible=False, band="5GHz")
        assert self._writes(mock_session_manager) == []

    def test_no_password_without_encryption(self, mock_session_manager: MagicMock) -> None:
        svc = self._router(mock_session_manager, lan=_wlan_mibs({"wl0": _WL0, "wl1": _WL1}, mode="None"))
        with pytest.raises(ValueError, match="has no encryption"):
            svc.set_network(password="New-Password-2")
        assert self._writes(mock_session_manager) == []

    @pytest.mark.parametrize(
        "answer,message",
        [
            ('{"status": false}', r"didn't accept the settings for wl0\.$"),
            ('{"status": null, "errors": [{"description": "Invalid value"}]}', "didn't accept the settings for wl0: Invalid value"),
        ],
    )
    def test_router_refusal_is_an_error(self, mock_session_manager: MagicMock, answer: str, message: str) -> None:
        svc = self._router(mock_session_manager, answers={"/sysbus/NeMo/Intf/wl0:setWLANConfig": answer})
        with pytest.raises(ValueError, match=message):
            svc.set_network(ssid="Home2")
        assert len(self._writes(mock_session_manager)) == 1  # stopped at the first access point

    def test_guest_network(self, mock_session_manager: MagicMock) -> None:
        svc = self._router(mock_session_manager)
        svc.set_guest_network(ssid="Friends")
        security = {"KeyPassPhrase": "Guest-Password-1", "WEPKey": "", "ModeEnabled": "WPA2-WPA3-Personal"}
        assert self._writes(mock_session_manager) == [
            (
                "/sysbus/NeMo/Intf/wlguest2:setWLANConfig",
                {"parameters": {"mibs": {"wlanvap": {"wlguest2": {"SSID": "Friends", "Security": security}}}}},
            )
        ]

    @pytest.mark.parametrize(
        "kwargs,message",
        [
            ({}, "Nothing to change"),
            ({"ssid": "Home"}, "guest Wi-Fi name must be different from the Wi-Fi name"),
            ({"password": "Old-Password-1"}, "guest Wi-Fi password must be different from the Wi-Fi password"),
            ({"password": "weak"}, "guest Wi-Fi password must be 12 to 63"),
        ],
    )
    def test_guest_network_refuses(self, mock_session_manager: MagicMock, kwargs: dict, message: str) -> None:
        svc = self._router(mock_session_manager)
        with pytest.raises(ValueError, match=message):
            svc.set_guest_network(**kwargs)
        assert self._writes(mock_session_manager) == []

    def test_no_guest_network(self, mock_session_manager: MagicMock) -> None:
        lan = _wlan_mibs({"wl0": _WL0, "wl1": _WL1})
        svc = self._router(mock_session_manager, lan=lan, answers={"/sysbus/NeMo/Intf/guest:getMIBs": lan})
        with pytest.raises(ValueError, match="no guest Wi-Fi network"):
            svc.set_guest_network(ssid="Friends")


def _channel_mibs(access_points: dict | None = None, **radios: dict) -> str:
    """A getMIBs answer for the LAN with channel settings: 5 GHz on auto (now 52), 2.4 GHz set to 6 by hand."""
    mibs = json.loads(_wlan_mibs(access_points or {"wl0": _WL0, "wl1": _WL1}))
    settings = {
        "wifi0_bcm": {
            "Channel": 52,
            "AutoChannelEnable": True,
            "PossibleChannels": "36,40,44,48,52,56,60,64,100,104,108,112,116,120,124,128,132,136,140",
        },
        "wifi1_bcm": {"Channel": 6, "AutoChannelEnable": False, "PossibleChannels": "1,2,3,4,5,6,7,8,9,10,11"},
    }
    for radio, values in mibs["status"]["wlanradio"].items():
        values |= settings[radio] | radios.get(radio, {})
    return json.dumps(mibs)


def _set_radio(access_point: str, radio: str, **settings: object) -> tuple:
    """The setWLANConfig request that changes only a radio's settings."""
    return f"/sysbus/NeMo/Intf/{access_point}:setWLANConfig", {"parameters": {"mibs": {"wlanradio": {radio: settings}}}}


class TestWifiChannel:
    """set_channel() and search_channel(), against a router with 5 GHz on wl0 (wifi0_bcm) and 2.4 GHz on wl1 (wifi1_bcm)."""

    @staticmethod
    def _router(sm: MagicMock, lan: str | None = None, set_answer: str = '{"status": null}') -> Wifi:
        answers = {"/sysbus/NeMo/Intf/lan:getMIBs": lan or _channel_mibs()}
        _answering(
            sm, answers | {f"/sysbus/NeMo/Intf/{vap}:setWLANConfig": set_answer for vap in ("wl0", "wl1")}, default='{"status": true}'
        )
        return _make_resource(Wifi, sm)

    @pytest.mark.parametrize(
        "args,expected",
        [
            (("5GHz", 52), _set_radio("wl0", "wifi0_bcm", Channel=52, AutoChannelEnable=False)),
            (("5GHz", 36, "80MHz"), _set_radio("wl0", "wifi0_bcm", Channel=36, AutoChannelEnable=False, OperatingChannelBandwidth="80MHz")),
            (("5GHz", "auto", "Auto"), _set_radio("wl0", "wifi0_bcm", AutoChannelEnable=True, OperatingChannelBandwidth="Auto")),
            (
                ("2.4GHz", 11, "40MHz"),
                _set_radio("wl1", "wifi1_bcm", Channel=11, AutoChannelEnable=False, OperatingChannelBandwidth="40MHz"),
            ),
            (("2.4GHz", "auto"), _set_radio("wl1", "wifi1_bcm", AutoChannelEnable=True)),
        ],
    )
    def test_set_channel(self, mock_session_manager: MagicMock, args: tuple, expected: tuple) -> None:
        """Only the radio's settings are sent, not the access point's, e.g. its password."""
        svc = self._router(mock_session_manager)
        assert svc.set_channel(*args) == '{"status": null}'
        assert _sent(mock_session_manager, (":getMIBs",)) == [expected]

    def test_2_4ghz_channels_default_to_1_to_13(self, mock_session_manager: MagicMock) -> None:
        svc = self._router(mock_session_manager, _channel_mibs(wifi1_bcm={"PossibleChannels": ""}))
        svc.set_channel("2.4GHz", 13)
        with pytest.raises(ValueError, match="one of 1, 2, .*, 13, got 14"):
            svc.set_channel("2.4GHz", 14)

    @pytest.mark.parametrize(
        "args,message",
        [
            (("5GHz", 140), r'The 5GHz channel must be "auto" or one of 36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 108, 112, got 140'),
            (("5GHz", 6), "The 5GHz channel must be"),
            (("2.4GHz", 13), r"The 2.4GHz channel must be \"auto\" or one of 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, got 13"),
            (("2.4GHz", True), "The 2.4GHz channel must be"),
            (("2.4GHz", "6"), "The 2.4GHz channel must be"),
            (("2.4GHz", "Auto"), "The 2.4GHz channel must be"),
            (("5GHz", 36, "160MHz"), r"The 5GHz bandwidth must be one of \['80MHz', 'Auto'\], got '160MHz'"),
            (("2.4GHz", 6, "Auto"), r"The 2.4GHz bandwidth must be one of \['20MHz', '40MHz'\]"),
            (("6GHz", 37), 'band must be "2.4GHz" or "5GHz", got \'6GHz\''),
        ],
    )
    def test_set_channel_refuses(self, mock_session_manager: MagicMock, args: tuple, message: str) -> None:
        svc = self._router(mock_session_manager)
        with pytest.raises(ValueError, match=message):
            svc.set_channel(*args)
        assert _sent(mock_session_manager, (":getMIBs",)) == []

    def test_set_channel_on_a_missing_band(self, mock_session_manager: MagicMock) -> None:
        svc = self._router(mock_session_manager, _channel_mibs({"wl0": _WL0}))
        with pytest.raises(ValueError, match="This router has no 2.4GHz Wi-Fi network"):
            svc.set_channel("2.4GHz", "auto")

    @pytest.mark.parametrize(
        "answer,message",
        [
            ('{"status": false}', "The router didn't accept the settings for wl0.$"),
            ('{"status": null, "errors": [{"description": "Invalid value"}]}', "didn't accept the settings for wl0: Invalid value"),
        ],
    )
    def test_set_channel_not_accepted(self, mock_session_manager: MagicMock, answer: str, message: str) -> None:
        svc = self._router(mock_session_manager, set_answer=answer)
        with pytest.raises(ValueError, match=message):
            svc.set_channel("5GHz", 36)

    def test_search_channel(self, mock_session_manager: MagicMock) -> None:
        svc = self._router(mock_session_manager)
        svc.search_channel("5GHz")
        assert _sent(mock_session_manager, (":getMIBs",)) == [("/sysbus/NeMo/Intf/wifi0_bcm:startAutoChannelSelection", {"parameters": {}})]

    def test_search_channel_set_by_hand(self, mock_session_manager: MagicMock) -> None:
        svc = self._router(mock_session_manager)
        with pytest.raises(ValueError, match=r"The 2.4GHz channel is set by hand \(channel 6\).*set_channel\(\"2.4GHz\", \"auto\"\)"):
            svc.search_channel("2.4GHz")
        assert _sent(mock_session_manager, (":getMIBs",)) == []


_WIFI_7 = {"Enabled24GHz": "b,g,n,ax,be", "Enabled5GHz": "a,n,ac,ax,be", "Enabled6GHz": "ax,be", "SupportedStandards": "a,b,g,n,ac,ax"}
_STANDARDS_URL = "/sysbus/SSW/Steering/MasterConfig/OperatingStandards"


class TestWifiSteering:
    """Band steering, the Wi-Fi standards and the WLAN-Box sync, against a router whose 5 and 2.4 GHz networks share
    their name and password, and that offers Wi-Fi 7 on every band."""

    READS = (":get", ":getMIBs")
    MAC = "AA:BB:CC:DD:EE:FF"

    @staticmethod
    def _router(sm: MagicMock, lan: str | None = None, standards: dict | None = None, stations: object = None) -> Wifi:
        responses = {
            "/sysbus/NeMo/Intf/lan:getMIBs": lan or _wlan_mibs({"wl0": _WL0, "wl1": _WL1}),
            "/sysbus/NeMo/Intf/guest:getMIBs": _wlan_mibs({"wlguest2": _WLGUEST2}),
            f"{_STANDARDS_URL}:get": json.dumps({"status": _WIFI_7 if standards is None else standards}),
            "/sysbus/SSW/Steering/ExceptionList/Station:get": json.dumps({"status": stations or {}}),
        }
        _answering(sm, responses)
        return _make_resource(Wifi, sm)

    @pytest.mark.parametrize("enable", [True, False])
    def test_set_steering_enabled(self, mock_session_manager: MagicMock, enable: bool) -> None:
        self._router(mock_session_manager).set_steering_enabled(enable)
        assert _sent(mock_session_manager, self.READS) == [("/sysbus/SSW/Steering:set", {"parameters": {"Enable": enable}})]

    @pytest.mark.parametrize(
        "wl1", [("wifi1_bcm", "2.4GHz", "Home-2", "Old-Password-1"), ("wifi1_bcm", "2.4GHz", "Home", "New-Password-2")]
    )
    def test_steering_needs_the_same_name_and_password(self, mock_session_manager: MagicMock, wl1: tuple) -> None:
        """Like the web UI, only to turn it on. The message never contains a password."""
        svc = self._router(mock_session_manager, lan=_wlan_mibs({"wl0": _WL0, "wl1": wl1}))
        with pytest.raises(ValueError, match=r"same name and password\. Give them the same with set_network\(\) first") as error:
            svc.set_steering_enabled(True)
        assert "Password-" not in str(error.value)
        assert _sent(mock_session_manager, self.READS) == []
        svc.set_steering_enabled(False)
        assert _sent(mock_session_manager, self.READS) == [("/sysbus/SSW/Steering:set", {"parameters": {"Enable": False}})]

    @pytest.mark.parametrize(
        "band,standard,standards,changes",
        [
            ("2.4GHz", 4, _WIFI_7, [("disable", "ax"), ("disable", "be")]),
            ("5GHz", 6, _WIFI_7, [("disable", "be")]),
            ("5GHz", 5, _WIFI_7, [("disable", "ax"), ("disable", "be")]),
            ("6GHz", 6, _WIFI_7, [("disable", "be")]),
            ("5GHz", 7, _WIFI_7, []),
            ("2.4GHz", 7, {"Enabled24GHz": "b,g,n"}, [("enable", "ax"), ("enable", "be")]),
            ("5GHz", 6, {"Enabled5GHz": "a,n,ac,be"}, [("enable", "ax"), ("disable", "be")]),
            ("6GHz", 7, {}, [("enable", "ax"), ("enable", "be")]),
        ],
    )
    def test_set_standard_one_by_one_like_the_web_ui_on_the_internet_box_4(
        self, mock_session_manager: MagicMock, band: str, standard: int, standards: dict, changes: list
    ) -> None:
        result = self._router(mock_session_manager, standards=standards).set_standard(band, standard)  # type: ignore[arg-type]
        assert _sent(mock_session_manager) == [
            (f"{_STANDARDS_URL}:{change}", {"parameters": {"opStd": name, "band": band}}) for change, name in changes
        ]
        assert mock_session_manager.post.call_args[0][0] == f"{_STANDARDS_URL}:get"  # the standards after the change
        assert json.loads(result) == {"status": standards}

    @pytest.mark.parametrize(
        "band,standard,message",
        [
            ("2.4GHz", 5, "The 2.4GHz standard must be one of 7, 6, 4, got 5"),
            ("5GHz", 4, "The 5GHz standard must be one of 7, 6, 5, got 4"),
            ("6GHz", 5, "The 6GHz standard must be one of 7, 6, got 5"),
            ("5GHz", True, "got True"),
            ("60GHz", 7, 'band must be "2.4GHz", "5GHz" or "6GHz", got \'60GHz\''),
        ],
    )
    def test_set_standard_offers_the_web_ui_standards(
        self, mock_session_manager: MagicMock, band: str, standard: object, message: str
    ) -> None:
        with pytest.raises(ValueError, match=message):
            self._router(mock_session_manager).set_standard(band, standard)  # type: ignore[arg-type]
        mock_session_manager.post.assert_not_called()

    @pytest.mark.parametrize("enable,value", [(True, 1), (False, 0)])
    def test_set_wlan_box_sync(self, mock_session_manager: MagicMock, enable: bool, value: int) -> None:
        self._router(mock_session_manager).set_wlan_box_sync(enable)
        assert _sent(mock_session_manager) == [("/sysbus/SSW/Steering/MasterConfig:set", {"parameters": {"SyncEnableField": value}})]

    @pytest.mark.parametrize(
        "kwargs,parameters",
        [
            ({"steer": False}, {"target": "NoSteer"}),
            ({"access_point": " Router"}, {"target": "Root", "type": "Force", "forceMode": "TargetAvailable"}),
            ({"access_point": "aa-bb-cc-00-00-01"}, {"target": "AA:BB:CC:00:00:01", "type": "Force", "forceMode": "TargetAvailable"}),
        ],
    )
    def test_set_device_steering_creates_an_exception(self, mock_session_manager: MagicMock, kwargs: dict, parameters: dict) -> None:
        self._router(mock_session_manager).set_device_steering("aa:bb:cc:dd:ee:ff", **kwargs)
        assert _sent(mock_session_manager) == [
            ("/sysbus/SSW/Steering/ExceptionList:createException", {"parameters": {"MAC": self.MAC, "mask": 6, **parameters}})
        ]

    @pytest.mark.parametrize("stations", [{"1": {"MAC": "AA:BB:CC:DD:EE:FF", "Target": "NoSteer"}}, [{"MAC": "aa:bb:cc:dd:ee:ff"}]])
    def test_set_device_steering_deletes_the_exception(self, mock_session_manager: MagicMock, stations: object) -> None:
        self._router(mock_session_manager, stations=stations).set_device_steering("AA-BB-CC-DD-EE-FF")
        assert _sent(mock_session_manager) == [
            ("/sysbus/SSW/Steering/ExceptionList:deleteException", {"parameters": {"MAC": self.MAC, "mask": 6}})
        ]

    def test_set_device_steering_without_an_exception(self, mock_session_manager: MagicMock) -> None:
        stations = {"1": {"MAC": "AA:BB:CC:00:00:01", "Target": "NoSteer"}}
        result = self._router(mock_session_manager, stations=stations).set_device_steering(self.MAC)
        assert json.loads(result) == {"status": stations}
        assert _sent(mock_session_manager) == []

    def test_set_device_steering_access_point_needs_steer(self, mock_session_manager: MagicMock) -> None:
        with pytest.raises(ValueError, match="access_point only applies to devices that band steering moves"):
            self._router(mock_session_manager).set_device_steering(self.MAC, steer=False, access_point="router")
        mock_session_manager.post.assert_not_called()


# ── WireGuard ─────────────────────────────────────────────────────────


class TestWireguardClients:
    """The server switch and the clients, against a router with WireGuard, its server off and a client "laptop"."""

    CLIENT = "/sysbus/WireGuard/Server/default/Client"
    CONFIG = (
        "[Interface]\nPrivateKey = cHJpdmF0ZS1rZXk=\nAddress = 10.0.1.3/32\nDNS = 192.168.1.1\n\n"
        "[Peer]\nPublicKey = cHVibGljLWtleQ==\nAllowedIPs = 0.0.0.0/0\nEndpoint = 203.0.113.5:51820\n"
    )
    READS = (":_get", ":getLANIP", ":getWANStatus")

    def _wireguard(self, sm: MagicMock, enabled: bool = True, public_ip: str = "203.0.113.5", **answers: object) -> Wireguard:
        clients = {
            "WireGuard.Server.1.Client.1.": {"Alias": "laptop", "Enable": True, "IntranetAccess": True},
            "WireGuard.Server.1.Client.": {},
        }
        _answering(
            sm,
            {
                "/sysbus/WireGuard:_get": json.dumps({"status": {"WireGuard.": {"Enable": enabled, "Status": "Enabled"}}}),
                f"{self.CLIENT}:_get": json.dumps({"status": clients}),
                "/sysbus/NMC:getLANIP": json.dumps({"status": None, "data": {"Address": "192.168.1.1"}}),
                "/sysbus/NMC:getWANStatus": json.dumps({"status": True, "data": {"IPAddress": public_ip}}),
                f"{self.CLIENT}/phone:GeneratePrivateKeyAndGetQRConfig": json.dumps({"status": self.CONFIG}),
                **{f"{self.CLIENT}/phone:{function}": answer for function, answer in answers.items()},
            },
            default='{"status": null}',
        )
        return _make_resource(Wireguard, sm)

    def test_client_status(self, mock_session_manager: MagicMock) -> None:
        _make_resource(Wireguard, mock_session_manager).client_status("laptop")
        assert mock_session_manager.post.call_args[0][0] == f"{self.CLIENT}/laptop/InfoStats:_get"

    @pytest.mark.parametrize("enable", [True, False])
    def test_set_server_enabled(self, mock_session_manager: MagicMock, enable: bool) -> None:
        self._wireguard(mock_session_manager).set_server_enabled(enable)
        assert _sent(mock_session_manager, self.READS) == [
            ("/sysbus/WireGuard/Server/default:_set", {"parameters": {"parameters": {"Enable": enable}}})
        ]

    def test_add_client_with_the_public_ip(self, mock_session_manager: MagicMock) -> None:
        svc = self._wireguard(mock_session_manager)
        assert json.loads(svc.add_client("phone")) == {"status": self.CONFIG}
        assert _sent(mock_session_manager, self.READS) == [
            (f"{self.CLIENT}:_add", {"parameters": {"parameters": {"Alias": "phone", "ExtraData": "203.0.113.5;192.168.1.1"}}}),
            (f"{self.CLIENT}/phone:_set", {"parameters": {"parameters": {"Enable": True, "IntranetAccess": True}}}),
            (f"{self.CLIENT}/phone:GeneratePrivateKeyAndGetQRConfig", {"parameters": {}}),
        ]

    def test_add_client_with_a_host_name(self, mock_session_manager: MagicMock) -> None:
        """Like the web UI, the router's public IP address in the configuration is replaced with the endpoint."""
        svc = self._wireguard(mock_session_manager)
        config = json.loads(svc.add_client("phone", endpoint="myhome.ddns.net", intranet_access=False))["status"]
        assert config == self.CONFIG.replace("Endpoint = 203.0.113.5:51820", "Endpoint = myhome.ddns.net:51820")
        assert _sent(mock_session_manager, self.READS)[:2] == [
            (f"{self.CLIENT}:_add", {"parameters": {"parameters": {"Alias": "phone", "ExtraData": "myhome.ddns.net;192.168.1.1"}}}),
            (f"{self.CLIENT}/phone:_set", {"parameters": {"parameters": {"Enable": True, "IntranetAccess": False}}}),
        ]
        assert "/sysbus/NMC:getWANStatus" not in [c[0][0] for c in mock_session_manager.post.call_args_list]

    @pytest.mark.parametrize(
        "kwargs,setup,message",
        [
            ({"name": "ph"}, {}, "client name must be 3 to 16 letters"),
            ({"name": "x" * 17}, {}, "client name must be"),
            ({"name": "1phone"}, {}, "client name must be"),
            ({"name": "_phone"}, {}, "client name must be"),
            ({"name": "my phone"}, {}, "client name must be"),
            ({"name": "laptop"}, {}, "There's already a WireGuard client named 'laptop'"),
            ({"endpoint": "my home"}, {}, "endpoint must be an IPv4 address or a host name"),
            ({"endpoint": "-home.ddns.net"}, {}, "endpoint must be"),
            ({}, {"enabled": False}, "WireGuard isn't available on this router"),
            ({}, {"public_ip": "0.0.0.0"}, "The router has no public IPv4 address. Give an endpoint"),
            ({}, {"public_ip": ""}, "no public IPv4 address"),
        ],
    )
    def test_add_client_refuses(self, mock_session_manager: MagicMock, kwargs: dict, setup: dict, message: str) -> None:
        svc = self._wireguard(mock_session_manager, **setup)
        with pytest.raises(ValueError, match=message):
            svc.add_client(**{"name": "phone", **kwargs})
        assert _sent(mock_session_manager, self.READS) == []

    @pytest.mark.parametrize(
        "answers,error",
        [
            ({"GeneratePrivateKeyAndGetQRConfig": '{"status": null}'}, ValueError),
            ({"GeneratePrivateKeyAndGetQRConfig": '{"status": "error"}'}, ValueError),
            ({"_set": _http_error(500)}, requests.HTTPError),
        ],
    )
    def test_add_client_deletes_the_client_again_on_errors(self, mock_session_manager: MagicMock, answers: dict, error: type) -> None:
        svc = self._wireguard(mock_session_manager, **answers)
        with pytest.raises(error):
            svc.add_client("phone")
        assert _sent(mock_session_manager, self.READS)[-1] == (f"{self.CLIENT}/phone:_del", {"parameters": {}})

    @pytest.mark.parametrize(
        "kwargs,changes",
        [({"enabled": False}, {"Enable": False}), ({"enabled": True, "intranet_access": False}, {"Enable": True, "IntranetAccess": False})],
    )
    def test_set_client(self, mock_session_manager: MagicMock, kwargs: dict, changes: dict) -> None:
        self._wireguard(mock_session_manager).set_client("laptop", **kwargs)
        assert _sent(mock_session_manager, self.READS) == [(f"{self.CLIENT}/laptop:_set", {"parameters": {"parameters": changes}})]

    def test_set_client_without_changes(self, mock_session_manager: MagicMock) -> None:
        with pytest.raises(ValueError, match="Nothing to change"):
            self._wireguard(mock_session_manager).set_client("laptop")
        mock_session_manager.post.assert_not_called()

    def test_delete_client(self, mock_session_manager: MagicMock) -> None:
        self._wireguard(mock_session_manager).delete_client("laptop")
        assert _sent(mock_session_manager, self.READS) == [(f"{self.CLIENT}/laptop:_del", {"parameters": {}})]

    @pytest.mark.parametrize("method,kwargs", [("set_client", {"enabled": False}), ("delete_client", {})])
    def test_unknown_client(self, mock_session_manager: MagicMock, method: str, kwargs: dict) -> None:
        with pytest.raises(ValueError, match="There's no WireGuard client named 'tablet'. The clients are: 'laptop'."):
            getattr(self._wireguard(mock_session_manager), method)("tablet", **kwargs)
        assert _sent(mock_session_manager, self.READS) == []

    def test_set_server_enabled_without_wireguard(self, mock_session_manager: MagicMock) -> None:
        with pytest.raises(ValueError, match="WireGuard isn't available"):
            self._wireguard(mock_session_manager, enabled=False).set_server_enabled(True)
        assert _sent(mock_session_manager, self.READS) == []


# ── WWAN ──────────────────────────────────────────────────────────────


class TestWWAN:
    def test_status_no_auth(self, mock_session_manager: MagicMock) -> None:
        svc = _make_resource(WWAN, mock_session_manager)
        svc.status()
        assert mock_session_manager.post.call_args[0][2] is False  # auth_required

    def test_mibs_no_auth(self, mock_session_manager: MagicMock) -> None:
        svc = _make_resource(WWAN, mock_session_manager)
        svc.mibs()
        assert mock_session_manager.post.call_args[0][2] is False  # auth_required
