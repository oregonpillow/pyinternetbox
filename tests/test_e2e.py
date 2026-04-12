"""End-to-end tests for the Internet Box client.

These tests make real HTTP requests to a live Swisscom/Wingo Internet Box gateway
and verify that every endpoint returns a valid HTTP status (2xx).

Since :meth:`SessionManager.post` and :meth:`SessionManager.get` both call
``raise_for_status()`` internally, any call that completes without raising a
``requests.HTTPError`` confirms a valid HTTP response code was received.

Run::

    uv run pytest tests/test_e2e.py -v

To also run destructive tests (write to the router)::

    uv run pytest tests/test_e2e.py -m destructive -v

Mutating methods (``LED.set``, ``Wifi.power``, ``MST.set``) are marked
``@pytest.mark.destructive`` and skipped by default. They are tested safely by
first reading the current value from the router and writing the same value back,
so the configuration is left unchanged after the test run.
"""

from __future__ import annotations

import json

import pytest

from internetbox_client.resources import *  # noqa: F403
from internetbox_client.utils.APIClient import SessionManager

# ── Configuration ─────────────────────────────────────────────────────────────

# ── Shared session fixture ────────────────────────────────────────────────────


@pytest.fixture(scope="session")
def sm():
    """Authenticated :class:`SessionManager` shared across the entire test session."""
    with SessionManager() as session:
        yield session


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make(cls, sm):
    """Instantiate *cls* backed by the shared session without creating a new auth context."""
    obj = object.__new__(cls)
    obj._sm = sm
    obj._owns_session = False
    return obj


def _ok(result: str) -> None:
    """Assert the call returned a string (HTTP 2xx confirmed via raise_for_status)."""
    assert isinstance(result, str)


# ── APServices ────────────────────────────────────────────────────────────────


class TestE2EAPServices:
    @pytest.fixture(scope="class")
    def svc(self, sm):
        return _make(APServices, sm)

    def test_info(self, svc):
        _ok(svc.info())


# ── CardDav ───────────────────────────────────────────────────────────────────


class TestE2ECardDav:
    @pytest.fixture(scope="class")
    def svc(self, sm):
        return _make(CardDav, sm)

    def test_status(self, svc):
        _ok(svc.status())


# ── Debug ─────────────────────────────────────────────────────────────────────


class TestE2EDebug:
    @pytest.fixture(scope="class")
    def svc(self, sm):
        return _make(Debug, sm)

    def test_status(self, svc):
        _ok(svc.status())

    def test_wifi_driver_stats(self, svc):
        _ok(svc.wifi_driver_stats())


# ── DECT ──────────────────────────────────────────────────────────────────────


class TestE2EDECT:
    @pytest.fixture(scope="class")
    def svc(self, sm):
        return _make(DECT, sm)

    def test_base_state(self, svc):
        _ok(svc.base_state())

    def test_nemo_state(self, svc):
        _ok(svc.nemo_state())

    def test_rfpi(self, svc):
        _ok(svc.rfpi())

    def test_pin(self, svc):
        _ok(svc.pin())

    def test_version(self, svc):
        _ok(svc.version())

    def test_dspg(self, svc):
        _ok(svc.dspg())


# ── Devices ───────────────────────────────────────────────────────────────────


class TestE2EDevices:
    @pytest.fixture(scope="class")
    def svc(self, sm):
        return _make(Devices, sm)

    def test_info(self, svc):
        _ok(svc.info())

    def test_get(self, svc):
        _ok(svc.get())

    def test_usb(self, svc):
        _ok(svc.usb())

    def test_topology(self, svc):
        _ok(svc.topology())

    def test_network_xt(self, svc):
        _ok(svc.network_xt())

    def test_memory_status(self, svc):
        _ok(svc.memory_status())


# ── DHCP ──────────────────────────────────────────────────────────────────────


class TestE2EDHCP:
    @pytest.fixture(scope="class")
    def svc(self, sm):
        return _make(DHCP, sm)

    def test_static_leases(self, svc):
        _ok(svc.static_leases())

    def test_server_pool(self, svc):
        _ok(svc.server_pool())

    def test_ipv6_prefix_information(self, svc):
        _ok(svc.ipv6_prefix_information())


# ── DNS ───────────────────────────────────────────────────────────────────────


class TestE2EDNS:
    @pytest.fixture(scope="class")
    def svc(self, sm):
        return _make(DNS, sm)

    def test_status(self, svc):
        _ok(svc.status())

    def test_mode(self, svc):
        _ok(svc.mode())

    def test_settings(self, svc):
        _ok(svc.settings())

    def test_user(self, svc):
        _ok(svc.user())

    def test_user_ipv6(self, svc):
        _ok(svc.user_ipv6())

    def test_cache(self, svc):
        _ok(svc.cache())


# ── DynDNS ────────────────────────────────────────────────────────────────────


class TestE2EDynDNS:
    @pytest.fixture(scope="class")
    def svc(self, sm):
        return _make(DynDNS, sm)

    def test_global_enable(self, svc):
        _ok(svc.global_enable())

    def test_hosts(self, svc):
        _ok(svc.hosts())

    def test_services(self, svc):
        _ok(svc.services())


# ── Events ────────────────────────────────────────────────────────────────────


class TestE2EEvents:
    @pytest.fixture(scope="class")
    def svc(self, sm):
        return _make(Events, sm)

    def test_service(self, svc):
        # id=None passes "None" as channelid — router returns HTTP 200 regardless
        _ok(svc.service())

    def test_handler(self, svc):
        _ok(svc.handler(["NMC.Wifi"]))

    def test_log(self, svc, sm):
        devices = _make(Devices, sm)
        keys = json.loads(devices.get(flags="lan")).get("status", [])
        if not keys:
            pytest.skip("No LAN devices found on this router")
        _ok(svc.log(keys[0]["Key"]))

    def test_open_channel(self, svc):
        events = [{"service": "Devices.Device.HGW", "event": "cpu"}]
        _ok(svc.open_channel(events))

    def test_open_poll_unsubscribe_channel(self, svc):
        """Open a channel, poll it, then unsubscribe — all in one test to share the channel ID."""
        events = [{"service": "Devices.Device.HGW", "event": "cpu"}]
        raw = svc.open_channel(events)
        _ok(raw)
        try:
            channel_id = json.loads(raw).get("status", {}).get("id")
        except (json.JSONDecodeError, AttributeError, TypeError):
            channel_id = None

        if channel_id is not None:
            _ok(svc.poll(channel_id))
            _ok(svc.unsubscribe(events, channel_id))

    def test_subscribe_unsubscribe(self, svc):
        """Open a channel, subscribe to an event, then unsubscribe."""
        events = [{"service": "Devices.Device.HGW", "event": "sysinfo"}]
        raw = svc.open_channel(events)
        try:
            channel_id = json.loads(raw).get("status", {}).get("id")
        except (json.JSONDecodeError, AttributeError, TypeError):
            channel_id = None

        if channel_id is not None:
            _ok(svc.subscribe(events, channel_id))
            _ok(svc.unsubscribe(events, channel_id))

    def test_device_network(self, svc):
        _ok(svc.device_network(["AA:BB:CC:DD:EE:FF"]))

    def test_ethernet_ports(self, svc):
        _ok(svc.ethernet_ports())


# ── Firewall ──────────────────────────────────────────────────────────────────


class TestE2EFirewall:
    @pytest.fixture(scope="class")
    def svc(self, sm):
        return _make(Firewall, sm)

    def test_dmz(self, svc):
        _ok(svc.dmz())

    def test_ipv6_level(self, svc):
        _ok(svc.ipv6_level())

    def test_port_forwarding(self, svc):
        _ok(svc.port_forwarding())

    def test_custom_rule(self, svc):
        _ok(svc.custom_rule())


# ── GenLog ────────────────────────────────────────────────────────────────────


class TestE2EGenLog:
    @pytest.fixture(scope="class")
    def svc(self, sm):
        return _make(GenLog, sm)

    def test_next_logs(self, svc):
        _ok(svc.next_logs("cpu", 10))

    def test_read_logs(self, svc):
        _ok(svc.read_logs(10))


# ── History ───────────────────────────────────────────────────────────────────


class TestE2EHistory:
    @pytest.fixture(scope="class")
    def svc(self, sm):
        return _make(History, sm)

    def test_backup_entries(self, svc):
        _ok(svc.backup_entries())

    def test_upgrade_entries(self, svc):
        _ok(svc.upgrade_entries())


# ── HTTPService ───────────────────────────────────────────────────────────────


class TestE2EHTTPService:
    @pytest.fixture(scope="class")
    def svc(self, sm):
        return _make(HTTPService, sm)

    def test_current_user(self, svc):
        _ok(svc.current_user())


# ── LAN ───────────────────────────────────────────────────────────────────────


class TestE2ELAN:
    @pytest.fixture(scope="class")
    def svc(self, sm):
        return _make(LAN, sm)

    def test_mac(self, svc):
        _ok(svc.mac())

    def test_ipv4_network(self, svc):
        _ok(svc.ipv4_network())

    def test_ipv6_configuration(self, svc):
        _ok(svc.ipv6_configuration())

    def test_mibs(self, svc):
        _ok(svc.mibs())

    def test_parameters(self, svc):
        _ok(svc.parameters())

    @pytest.mark.parametrize("port", [0, 1, 2, 3, 4])
    def test_ethernet_port(self, svc, port):
        _ok(svc.ethernet_port(port))

    def test_mac_lookup(self, svc, sm):
        devices = _make(Devices, sm)
        keys = json.loads(devices.get(flags="lan")).get("status", [])
        if not keys:
            pytest.skip("No LAN devices found on this router")
        _ok(svc.mac_lookup(keys[0]["Key"]))


# ── LED ───────────────────────────────────────────────────────────────────────


class TestE2ELED:
    @pytest.fixture(scope="class")
    def svc(self, sm):
        return _make(LED, sm)

    @pytest.mark.parametrize("led_type", ["Status", "Wireless"])
    def test_status(self, svc, led_type):
        _ok(svc.status(led_type))

    @pytest.mark.parametrize("led_type", ["Status", "Wireless"])
    def test_nmc_status(self, svc, led_type):
        _ok(svc.nmc_status(led_type))

    @pytest.mark.parametrize("led_type", ["Status", "Wireless"])
    @pytest.mark.destructive
    def test_set_reverts_brightness(self, svc, led_type):
        """Read current brightness and write the same value back — effective no-op."""
        raw = svc.status(led_type)
        try:
            brightness = int(json.loads(raw).get("status", {}).get("data", {}).get("Brightness", 100))
        except (json.JSONDecodeError, TypeError, ValueError):
            brightness = 100
        _ok(svc.set(led_type, brightness))

    @pytest.mark.destructive
    def test_party_time_on(self, svc):
        _ok(svc.party_time(mode="on", flashes=3))

    @pytest.mark.destructive
    def test_party_time_off(self, svc):
        _ok(svc.party_time(mode="off"))

    @pytest.mark.destructive
    def test_morse_code_yolo(self, svc):
        _ok(svc.morse_code(message="YOLO", led="Status"))

    @pytest.mark.destructive
    def test_morse_code_yolo_wireless(self, svc):
        _ok(svc.morse_code(message="YOLO", led="Wireless"))


# ── Mitigation ────────────────────────────────────────────────────────────────


class TestE2EMitigation:
    @pytest.fixture(scope="class")
    def svc(self, sm):
        return _make(Mitigation, sm)

    def test_status(self, svc):
        _ok(svc.status())


# ── NMC ───────────────────────────────────────────────────────────────────────


class TestE2ENMC:
    @pytest.fixture(scope="class")
    def svc(self, sm):
        return _make(NMC, sm)

    def test_status(self, svc):
        _ok(svc.status())

    def test_ip_conflicts(self, svc):
        _ok(svc.ip_conflicts())

    def test_wan_status(self, svc):
        _ok(svc.wan_status())

    def test_orientation(self, svc):
        _ok(svc.orientation())

    def test_lan_ip(self, svc):
        _ok(svc.lan_ip())

    def test_phonebook_backup(self, svc):
        _ok(svc.phonebook_backup())

    def test_static_routes(self, svc):
        _ok(svc.static_routes())

    def test_network_config(self, svc):
        _ok(svc.network_config())

    def test_bdd(self, svc):
        _ok(svc.bdd())


# ── OopsTracker ───────────────────────────────────────────────────────────────


class TestE2EOopsTracker:
    @pytest.fixture(scope="class")
    def svc(self, sm):
        return _make(OopsTracker, sm)

    def test_status(self, svc):
        _ok(svc.status())

    def test_oopses(self, svc):
        _ok(svc.oopses())


# ── PasswordRecovery ──────────────────────────────────────────────────────────


class TestE2EPasswordRecovery:
    @pytest.fixture(scope="class")
    def svc(self, sm):
        return _make(PasswordRecovery, sm)

    def test_status(self, svc):
        _ok(svc.status())


# ── Phonebook ─────────────────────────────────────────────────────────────────


class TestE2EPhonebook:
    @pytest.fixture(scope="class")
    def svc(self, sm):
        return _make(Phonebook, sm)

    def test_all_contacts(self, svc):
        _ok(svc.all_contacts())


# ── PowerManagement ───────────────────────────────────────────────────────────


class TestE2EPowerManagement:
    @pytest.fixture(scope="class")
    def svc(self, sm):
        return _make(PowerManagement, sm)

    def test_profiles(self, svc):
        _ok(svc.profiles())


# ── Scheduler ─────────────────────────────────────────────────────────────────


class TestE2EScheduler:
    @pytest.fixture(scope="class")
    def svc(self, sm):
        return _make(Scheduler, sm)

    def test_complete_schedules(self, svc):
        _ok(svc.complete_schedules())


# ── Security ──────────────────────────────────────────────────────────────────


class TestE2ESecurity:
    @pytest.fixture(scope="class")
    def svc(self, sm):
        return _make(Security, sm)

    def test_gateway_status(self, svc):
        _ok(svc.gateway_status())

    def test_user_exposure_status(self, svc):
        _ok(svc.user_exposure_status())

    def test_package_management_status(self, svc):
        _ok(svc.package_management_status())


# ── SpeedTest ─────────────────────────────────────────────────────────────────


class TestE2ESpeedTest:
    @pytest.fixture(scope="class")
    def svc(self, sm):
        return _make(SpeedTest, sm)

    def test_status(self, svc):
        _ok(svc.status())

    def test_start(self, svc):
        """Trigger a speed test — does not change persistent router configuration."""
        _ok(svc.start())


# ── Static ────────────────────────────────────────────────────────────────────


class TestE2EStatic:
    @pytest.fixture(scope="class")
    def svc(self, sm):
        return _make(Static, sm)

    def test_settings(self, svc):
        _ok(svc.settings())

    @pytest.mark.parametrize("language", ["en", "de", "fr", "it"])
    def test_translations(self, svc, language):
        _ok(svc.translations(language))


# ── Sysbus ────────────────────────────────────────────────────────────────────


class TestE2ESysbus:
    @pytest.fixture(scope="class")
    def svc(self, sm):
        return _make(Sysbus, sm)

    def test_gpio(self, svc):
        _ok(svc.gpio())

    def test_time(self, svc):
        _ok(svc.time())

    def test_mibs(self, svc):
        _ok(svc.mibs())

    def test_veip(self, svc):
        _ok(svc.veip())

    def test_veip_mibs(self, svc):
        _ok(svc.veip_mibs())

    def test_netmaster(self, svc):
        _ok(svc.netmaster())

    def test_multipath_tcp(self, svc):
        _ok(svc.multipath_tcp())

    def test_nemo_has_flag(self, svc):
        _ok(svc.nemo_has_flag())


# ── Temperature ───────────────────────────────────────────────────────────────


class TestE2ETemperature:
    @pytest.fixture(scope="class")
    def svc(self, sm):
        return _make(Temperature, sm)

    def test_sensor(self, svc):
        _ok(svc.sensor())


# ── MST ───────────────────────────────────────────────────────────────────────


class TestE2EMST:
    @pytest.fixture(scope="class")
    def svc(self, sm):
        return _make(MST, sm)

    def test_status(self, svc):
        _ok(svc.status())

    def test_config(self, svc):
        _ok(svc.config("143fa619e252"))

    def test_get(self, svc):
        _ok(svc.get())

    # TODO: figure out valid payloads for MST.set()
    # @pytest.mark.destructive
    # def test_set(self, svc):
    #     """set with empty parameters is effectively a no-op on the router."""
    #     _ok(svc.set())

    def test_stats(self, svc):
        ids = json.loads(svc.get()).get("data", {}).get("ids", [])
        if not ids:
            pytest.skip("No MST entries found on this router")
        _ok(svc.stats(id=ids[0]))


# ── UserManagement ────────────────────────────────────────────────────────────


class TestE2EUserManagement:
    @pytest.fixture(scope="class")
    def svc(self, sm):
        return _make(UserManagement, sm)

    def test_user_log(self, svc):
        _ok(svc.user_log())


# ── Voice ─────────────────────────────────────────────────────────────────────


class TestE2EVoice:
    @pytest.fixture(scope="class")
    def svc(self, sm):
        return _make(Voice, sm)

    def test_status(self, svc):
        _ok(svc.status())

    def test_trunks(self, svc):
        _ok(svc.trunks())

    def test_sip_extensions_status(self, svc):
        _ok(svc.sip_extensions_status())

    def test_groups(self, svc):
        _ok(svc.groups())

    def test_handsets(self, svc):
        _ok(svc.handsets())

    def test_call_list(self, svc):
        _ok(svc.call_list())


# ── VPN ───────────────────────────────────────────────────────────────────────


class TestE2EVPN:
    @pytest.fixture(scope="class")
    def svc(self, sm):
        return _make(VPN, sm)

    def test_status(self, svc):
        _ok(svc.status())

    def test_servers_config(self, svc):
        _ok(svc.servers_config())


# ── WebUI ─────────────────────────────────────────────────────────────────────


class TestE2EWebUI:
    @pytest.fixture(scope="class")
    def svc(self, sm):
        return _make(WebUI, sm)

    def test_status(self, svc):
        _ok(svc.status())

    def test_release_notes(self, svc):
        _ok(svc.release_notes())


# ── Wifi ──────────────────────────────────────────────────────────────────────


class TestE2EWifi:
    @pytest.fixture(scope="class")
    def svc(self, sm):
        return _make(Wifi, sm)

    def test_status(self, svc):
        _ok(svc.status())

    def test_steering(self, svc):
        _ok(svc.steering())

    def test_ssid(self, svc):
        _ok(svc.ssid())

    def test_guest(self, svc):
        _ok(svc.guest())

    @pytest.mark.parametrize("radio_id", [0, 1])
    def test_radio(self, svc, radio_id):
        _ok(svc.radio(radio_id))

    @pytest.mark.parametrize("radio_id", [0, 1])
    def test_spectrum_info(self, svc, radio_id):
        _ok(svc.spectrum_info(radio_id))

    @pytest.mark.parametrize("radio_id", [0, 1])
    def test_scan(self, svc, radio_id):
        _ok(svc.scan(radio_id))

    @pytest.mark.parametrize("radio_id", [0, 1])
    @pytest.mark.destructive
    def test_power_reverts(self, svc, radio_id):
        """Read the current TX power and write the same value back — effective no-op."""
        raw = svc.radio(radio_id)
        try:
            current = int(
                json.loads(raw)
                .get("status", {})
                .get("data", {})
                .get("wlanradio", {})
                .get(f"wifi{radio_id}_bcm", {})
                .get("TransmitPower", 100)
            )
            if current not in (0, 25, 50, 75, 100):
                current = 100
        except Exception:
            current = 100
        _ok(svc.power(radio_id, current))

    @pytest.mark.parametrize("radio_id", [0, 1])
    def test_latest_power(self, svc, radio_id):
        _ok(svc.latest_power(radio_id))

    @pytest.mark.parametrize("radio_id", [0, 1])
    def test_per_antenna_rssi(self, svc, radio_id):
        _ok(svc.per_antenna_rssi(radio_id))

    @pytest.mark.parametrize("radio_id", [0, 1])
    def test_station_stats(self, svc, radio_id):
        _ok(svc.station_stats(radio_id))

    def test_guest_mibs(self, svc):
        _ok(svc.guest_mibs())

    def test_steering_master_config(self, svc):
        _ok(svc.steering_master_config())

    def test_steering_operating_standards(self, svc):
        _ok(svc.steering_operating_standards())

    def test_steering_log(self, svc):
        _ok(svc.steering_log())

    def test_steering_radio(self, svc):
        _ok(svc.steering_radio())

    def test_steering_exception_list(self, svc):
        _ok(svc.steering_exception_list())

    def test_activation_timer(self, svc):
        _ok(svc.activation_timer())


# ── Wireguard ─────────────────────────────────────────────────────────────────


class TestE2EWireguard:
    @pytest.fixture(scope="class")
    def svc(self, sm):
        return _make(Wireguard, sm)

    def test_app_status(self, svc):
        _ok(svc.app_status())

    def test_server_status(self, svc):
        _ok(svc.server_status())

    def test_client_status(self, svc):
        _ok(svc.clients())


# ── WWAN ──────────────────────────────────────────────────────────────────────


class TestE2EWWAN:
    @pytest.fixture(scope="class")
    def svc(self, sm):
        return _make(WWAN, sm)

    def test_status(self, svc):
        _ok(svc.status())

    def test_mibs(self, svc):
        _ok(svc.mibs())

    def test_device(self, svc):
        _ok(svc.device())

    def test_device_results(self, svc):
        _ok(svc.device_results())
