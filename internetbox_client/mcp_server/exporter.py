"""The collector behind `ibox mcp-exporter`: adds up the usage events from `ibox mcp` servers and serves them to Prometheus.

AI apps start a short-lived `ibox mcp` process per project or window, which Prometheus can't scrape. Each one sends its
events here instead (see metrics.MetricsSender), with HTTP POST to /events: {"events": [{"tool": "list_devices", ...}]}.
"""

from __future__ import annotations

import json
import logging
import math
import re
import threading
from collections.abc import Mapping
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, Counter, Histogram, generate_latest

from internetbox_client.mcp_server.metrics import EVENTS_PATH

logger = logging.getLogger(__name__)

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 9102
MAX_BODY_BYTES = 1_000_000
# Label combinations of ibox_mcp_tool_calls_total kept at most, so junk events can't flood Prometheus.
MAX_SERIES = 2000

ACTIONS = frozenset({"read", "write", "disruptive"})
OUTCOMES = frozenset({"ok", "error", "refused", "declined"})
_TOOL = re.compile(r"[a-z][a-z0-9_]{0,63}")
_FUNCTION = re.compile(r"[a-z][a-z0-9_]{0,31}\.[a-z][a-z0-9_]{0,63}")
_CLIENT = re.compile(r"[\w .()/@+-]{1,64}")
_VERSION = re.compile(r"[\w.+-]{1,64}")
_BUCKETS = (0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60, 120)


class InvalidEvent(ValueError):
    """An event the collector doesn't count. The message is the reason, e.g. "unknown outcome"."""


def check_event(event: object) -> dict[str, Any]:
    """The event's labels and duration, after checking them.

    Raises:
        InvalidEvent: if a field is missing or invalid.
    """
    if not isinstance(event, Mapping):
        raise InvalidEvent("not an object")
    tool, function, action, outcome = (event.get(key) for key in ("tool", "function", "action", "outcome"))
    if not isinstance(tool, str) or not _TOOL.fullmatch(tool):
        raise InvalidEvent("invalid tool")
    if function is None:
        function = ""
    if not isinstance(function, str) or (function and not _FUNCTION.fullmatch(function)):
        raise InvalidEvent("invalid function")
    if action not in ACTIONS:
        raise InvalidEvent("unknown action")
    if outcome not in OUTCOMES:
        raise InvalidEvent("unknown outcome")
    duration = event.get("duration_seconds")
    if isinstance(duration, bool) or not isinstance(duration, int | float) or not math.isfinite(duration) or not 0 <= duration <= 86400:
        raise InvalidEvent("invalid duration_seconds")
    client = event.get("client")
    if client is not None and not isinstance(client, str):
        raise InvalidEvent("invalid client")
    # Apps name themselves, e.g. "opencode" or "Visual Studio Code". Odd names are counted, as "other".
    client = (client or "").strip()
    client = client if _CLIENT.fullmatch(client) else "other" if client else "unknown"
    version = event.get("server_version")
    if version is not None and (not isinstance(version, str) or not _VERSION.fullmatch(version)):
        raise InvalidEvent("invalid server_version")
    return {"tool": tool, "function": function, "action": action, "outcome": outcome, "client": client, "duration": float(duration)}


class EventCollector:
    """Counts the events from MCP servers, in its own Prometheus registry."""

    def __init__(self, max_series: int = MAX_SERIES) -> None:
        self.registry = CollectorRegistry()
        self._max_series = max_series
        self._series: set[tuple[str, ...]] = set()
        self._lock = threading.Lock()
        self.calls = Counter(
            "ibox_mcp_tool_calls",
            "MCP tool calls, by tool, library function, what it does to the router, outcome and AI app.",
            ["tool", "function", "action", "outcome", "client"],
            registry=self.registry,
        )
        self.duration = Histogram(
            "ibox_mcp_tool_call_duration_seconds", "How long MCP tool calls took.", ["tool"], buckets=_BUCKETS, registry=self.registry
        )
        self.received = Counter("ibox_mcp_events_received", "Events received from MCP servers.", registry=self.registry)
        self.rejected = Counter("ibox_mcp_events_rejected", "Events not counted, by reason.", ["reason"], registry=self.registry)

    def add(self, events: object) -> tuple[int, int]:
        """Count a batch of events.

        Returns:
            tuple: how many events were counted and how many were rejected.
        """
        if not isinstance(events, list):
            raise InvalidEvent('expected {"events": [...]}')
        counted = 0
        for event in events:
            self.received.inc()
            try:
                checked = check_event(event)
            except InvalidEvent as exc:
                self.rejected.labels(reason=str(exc)).inc()
                continue
            labels = (checked["tool"], checked["function"], checked["action"], checked["outcome"], checked["client"])
            with self._lock:
                if labels not in self._series and len(self._series) >= self._max_series:
                    self.rejected.labels(reason="too many series").inc()
                    continue
                self._series.add(labels)
            self.calls.labels(*labels).inc()
            self.duration.labels(tool=checked["tool"]).observe(checked["duration"])
            counted += 1
        return counted, len(events) - counted


def _handler(collector: EventCollector) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = "ibox-mcp-exporter"

        def do_GET(self) -> None:
            path = self.path.split("?", 1)[0]
            if path == "/metrics":
                self._reply(200, generate_latest(collector.registry), CONTENT_TYPE_LATEST)
            elif path == "/":
                self._reply(200, b"ibox mcp-exporter: metrics at /metrics, events to POST /events\n", "text/plain; charset=utf-8")
            else:
                self._reply(404, b"Not found\n", "text/plain; charset=utf-8")

        def do_POST(self) -> None:
            if self.path.split("?", 1)[0] != EVENTS_PATH:
                self._reply(404, b"Not found\n", "text/plain; charset=utf-8")
                return
            try:
                length = int(self.headers.get("Content-Length", ""))
            except ValueError:
                self._json(411, {"error": "Content-Length required"})
                return
            if not 0 <= length <= MAX_BODY_BYTES:
                self._json(413, {"error": f"at most {MAX_BODY_BYTES} bytes"})
                return
            try:
                body = json.loads(self.rfile.read(length))
                counted, rejected = collector.add(body.get("events") if isinstance(body, dict) else None)
            except (ValueError, UnicodeDecodeError) as exc:  # InvalidEvent is a ValueError, and so is invalid JSON
                collector.rejected.labels(reason="invalid request").inc()
                self._json(400, {"error": str(exc) if isinstance(exc, InvalidEvent) else "invalid JSON"})
                return
            self._json(200, {"counted": counted, "rejected": rejected})

        def _json(self, status: int, body: dict) -> None:
            self._reply(status, json.dumps(body).encode(), "application/json")

        def _reply(self, status: int, body: bytes, content_type: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 - the base class's name
            logger.debug("%s - %s", self.address_string(), format % args)

    return Handler


def make_server(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT, collector: EventCollector | None = None) -> ThreadingHTTPServer:
    """An HTTP server for the collector: GET /metrics for Prometheus, POST /events for `ibox mcp`. Call serve_forever() on it."""
    server = ThreadingHTTPServer((host, port), _handler(collector or EventCollector()))
    server.daemon_threads = True
    return server
