"""Map the Internet Box API and compare it with what pyinternetbox implements.

Sources:

1. The router's web interface JavaScript (no login needed): every endpoint the
   official web UI calls, plus the parameter names it sends.
2. The router's self-description (needs the admin password): ``GET /sysbus/<object>``
   lists each object's functions and their arguments.
3. This package's resources: the endpoints the client already implements.

The script only reads from the router. Parameter values (which can contain Wi-Fi keys,
MAC addresses or device names) and instance keys never appear in the report.

Usage::

    uv run scripts/discover_endpoints.py                     # both sources, password from IB_PASSWORD
    uv run scripts/discover_endpoints.py --no-login          # web UI JavaScript only
    uv run scripts/discover_endpoints.py -H 192.168.1.1 -o docs/API_MAP.md
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from internetbox_client.utils.APIClient import SessionManager

ROOT = Path(__file__).resolve().parent.parent
RESOURCES_DIR = ROOT / "internetbox_client" / "resources"

# Method-name prefixes that indicate a call changes something on the router.
WRITE_PREFIXES = (
    "set", "add", "delete", "del", "remove", "enable", "disable", "start", "stop", "reboot", "reset", "launch",
    "override", "send", "clear", "modify", "create", "destroy", "update", "commit", "apply", "change", "restart",
    "wake", "block", "upgrade", "unpair", "pair", "save", "import", "configure", "suspend", "refresh", "restore",
    "trigger", "flush", "renew", "register", "unregister", "connect", "disconnect", "release", "install", "uninstall",
)  # fmt: skip

# Top-level objects that the web UI and client don't reference but exist on SoftAtHome firmware.
EXTRA_ROOTS = ("Screen", "HomeLan", "UPnP-IGD", "SFP", "UplinkMonitor", "Time", "Hosts", "IoTService", "USBHosts", "WOL")
# Readable objects whose parents are hidden (NeMo.Intf lists nothing, but its interfaces can be read).
EXTRA_SEEDS = ("NeMo/Intf/lan", "NeMo/Intf/data", "NeMo/Intf/lo", "NeMo/Intf/wl0", "NeMo/Intf/eth0", "NeMo/Intf/veip0")

DYNAMIC = "{id}"


def is_write(method: str) -> bool:
    return method.lower().startswith(WRITE_PREFIXES)


# ── Path handling ─────────────────────────────────────────────────────


def split_path(path: str) -> list[str]:
    return [seg for seg in re.split(r"[./]", path) if seg]


class Model:
    """Object tree learned from the router's self-description: path → functions and writable parameters."""

    def __init__(self) -> None:
        self.functions: dict[str, dict[str, list[tuple[str, bool]]]] = defaultdict(dict)
        self.writable: dict[str, dict[str, str]] = defaultdict(dict)  # path → parameter name → type (values never stored)
        self.children: dict[str, set[str]] = defaultdict(set)  # generalized path → child segments (incl. DYNAMIC)

    def add(self, path: tuple[str, ...], node: dict) -> None:
        key = ".".join(path)
        for i in range(1, len(path)):
            self.children[".".join(path[:i])].add(path[i])
        for fn in node.get("functions", []):
            args = [(a["name"], bool(a.get("attributes", {}).get("mandatory"))) for a in fn.get("arguments", [])]
            self.functions[key].setdefault(fn["name"], args)
        for param in node.get("parameters", []):
            if not param.get("attributes", {}).get("read_only"):
                self.writable[key].setdefault(param["name"], param.get("type", "?"))

    def generalize(self, segments: list[str]) -> list[str]:
        """Replace instance segments (e.g. a MAC address or "lan") with DYNAMIC, using the learned tree."""
        out: list[str] = []
        for i, seg in enumerate(segments):
            known = self.children.get(".".join(out), set()) if i else None
            if i == 0 or seg == DYNAMIC or (known is not None and seg in known):
                out.append(seg)
            elif known and DYNAMIC in known:
                out.append(DYNAMIC)
            else:
                out.append(DYNAMIC if _looks_like_instance(seg) else seg)
        return out


def _looks_like_instance(seg: str) -> bool:
    """Fallback when the router's self-description isn't available."""
    return "{" in seg or seg[:1].islower() or seg.isdigit() or seg == "HGW"


@dataclass
class Endpoint:
    path: list[str]
    method: str
    params: set[str] = field(default_factory=set)

    def key(self, model: Model) -> str:
        return ".".join(model.generalize(self.path)) + ":" + self.method


# ── Source 1: web UI JavaScript ───────────────────────────────────────


def fetch_webui_js(sm: SessionManager) -> dict[str, str]:
    index = sm.session.get(sm.base_url + "/", timeout=sm.timeout).text
    queue = re.findall(r'src="(/[^"]+\.js[^"]*)"', index)
    seen: set[str] = set()
    sources: dict[str, str] = {}
    while queue:
        path = queue.pop(0)
        if path in seen:
            continue
        seen.add(path)
        resp = sm.session.get(sm.base_url + path, timeout=sm.timeout)
        if resp.status_code != 200:
            continue
        sources[path] = resp.text
        queue += re.findall(r'"(/[A-Za-z0-9_/.-]+\.js(?:\?v=\w+)?)"', resp.text)
    return sources


_URL_RE = re.compile(r'/sysbus/((?:[A-Za-z0-9_\-]+/|"\+[^"]{1,80}?\+"/?)*(?:[A-Za-z0-9_\-]+|"\+[^"]{1,80}?\+")):([A-Za-z0-9_]+)"')
_WS_RE = re.compile(r'service:("[^"]*"(?:\+[^,]{1,80}?)?),method:"([A-Za-z0-9_]+)"')
_MAP_KEY_RE = re.compile(r'(\w+):"$')  # the key before a URL, e.g. "create" in a model's url:{create:"/sysbus/..."}


def _parameter_names(js: str, start: int) -> set[str]:
    """Top-level keys of the first ``parameters:{...}`` object shortly after *start*."""
    window = js[start : start + 600]
    stop = min((i for i in (window.find("/sysbus/", 10), window.find("service:", 10)) if i > 0), default=len(window))
    pos = window.find("parameters:{", 0, stop)
    if pos < 0:
        return set()
    body, depth = [], 0
    for ch in window[pos + len("parameters:") :]:
        depth += ch in "{[("
        depth -= ch in "}])"
        if depth == 0:
            break
        body.append(ch if depth == 1 else " ")
    return set(re.findall(r'[{,]\s*"?([A-Za-z_][A-Za-z0-9_]*)"?\s*:', "".join(body)))


def _model_parameters(js: str, start: int) -> set[str]:
    """What a web UI model sends to the create/update URL in its url:{...} map at *start*: its toJSON's parameters."""
    map_end = js.find("}", start)
    model_end = js.find("swc.constructors.", map_end)
    model = js[map_end : model_end if model_end > 0 else map_end + 5000]
    to_json = model.find("toJSON:function")
    return _parameter_names(js, map_end + max(to_json, 0))


def _ws_service_path(expr: str) -> list[str]:
    # Join the pieces first: in "Devices.Device.ETH"+e the variable is part of the segment ETH0, not a segment of its own.
    service = ""
    for piece in expr.split("+"):
        piece = piece.strip()
        if piece.startswith('"') and piece.endswith('"'):
            service += piece.strip('"')
        elif piece:
            service += DYNAMIC
    return [DYNAMIC if DYNAMIC in seg else seg for seg in split_path(service)]


def extract_webui_endpoints(sources: dict[str, str]) -> list[Endpoint]:
    found: dict[tuple[str, str], Endpoint] = {}
    for js in sources.values():
        for m in _URL_RE.finditer(js):
            raw = re.sub(r'"\+[^"]{1,80}?\+"', f"/{DYNAMIC}/", m.group(1))
            path = split_path(raw)
            ep = found.setdefault((".".join(path), m.group(2)), Endpoint(path, m.group(2)))
            key = _MAP_KEY_RE.search(js, max(0, m.start() - 20), m.start())
            if key and key[1] in ("create", "update"):
                ep.params |= _model_parameters(js, m.start())
            elif not key or key[1] not in ("delete", "commit"):  # a model doesn't send its body to these
                ep.params |= _parameter_names(js, m.start())
        for m in _WS_RE.finditer(js):
            path = _ws_service_path(m.group(1))
            if not path or path[0].startswith("com"):  # Swisscom app services, not sysbus objects
                continue
            ep = found.setdefault((".".join(path), m.group(2)), Endpoint(path, m.group(2)))
            ep.params |= _parameter_names(js, m.start())
    return list(found.values())


# ── Source 2: the router's self-description ───────────────────────────


def walk_model(sm: SessionManager, seeds: list[list[str]], max_requests: int) -> Model:
    """Read objects breadth-first, starting from *seeds* (paths without instance placeholders).

    Some parents are hidden even from the admin account (e.g. ``NeMo.Intf``) while their
    instances are readable, so seeds include concrete paths like ``NeMo/Intf/lan``.
    """
    model = Model()
    queue: list[tuple[list[str], tuple[str, ...] | None]] = [(seed, None) for seed in seeds]
    seen: set[str] = set()
    requests_made = 0
    while queue and requests_made < max_requests:
        concrete, general = queue.pop(0)
        if "/".join(concrete) in seen:
            continue
        seen.add("/".join(concrete))
        requests_made += 1
        try:
            node = json.loads(sm.get(f"/sysbus/{'/'.join(concrete)}?_restDepth=1"))
        except Exception:  # unknown object, permission denied, odd response: skip
            continue
        if not isinstance(node, dict) or "objectInfo" not in node:
            continue
        if general is None:  # seed: only the node itself knows whether it is an instance
            is_instance = node["objectInfo"].get("attributes", {}).get("instance")
            general = (*concrete[:-1], DYNAMIC if is_instance else concrete[-1])
        model.add(general, node)
        if sys.stderr.isatty():
            print(f"\r  {requests_made} objects read, {sum(map(len, model.functions.values()))} functions", end="", file=sys.stderr)
        instances = node.get("instances", [])
        for inst in instances:
            model.add((*general, DYNAMIC), inst)
        if instances:
            queue.append(([*concrete, instances[0]["objectInfo"]["key"]], (*general, DYNAMIC)))
        if "templateInfo" in node:
            continue  # template children only exist under instances, reached via the first instance
        for child in node.get("children", []):
            name = child["objectInfo"]["key"]
            queue.append(([*concrete, name], (*general, name)))
    print(f"\r  {requests_made} objects read, {sum(map(len, model.functions.values()))} functions", file=sys.stderr)
    return model


# ── Source 3: the client ──────────────────────────────────────────────


def client_endpoints() -> list[Endpoint]:
    eps = []
    for src in RESOURCES_DIR.glob("*.py"):
        text = src.read_text()
        for path, method in re.findall(r'"/sysbus/([A-Za-z0-9_/{}()\-]+):([A-Za-z0-9_]+)"', text):
            eps.append(Endpoint([DYNAMIC if "{" in s else s for s in split_path(path)], method))
        for service, method in re.findall(r'"service":\s*f?"([^"]+)",\s*"method":\s*"([A-Za-z0-9_]+)"', text):
            if not service.startswith("com"):
                service = re.sub(r"\{[^{}]*\}", DYNAMIC, service)  # f-string placeholders such as {mac.upper()} contain dots
                eps.append(Endpoint([DYNAMIC if "{" in s else s for s in split_path(service)], method))
    return eps


# ── Report ────────────────────────────────────────────────────────────


def render(model: Model, webui: list[Endpoint], client: list[Endpoint], device: dict, js_build: str) -> str:
    webui_keys = {ep.key(model): ep for ep in webui}
    client_keys = {ep.key(model) for ep in client}
    router_keys = {f"{path}:{fn}" for path, fns in model.functions.items() for fn in fns}
    missing = [k for k in webui_keys if k not in client_keys]

    def count(keys) -> tuple[int, int]:
        keys = list(keys)
        return len(keys), sum(is_write(k.split(":")[1]) for k in keys)

    def gen(path: str) -> str:
        return path.replace(DYNAMIC, "{id}")

    today = dt.date.today().isoformat()
    lines = [
        "# Internet Box API map",
        "",
        f"> Generated by `scripts/discover_endpoints.py` on {today} from an {device.get('ModelName', 'unknown model')} "
        f"(firmware {device.get('SoftwareVersion', '?')}, web UI build {js_build}). "
        "Don't edit by hand; re-run the script after firmware updates or on other models.",
        "",
        "`{id}` stands for an instance key, e.g. a device MAC address, an interface name (`lan`, `wl0`) or a pool name (`default`).",
        "",
        "## Summary",
        "",
        "| | Endpoints | Change settings |",
        "| --- | --- | --- |",
    ]
    rows = [("Called by the web interface", webui_keys), ("Implemented in pyinternetbox", client_keys)]
    if router_keys:
        rows.insert(1, ("Functions exposed by the router (self-description)", router_keys))
    rows.append(("Web interface endpoints missing from pyinternetbox", missing))
    for label, keys in rows:
        total, writes = count(keys)
        lines.append(f"| {label} | {total} | {writes} |")
    if model.writable:
        total = sum(map(len, model.writable.values()))
        lines.append(f"| Writable parameters (generic `set`) on {len(model.writable)} objects | {total} | {total} |")

    lines += [
        "",
        "## Endpoints used by the web interface",
        "",
        "Parameters are the names the web UI sends (values omitted).",
        "",
        "- ✏️ changes settings",
        "- ✅ implemented in pyinternetbox",
        "",
        "| Endpoint | ✏️ | ✅ | Parameters |",
        "| --- | --- | --- | --- |",
    ]
    for key in sorted(webui_keys, key=lambda k: (k not in client_keys, not is_write(k.split(":")[1]), k)):
        ep = webui_keys[key]
        params = ", ".join(f"`{p}`" for p in sorted(ep.params))
        lines.append(f"| `{gen(key)}` | {'✏️' if is_write(ep.method) else ''} | {'✅' if key in client_keys else ''} | {params} |")

    if model.functions or model.writable:
        lines += [
            "",
            "## Everything the router exposes",
            "",
            "From the router's self-description.",
            "",
            "- `?` after an argument: optional",
            "- ✏️ changes settings",
            "- 🌐 used by the web interface",
            "- ✅ implemented in pyinternetbox",
            "",
            "Besides the listed functions, every object accepts the generic `get` (read all parameters) and "
            '`set` (`{"parameters": {"parameters": {"Name": value}}}`), which can change any of its writable parameters.',
        ]
        for path in sorted(set(model.functions) | set(model.writable)):
            fns, writable = model.functions.get(path, {}), model.writable.get(path, {})
            if not fns and not writable:
                continue
            lines += ["", f"### `{gen(path)}`", ""]
            for name in sorted(fns):
                key = f"{path}:{name}"
                args = ", ".join(f"{a}{'' if mandatory else '?'}" for a, mandatory in fns[name])
                marks = (" 🌐" if key in webui_keys else "") + (" ✅" if key in client_keys else "")
                lines.append(f"- `{name}({args})`{' ✏️' if is_write(name) else ''}{marks}")
            if writable:
                params = ", ".join(f"`{name}` ({typ})" for name, typ in sorted(writable.items()))
                lines.append(f"- Writable parameters: {params}")

    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("-H", "--host", default=os.getenv("IB_HOSTNAME", "https://internetbox.swisscom.ch"))
    parser.add_argument("-k", "--insecure", action="store_true", help="Skip SSL certificate verification.")
    parser.add_argument("--no-login", action="store_true", help="Only analyse the web UI JavaScript.")
    parser.add_argument("--max-requests", type=int, default=3000, help="Upper bound on objects read from the router.")
    parser.add_argument("-o", "--output", type=Path, default=ROOT / "docs" / "API_MAP.md")
    args = parser.parse_args()

    sm = SessionManager(hostname=args.host, application_name="pyinternetbox-discovery", ssl_verify=False if args.insecure else None)
    with sm:
        print("Downloading web UI JavaScript...", file=sys.stderr)
        sources = fetch_webui_js(sm)
        js_build = next((m.group(1) for p in sources for m in [re.search(r"\?v=(\w+)", p)] if m), "?")
        webui = extract_webui_endpoints(sources)
        client = client_endpoints()
        device = json.loads(sm.post("/sysbus/DeviceInfo:get", {"parameters": {}}, auth_required=False)).get("status", {})
        print(f"  {len(sources)} files, {len(webui)} endpoints", file=sys.stderr)

        model = Model()
        if not args.no_login:
            print("Reading the router's self-description...", file=sys.stderr)
            seeds = [[root] for root in sorted({ep.path[0] for ep in webui + client} | set(EXTRA_ROOTS))]
            for ep in webui + client:
                prefix = ep.path[: ep.path.index(DYNAMIC)] if DYNAMIC in ep.path else ep.path
                if len(prefix) > 1:
                    seeds.append(prefix)
            seeds += [path.split("/") for path in EXTRA_SEEDS]
            model = walk_model(sm, seeds, args.max_requests)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render(model, webui, client, device, js_build))
    print(f"Report written to {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()
