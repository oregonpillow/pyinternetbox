"""Typer CLI for the Internet Box Client."""

from __future__ import annotations

import collections.abc
import contextlib
import inspect
import json
import threading
import types
import typing
from collections.abc import Iterator
from typing import TYPE_CHECKING, Annotated, NoReturn, Optional

import requests
import typer

from internetbox_client import PROJECT_NAME, PROJECT_URL, __version__
from internetbox_client.utils.APIClient import APIClient
from internetbox_client.utils.confirmations import QUESTIONS

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
    """Pretty-print a JSON response to stdout (valid JSON, jq-compatible). Other text is printed as it is, e.g. a backup file."""
    try:
        data = json.loads(raw)
        typer.echo(json.dumps(data, indent=2, ensure_ascii=False))
    except (json.JSONDecodeError, ValueError):
        typer.echo(raw, nl=not raw.endswith("\n"))


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
    except requests.exceptions.HTTPError as exc:  # the message ends with the router's reasons, if it gave any
        _fail(f"The router rejected the request: {exc}")
    except ValueError as exc:  # invalid input caught by a resource method, e.g. a malformed MAC address
        _fail(str(exc))
    except OSError as exc:  # a file that can't be read, e.g. a mistyped backup file name
        _fail(str(exc))


def _fail(message: str, hint: bool = False) -> NoReturn:
    if hint and "internetbox.swisscom.ch" in _hostname:
        message += f"\n\n{_DEFAULT_HOST_HINT}"
    typer.echo(message, err=True)
    raise typer.Exit(1)


# ── Dynamic CLI generation ────────────────────────────────────────────

# Commands that ask before running, unless given --yes: the question, and whether to ask, given the method's arguments.
_CONFIRM = QUESTIONS


def _base_type(ann: object) -> object:
    """Reduce an annotation to what the CLI needs, e.g. ``dict[str, int] | None`` -> ``dict``."""
    if isinstance(ann, types.UnionType) or typing.get_origin(ann) is typing.Union:
        args = [a for a in typing.get_args(ann) if a is not type(None)]
        if len(args) == 1:
            ann = args[0]
    origin = typing.get_origin(ann)
    if origin in (list, collections.abc.Sequence):
        return list
    if origin in (dict, collections.abc.Mapping):
        return dict
    return ann


def _typer_annotation(param: inspect.Parameter) -> type:
    """Map a resource-method parameter annotation to a Typer-friendly type."""
    ann = _base_type(param.annotation)
    if ann in (int, float, str, bool):
        return ann
    # dict, list, Literal, and anything else → accept as string on the CLI
    return str


def _union_options(ann: object) -> tuple | None:
    """The types of a union left after _base_type, e.g. ``int | Literal["auto"]``; None for other annotations."""
    if isinstance(ann, types.UnionType) or typing.get_origin(ann) is typing.Union:
        return tuple(a for a in typing.get_args(ann) if a is not type(None))
    return None


def _describe(ann: object) -> str:
    """A union member for help and error messages, e.g. "a number" or "'auto'"."""
    if typing.get_origin(ann) is typing.Literal:
        return " or ".join(repr(choice) for choice in typing.get_args(ann))
    return "a whole number" if ann is int else "a number" if ann is float else "text"


def _typer_help(pname: str, param: inspect.Parameter) -> str:
    """Build a short help string for a CLI parameter."""
    ann = _base_type(param.annotation)
    help_str = pname.replace("_", " ").title()
    if ann is list:
        help_str += " (comma-separated or JSON array)"
    elif ann is dict:
        help_str += " (JSON object)"
    elif getattr(ann, "__origin__", None) is typing.Literal:
        help_str += f" (choices: {list(ann.__args__)})"
    elif _union_options(ann):
        help_str += f" ({' or '.join(_describe(option) for option in _union_options(ann) or ())})"
    elif ann is bool and param.default is inspect.Parameter.empty:  # options are --x/--no-x flags instead
        help_str += " (true or false)"
    return help_str


def _coerce_value(val: str, ann: object) -> object:
    """Coerce a CLI string value to the target annotation type."""
    ann = _base_type(ann)
    if ann is dict:
        return json.loads(val)
    if ann is list:
        try:
            parsed = json.loads(val)
        except ValueError:
            parsed = None
        return parsed if isinstance(parsed, list) else [v.strip() for v in val.split(",") if v.strip()]
    if ann in (int, float):
        return ann(val)
    if getattr(ann, "__origin__", None) is typing.Literal:
        return type(ann.__args__[0])(val)
    options = _union_options(ann)
    if options:
        # A choice such as "auto" first, then the other types in order, e.g. a channel number.
        for option in options:
            for choice in typing.get_args(option) if typing.get_origin(option) is typing.Literal else ():
                if str(choice) == val:
                    return choice
        for option in options:
            if typing.get_origin(option) is not typing.Literal:
                with contextlib.suppress(ValueError):
                    return _coerce_value(val, option)
        raise ValueError(f"Expected {' or '.join(_describe(option) for option in options)}, got {val!r}")
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
            # Typer Option. Booleans get an explicit --x/--no-x pair: a lone --x flag with a True default would
            # set the value to False when given.
            flag = f"--{pname.replace('_', '-')}"
            decl = f"{flag}/--no-{flag[2:]}" if ann_type is bool else flag
            sig_parts.append(
                f"{pname}: Annotated[Optional[{ann_type.__name__}], "
                f"typer.Option({decl!r}, help={help_str!r}, show_default=True)] = {param.default!r}"
            )
        else:
            # Typer Argument
            sig_parts.append(f"{pname}: Annotated[{ann_type.__name__}, typer.Argument(help={help_str!r})]")

    question, needs_confirmation = _CONFIRM.get((attr_name, method_name), (None, None))
    if question:
        sig_parts.append('yes: Annotated[bool, typer.Option("--yes", "-y", help="Don\'t ask for confirmation.")] = False')

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
        call_kwargs = {}
        for pname, param in params:
            val = local_values.get(pname)
            if val is not None:
                try:
                    val = _coerce_value(val, param.annotation)
                except ValueError as exc:
                    raise typer.BadParameter(str(exc), param_hint=f"'{pname}'") from exc
            call_kwargs[pname] = val
        if question and needs_confirmation(call_kwargs) and not local_values["yes"]:
            typer.confirm(question, abort=True)
        with _friendly_errors(), _make_client() as client:
            resource = getattr(client, a)
            _output(getattr(resource, m)(**call_kwargs))

    ns["_invoke"] = _invoke
    return cmd


def _register_command(
    group: typer.Typer, attr_name: str, method_name: str, params: list[tuple[str, inspect.Parameter]], help_text: str
) -> None:
    """Register a single CLI command, with or without parameters."""
    cli_name = method_name.replace("_", "-")

    if not params and (attr_name, method_name) not in _CONFIRM:

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

            sig = inspect.signature(method, eval_str=True)  # resolve string annotations (from __future__ import annotations)
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
    supplied before the 'export' sub-command. The password is required, since
    almost every metric needs it, and the exporter stops if the router refuses it.
    """
    import signal

    import prometheus_client

    from internetbox_client.exporter import InternetBoxCollector
    from internetbox_client.metrics import register_metrics

    typer.echo(f"{PROJECT_NAME} {__version__}  |  {PROJECT_URL}")

    if not _password:
        _fail("The exporter needs the router password: set IB_PASSWORD, or give --password before export.")
    client = _make_client()
    # Use a distinct application name so the exporter session does not
    # collide with an active browser session on the router.
    client._sm.application_name = "prometheus-exporter"

    # A refused login would fail every collection, so stop. If the router can't be reached, e.g. while it restarts,
    # keep going: the collectors log in when it's back.
    try:
        client._sm._ensure_authenticated()
    except requests.exceptions.RequestException as exc:
        if exc.response is not None and exc.response.status_code == 401:
            _fail(
                f"The router at {_hostname} refused the login. Check the password (IB_PASSWORD or --password) "
                "and the user name (IB_USERNAME or --username, default admin)."
            )
        typer.echo(f"Could not log in to the router yet, trying again every {interval}s: {exc}", err=True)

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


# ── MCP server ───────────────────────────────────────────────────────


@app.command(name="mcp")
def mcp_server(
    allow_writes: Annotated[bool, typer.Option("--allow-writes", help="Offer tools that change settings.")] = False,
    allow_disruptive: Annotated[
        bool,
        typer.Option(
            "--allow-disruptive",
            help="Also offer changes that cut the Wi-Fi or internet for others, e.g. a restart. Implies --allow-writes.",
        ),
    ] = False,
    show_secrets: Annotated[bool, typer.Option("--show-secrets", help="Show passwords and keys to the AI app.")] = False,
    metrics_url: Annotated[
        Optional[str],
        typer.Option("--metrics-url", envvar="IB_MCP_METRICS_URL", help="Send usage metrics to `ibox mcp-exporter` at this URL."),
    ] = None,
) -> None:
    """Start an MCP server over stdio, for AI apps such as OpenCode or Claude Desktop.

    The app starts this command itself: see the README for its configuration.
    Reads are always offered; changes need --allow-writes or --allow-disruptive.
    Needs pyinternetbox's optional mcp dependencies (see the README).
    """
    try:
        from internetbox_client.mcp_server.server import Options, build_server
    except ImportError as exc:
        if not (exc.name or "").startswith(("mcp", "pydantic")):
            raise
        _fail(
            'The MCP server needs the mcp extra: pip install "pyinternetbox[mcp]", or run it with uvx --from "pyinternetbox[mcp]" ibox mcp'
        )
    from internetbox_client.mcp_server.metrics import MetricsSender

    if not _password:
        _fail("The MCP server needs the router password: set IB_PASSWORD, or give --password before mcp.")
    sender = None
    if metrics_url:
        try:
            sender = MetricsSender(metrics_url)
        except ValueError as exc:
            _fail(str(exc))
    client = _make_client()
    # A distinct application name, so the server's session doesn't end a browser session on the router.
    client._sm.application_name = "pyinternetbox-mcp"
    options = Options(allow_writes=allow_writes, allow_disruptive=allow_disruptive, show_secrets=show_secrets)
    try:
        build_server(client, options, sender).run("stdio")  # stdout carries the MCP messages: nothing else may print there
    except KeyboardInterrupt:
        pass
    finally:
        if sender is not None:
            sender.close()
        client.close()


@app.command(name="mcp-exporter")
def mcp_exporter(
    host: Annotated[
        str, typer.Option("--host", envvar="IB_MCP_EXPORTER_HOST", help="Address to listen on. 0.0.0.0 accepts events from other hosts.")
    ] = "127.0.0.1",
    port: Annotated[int, typer.Option("--port", "-P", envvar="IB_MCP_EXPORTER_PORT", help="TCP port to listen on.")] = 9102,
) -> None:
    """Collect usage metrics from `ibox mcp` servers and serve them to Prometheus at /metrics.

    Start the MCP servers with --metrics-url http://HOST:PORT. Needs no router access.
    """
    import signal

    from internetbox_client.mcp_server.exporter import make_server

    try:
        server = make_server(host, port)
    except OSError as exc:
        _fail(f"Could not listen on {host}:{port}: {exc}")
    typer.echo(f"{PROJECT_NAME} {__version__}  |  {PROJECT_URL}")
    typer.echo(f"MCP metrics collector listening on http://{host}:{port}: metrics at /metrics, events to POST /events")
    signal.signal(signal.SIGTERM, lambda _sig, _frame: threading.Thread(target=server.shutdown).start())
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        typer.echo("Stopping MCP metrics collector...")
        server.server_close()


if __name__ == "__main__":
    app()
