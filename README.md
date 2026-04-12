<div align="center">
  <img src="docs/logo.svg" width="400px" alt="Grafana Dashboard" />
  <h1 style="font-size: 28px; margin: 10px 0;">pyinternetbox</h1>
  <p>Python library and CLI tool (with built in exporter) for Swisscom / Wingo Internet Box routers.</p>
</div>
<br>

## 📚 Table of Contents

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [🚀 Getting Started](#-getting-started)
  - [Installation](#installation)
  - [CLI usage](#cli-usage)
  - [Library usage](#library-usage)
- [📡 Running the Exporter](#-running-the-exporter)
- [Environment Variables](#environment-variables)
- [Usage without authentication](#usage-without-authentication)
- [🧑‍💻 Development](#-development)
  - [How to contribute](#how-to-contribute)
  - [Creating more complex methods](#creating-more-complex-methods)
  - [Supported Internet Box Models](#supported-internet-box-models)
  - [Model Information](#model-information)
  - [Development Requirements](#development-requirements)
  - [🪝 Pre-commit Hooks](#-pre-commit-hooks)
- [🧪 Tests](#-tests)
  - [End-to-End (E2E) Tests](#end-to-end-e2e-tests)
- [Related Projects](#related-projects)
- [Disclaimer](#disclaimer)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

## 🚀 Getting Started

### Installation

(no official release yet, install from source)

**with uv** (recommended):

```sh
uv sync
```

**with pip**:

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

### CLI usage

**with uv**

```sh
uv run ibox --help
```

**with pip**:

```sh
ibox --help
```

The CLI outputs pretty JSON but can still be piped to popular tools like `jq`.

### Library usage

```python
from internetbox_client import InternetBoxClient

with InternetBoxClient() as ibox:
    print(ibox.nmc.status())         # no auth required
    print(ibox.wifi.status())        # no auth required
    print(ibox.devices.topology())   # auth required
    print(ibox.vpn.status())         # auth required
```

## 📡 Running the Exporter

The exporter exposes router metrics in [Prometheus](https://prometheus.io/) format on port `9101`.
Only a sample of metrics are currently implemented - contributions are welcome!

**with uv / pip**:

```sh
ibox export
```

**with Docker Compose**:

Set set environent variables in `docker-compose.yml`, then:

```sh
docker compose up -d
```

Metrics will be available at `http://localhost:9101/metrics`.

example Prometheus config:

```yaml
scrape_configs:
  - job_name: "pyinternetbox"
    scrape_interval: 30s
    metrics_path: /metrics
    static_configs:
      - targets: ["localhost:9101"]
```

Dashboards can be found in the Grafana folder.

<p align="center">
  <img src="grafana/internetbox4.jpg" alt="Grafana Dashboard" width=600/>
</p>

## Environment Variables

| **Variable**           | **Description**                                                                                                                                                                                         | **Required** |
| ---------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------ |
| `IB_HOSTNAME`          | Hostname or IP address of the Internet Box router. Defaults to `https://internetbox.swisscom.ch`.                                                                                                       | No           |
| `IB_USERNAME`          | Username for router authentication. Defaults to `admin`.                                                                                                                                                | No           |
| `IB_PASSWORD`          | Password for router authentication. Defaults to an empty string. Without a password many of the client methods will not work. See below for complete list of methods that don't require authentication. | No           |
| `IB_EXPORTER_PORT`     | TCP port the Prometheus `/metrics` endpoint listens on. Defaults to `9101`.                                                                                                                             | No           |
| `IB_EXPORTER_INTERVAL` | Seconds between data collection cycles when running the exporter. Defaults to `30`.                                                                                                                     | No           |
| `IB_SSL_VERIFY`        | Set to `false` to disable SSL certificate verification. Useful when connecting via local IP (e.g. `https://192.168.1.1`) instead of `https://internetbox.swisscom.ch`. Defaults to `true`.              | No           |

## Usage without authentication

A limited selection of methods are available without authentication, which means they can be used even if you don't have the password to your router.

| **Method**              | **API**                           | **CLI**                         |
| ----------------------- | --------------------------------- | ------------------------------- |
| Devices.info            | `ibox.devices.info()`             | `ibox devices info`             |
| DNS.status              | `ibox.dns.status()`               | `ibox dns status`               |
| Mitigation.status       | `ibox.mitigation.status()`        | `ibox mitigation status`        |
| NMC.status              | `ibox.nmc.status()`               | `ibox nmc status`               |
| NMC.ip_conflicts        | `ibox.nmc.ip_conflicts()`         | `ibox nmc ip-conflicts`         |
| NMC.wan_status          | `ibox.nmc.wan_status()`           | `ibox nmc wan-status`           |
| NMC.orientation         | `ibox.nmc.orientation()`          | `ibox nmc orientation`          |
| PasswordRecovery.status | `ibox.password_recovery.status()` | `ibox password-recovery status` |
| Static.settings         | `ibox.static.settings()`          | `ibox static settings`          |
| Static.translations     | `ibox.static.translations()`      | `ibox static translations`      |
| Sysbus.gpios            | `ibox.sysbus.gpios()`             | `ibox sysbus gpios`             |
| Sysbus.mibs             | `ibox.sysbus.mibs()`              | `ibox sysbus mibs`              |
| Sysbus.veip             | `ibox.sysbus.veip()`              | `ibox sysbus veip`              |
| Sysbus.veip_mibs        | `ibox.sysbus.veip_mibs()`         | `ibox sysbus veip-mibs`         |
| Voice.status            | `ibox.voice.status()`             | `ibox voice status`             |
| Voice.trunks            | `ibox.voice.trunks()`             | `ibox voice trunks`             |
| Wifi.status             | `ibox.wifi.status()`              | `ibox wifi status`              |
| WWAN.status             | `ibox.wwan.status()`              | `ibox wwan status`              |
| WWAN.mibs               | `ibox.wwan.mibs()`                | `ibox wwan mibs`                |

\*Methods that do not require authentication have the following parameter set within their respective method: `auth_required=False`. Search for this in codebase if you need to identify them.

## 🧑‍💻 Development

So far the project is in early stages and I'm the only contributor, but I welcome contributions from the community! If you want to contribute, please fork the repository and create a pull request with your changes. At the moment I've only tested with an IB4 box, if you have a different box any testing you can provide would be greatly appreciaited! :)

### How to contribute

- Read the [MISSING_ENDPOINTS](./docs/MISSING_ENDPOINTS.md) doc if you want to work on implementing missing endpoints that might work from the [LiveboxMonitor](https://github.com/p-dor/LiveboxMonitor)
- Try creating more complex methods, see below for more details
- Take a stab at implementing any bugs or features raised in the issues
- Test the library with different Swisscom/Wingo Internet Box models and report any issues you find - testers are much appreciaited!!
- Contribute more dashboards :)
- Add missing metrics in the exporter: only a subset of methods in this client are currently implemented
- Improve the pipeline
- Buy me a coffee ☕️ ;)

### Creating more complex methods

When logged into the web interface, within developer tools you can see the REST-API logic within the js scripts.

Pretty much all the REST-API logic is contained within these. These scripts could be parsed to find missing endpoints and provide a template for how to interact and combine calls for more powerful dynamic methods.

The scripts likely differ based on the Web portal version.
The `Web portal version` can be found in the web gui: `Diagnostics > Internet-Box`.

To view the js scripts:

> 1. Open your Internet Box web interface (e.g. `https://internetbox.swisscom.ch`) and log in
> 2. Open your browser's Developer Tools (F12) → **Network** tab
> 3. Reload the page and filter by JS — download `app.min.js` and `core.min.js`

### Supported Internet Box Models

| **Model**          | **Tested** | **Notes**                     |
| ------------------ | ---------- | ----------------------------- |
| Internet Box 2     | No         | Expected to work partially    |
| Internet Box 3     | No         | Expected to work partially    |
| Internet Box 4     | ✅         | Tested and confirmed to work. |
| Internet Box 5     | No         | Expected to work              |
| Internet Box 5 Pro | No         | Expected to work              |

### Model Information

| **Model**      | **Manufacturer** | **Model Name** | **OUI Number** |
| -------------- | ---------------- | -------------- | -------------- |
| Internet Box 4 | Arcadyan         | IB4-00         | 1883BF         |

To check your model run `ibox devices info`. Submit a PR if you have a model not listed here.

### Development Requirements

In order to run tests and pre-commit hooks you need to have the development dependencies installed.

In addition to UV, you will need [prettier](https://prettier.io/) and [doctoc](https://github.com/thlorenz/doctoc) to run pre-commit hooks. You can install npx with [npm](https://nodejs.org/en/download/) and then use npx to install the tools:

```sh
npm install -g npx
npx install -g doctoc
npx install -g prettier
```

Clone the repo and install all dependencies including dev tools:

```sh
uv sync
```

### 🪝 Pre-commit Hooks

This project uses pre-commit hooks. To set it up:

- `uv tool install pre-commit --with pre-commit-uv`
- `uvx pre-commit install`
- test by running all hooks: `uvx pre-commit run -a`

## 🧪 Tests

| **Test**       | **Description**                                                                                                                                                                                                                                                                                        | **Check**                            | **Fix**                         |
| -------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------ | ------------------------------- |
| **Unit Tests** | Run unit tests                                                                                                                                                                                                                                                                                         | `uv run pytest`                      | N/A                             |
| **End-to-End** | Makes real HTTP requests to your router and verifies every endpoint returns a valid HTTP response code. Excluded from the default test run. Requires `IB_PASSWORD` to be set (see [Environment Variables](#environment-variables)). Read-only and destructive tests can be run separately (see below). | `uv run pytest tests/test_e2e.py -v` | N/A                             |
| **Coverage**   | Check test coverage                                                                                                                                                                                                                                                                                    | `uv run pytest --cov`                | N/A                             |
| **Linting**    | Check code for linting issues                                                                                                                                                                                                                                                                          | `uv run ruff check .`                | `uv run ruff check --fix .`     |
| **Formatting** | Check code formatting                                                                                                                                                                                                                                                                                  | `uv run ruff format --check .`       | `uv run ruff format .`          |
| **isort**      | Check import sorting consistency                                                                                                                                                                                                                                                                       | `ruff check --select I .`            | `ruff check --select I --fix .` |
| **deptry**     | Checks unused or missing dependencies                                                                                                                                                                                                                                                                  | `uv run deptry .`                    | N/A                             |
| **prettier**   | Check markdown formatting                                                                                                                                                                                                                                                                              | `npx prettier --check .`             | `npx prettier --write .`        |
| **doctoc**     | Auto-generate table of contents in markdown                                                                                                                                                                                                                                                            | `npx doctoc README.md`               | `npx doctoc README.md`          |

### End-to-End (E2E) Tests

⚠️ Use the E2E tests with caution especially if you have a production router (any router where downtime could expose you to the wrath of your partner or roommates).

The tests are designed to be safe but they do make real HTTP requests to your router and some of the tests are destructive (they change a setting on the router and then attempt to change it back). If you want to be extra cautious you can run only the read-only tests which shouldn't make any changes to the router.

```sh
# 🔬 Read-only — should be safe for any environment (default when running e2e)
uv run pytest tests/test_e2e.py -m "not destructive" -v

# 💥 All tests including destructive (writes to the router, then reverts)
uv run pytest tests/test_e2e.py -v

# 💥 Only destructive tests
uv run pytest tests/test_e2e.py -m destructive -v
```

Destructive tests write to the router but always revert the original value immediately after (LED brightness, Wi-Fi TX power, MST rules).

## Related Projects

- [LiveboxMonitor](https://github.com/p-dor/LiveboxMonitor)
- [sysbus](https://github.com/rene-d/sysbus)
- [internetbox2-exporter](https://github.com/simonkrenger/internetbox2-exporter)

## Disclaimer

While I work at Swisscom, this project is a personal endeavor and is not affiliated with or endorsed by Swisscom. The information provided in this project is based on my own research and experience from observing the REST-API calls the router makes when you login using developer tools in your browser. Use at your own risk. I don't work with the Internet Box team or have any affiliation with them.
