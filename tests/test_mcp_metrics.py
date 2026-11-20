"""Tests for the MCP usage metrics: the sender in `ibox mcp` and the collector behind `ibox mcp-exporter`."""

from __future__ import annotations

import http.client
import json
import logging
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Iterator
from typing import Any
from unittest.mock import patch

import pytest
import requests

from internetbox_client.mcp_server.exporter import MAX_BODY_BYTES, EventCollector, InvalidEvent, check_event, make_server
from internetbox_client.mcp_server.metrics import MetricsSender, events_url

EVENT = {
    "tool": "call_router_function",
    "function": "wifi.summary",
    "action": "read",
    "outcome": "ok",
    "duration_seconds": 0.25,
    "client": "opencode",
    "server_version": "1.2.3",
}


# ── Sender ──────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "url,expected",
    [
        ("http://127.0.0.1:9102", "http://127.0.0.1:9102/events"),
        ("http://127.0.0.1:9102/", "http://127.0.0.1:9102/events"),
        ("127.0.0.1:9102", "http://127.0.0.1:9102/events"),
        ("https://metrics.example.org/mcp/events", "https://metrics.example.org/mcp/events"),
    ],
)
def test_events_url(url: str, expected: str) -> None:
    assert events_url(url) == expected


@pytest.mark.parametrize("url", ["ftp://127.0.0.1", "http://", ""])
def test_events_url_rejects(url: str) -> None:
    with pytest.raises(ValueError, match="must look like http://127.0.0.1:9102"):
        events_url(url)


def test_sender_posts_events_in_batches() -> None:
    posted: list[Any] = []
    with patch.object(requests.Session, "post", side_effect=lambda url, json, timeout: posted.append((url, json)) or _ok()):
        sender = MetricsSender("http://127.0.0.1:9102")
        for n in range(3):
            sender.send({**EVENT, "duration_seconds": n})
        sender.close()
    assert [event["duration_seconds"] for _, body in posted for event in body["events"]] == [0, 1, 2]
    assert all(url == "http://127.0.0.1:9102/events" for url, _ in posted)


def test_sender_never_raises_and_warns_once(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING), patch.object(requests.Session, "post", side_effect=requests.ConnectionError("refused")) as post:
        sender = MetricsSender("http://127.0.0.1:9102")
        sender.send(EVENT)
        _wait_for(lambda: post.call_count == 1)
        sender.send(EVENT)
        sender.close()
    assert post.call_count == 2
    warnings = [r.getMessage() for r in caplog.records if r.name == "internetbox_client.mcp_server.metrics"]
    assert warnings == ["Dropping MCP metrics events for http://127.0.0.1:9102/events: refused. Is ibox mcp-exporter running?"]


def test_sender_drops_events_when_the_queue_is_full(caplog: pytest.LogCaptureFixture) -> None:
    release = threading.Event()
    with caplog.at_level(logging.WARNING), patch.object(requests.Session, "post", side_effect=lambda *a, **k: release.wait() or _ok()):
        sender = MetricsSender("http://127.0.0.1:9102", max_queued=2, max_batch=1)
        started = time.monotonic()
        for _ in range(10):
            sender.send(EVENT)
        assert time.monotonic() - started < 0.5  # send() never waits
        release.set()
        sender.close()
    assert any("too many events are waiting" in r.getMessage() for r in caplog.records)


def test_close_gives_up_when_the_collector_hangs() -> None:
    release = threading.Event()
    with patch.object(requests.Session, "post", side_effect=lambda *a, **k: release.wait() or _ok()):
        sender = MetricsSender("http://127.0.0.1:9102", max_queued=1, max_batch=1)
        sender.send(EVENT)
        _wait_for(lambda: sender._queue.empty())
        sender.send(EVENT)  # fills the queue while the first one hangs
        started = time.monotonic()
        sender.close(timeout=0.2)
        assert time.monotonic() - started < 1
        release.set()


def _ok() -> requests.Response:
    response = requests.Response()
    response.status_code = 200
    return response


def _wait_for(condition: Any, timeout: float = 2) -> None:
    deadline = time.monotonic() + timeout
    while not condition():
        assert time.monotonic() < deadline, "timed out"
        time.sleep(0.01)


# ── Collector ───────────────────────────────────────────────────────────


def test_check_event() -> None:
    assert check_event(EVENT) == {
        "tool": "call_router_function",
        "function": "wifi.summary",
        "action": "read",
        "outcome": "ok",
        "client": "opencode",
        "duration": 0.25,
    }
    assert check_event({**EVENT, "function": None, "client": None})["client"] == "unknown"
    assert check_event({**EVENT, "client": "Visual Studio Code"})["client"] == "Visual Studio Code"
    assert check_event({**EVENT, "client": "x\ny"})["client"] == "other"


@pytest.mark.parametrize(
    "change,reason",
    [
        ({"tool": "Bad Tool"}, "invalid tool"),
        ({"tool": None}, "invalid tool"),
        ({"function": "wifi"}, "invalid function"),
        ({"action": "delete"}, "unknown action"),
        ({"outcome": "maybe"}, "unknown outcome"),
        ({"duration_seconds": -1}, "invalid duration_seconds"),
        ({"duration_seconds": float("nan")}, "invalid duration_seconds"),
        ({"duration_seconds": True}, "invalid duration_seconds"),
        ({"client": 5}, "invalid client"),
        ({"server_version": "1 2"}, "invalid server_version"),
    ],
)
def test_check_event_rejects(change: dict, reason: str) -> None:
    with pytest.raises(InvalidEvent, match=reason):
        check_event({**EVENT, **change})
    with pytest.raises(InvalidEvent, match="not an object"):
        check_event(["tool"])


def _value(collector: EventCollector, name: str, labels: dict | None = None) -> float | None:
    return collector.registry.get_sample_value(name, labels or {})


def test_collector_counts_events() -> None:
    collector = EventCollector()
    assert collector.add([EVENT, EVENT, {**EVENT, "outcome": "bad"}]) == (2, 1)
    labels = {"tool": "call_router_function", "function": "wifi.summary", "action": "read", "outcome": "ok", "client": "opencode"}
    assert _value(collector, "ibox_mcp_tool_calls_total", labels) == 2
    assert _value(collector, "ibox_mcp_tool_call_duration_seconds_count", {"tool": "call_router_function"}) == 2
    assert _value(collector, "ibox_mcp_events_received_total") == 3
    assert _value(collector, "ibox_mcp_events_rejected_total", {"reason": "unknown outcome"}) == 1


def test_collector_caps_the_series() -> None:
    collector = EventCollector(max_series=2)
    events = [{**EVENT, "tool": f"tool_{n}"} for n in range(4)]
    assert collector.add(events) == (2, 2)
    assert collector.add([events[0]]) == (1, 0)  # known series are still counted
    assert _value(collector, "ibox_mcp_events_rejected_total", {"reason": "too many series"}) == 2


def test_collector_wants_a_list() -> None:
    with pytest.raises(InvalidEvent, match="expected"):
        EventCollector().add({"tool": "x"})


@pytest.fixture()
def collector_url() -> Iterator[tuple[str, EventCollector]]:
    collector = EventCollector()
    server = make_server("127.0.0.1", 0, collector)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}", collector
    server.shutdown()
    server.server_close()


def _request(url: str, data: bytes | None = None, headers: dict | None = None) -> tuple[int, str]:
    request = urllib.request.Request(url, data=data, headers=headers or {}, method="POST" if data is not None else "GET")
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status, response.read().decode()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode()


def test_collector_http(collector_url: tuple[str, EventCollector]) -> None:
    url, collector = collector_url
    assert _request(f"{url}/events", json.dumps({"events": [EVENT]}).encode()) == (200, '{"counted": 1, "rejected": 0}')
    status, metrics = _request(f"{url}/metrics")
    assert status == 200
    assert (
        'ibox_mcp_tool_calls_total{action="read",client="opencode",function="wifi.summary",outcome="ok",tool="call_router_function"} 1.0'
        in metrics
    )
    assert _request(url)[0] == 200
    assert _request(f"{url}/nope")[0] == 404
    assert _request(f"{url}/nope", b"{}")[0] == 404
    assert _request(f"{url}/events", b"not json") == (400, '{"error": "invalid JSON"}')
    assert _request(f"{url}/events", b'{"events": 1}') == (400, '{"error": "expected {\\"events\\": [...]}"}')
    assert _value(collector, "ibox_mcp_events_rejected_total", {"reason": "invalid request"}) == 2


def _raw_post(url: str, headers: dict[str, str]) -> int:
    """POST /events with these headers and no body."""
    connection = http.client.HTTPConnection(url.removeprefix("http://"), timeout=5)
    connection.putrequest("POST", "/events")
    for name, value in headers.items():
        connection.putheader(name, value)
    connection.endheaders()
    status = connection.getresponse().status
    connection.close()
    return status


def test_collector_limits_the_body(collector_url: tuple[str, EventCollector]) -> None:
    url, _ = collector_url
    assert _raw_post(url, {"Content-Length": str(MAX_BODY_BYTES + 1)}) == 413
    assert _raw_post(url, {}) == 411


def test_sender_to_collector(collector_url: tuple[str, EventCollector]) -> None:
    url, collector = collector_url
    sender = MetricsSender(url)
    sender.send(EVENT)
    sender.send({**EVENT, "outcome": "declined"})
    sender.close()
    assert _value(collector, "ibox_mcp_events_received_total") == 2
