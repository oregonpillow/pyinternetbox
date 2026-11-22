<div align="center">
  <img src="https://raw.githubusercontent.com/oregonpillow/pyinternetbox/master/grafana/internetbox4.jpg" width="50%" alt="Grafana Dashboard" />
  <h1 style="font-size: 28px; margin: 10px 0;">pyinternetbox</h1>
  <p style="font-size: 16px; margin: 0;"><b>Your Swisscom Internet Box - with batteries included.</b></p>
  <p>Python library | CLI | MCP server | Prometheus exporters | Grafana dashboards</p>
  <p><a href="https://oregonpillow.github.io/pyinternetbox/"><b>Documentation</b></a></p>
</div>
<br>

pyinternetbox talks to the Swisscom Internet Box the way its web interface does. Read its status and change its settings from Python or the `ibox` command line, collect its metrics with Prometheus, or let an AI app look after it. It's tested on the Internet Box 4: see [Supported models](https://oregonpillow.github.io/pyinternetbox/reference/models/).

## 🚀 Installation

```sh
pip install pyinternetbox          # library + `ibox` CLI
pip install "pyinternetbox[mcp]"   # also the MCP server, `ibox mcp`
uv tool install pyinternetbox      # or: just the `ibox` CLI, in its own environment
```

Most functions need the router's admin password. Give it, and the router's address if it isn't `internetbox.swisscom.ch`, as environment variables:

```sh
export IB_HOSTNAME=192.168.1.1
export IB_PASSWORD=secret
```

## ⚡ Quick start

**CLI**: every library function is a command, and the output is JSON, ready for `jq`.

```sh
ibox devices summary
ibox wifi summary
ibox firewall set-port-forwarding minecraft 192.168.1.20 25565 --protocol tcp
```

**Library**:

```python
from internetbox_client import InternetBoxClient

with InternetBoxClient() as ibox:
    print(ibox.devices.summary())
```

**Prometheus exporter**, with Docker. The metrics are at `http://localhost:9101/metrics`.

```sh
docker run -d -p 9101:9101 -e IB_PASSWORD=secret oregonpillow/pyinternetbox:latest
```

**MCP server**, for AI apps such as OpenCode or Claude Desktop. The app starts it with `uvx --from "pyinternetbox[mcp]" ibox mcp`, and it's read-only unless you allow changes.

## 📚 Documentation

- [Getting started](https://oregonpillow.github.io/pyinternetbox/getting-started/): installation, the CLI and the library
- [Exporter](https://oregonpillow.github.io/pyinternetbox/exporter/): running it, the metrics and the Grafana dashboards
- [MCP server](https://oregonpillow.github.io/pyinternetbox/mcp/): setup, and what the AI may do
- [Library reference](https://oregonpillow.github.io/pyinternetbox/reference/library/): every method
- [Contributing](https://oregonpillow.github.io/pyinternetbox/contributing/): development, tests and releasing. Contributions are welcome!
- [Changelog](https://oregonpillow.github.io/pyinternetbox/changelog/)

## Related Projects

- [LiveboxMonitor](https://github.com/p-dor/LiveboxMonitor)
- [sysbus](https://github.com/rene-d/sysbus)
- [internetbox2-exporter](https://github.com/simonkrenger/internetbox2-exporter)

## Disclaimer

While I work at Swisscom, this project is a personal endeavor and is not affiliated with or endorsed by Swisscom. The information provided in this project is based on my own research and experience from observing the REST-API calls the router makes when you login using developer tools in your browser. Use at your own risk. I don't work with the Internet Box team or have any affiliation with them.
