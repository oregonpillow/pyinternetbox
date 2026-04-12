"""Tests for resource classes.

Each resource is tested by verifying it calls the correct endpoint with the
expected payload via the mocked SessionManager.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

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
            ("ipv6_level", "/sysbus/Firewall:getFirewallIPv6Level"),
            ("port_forwarding", "/sysbus/Firewall:getPortForwarding"),
            ("custom_rule", "/sysbus/Firewall:getCustomRule"),
        ],
    )
    def test_endpoints(self, mock_session_manager: MagicMock, method: str, endpoint: str) -> None:
        svc = _make_resource(Firewall, mock_session_manager)
        getattr(svc, method)()
        assert mock_session_manager.post.call_args[0][0] == endpoint


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

    def test_bdd_uses_ws(self, mock_session_manager: MagicMock) -> None:
        svc = _make_resource(NMC, mock_session_manager)
        svc.bdd()
        data = mock_session_manager.post.call_args[0][1]
        assert data["service"] == "NMC.BDD"


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


# ── Security ──────────────────────────────────────────────────────────


class TestSecurity:
    @pytest.mark.parametrize(
        "method,endpoint",
        [
            ("gateway_status", "/sysbus/SecurityGateway:get"),
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


# ── MST ───────────────────────────────────────────────────────────────


class TestMST:
    @pytest.mark.parametrize(
        "method,endpoint", [("status", "/sysbus/ToD/MaxSurfTime:get"), ("get", "/sysbus/ToD:listMST"), ("set", "/sysbus/ToD:setMST")]
    )
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
