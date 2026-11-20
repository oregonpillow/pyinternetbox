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

Tests that change settings are marked ``@pytest.mark.destructive``. They leave the configuration as they found it:
they write the current value back (LED brightness, Wi-Fi TX power, firewall levels and basic actions, UPnP, WPS, DNS
servers for devices, 6 GHz power saving), or create something temporary and delete it again (a disabled port
forwarding rule, custom firewall rule and DynDNS host and a phone book contact named after ``DUMMY_RULE``, a WireGuard
client, a static route to an unused network, and a device entry, IP address reservation, schedule and time limit for
``FAKE_MAC``, which no real device uses). They skip rather than touch existing settings, e.g. a DMZ host or calls in
the call list.

Tests that interrupt the network for everyone, such as turning Wi-Fi off and on, writing the Wi-Fi names or channels
back or saving a Wi-Fi schedule, are also marked ``@pytest.mark.disruptive`` and only run when ``IB_E2E_DISRUPTIVE=1``
is set.
"""

from __future__ import annotations

import contextlib
import ipaddress
import json
import socket
import time
from urllib.parse import urlsplit

import pytest
import requests

from internetbox_client.resources import *  # noqa: F403
from internetbox_client.utils.APIClient import SessionManager

# ── Configuration ─────────────────────────────────────────────────────────────

# Write tests give this locally administered MAC address, which no real device uses, a device entry, IP address
# reservation, schedule and time limit, and name their port forwarding rule and phone book contact DUMMY_RULE, so
# existing settings are never modified.
FAKE_MAC = "02:00:00:00:00:01"
DUMMY_RULE = "pyinternetbox-e2e"

# ── Shared session fixture ────────────────────────────────────────────────────


@pytest.fixture(scope="session")
def sm():
    """Authenticated :class:`SessionManager` shared across the entire test session.

    Uses its own application name so it doesn't end a web UI session open in a browser.
    """
    with SessionManager(application_name="pyinternetbox-e2e") as session:
        yield session


@pytest.fixture(scope="session")
def fake_mac(sm):
    """FAKE_MAC, after checking that the router has nothing for it. Anything the tests leave for it is removed at the end."""
    if uses := _uses(sm, FAKE_MAC):
        pytest.skip(f"{FAKE_MAC} is in use on this router: {', '.join(uses)}")
    yield FAKE_MAC
    _forget(sm, FAKE_MAC)


@pytest.fixture(scope="session")
def free_ip(sm) -> str:
    """A LAN address outside the DHCP pool that no device, lease, port forwarding rule or DMZ uses."""
    free = _free_addresses(sm)
    if not free:
        pytest.skip("No free LAN address outside the DHCP pool")
    return free[0]


def _free_addresses(sm) -> list[str]:
    """The LAN addresses outside the DHCP pool that no device, lease, port forwarding rule or DMZ uses, highest first."""
    lan = json.loads(_make(NMC, sm).lan_ip())["data"]
    pool = range(int(ipaddress.ip_address(lan["DHCPMinAddress"])), int(ipaddress.ip_address(lan["DHCPMaxAddress"])) + 1)
    used = {lan["Address"]}
    for device in _lan_devices(sm):
        used |= {device.get("IPAddress")} | {address.get("Address") for address in device.get("IPv4Address") or []}
    used |= {lease["IPAddress"] for lease in json.loads(_make(DHCP, sm).static_leases())["status"]}
    firewall = _make(Firewall, sm)
    for rules in (json.loads(firewall.port_forwarding())["status"], json.loads(firewall.dmz())["status"]):
        used |= {rule["DestinationIPAddress"] for rule in rules.values()}
    network = ipaddress.ip_network(f"{lan['Address']}/{lan['Netmask']}", strict=False)
    return [str(host) for host in reversed(list(network.hosts())) if int(host) not in pool and str(host) not in used]


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


def _no_errors(result: str) -> dict:
    """Assert the router accepted a call. It reports errors with HTTP 200 and an "errors" list."""
    data = json.loads(result)
    assert not data.get("errors"), data["errors"]
    return data


def _payload(result: str) -> dict:
    """The settings in a response: some endpoints return them in "status", others in "data"."""
    data = json.loads(result)
    return data.get("status") or data.get("data") or {}


@contextlib.contextmanager
def _skip_if_unavailable():
    """Skip the test if the router doesn't have the object it calls (HTTP 404) or refuses the call even for the admin
    account (HTTP 401). Both depend on the model and firmware.

    Only for endpoints known to vary: a misspelled endpoint also gives HTTP 404.
    """
    try:
        yield
    except requests.HTTPError as exc:
        reasons = {404: "isn't on this router", 401: "is refused even for the admin account on this router"}
        if exc.response is None or exc.response.status_code not in reasons:
            raise
        pytest.skip(f"{urlsplit(exc.response.url).path} {reasons[exc.response.status_code]} (HTTP {exc.response.status_code})")


def _lan_devices(sm) -> list[dict]:
    return json.loads(_make(Devices, sm).get(expression="lan and not self", flags=""))["status"]


def _mst_id(mac: str) -> str:
    return mac.replace(":", "").lower()


def _mst_ids(sm) -> list[str]:
    return (json.loads(_make(MST, sm).get()).get("data") or {}).get("ids", [])


def _has_lease(sm, mac: str) -> bool:
    return any(lease["MACAddress"].upper() == mac for lease in json.loads(_make(DHCP, sm).static_leases())["status"])


def _uses(sm, mac: str) -> list[str]:
    """What the router has for *mac*. An IP address reservation also creates a device entry."""
    checks = {
        "device": lambda: any(device["Key"] == mac for device in _lan_devices(sm)),
        "IP address reservation": lambda: _has_lease(sm, mac),
        "schedule": lambda: json.loads(_make(Scheduler, sm).device_schedule(mac)).get("status"),
        "time limit": lambda: _mst_id(mac) in _mst_ids(sm),
    }
    return [use for use, check in checks.items() if check()]


def _forget(sm, mac: str) -> None:
    """Delete everything the router has for *mac*, in an order that doesn't bring the device entry back."""
    if _has_lease(sm, mac):
        _make(DHCP, sm).delete_static_lease(mac)  # creates the device entry if it's gone
    if any(device["Key"] == mac for device in _lan_devices(sm)):
        _make(Devices, sm).remove(mac)  # also deletes the schedule and time limit
    else:
        _make(Scheduler, sm).remove_device_schedule(mac)
        if _mst_id(mac) in _mst_ids(sm):
            _make(MST, sm).delete(mac)


def _wait_for(condition, timeout: float = 10) -> bool:
    """Poll *condition* until it's true or *timeout* seconds have passed: some changes take a moment to show."""
    deadline = time.monotonic() + timeout
    while not condition():
        if time.monotonic() > deadline:
            return False
        time.sleep(0.25)
    return True


def _port_forwards(firewall) -> dict[str, tuple]:
    """Port forwarding rules by ID, reduced to their settings (their status can change on its own)."""
    rules = json.loads(firewall.port_forwarding())["status"]
    fields = ("Enable", "Protocol", "ExternalPort", "InternalPort", "DestinationIPAddress", "Description")
    return {rule_id: tuple(rule[field] for field in fields) for rule_id, rule in rules.items()}


def _custom_rules(firewall) -> dict[tuple[str, str], tuple]:
    """Custom firewall rules by (chain, ID), reduced to their settings."""
    fields = ("Enable", "Target", "Protocol", "DestinationPort", "SourceMACAddress", "DestinationMACAddress", "Description")
    return {(chain, rule_id): tuple(rule.get(field) for field in fields) for chain, rule_id, rule in firewall._custom_rules()}


def _dyndns_hosts(dyndns) -> list[tuple]:
    """DynDNS hosts, without their password (kept out of assertion messages) and status (it changes on its own)."""
    return sorted((host["service"], host["hostname"], host["username"], host["enable"]) for host in json.loads(dyndns.hosts())["status"])


def _wireguard_server(wireguard) -> dict[str, dict]:
    """The WireGuard server's settings, without its status (it can change on its own, e.g. after it was turned off)."""
    servers = json.loads(wireguard.server_status())["status"]
    return {key: {name: value for name, value in server.items() if name != "Status"} for key, server in servers.items()}


def _wireguard_clients(wireguard) -> dict[str, tuple]:
    """WireGuard clients by name, reduced to their settings."""
    fields = ("Enable", "IntranetAccess", "PublicKey", "PrivateIPAddress", "ExtraData")
    return {name: tuple(client.get(field) for field in fields) for name, client in wireguard._clients().items()}


def _runner_is_wired(sm) -> bool:
    """Whether this machine reaches the router through an Ethernet port, not Wi-Fi (incl. a mesh extender's)."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
        probe.connect((urlsplit(sm.base_url).hostname, 443))
        local_ip = probe.getsockname()[0]
    me = next((device for device in _lan_devices(sm) if device.get("IPAddress") == local_ip), None)
    return bool(me) and me.get("InterfaceName", "").lower().startswith("eth") and "wifi" not in (me.get("Tags") or "").split()


def _wifi_networks(wifi) -> tuple[dict, dict]:
    """What set_network() and set_guest_network() can change: the access points' and the mesh networks' settings."""
    main, guest = wifi._access_points()
    access_points = {
        name: (ap["SSID"], ap.get("SSIDAdvertisementEnabled"), ap["Security"]["KeyPassPhrase"], ap["Security"]["ModeEnabled"])
        for name, ap in {**main, **guest}.items()
    }
    mesh = {
        name: (entry["SSID"], entry["SSIDAdvertisementEnabled"], entry.get("PassPhrase"), entry["PersistentEnable"])
        for name, entry in json.loads(wifi.ssid())["status"].items()
    }
    return access_points, mesh


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

    def test_ringtone(self, svc):
        with _skip_if_unavailable():
            _ok(svc.ringtone())


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

    def test_summary(self, svc, sm):
        summary = {device["mac"]: device for device in json.loads(svc.summary())}
        devices = {device["Key"]: device for device in _lan_devices(sm)}
        assert summary.keys() == devices.keys()
        for mac, device in devices.items():
            assert (summary[mac]["name"], summary[mac]["ip"]) == (device.get("Name"), device.get("IPAddress") or None)
        # Devices can connect or leave between the two calls, but this computer stays connected.
        assert any(device["connected"] and device["connection"] for device in summary.values())

    def test_network_xt(self, svc):
        _ok(svc.network_xt())

    def test_memory_status(self, svc):
        _ok(svc.memory_status())

    @pytest.mark.destructive
    def test_rename_remove(self, svc, sm, fake_mac, free_ip):
        """Give FAKE_MAC a device entry (the router creates one for an IP address reservation), rename it, remove it."""

        def device() -> dict | None:
            return next((d for d in _lan_devices(sm) if d["Key"] == fake_mac), None)

        try:
            _no_errors(_make(DHCP, sm).add_static_lease(fake_mac, free_ip))
            assert _wait_for(lambda: device() is not None)
            _no_errors(svc.rename(fake_mac, "pyinternetbox-e2e"))
            assert _wait_for(lambda: device()["Name"] == "pyinternetbox-e2e")
            _no_errors(svc.remove(fake_mac))
            assert device() is None
        finally:
            _forget(sm, fake_mac)
        assert _uses(sm, fake_mac) == []

    @pytest.mark.destructive
    def test_wake_on_lan(self, svc, fake_mac):
        _no_errors(svc.wake_on_lan(fake_mac))

    @pytest.mark.destructive
    def test_block_unblock(self, svc, sm, fake_mac):
        """Block and unblock a device that doesn't exist, then remove the schedule and time limit that created."""
        scheduler, mst = _make(Scheduler, sm), _make(MST, sm)
        try:
            info = _no_errors(svc.block(fake_mac))["data"]["scheduleInfo"]
            assert (info["enable"], info["value"], info["schedule"]) == (True, "Disable", [{"state": "Disable", "begin": 0, "end": 604800}])
            assert json.loads(mst.config(_mst_id(fake_mac)))["data"]["enable"] is True
            info = _no_errors(svc.unblock(fake_mac))["data"]["scheduleInfo"]
            assert (info["enable"], info["value"]) == (False, "Enable")
            assert json.loads(mst.config(_mst_id(fake_mac)))["data"]["enable"] is False
        finally:
            if json.loads(scheduler.device_schedule(fake_mac)).get("status"):
                scheduler.remove_device_schedule(fake_mac)
            if _mst_id(fake_mac) in _mst_ids(sm):
                mst.delete(fake_mac)
        assert json.loads(scheduler.device_schedule(fake_mac))["status"] is False
        assert _mst_id(fake_mac) not in _mst_ids(sm)

    @pytest.mark.destructive
    def test_unblock_without_parental_controls_creates_nothing(self, svc, sm, fake_mac):
        assert json.loads(svc.unblock(fake_mac))["status"] is False
        assert _mst_id(fake_mac) not in _mst_ids(sm)


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

    @pytest.mark.destructive
    def test_static_lease_add_delete(self, svc, sm, fake_mac, free_ip):
        def leases() -> dict[str, str]:
            return {lease["MACAddress"].upper(): lease["IPAddress"] for lease in json.loads(svc.static_leases())["status"]}

        try:
            _no_errors(svc.add_static_lease(fake_mac, free_ip))
            assert leases()[fake_mac] == free_ip
            _no_errors(svc.delete_static_lease(fake_mac))
            assert fake_mac not in leases()
        finally:
            _forget(sm, fake_mac)  # also the device entry the router created for the reservation
        assert _uses(sm, fake_mac) == []


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

    @pytest.mark.destructive
    def test_set_device_servers_reverts(self, svc):
        """Write the DNS servers devices get back: effective no-op."""

        def servers():
            return [
                [ipaddress.ip_address(server) for server in json.loads(raw)["status"]["DNSServers"].split(",") if server]
                for raw in (svc.user(), svc.user_ipv6())
            ]

        v4, v6 = servers()
        assert _no_errors(svc.set_device_servers([str(server) for server in v4]))["status"] is True
        assert _no_errors(svc.set_device_servers_ipv6([str(server) for server in v6]))["status"] is True
        assert servers() == [v4, v6]

    @pytest.mark.destructive
    def test_flush_cache(self, svc):
        _no_errors(svc.flush_cache())


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

    @pytest.mark.destructive
    def test_host_add_update_delete(self, svc):
        """Add a dummy host that the router doesn't keep up to date, replace it and delete it. Swisscom's host stays.

        Skipped if there's another host: the web UI only shows one besides Swisscom's.
        """
        before = _dyndns_hosts(svc)
        if any(service.lower() != "swisscom" for service, *_ in before):
            pytest.skip("A DynDNS host besides Swisscom's is set; not touching it")
        hostname = f"{DUMMY_RULE}.example.com"
        try:
            assert _no_errors(svc.set_host("dyndns", hostname, "pyinternetbox", "not-a-real-password", enable=False))["status"] is True
            assert (set(_dyndns_hosts(svc)) - set(before)) == {("dyndns", hostname, "pyinternetbox", False)}
            # Another account for the same service: replaced, not added.
            _no_errors(svc.set_host("dyndns", hostname, "pyinternetbox-2", "not-a-real-password", enable=False))
            assert (set(_dyndns_hosts(svc)) - set(before)) == {("dyndns", hostname, "pyinternetbox-2", False)}
            _no_errors(svc.delete_host(hostname))
        finally:
            for host in set(_dyndns_hosts(svc)) - set(before):
                svc.delete_host(host[1])
        assert _dyndns_hosts(svc) == before


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

    def test_custom_rules(self, svc):
        rules = json.loads(svc.custom_rules())
        assert {(rule["chain"], rule["id"]) for rule in rules} == set(_custom_rules(svc))
        assert {rule["action"] for rule in rules} <= {"allow", "block"}

    def test_custom_policy(self, svc):
        policy = json.loads(svc.custom_policy())
        assert set(policy) == {"ipv4", "ipv6_outbound", "ipv6_inbound"}
        assert set(policy.values()) <= {"allow", "block"}

    @pytest.mark.destructive
    def test_custom_rule_add_update_move_delete(self, svc, fake_mac):
        """Add a disabled dummy rule for FAKE_MAC, change it, move it to IPv6, turn it on and off and delete it.

        Custom rules only apply at the Custom firewall level, and this one only to a device that doesn't exist.
        """
        before = _custom_rules(svc)
        assert DUMMY_RULE not in {rule[-1] for rule in before.values()}

        def dummy() -> list[tuple]:
            """The dummy rules' chain and settings."""
            return [(chain, *rule) for (chain, _), rule in _custom_rules(svc).items() if rule[-1] == DUMMY_RULE]

        try:
            created = _no_errors(svc.set_custom_rule(DUMMY_RULE, "65001", "block", protocol="tcp", device=fake_mac, enabled=False))
            assert ("Custom", created["status"]) in _custom_rules(svc)
            assert dummy() == [("Custom", False, "Drop", "6", "65001", fake_mac, "", DUMMY_RULE)]
            # For all devices now: the router would keep the device if the rule weren't replaced.
            _no_errors(svc.set_custom_rule(DUMMY_RULE, "65001-65002", "allow", enabled=False))
            assert dummy() == [("Custom", False, "Accept", "6,17", "65001-65002", "", "", DUMMY_RULE)]
            # Inbound IPv6: another chain, with the device as the destination.
            _no_errors(svc.set_custom_rule(DUMMY_RULE, "65001", "block", ip_version=6, direction="inbound", device=fake_mac, enabled=False))
            moved = [("Custom_V6In", False, "Drop", "6,17", "65001", "", fake_mac, DUMMY_RULE)]
            assert dummy() == moved
            _no_errors(svc.enable_custom_rule(DUMMY_RULE))
            assert dummy() == [("Custom_V6In", True, *moved[0][2:])]
            _no_errors(svc.enable_custom_rule(DUMMY_RULE, False))
            assert dummy() == moved
            _no_errors(svc.delete_custom_rule(DUMMY_RULE))
        finally:
            for _ in range(3):
                if dummy():
                    svc.delete_custom_rule(DUMMY_RULE)
        assert _custom_rules(svc) == before

    @pytest.mark.destructive
    def test_set_custom_policy_reverts(self, svc):
        """Write the basic actions of the custom firewall back: effective no-op."""
        chains = {
            "ipv4": (4, "outbound", "Custom"),
            "ipv6_outbound": (6, "outbound", "Custom_V6Out"),
            "ipv6_inbound": (6, "inbound", "Custom_V6In"),
        }
        raw = {key: svc.post("/sysbus/Firewall:getChainPolicy", {"parameters": {"chain": chain}}) for key, (_, _, chain) in chains.items()}
        before = json.loads(svc.custom_policy())
        for key, (ip_version, direction, _) in chains.items():
            if json.loads(raw[key])["status"] in ("Accept", "Drop"):  # a chain without a policy keeps none
                _no_errors(svc.set_custom_policy(before[key], ip_version, direction))
        assert json.loads(svc.custom_policy()) == before
        assert {
            key: svc.post("/sysbus/Firewall:getChainPolicy", {"parameters": {"chain": chain}}) for key, (_, _, chain) in chains.items()
        } == raw

    def test_level(self, svc):
        _ok(svc.level())

    @pytest.mark.destructive
    def test_set_levels_reverts(self, svc):
        """Write the current firewall levels back: effective no-op."""
        v4, v6 = json.loads(svc.level())["status"], json.loads(svc.ipv6_level())["status"]
        assert _no_errors(svc.set_level(v4))["status"] is True
        assert _no_errors(svc.set_ipv6_level(v6))["status"] is True
        assert (json.loads(svc.level())["status"], json.loads(svc.ipv6_level())["status"]) == (v4, v6)

    @pytest.mark.destructive
    def test_port_forwarding_add_update_delete(self, svc, free_ip):
        """Add a disabled dummy rule, change it and delete it, leaving the other rules untouched."""
        rule_id = f"webui_{DUMMY_RULE}"
        before = _port_forwards(svc)
        assert rule_id not in before
        try:
            created = _no_errors(svc.set_port_forwarding(DUMMY_RULE, free_ip, "65001", protocol="tcp", enabled=False))
            assert created["status"] == rule_id
            assert _port_forwards(svc)[rule_id] == (False, "6", "65001", "65001", free_ip, DUMMY_RULE)
            _no_errors(svc.set_port_forwarding(DUMMY_RULE, free_ip, "65001-65002", "65011", enabled=False))
            assert _port_forwards(svc)[rule_id][:4] == (False, "6,17", "65001-65002", "65011")
            _no_errors(svc.delete_port_forwarding(DUMMY_RULE))
        finally:
            if rule_id in _port_forwards(svc):
                svc.delete_port_forwarding(rule_id)
        assert _port_forwards(svc) == before

    @pytest.mark.destructive
    def test_dmz_set_delete(self, svc, free_ip):
        """Point the DMZ at an unused address, then remove it. Skipped if a DMZ host is already set."""
        if json.loads(svc.dmz())["status"]:
            pytest.skip("A DMZ host is set; not touching it")
        try:
            assert _no_errors(svc.set_dmz(free_ip))["status"] == "webui"
            assert json.loads(svc.dmz())["status"]["webui"]["DestinationIPAddress"] == free_ip
        finally:
            svc.delete_dmz()
        assert json.loads(svc.dmz())["status"] == {}

    def test_status(self, svc):
        _ok(svc.status())

    @pytest.mark.destructive
    def test_set_upnp_enabled_reverts(self, svc):
        """Write the current UPnP setting back: effective no-op."""
        enabled = _payload(svc.status())["UpnpPortForwardingEnable"]
        assert _no_errors(svc.set_upnp_enabled(enabled))["status"] is True
        assert _payload(svc.status())["UpnpPortForwardingEnable"] is enabled


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

    @pytest.mark.destructive
    def test_static_route_add_update_delete(self, svc, sm, free_ip):
        """Route an unused private network to unused LAN addresses, change its gateway and delete it."""
        destination, network = "172.31.254.0/24", ipaddress.ip_network("172.31.254.0/24")
        before, forwards = json.loads(svc.static_routes())["status"], _port_forwards(_make(Firewall, sm))
        if any(network.overlaps(ipaddress.ip_network(f"{route['Dst']}/{route['DstLen']}", strict=False)) for route in before.values()):
            pytest.skip(f"A static route overlaps {destination}; not touching it")
        gateways = [free_ip, *(address for address in _free_addresses(sm) if address != free_ip)][:2]
        if len(gateways) < 2:
            pytest.skip("Fewer than two free LAN addresses outside the DHCP pool")

        def added() -> dict[str, tuple]:
            routes = json.loads(svc.static_routes())["status"]
            return {
                name: (route["Dst"], route["DstLen"], route["Gateway"], route["Enable"])
                for name, route in routes.items()
                if name not in before
            }

        try:
            _no_errors(svc.set_static_route(destination, gateways[0]))
            ((name, route),) = added().items()
            assert route == ("172.31.254.0", 24, gateways[0], True)
            _no_errors(svc.set_static_route(destination, gateways[1]))
            assert added() == {name: ("172.31.254.0", 24, gateways[1], True)}
            _no_errors(svc.delete_static_route(destination))
        finally:
            for name in added():
                svc.delete_static_route(name)
        assert json.loads(svc.static_routes())["status"].keys() == before.keys()
        assert _port_forwards(_make(Firewall, sm)) == forwards

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

    @pytest.mark.destructive
    def test_contact_add_modify_delete(self, svc):
        """Add a contact named DUMMY_RULE, change it and delete it, leaving the other contacts untouched."""

        def contacts():
            return sorted(json.dumps(contact, sort_keys=True) for contact in json.loads(svc.all_contacts())["status"])

        before = contacts()
        if any(f'"formattedName": "{DUMMY_RULE}' in contact for contact in before):
            pytest.skip(f"A contact named {DUMMY_RULE} exists")
        home = {"name": "0000000000", "type": "HOME", "preferred": False}
        contact = {"name": f"N:{DUMMY_RULE}", "formattedName": DUMMY_RULE, "title": "e2e", "telephoneNumbers": [home]}
        contact_id = _no_errors(svc.add_contact(contact))["status"]
        try:
            cell = {"name": "0000000001", "type": "CELL", "preferred": False}
            changes = {"formattedName": f"{DUMMY_RULE} 2", "telephoneNumbers": [cell]}
            assert _no_errors(svc.modify_contact(contact_id, changes))["status"] is True
            stored = json.loads(svc.get_contact(contact_id))["status"]
            assert (stored["formattedName"], stored["title"]) == (f"{DUMMY_RULE} 2", "e2e")  # fields left out stay
            assert [(number["name"], number["type"]) for number in stored["telephoneNumbers"]] == [("0000000001", "CELL")]
            assert _no_errors(svc.delete_contact(contact_id))["status"] is True
        finally:
            if json.loads(svc.get_contact(contact_id))["status"]:
                svc.delete_contact(contact_id)
        assert json.loads(svc.delete_contact(contact_id))["status"] is False
        assert json.loads(svc.modify_contact(contact_id, {"formattedName": DUMMY_RULE}))["status"] is False
        assert contacts() == before


# ── PowerManagement ───────────────────────────────────────────────────────────


class TestE2EPowerManagement:
    @pytest.fixture(scope="class")
    def svc(self, sm):
        return _make(PowerManagement, sm)

    def test_profiles(self, svc):
        _ok(svc.profiles())

    @pytest.mark.destructive
    def test_set_wifi_6ghz_power_saving_reverts(self, svc):
        """Write the 6 GHz power saving setting back: effective no-op."""
        profile = json.loads(svc.profiles())["status"].get("ECO_6G_SCS")
        if not profile:
            pytest.skip("This router has no 6 GHz power saving")
        _no_errors(svc.set_wifi_6ghz_power_saving(profile["Activate"]))
        assert json.loads(svc.profiles())["status"]["ECO_6G_SCS"]["Activate"] is profile["Activate"]


# ── Scheduler ─────────────────────────────────────────────────────────────────


class TestE2EScheduler:
    @pytest.fixture(scope="class")
    def svc(self, sm):
        return _make(Scheduler, sm)

    def test_complete_schedules(self, svc):
        _ok(svc.complete_schedules())

    @pytest.mark.destructive
    def test_device_schedule_set_enable_remove(self, svc, fake_mac):
        periods = [{"begin": "Sun 22:00", "end": "Mon 07:00"}, {"begin": "Wed 12:00", "end": "Wed 13:30"}]
        try:
            _no_errors(svc.set_device_schedule(fake_mac, periods, enable=False))
            info = json.loads(svc.device_schedule(fake_mac))["data"]["scheduleInfo"]
            assert info["enable"] is False
            assert [(p["begin"], p["end"]) for p in info["schedule"]] == [(0, 25200), (216000, 221400), (597600, 604800)]
            _no_errors(svc.enable_device_schedule(fake_mac))
            assert json.loads(svc.device_schedule(fake_mac))["data"]["scheduleInfo"]["enable"] is True
        finally:
            if json.loads(svc.device_schedule(fake_mac)).get("status"):
                svc.remove_device_schedule(fake_mac)
        assert json.loads(svc.device_schedule(fake_mac))["status"] is False

    def test_wifi_schedule(self, svc):
        _ok(svc.wifi_schedule())

    @pytest.mark.destructive
    @pytest.mark.disruptive
    def test_wifi_schedule_set_enable_remove(self, svc):
        """Create a Wi-Fi schedule with one off minute half a week from now, turn it on and off, and delete it.

        Wi-Fi stays on, but the router may restart it while saving. Skipped if there's a Wi-Fi schedule.
        """
        if json.loads(svc.wifi_schedule())["status"]:
            pytest.skip("A Wi-Fi schedule is set; not touching it")
        week, now = 7 * 86400, time.localtime()
        begin = (now.tm_wday * 86400 + now.tm_hour * 3600 + now.tm_min * 60 + week // 2) % week  # seconds since Monday 00:00

        def info() -> dict:
            return json.loads(svc.wifi_schedule())["data"]["scheduleInfo"]

        try:
            _no_errors(svc.set_wifi_schedule([{"begin": begin, "end": begin + 60}], enable=False))
            assert (info()["enable"], [(p["begin"], p["end"], p["state"]) for p in info()["schedule"]]) == (
                False,
                [(begin, begin + 60, "Disable")],
            )
            _no_errors(svc.enable_wifi_schedule())
            assert info()["enable"] is True
            _no_errors(svc.enable_wifi_schedule(False))
            assert info()["enable"] is False
            assert len(info()["schedule"]) == 1
        finally:
            if json.loads(svc.wifi_schedule()).get("status"):
                svc.remove_wifi_schedule()
        assert json.loads(svc.wifi_schedule())["status"] is False


# ── Security ──────────────────────────────────────────────────────────────────


class TestE2ESecurity:
    @pytest.fixture(scope="class")
    def svc(self, sm):
        return _make(Security, sm)

    def test_home_security_status(self, svc):
        assert "PackageStatus" in _payload(svc.home_security_status())

    def test_user_exposure_status(self, svc):
        with _skip_if_unavailable():
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
        ids = json.loads(svc.get()).get("data", {}).get("ids", [])
        if not ids:
            pytest.skip("No MST entries found on this router")
        _ok(svc.config(ids[0]))

    def test_get(self, svc):
        _ok(svc.get())

    @pytest.mark.destructive
    def test_set_delete(self, svc, sm, fake_mac):
        try:
            _no_errors(svc.set(fake_mac, enable=False, minutes_per_day=90))
            _no_errors(svc.set(fake_mac, enable=False, allowed_time={"Saturday": 240}))
            data = json.loads(svc.config(_mst_id(fake_mac)))["data"]
            assert data["enable"] is False
            assert data["allowedTime"] == {"Mon": 90, "Tue": 90, "Wed": 90, "Thu": 90, "Fri": 90, "Sat": 240, "Sun": 90}
            _no_errors(svc.delete(fake_mac))
        finally:
            if _mst_id(fake_mac) in _mst_ids(sm):
                svc.delete(fake_mac)
        assert _mst_id(fake_mac) not in _mst_ids(sm)

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

    @pytest.mark.destructive
    def test_clear_empty_call_list(self, svc):
        """Clear the call list while it's empty: no-op. Skipped if it has calls."""
        if json.loads(svc.call_list())["status"]:
            pytest.skip("The call list has calls; not deleting them")
        with pytest.raises(requests.HTTPError):  # no call has this ID
            svc.delete_call("0")
        _no_errors(svc.clear_call_list())
        assert json.loads(svc.call_list())["status"] == []


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
        with _skip_if_unavailable():
            _ok(svc.release_notes())


# ── Wifi ──────────────────────────────────────────────────────────────────────


class TestE2EWifi:
    @pytest.fixture(scope="class")
    def svc(self, sm):
        return _make(Wifi, sm)

    def test_status(self, svc):
        _ok(svc.status())

    def test_summary(self, svc):
        summary = json.loads(svc.summary())
        access_points, _ = _wifi_networks(svc)
        assert sorted((n["ssid"], n["visible"], n["password"], n["encryption"]) for n in summary["networks"]) == sorted(
            access_points.values()
        )
        assert {n["band"] for n in summary["networks"]} <= {"2.4GHz", "5GHz", "6GHz"}
        assert all(isinstance(n["channel"], int) and isinstance(n["connected_devices"], int) for n in summary["networks"])
        assert summary["wps"] == _payload(svc.status())["WPSEnable"]

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

    @pytest.mark.destructive
    def test_set_guest_enabled_noop(self, svc):
        """Turn the guest network off while it's off: no-op. Skipped if it's on."""
        if _payload(svc.guest())["Enable"]:
            pytest.skip("Guest Wi-Fi is on; not touching it")
        _no_errors(svc.set_guest_enabled(False))
        assert _payload(svc.guest())["Enable"] is False

    @pytest.mark.destructive
    @pytest.mark.disruptive
    def test_guest_on_off(self, svc):
        """Turn the guest network on with a 1-hour timer, then off again. Skipped if it's on."""
        if _payload(svc.guest())["Enable"]:
            pytest.skip("Guest Wi-Fi is on; not touching it")
        timer = json.loads(svc.activation_timer())["status"]
        try:
            _no_errors(svc.set_guest_enabled(True, hours=1))
            assert _payload(svc.guest())["Enable"] is True
            assert json.loads(svc.activation_timer())["status"] != timer
        finally:
            svc.set_guest_enabled(False)
            if json.loads(svc.activation_timer())["status"] != timer:
                svc.post("/sysbus/NMC/WlanTimer:setActivationTimer", {"parameters": {"InterfaceName": "guest", "Timeout": timer}})
        assert _payload(svc.guest())["Enable"] is False
        assert json.loads(svc.activation_timer())["status"] == timer

    @pytest.mark.destructive
    @pytest.mark.disruptive
    def test_set_enabled_off_on(self, svc, sm):
        """Turn all Wi-Fi off, then on again: wireless devices lose their connection meanwhile.

        The guest network stays off afterwards, so it's turned back on if it was on.
        """
        if not _runner_is_wired(sm):
            pytest.skip("This machine isn't wired to the router, so it couldn't turn Wi-Fi back on")
        if not _payload(svc.status())["Enable"]:
            pytest.skip("Wi-Fi is off; not touching it")
        guest_on = _payload(svc.guest())["Enable"]
        if guest_on and json.loads(svc.activation_timer())["status"]:
            pytest.skip("Guest Wi-Fi is on with a timer, which this test couldn't restore")
        try:
            _no_errors(svc.set_enabled(False))
            assert _payload(svc.status())["Enable"] is False
        finally:
            svc.set_enabled(True)
            if guest_on:
                svc.set_guest_enabled(True)
        assert _payload(svc.status())["Enable"] is True
        assert _payload(svc.guest())["Enable"] is guest_on

    @pytest.mark.destructive
    def test_set_wps_enabled_reverts(self, svc):
        """Write the current WPS setting back: effective no-op."""
        enabled = _payload(svc.status())["WPSEnable"]
        _no_errors(svc.set_wps_enabled(enabled))
        assert _payload(svc.status())["WPSEnable"] is enabled

    @pytest.mark.destructive
    def test_wps_pairing_start_stop(self, svc):
        """Start WPS pairing and stop it straight away. Skipped if WPS is off."""
        if not _payload(svc.status())["WPSEnable"]:
            pytest.skip("WPS is off; not turning it on")
        try:
            _no_errors(svc.start_wps_pairing())
        finally:
            _no_errors(svc.stop_wps_pairing())

    @pytest.mark.destructive
    @pytest.mark.disruptive
    def test_set_network_reverts(self, svc, sm):
        """Write each band's name and visibility back: wireless devices reconnect meanwhile."""
        if not _runner_is_wired(sm):
            pytest.skip("This machine isn't wired to the router, so it would lose its connection")
        before = _wifi_networks(svc)
        main, _ = svc._access_points()
        if _payload(svc.status()).get("ConfigurationMode"):
            changes = [{"band": None, **next(iter(main.values()))}]
        else:
            changes = [{**ap, "band": ap["Band"]} for ap in main.values() if ap["Band"] in ("2.4GHz", "5GHz")]
        for ap in changes:
            _no_errors(svc.set_network(ssid=ap["SSID"], visible=ap["SSIDAdvertisementEnabled"], band=ap["band"]))
        assert _wifi_networks(svc) == before

    @pytest.mark.destructive
    @pytest.mark.disruptive
    def test_set_guest_network_reverts(self, svc):
        """Write the guest network's name back: its devices reconnect meanwhile. It stays on or off."""
        _, guest = svc._access_points()
        if len({ap["SSID"] for ap in guest.values()}) != 1:
            pytest.skip("No guest network, or one with a different name per band")
        before, guest_on = _wifi_networks(svc), _payload(svc.guest())["Enable"]
        _no_errors(svc.set_guest_network(ssid=next(iter(guest.values()))["SSID"]))
        assert (_wifi_networks(svc), _payload(svc.guest())["Enable"]) == (before, guest_on)

    @pytest.mark.parametrize("band", ["2.4GHz", "5GHz"])
    @pytest.mark.destructive
    @pytest.mark.disruptive
    def test_set_channel_reverts(self, svc, sm, band):
        """Write the band's channel setting back: its devices may reconnect, and the router may search for a channel."""
        if not _runner_is_wired(sm):
            pytest.skip("This machine isn't wired to the router, so it could lose its connection")
        _, _, radio = svc._radio(band)
        auto, bandwidth = radio["AutoChannelEnable"], radio.get("OperatingChannelBandwidth")
        offered = {"2.4GHz": ("20MHz", "40MHz"), "5GHz": ("80MHz", "Auto")}[band]  # other widths are kept as they are
        _no_errors(svc.set_channel(band, "auto" if auto else radio["Channel"], bandwidth if bandwidth in offered else None))
        _, _, after = svc._radio(band)
        assert (after["AutoChannelEnable"], after.get("OperatingChannelBandwidth")) == (auto, bandwidth)
        if not auto:
            assert after["Channel"] == radio["Channel"]

    @pytest.mark.parametrize("band", ["2.4GHz", "5GHz"])
    @pytest.mark.destructive
    @pytest.mark.disruptive
    def test_search_channel(self, svc, sm, band):
        """Let the router choose the band's channel again: if it picks another one, its devices reconnect."""
        if not _runner_is_wired(sm):
            pytest.skip("This machine isn't wired to the router, so it could lose its connection")
        if not svc._radio(band)[2]["AutoChannelEnable"]:
            pytest.skip(f"The {band} channel is set by hand; not changing that")
        _no_errors(svc.search_channel(band))
        assert svc._radio(band)[2]["AutoChannelEnable"] is True


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

    @pytest.mark.destructive
    def test_client_add_set_delete(self, svc, sm):
        """Add a dummy client, change it and delete it, leaving the other clients untouched. The server stays as it is."""
        with _skip_if_unavailable():
            before = _wireguard_clients(svc)
        if not any(app.get("Enable") for app in json.loads(svc.app_status())["status"].values()):
            pytest.skip("WireGuard isn't available on this router")
        name, endpoint = "pyiboxe2e", f"{DUMMY_RULE}.example.com"
        assert name not in before
        server = _wireguard_server(svc)
        lan_ip = json.loads(_make(NMC, sm).lan_ip())["data"]["Address"]
        try:
            config = json.loads(svc.add_client(name, endpoint=endpoint, intranet_access=False))["status"]
            # Without printing the configuration: it contains the client's private key.
            has_keys = "[Interface]" in config and "PrivateKey = " in config and "[Peer]" in config
            has_endpoint = f"Endpoint = {endpoint}:" in config
            assert has_keys
            assert has_endpoint
            client = _wireguard_clients(svc)[name]
            assert (client[0], client[1], client[4]) == (True, False, f"{endpoint};{lan_ip}")
            _no_errors(svc.set_client(name, enabled=False, intranet_access=True))
            assert _wireguard_clients(svc)[name][:2] == (False, True)
            _no_errors(svc.delete_client(name))
        finally:
            if name in _wireguard_clients(svc):
                svc.delete_client(name)
        assert _wireguard_clients(svc) == before
        assert _wireguard_server(svc) == server

    @pytest.mark.destructive
    @pytest.mark.disruptive
    def test_set_server_enabled_on_off(self, svc):
        """Turn the WireGuard server on, then off again: meanwhile it accepts VPN connections. Skipped if it's on."""

        def enabled() -> bool:
            return any(server.get("Enable") for server in json.loads(svc.server_status())["status"].values())

        if enabled():
            pytest.skip("The WireGuard server is on; turning it off would disconnect VPN clients")
        try:
            _no_errors(svc.set_server_enabled(True))
            assert enabled() is True
        finally:
            svc.set_server_enabled(False)
        assert enabled() is False


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


# ── MCP server ────────────────────────────────────────────────────────────────


class TestE2EMCP:
    """The MCP server's read tools, through an in-process MCP client. Needs the mcp extra."""

    @pytest.fixture(scope="class")
    def server(self, sm):
        from unittest.mock import patch

        from internetbox_client import InternetBoxClient

        server_module = pytest.importorskip("internetbox_client.mcp_server.server")
        with patch("internetbox_client.client.SessionManager", return_value=sm):
            client = InternetBoxClient()
        return server_module.build_server(client)

    @staticmethod
    def _call(server, tool: str, arguments: dict | None = None) -> str:
        import asyncio

        from mcp import Client

        async def main():
            async with Client(server, mode="legacy") as client:
                return await client.call_tool(tool, arguments or {})

        result = asyncio.run(main())
        assert not result.is_error, result.content[0].text
        return result.content[0].text

    @pytest.mark.parametrize(
        "tool",
        [
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
        ],
    )
    def test_read_tools(self, server, tool):
        answer = json.loads(self._call(server, tool))
        if isinstance(answer, dict):
            assert [part for part, value in answer.items() if isinstance(value, dict) and "error" in value] == []

    def test_passwords_are_hidden(self, server, sm):
        passwords = {network["password"] for network in json.loads(Wifi(session_manager=sm).summary())["networks"] if network["password"]}
        answer = self._call(server, "wifi_overview")
        assert passwords and not any(password in answer for password in passwords)
        assert '"password":"<hidden>"' in answer

    def test_call_router_function(self, server):
        assert json.loads(self._call(server, "call_router_function", {"function": "wifi.radio", "arguments": {"id": 0}}))["status"]
