# Changelog

What's new in each release of pyinternetbox. The newest release comes first. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow [Semantic Versioning](https://semver.org/).

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

[0.2.0]: https://github.com/oregonpillow/pyinternetbox/compare/v0.1.1...v0.2.0
[0.1.1]: https://github.com/oregonpillow/pyinternetbox/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/oregonpillow/pyinternetbox/releases/tag/v0.1.0
