"""Typer CLI for the Internet Box Client."""

from __future__ import annotations

import contextlib
import inspect
import json
import threading
import typing
from collections.abc import Iterator
from typing import TYPE_CHECKING, Annotated, NoReturn, Optional

import requests
import typer

from internetbox_client import PROJECT_NAME, PROJECT_URL, __version__
from internetbox_client.utils.APIClient import APIClient

if TYPE_CHECKING:
    from internetbox_client import InternetBoxClient

app = typer.Typer(name="internetbox", help="CLI for the Swisscom Internet Box API.")

# ── Global state set by the callback ──────────────────────────────────
_hostname: str = "https://internetbox.swisscom.ch"
_password: str = ""
_username: str = "admin"
_insecure: bool = False


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"{PROJECT_NAME} {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    hostname: Annotated[
        str, typer.Option("--host", "-H", envvar="IB_HOSTNAME", help="Router hostname or IP.")
    ] = "https://internetbox.swisscom.ch",
    password: Annotated[str, typer.Option("--password", "-p", envvar="IB_PASSWORD", help="Router admin password.")] = "",
    username: Annotated[str, typer.Option("--username", "-u", envvar="IB_USERNAME", help="Router admin username.")] = "admin",
    insecure: Annotated[
        bool, typer.Option("--insecure", "-k", help="Skip SSL certificate verification (done automatically when --host is an IP address).")
    ] = False,
    version: Annotated[
        bool, typer.Option("--version", "-V", callback=_version_callback, is_eager=True, help="Show the version and exit.")
    ] = False,
):
    global _hostname, _password, _username, _insecure
    _hostname = hostname
    _password = password
    _username = username
    _insecure = insecure


def _output(raw: str) -> None:
    """Pretty-print a JSON response to stdout (valid JSON, jq-compatible)."""
    try:
        data = json.loads(raw)
        typer.echo(json.dumps(data, indent=2, ensure_ascii=False))
    except (json.JSONDecodeError, ValueError):
        typer.echo(raw)


def _make_client() -> InternetBoxClient:
    from internetbox_client import InternetBoxClient

    return InternetBoxClient(hostname=_hostname, password=_password, username=_username, ssl_verify=False if _insecure else None)


_DEFAULT_HOST_HINT = (
    "internetbox.swisscom.ch only reaches your router if your DNS resolves it to the router's LAN address. "
    "Custom DNS servers (Pi-hole, AdGuard, 1.1.1.1, ...) return Swisscom's public address instead. "
    "Check with `getent hosts internetbox.swisscom.ch` (Linux) or pass the router IP, e.g. --host 192.168.1.1."
)


@contextlib.contextmanager
def _friendly_errors() -> Iterator[None]:
    """Turn network failures into a short explanation instead of a traceback."""
    try:
        yield
    except requests.exceptions.SSLError as exc:
        _fail(f"SSL error talking to {_hostname}: {exc}\nUse --insecure / -k to skip certificate verification.")
    except requests.exceptions.ReadTimeout:
        _fail(f"{_hostname} accepted the connection but did not answer in time.", hint=True)
    except requests.exceptions.ConnectionError as exc:
        _fail(f"Could not connect to {_hostname}: {exc}", hint=True)


def _fail(message: str, hint: bool = False) -> NoReturn:
    if hint and "internetbox.swisscom.ch" in _hostname:
        message += f"\n\n{_DEFAULT_HOST_HINT}"
    typer.echo(message, err=True)
    raise typer.Exit(1)


# ── Dynamic CLI generation ────────────────────────────────────────────


def _typer_annotation(param: inspect.Parameter) -> type:
    """Map a resource-method parameter annotation to a Typer-friendly type."""
    ann = param.annotation
    if ann in (int, float, str, bool):
        return ann
    # dict, list, Literal, and anything else → accept as string on the CLI
    return str


def _typer_help(pname: str, param: inspect.Parameter) -> str:
    """Build a short help string for a CLI parameter."""
    ann = param.annotation
    help_str = pname.replace("_", " ").title()
    if ann is list:
        help_str += " (comma-separated or JSON array)"
    elif getattr(ann, "__origin__", None) is typing.Literal:
        help_str += f" (choices: {list(ann.__args__)})"
    return help_str


def _coerce_value(val: str, ann: type) -> object:
    """Coerce a CLI string value to the target annotation type."""
    if ann in (dict, list):
        return json.loads(val)
    if ann is list:
        try:
            return json.loads(val)
        except (json.JSONDecodeError, ValueError):
            return [v.strip() for v in val.split(",") if v.strip()]
    if ann in (int, float):
        return ann(val)
    if getattr(ann, "__origin__", None) is typing.Literal:
        return type(ann.__args__[0])(val)
    return val


def _build_command_func(attr_name: str, method_name: str, params: list[tuple[str, inspect.Parameter]]):
    """Return a function with an explicit signature matching *params*.

    Typer introspects function signatures to generate CLI arguments/options.
    We dynamically create a function whose parameter names, defaults and
    ``Annotated`` type hints match the resource method so that Typer can
    generate proper ``--option`` / ``ARGUMENT`` entries.
    """
    # Build the function source with the correct signature
    sig_parts: list[str] = []
    for pname, param in params:
        ann_type = _typer_annotation(param)
        help_str = _typer_help(pname, param)
        has_default = param.default is not inspect.Parameter.empty

        if has_default:
            # Typer Option
            sig_parts.append(
                f"{pname}: Annotated[Optional[{ann_type.__name__}], "
                f'typer.Option("--{pname.replace("_", "-")}", help={help_str!r}, show_default=True)] = {param.default!r}'
            )
        else:
            # Typer Argument
            sig_parts.append(f"{pname}: Annotated[{ann_type.__name__}, typer.Argument(help={help_str!r})]")

    sig = ", ".join(sig_parts)
    func_src = f"def cmd({sig}):\n    _invoke({attr_name!r}, {method_name!r}, locals())\n"

    # Namespace for exec
    ns: dict[str, object] = {
        "Annotated": Annotated,
        "Optional": Optional,
        "typer": typer,
        "_invoke": None,  # placeholder, set below
    }
    for pname, param in params:
        ns[_typer_annotation(param).__name__] = _typer_annotation(param)

    exec(func_src, ns)  # noqa: S102
    cmd = ns["cmd"]

    # Wire up the actual invocation logic (closure, not exec'd)
    def _invoke(a: str, m: str, local_values: dict) -> None:
        with _friendly_errors(), _make_client() as client:
            resource = getattr(client, a)
            call_kwargs = {}
            for pname, param in params:
                val = local_values.get(pname)
                if val is not None:
                    val = _coerce_value(val, param.annotation)
                call_kwargs[pname] = val
            _output(getattr(resource, m)(**call_kwargs))

    ns["_invoke"] = _invoke
    return cmd


def _register_command(
    group: typer.Typer, attr_name: str, method_name: str, params: list[tuple[str, inspect.Parameter]], help_text: str
) -> None:
    """Register a single CLI command, with or without parameters."""
    cli_name = method_name.replace("_", "-")

    if not params:

        def _make_no_param_cmd(a: str = attr_name, m: str = method_name):
            @group.command(name=cli_name, help=help_text)
            def cmd():
                with _friendly_errors(), _make_client() as client:
                    _output(getattr(getattr(client, a), m)())

        _make_no_param_cmd()
    else:
        cmd = _build_command_func(attr_name, method_name, params)
        group.command(name=cli_name, help=help_text)(cmd)


def _build_cli() -> None:
    """Introspect InternetBoxClient and register all sub-commands."""
    import internetbox_client.resources as ibc_module
    from internetbox_client import InternetBoxClient

    # Discover all APIClient subclasses in the module
    resource_classes: dict[str, type] = {}
    for name, obj in inspect.getmembers(ibc_module, inspect.isclass):
        if issubclass(obj, APIClient) and obj is not APIClient:
            resource_classes[name] = obj

    # Map attr names → classes by parsing __init__ source lines
    init_source = inspect.getsource(InternetBoxClient.__init__)
    attr_to_class: dict[str, type] = {}
    for line in init_source.splitlines():
        line = line.strip()
        if line.startswith("self.") and "session_manager=" in line and not line.startswith("self._"):
            attr_name = line.split("=")[0].replace("self.", "").strip()
            cls_name = line.split("=", 1)[1].strip().split("(")[0].strip()
            if cls_name in resource_classes:
                attr_to_class[attr_name] = resource_classes[cls_name]

    # Only skip methods that are defined directly on APIClient (the HTTP helpers),
    # not methods that a subclass has overridden with domain logic (e.g. Devices.get).
    api_client_methods = set(APIClient.__dict__)

    for attr_name, cls in attr_to_class.items():
        group = typer.Typer(help=cls.__doc__ or f"{attr_name} commands")

        for method_name, method in inspect.getmembers(cls, predicate=inspect.isfunction):
            if method_name.startswith("_") or (method_name in api_client_methods and method_name not in cls.__dict__):
                continue

            sig = inspect.signature(method)
            doc = (method.__doc__ or "").strip().split("\n")[0]  # Use first line of docstring as command help
            # doc = inspect.cleandoc(method.__doc__ or "")  # Use full cleaned docstring as command help
            params = [(n, p) for n, p in sig.parameters.items() if n != "self"]

            _register_command(group, attr_name, method_name, params, doc)

        app.add_typer(group, name=attr_name.replace("_", "-"))


_build_cli()


# ── Prometheus exporter ──────────────────────────────────────────────


@app.command()
def export(
    port: Annotated[int, typer.Option("--port", "-P", envvar="IB_EXPORTER_PORT", help="TCP port the /metrics endpoint listens on.")] = 9101,
    interval: Annotated[
        int, typer.Option("--interval", "-i", envvar="IB_EXPORTER_INTERVAL", help="Seconds between data collection cycles.")
    ] = 30,
) -> None:
    """Start a Prometheus /metrics exporter for the Internet Box.

    Opens a single authenticated session and keeps it alive for the lifetime
    of the process.  User-defined collection callbacks are called every
    INTERVAL seconds in a background thread; the resulting Gauge metrics are
    served at http://0.0.0.0:PORT/metrics.

    Register collection callbacks via InternetBoxCollector.register_collector
    before the export loop starts.  Each callback receives the collector
    instance and should call update_gauge() to publish values.

    Connection credentials are taken from --host / --password / --username
    (or the IB_HOSTNAME / IB_PASSWORD / IB_USERNAME environment variables)
    supplied before the 'export' sub-command.
    """
    import signal

    import prometheus_client

    from internetbox_client.exporter import InternetBoxCollector
    from internetbox_client.metrics import register_metrics

    typer.echo(f"{PROJECT_NAME} {__version__}  |  {PROJECT_URL}")

    client = _make_client()
    # Use a distinct application name so the exporter session does not
    # collide with an active browser session on the router.
    client._sm.application_name = "prometheus-exporter"

    collector = InternetBoxCollector(client, interval=interval)
    register_metrics(collector, client)
    collector.start()

    prometheus_client.REGISTRY.register(collector)
    prometheus_client.start_http_server(port)

    typer.echo(f"Prometheus exporter listening on http://0.0.0.0:{port}/metrics")
    typer.echo(f"Collection interval: {interval}s  |  Press Ctrl-C to stop.")

    _shutdown = threading.Event()
    signal.signal(signal.SIGTERM, lambda _sig, _frame: _shutdown.set())

    try:
        while not _shutdown.wait(timeout=1):
            pass
    except KeyboardInterrupt:
        pass
    finally:
        typer.echo("Stopping exporter...")
        collector.stop()
        client.close()


if __name__ == "__main__":
    app()
