# Development

## Development requirements

In order to run tests and pre-commit hooks you need to have the development dependencies installed.

In addition to UV, you will need [prettier](https://prettier.io/) to run pre-commit hooks. You can install npx with [npm](https://nodejs.org/en/download/) and then use npx to install it:

```sh
npm install -g npx
npx install -g prettier
```

Clone the repo and install all dependencies including dev tools:

```sh
uv sync
```

## Pre-commit hooks

This project uses pre-commit hooks. To set it up:

- `uv tool install pre-commit --with pre-commit-uv`
- `uvx pre-commit install`
- test by running all hooks: `uvx pre-commit run -a`

## Documentation

This site is built from `docs/` and `zensical.toml` with [Zensical](https://zensical.org). The library reference comes from the docstrings. A new group of `InternetBoxClient` needs a page in `docs/reference/library/` and an entry in the `nav` of `zensical.toml`; `tests/test_docs.py` checks that it has both. To preview the site while you edit it, at `http://localhost:8000`:

```sh
uv run --group docs zensical serve
```

The site is published with each release: see [Releasing](releasing.md). The Tests workflow builds it on every push and pull request, so a broken link fails there, before a release.

## Tests

| **Test**       | **Description**                                                                                                                                                                                                                                                                                                       | **Check**                                     | **Fix**                         |
| -------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------- | ------------------------------- |
| **Unit Tests** | Run unit tests                                                                                                                                                                                                                                                                                                        | `uv run pytest`                               | N/A                             |
| **End-to-End** | Makes real HTTP requests to your router and verifies every endpoint returns a valid HTTP response code. Excluded from the default test run. Requires `IB_PASSWORD` to be set (see [Environment variables](../reference/environment-variables.md)). Read-only and destructive tests can be run separately (see below). | `uv run pytest tests/test_e2e.py -v`          | N/A                             |
| **Coverage**   | Check test coverage                                                                                                                                                                                                                                                                                                   | `uv run pytest --cov`                         | N/A                             |
| **Linting**    | Check code for linting issues                                                                                                                                                                                                                                                                                         | `uv run ruff check .`                         | `uv run ruff check --fix .`     |
| **Formatting** | Check code formatting                                                                                                                                                                                                                                                                                                 | `uv run ruff format --check .`                | `uv run ruff format .`          |
| **isort**      | Check import sorting consistency                                                                                                                                                                                                                                                                                      | `ruff check --select I .`                     | `ruff check --select I --fix .` |
| **deptry**     | Checks unused or missing dependencies                                                                                                                                                                                                                                                                                 | `uv run deptry .`                             | N/A                             |
| **prettier**   | Check markdown formatting                                                                                                                                                                                                                                                                                             | `npx prettier --check .`                      | `npx prettier --write .`        |
| **Docs**       | Build the documentation site and check its links                                                                                                                                                                                                                                                                      | `uv run --group docs zensical build --strict` | N/A                             |

### End-to-end (E2E) tests

⚠️ Use the E2E tests with caution especially if you have a production router (any router where downtime could expose you to the wrath of your partner or roommates).

The tests are designed to be safe but they do make real HTTP requests to your router and some of the tests are destructive (they change a setting on the router and then attempt to change it back). If you want to be extra cautious you can run only the read-only tests which shouldn't make any changes to the router.

```sh
# 🔬 Read-only — should be safe for any environment
uv run pytest tests/test_e2e.py -m "not destructive" -v

# 💥 All tests including destructive (writes to the router, then reverts)
uv run pytest tests/test_e2e.py -v

# 💥 Only destructive tests
uv run pytest tests/test_e2e.py -m destructive -v

# 📴 Also tests that briefly cut the network for everyone (guest Wi-Fi on/off, all Wi-Fi off/on, Wi-Fi channels and standards, band steering, the router's DNS servers, Wi-Fi schedule, VPN server on/off, WireGuard off/on)
IB_E2E_DISRUPTIVE=1 uv run pytest tests/test_e2e.py -m disruptive -v
```

Destructive tests leave the router as they found it. They write the current value back (LED brightness, Wi-Fi TX power, firewall levels, the custom firewall's basic actions, ping replies, the DNS cache switch, WLAN-Box sync, 6 GHz power saving, the DynDNS and WireGuard switches), or create something temporary and delete it again: a disabled port forwarding rule, protocol forwarding rule, IPv6 pinhole and custom firewall rule and a DynDNS host that the router doesn't keep up to date, named after `pyinternetbox-e2e`, a WireGuard client named `pyiboxe2e`, a static route to the unused network `172.31.254.0/24`, and a device entry with a type and DNS name, IP address reservations on the home and guest networks, an access schedule and its overrides, time limit and band steering exception for the made-up MAC address `02:00:00:00:00:01`. They skip instead of touching existing settings, e.g. when a DMZ host, another DynDNS host or a Wi-Fi schedule is set, or the guest Wi-Fi is on. Saving the log files replaces the ones saved on the router before.

Tests that cut the network for everyone are skipped unless `IB_E2E_DISRUPTIVE=1` is set. The tests that turn Wi-Fi off and on or write the Wi-Fi names, channels or standards back also skip unless the machine running them is connected to the router by cable, since it could lose its connection otherwise. Turning Wi-Fi off and on leaves the guest network off, so the test turns it back on if it was on.
