# Changelog

What's new in each release of pyinternetbox. The newest release comes first. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- **Wi-Fi**: turn band steering on or off (`wifi.set_steering_enabled()`), leave a device out of band steering or keep it on the router or a WLAN-Box (`wifi.set_device_steering()`), choose the newest Wi-Fi standard each band offers, e.g. Wi-Fi 6 instead of 7 (`wifi.set_standard()`), and whether WLAN-Boxes turn their Wi-Fi on and off with the router's (`wifi.set_wlan_box_sync()`).
- **DNS**: set the DNS servers the router itself asks, e.g. a Pi-hole, or go back to the internet provider's (`dns.set_upstream_servers()`), turn the DNS cache on or off (`dns.set_cache_enabled()`), and count the DNS queries the router answered (`dns.metrics()`).
- **Fixed IP addresses**: also on the guest Wi-Fi, with `pool="guest"` for `dhcp.static_leases()`, `add_static_lease()` and `delete_static_lease()` (`--pool guest` in the CLI). `dhcp.ipv6_server_status()` tells whether the DHCPv6 server runs.
- **Devices**: set a device's type, which picks its icon (`devices.set_type()`, with the web interface's types in `DEVICE_TYPES`), give it a different name in the router's DNS than the one the web interface shows (`devices.set_dns_name()`, `remove_dns_name()`), go back to the name it was found with (`devices.reset_name()`), set every device's traffic counters to 0 (`devices.reset_traffic_counters()`) and delete a Wi-Fi device's recent traffic readings, which the web interface draws its graphs from (`devices.clear_traffic_history()`).
- **Parental controls**: allow or block a device's internet access now, whatever its schedule says, e.g. for one more evening (`scheduler.override_device_schedule()`). The override lasts until it's set back to `"schedule"`, or with `until_next_change=True` until the schedule next switches the other way.
- **Firewall**: whether the router answers pings from the internet (`firewall.respond_to_ping()`, `set_respond_to_ping()`), forwarding whole IP protocols such as GRE to a device (`firewall.protocol_forwarding()`, `set_protocol_forwarding()`, `delete_protocol_forwarding()`), IPv6 pinholes (`firewall.ipv6_pinholes()`, `set_ipv6_pinhole()`, `delete_ipv6_pinhole()`), deleting all port forwarding rules at once (`firewall.delete_all_port_forwarding()`), and how the router presents itself to devices over UPnP (`firewall.upnp_description()`).
- **Remote access**: turn DynDNS on or off for all hosts at once (`dyndns.set_enabled()`), and WireGuard as a whole, which the web interface can't (`wireguard.set_enabled()`). Like the web interface, `wireguard.set_server_enabled(True)` and `add_client()` create the VPN server first on a router that doesn't have one yet.
- **Troubleshooting**: save a log file for technical support and a Wi-Fi debug snapshot on the router (`debug.save_log_file()`, `debug.save_wifi_logs()`).
- **Exporter**: DNS query counts since the router last booted: how many queries the router answered itself or passed on, and per DNS server how many it sent, failed or retried (`internetbox_dns_*_total`). See "DNS query metrics" in the README.
- **CLI**: turning band steering on, changing a Wi-Fi standard or the router's DNS servers, deleting all port forwarding rules, resetting the traffic counters and turning WireGuard off ask for confirmation first, and so does the MCP server.
- **MCP server**: `lan_settings` also lists the guest Wi-Fi's fixed IP addresses, and `parental_controls` shows whether a device's schedule is overridden.

### Changed

- `devices.block()` also ends an override that allows the device's internet access (see `scheduler.override_device_schedule()`). Otherwise the device would stay unblocked.
- When WireGuard is turned off, `wireguard.set_server_enabled()` and `add_client()` say how to turn it on (`wireguard.set_enabled(True)`).

## [0.2.0] - 2026-11-20

pyinternetbox can now change the router's settings, like the switches and forms of the web interface: Wi-Fi, devices, parental controls, firewall, DNS, VPN and more. A new MCP server, `ibox mcp`, lets AI apps such as OpenCode look at the router and, if you allow it, manage it.

### Upgrade notes

- `security.gateway_status()` (`ibox security gateway-status`) is replaced by `security.home_security_status()` (`ibox security home-security-status`), which reads the Home Security status the web interface shows.
- `mst.set()` now needs the device's MAC address, and takes the daily time limits: `mst.set(mac, enable=True, minutes_per_day=None, allowed_time=None)`. It used to take no arguments and couldn't set anything.

### Added

- **Changing settings**, in the library and as CLI commands (`ibox <group> --help` lists them):
  - Wi-Fi: turn Wi-Fi and the guest Wi-Fi on or off (the guest Wi-Fi also for a number of hours), change network names, passwords and visibility, set the channel and channel width or let the router choose one, and turn WPS on or off or start pairing.
  - Devices: rename them, block or allow their internet access, wake them with Wake-on-LAN, or remove them from the device list.
  - Parental controls: a weekly internet access schedule per device, daily time limits (`mst.set()`, `mst.delete()`) and a Wi-Fi schedule.
  - Firewall: IPv4 and IPv6 levels, port forwarding rules, the DMZ, UPnP, and the custom firewall's rules and basic policy.
  - Home network: fixed IP addresses for devices, static routes, the DNS servers the router gives devices (IPv4 and IPv6), and emptying the DNS cache.
  - Remote access: DynDNS hosts, and the WireGuard VPN server and its clients. `wireguard.add_client()` returns the new client's configuration, with its private key.
  - Backups: save all settings to a file and restore them (`ibox nmc backup`, `ibox nmc restore`), or back them up to Swisscom (`ibox nmc backup-to-swisscom`).
  - Restarting the router (`ibox nmc reboot`), editing and deleting phone book contacts, deleting calls or clearing the call list, and 6 GHz Wi-Fi power saving.
- **Overviews**: `ibox devices summary` and `ibox wifi summary` (`devices.summary()`, `wifi.summary()`) give a short list of the devices and the Wi-Fi networks, and `firewall.custom_rules()` lists the custom firewall rules.
- **MCP server** for AI apps such as OpenCode or Claude Desktop: `ibox mcp`, installed with `pip install "pyinternetbox[mcp]"`. It's read-only unless started with `--allow-writes` or `--allow-disruptive`. Changes that cut connections ask you first, and passwords and keys stay hidden unless you add `--show-secrets`. `ibox mcp-exporter` collects its usage metrics for Prometheus. See the README for the setup.
- **CLI**: commands that cut connections, e.g. a restart, turning Wi-Fi off or a new Wi-Fi password, ask for confirmation first. Add `--yes` to skip the question in scripts. Lists can be given comma-separated (`ibox dns set-device-servers 1.1.1.1,9.9.9.9`) and other values as JSON.
- **Library**: `action(method)` tells whether a method only reads, changes settings, or cuts connections (`"read"`, `"write"` or `"disruptive"`), and `hide_secrets()` replaces passwords and keys in a response with `"<hidden>"`. `nmc.wan_status(details=True)` also returns the public IP addresses, the gateway and the provider's DNS servers.
- **For contributors**: `scripts/discover_endpoints.py` and [docs/API_MAP.md](docs/API_MAP.md) list every endpoint the web interface uses and every function the router offers, and which ones the library covers.

### Changed

- The library logs in again by itself when the router ends the session, e.g. after 10 minutes without requests on an Internet Box 4 or after a restart, and sends the request once more. The request used to fail with HTTP 401, and the exporter missed a collection.
- When the router refuses a request, the error message includes the router's reason, e.g. "Router says: Invalid port-range (InternalPort, ExternalPort)". The CLI shows these errors, and invalid input such as a malformed MAC address, as a short message instead of a traceback.
- `firewall.custom_rule()` takes an optional `chain` argument for the IPv6 rules.

### Fixed

- `dect.ringtone()` no longer makes the router drop the connection. The Internet Box 4 doesn't offer it (HTTP 404).

## [0.1.1] - 2026-11-19

### Fixed

- Requests time out instead of hanging when the router can't be reached, and the CLI explains connection, timeout and SSL errors instead of showing a traceback. With the default host, it explains how to check that `internetbox.swisscom.ch` reaches the router.

## [0.1.0] - 2026-11-19

First release: the Python library, the `ibox` CLI and a Prometheus exporter with Grafana dashboards, for Swisscom and Wingo Internet Box routers. Published on PyPI and as the Docker image `oregonpillow/pyinternetbox`.

[Unreleased]: https://github.com/oregonpillow/pyinternetbox/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/oregonpillow/pyinternetbox/compare/v0.1.1...v0.2.0
[0.1.1]: https://github.com/oregonpillow/pyinternetbox/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/oregonpillow/pyinternetbox/releases/tag/v0.1.0
