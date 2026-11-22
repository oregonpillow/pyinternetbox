# Getting started

## Installation

**from PyPI**:

```sh
pip install pyinternetbox          # library + `ibox` CLI
pip install "pyinternetbox[mcp]"   # also the MCP server, `ibox mcp`
uv tool install pyinternetbox      # or: just the `ibox` CLI, in its own environment
```

**with Docker** (runs the [exporter](exporter.md)):

```sh
docker run -d -p 9101:9101 -e IB_PASSWORD=secret oregonpillow/pyinternetbox:latest
```

**from source** (for development) **with uv**:

```sh
uv sync
```

**from source with pip**:

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Connecting to the router

Most functions need the router's admin password. Give it, and the router's address if it isn't `internetbox.swisscom.ch`, as [environment variables](reference/environment-variables.md):

```sh
export IB_HOSTNAME=192.168.1.1
export IB_PASSWORD=secret
```

Or give them to each command, before the command's group: `ibox -H 192.168.1.1 -p secret wifi summary`. Some functions work without the password: see [Usage without a password](reference/without-password.md).

## CLI usage

**with uv** (from source)

```sh
uv run ibox --help
```

**with pip / uv tool**:

```sh
ibox --help
ibox --version
```

The CLI outputs pretty JSON but can still be piped to popular tools like `jq`. `ibox devices summary` and `ibox wifi summary` give a short overview of the devices and the Wi-Fi networks.

Commands that change settings do what the matching switch or form in the web interface does. `ibox <group> --help` lists them, for example:

```sh
ibox firewall set-port-forwarding minecraft 192.168.1.20 25565 --protocol tcp
ibox devices block AA:BB:CC:DD:EE:FF
ibox mst set AA:BB:CC:DD:EE:FF --minutes-per-day 120 --allowed-time '{"Sat": 240, "Sun": 240}'
ibox wifi set-network --ssid MyHome --password 'Correct-Horse-9'
ibox wifi set-channel 2.4GHz 6 --bandwidth 20MHz
ibox firewall set-custom-rule Telnet 23 block --protocol tcp
ibox dns set-device-servers 1.1.1.1,9.9.9.9
```

`ibox wireguard add-client` prints the new VPN client's configuration, with its private key. To save it for the WireGuard app:

```sh
ibox wireguard add-client phone --endpoint myhome.ddns.net | jq -r .status > phone.conf
```

To save all settings to a file and load them back later, like the web interface's "Save Current Configuration" and "Restore Configuration" buttons (the phone book isn't included, and a restore leaves it as it is):

```sh
ibox nmc backup > internetbox.cfg
ibox nmc restore internetbox.cfg
```

`ibox nmc backup-to-swisscom` uploads the settings to Swisscom, as the web interface does when you save a change. It only works if backup to Swisscom is turned on for your router; the web interface has no setting for it. The upload runs in the background for about a minute, and `ibox nmc network-config` shows its status.

Commands that cut connections ask for confirmation first: `ibox nmc reboot`, `ibox nmc restore` (the router restarts afterwards), turning Wi-Fi or the guest Wi-Fi off, changing Wi-Fi names, passwords, channels or standards, turning on band steering or a Wi-Fi schedule, changing the DNS servers the router asks, blocking outgoing traffic in the custom firewall and turning off WireGuard or the WireGuard VPN server. So do commands that delete what can't be brought back: `ibox voice clear-call-list`, `ibox firewall delete-all-port-forwarding` and `ibox devices reset-traffic-counters`. Add `--yes` to skip the question in scripts.

## Library usage

```python
from internetbox_client import InternetBoxClient

with InternetBoxClient() as ibox:
    print(ibox.nmc.status())         # no auth required
    print(ibox.wifi.status())        # no auth required
    print(ibox.devices.topology())   # auth required
    print(ibox.vpn.status())         # auth required
```

The [library reference](reference/library/index.md) describes every method.

For tools built on the library, e.g. the [MCP server](mcp.md), each method is labelled with what it does to the router, and `hide_secrets()` replaces passwords and keys in a response. The library and the CLI show them.

```python
import json

from internetbox_client.utils.helpers import hide_secrets
from internetbox_client.utils.labels import action

action(ibox.wifi.summary)                      # "read"; also "write" or "disruptive" (cuts connections)
hide_secrets(json.loads(ibox.wifi.summary()))  # passwords and keys become "<hidden>"
```
