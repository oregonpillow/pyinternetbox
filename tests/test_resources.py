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

    @pytest.mark.parametrize("key,service", [("aa-bb-cc-dd-ee-ff", "Devices.Device.AA:BB:CC:DD:EE:FF"), ("HGW", "Devices.Device.HGW")])
    def test_rename(self, mock_session_manager: MagicMock, key: str, service: str) -> None:
        """Keys are case-sensitive: MAC addresses are normalised to the router's upper case, other keys pass unchanged."""
        svc = _make_resource(Devices, mock_session_manager)
        svc.rename(key, "Laptop")
        assert mock_session_manager.post.call_args[0][:2] == (
            "/ws",
            {"service": service, "method": "set", "parameters": {"parameters": {"Name": "Laptop"}}},
        )

    def test_wake_on_lan(self, mock_session_manager: MagicMock) -> None:
        svc = _make_resource(Devices, mock_session_manager)
        svc.wake_on_lan("aa:bb:cc:dd:ee:ff")
        assert mock_session_manager.post.call_args[0][:2] == (
            "/sysbus/WOL:sendWakeOnLan",
            {"parameters": {"hostID": "AA:BB:CC:DD:EE:FF", "broadcast": True, "retries": 3, "interval": 60000}},
        )


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
            ("level", "/sysbus/Firewall:getFirewallLevel"),
            ("ipv6_level", "/sysbus/Firewall:getFirewallIPv6Level"),
            ("port_forwarding", "/sysbus/Firewall:getPortForwarding"),
            ("custom_rule", "/sysbus/Firewall:getCustomRule"),
            ("delete_dmz", "/sysbus/Firewall:deleteDMZ"),
        ],
    )
    def test_endpoints(self, mock_session_manager: MagicMock, method: str, endpoint: str) -> None:
        svc = _make_resource(Firewall, mock_session_manager)
        getattr(svc, method)()
        assert mock_session_manager.post.call_args[0][0] == endpoint

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
