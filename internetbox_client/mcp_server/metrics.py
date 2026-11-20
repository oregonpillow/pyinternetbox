"""Usage events from `ibox mcp` to `ibox mcp-exporter`, sent in the background so tool calls never wait for them."""

from __future__ import annotations

import logging
import queue
import threading
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import requests

logger = logging.getLogger(__name__)

EVENTS_PATH = "/events"
_STOP = object()


def events_url(url: str) -> str:
    """The collector's events endpoint for a --metrics-url, e.g. "http://127.0.0.1:9102" -> "http://127.0.0.1:9102/events".

    Raises:
        ValueError: if *url* isn't an http(s) URL.
    """
    parts = urlsplit(url.strip() if "://" in url else f"http://{url.strip()}")
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise ValueError(f"The metrics URL must look like http://127.0.0.1:9102, got {url!r}")
    path = parts.path if parts.path not in ("", "/") else EVENTS_PATH
    return urlunsplit((parts.scheme, parts.netloc, path, parts.query, ""))


class MetricsSender:
    """Sends events to the collector with HTTP POST, from a background thread.

    send() never blocks and never raises. When the collector is down or slow, or the queue is full, events are dropped
    rather than retried, and a warning is logged once (to stderr: stdout carries the MCP messages).
    """

    def __init__(self, url: str, timeout: float = 1.0, max_queued: int = 1000, max_batch: int = 100) -> None:
        self.url = events_url(url)
        self._timeout = timeout
        self._max_batch = max_batch
        self._queue: queue.Queue[Any] = queue.Queue(maxsize=max_queued)
        self._session = requests.Session()
        self._warned = False
        self._thread = threading.Thread(target=self._run, name="ibox-mcp-metrics", daemon=True)
        self._thread.start()

    def send(self, event: dict[str, Any]) -> None:
        """Queue an event for sending, or drop it if the queue is full."""
        try:
            self._queue.put_nowait(event)
        except queue.Full:
            self._warn("too many events are waiting")

    def close(self, timeout: float = 1.0) -> None:
        """Send the events still queued, waiting at most *timeout* seconds, then stop."""
        try:
            self._queue.put(_STOP, timeout=timeout)
        except queue.Full:
            return
        self._thread.join(timeout)
        self._session.close()

    def _run(self) -> None:
        while True:
            batch = [self._queue.get()]
            while batch[-1] is not _STOP and len(batch) < self._max_batch:
                try:
                    batch.append(self._queue.get_nowait())
                except queue.Empty:
                    break
            events = [event for event in batch if event is not _STOP]
            if events:
                self._post(events)
            if batch[-1] is _STOP:
                return

    def _post(self, events: list[dict[str, Any]]) -> None:
        try:
            response = self._session.post(self.url, json={"events": events}, timeout=self._timeout)
            response.raise_for_status()
        except Exception as exc:  # noqa: BLE001 - metrics must never stop the server, whatever goes wrong
            self._warn(str(exc))

    def _warn(self, reason: str) -> None:
        if not self._warned:
            self._warned = True
            logger.warning("Dropping MCP metrics events for %s: %s. Is ibox mcp-exporter running?", self.url, reason)
