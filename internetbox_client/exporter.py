"""Prometheus exporter for the Internet Box.

Provides `InternetBoxCollector`, a custom Prometheus Collector that polls
the router on a background thread. Metrics are published by registering
collection callbacks that call `InternetBoxCollector.update_gauge`.

The session authenticates lazily and re-authenticates automatically if a
401 is received mid-scrape.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from typing import TYPE_CHECKING

from prometheus_client.core import GaugeMetricFamily
from prometheus_client.registry import Collector

if TYPE_CHECKING:
    from internetbox_client import InternetBoxClient

logger = logging.getLogger(__name__)


class _GaugeMetric:
    """Internal representation of a single named Gauge metric.

    Stores one sample per unique label-value combination.
    """

    __slots__ = ("name", "description", "label_names", "_samples")

    def __init__(self, name: str, description: str, label_names: list[str]) -> None:
        self.name = name
        self.description = description
        self.label_names = list(label_names)
        # Map of label-value tuple -> float sample
        self._samples: dict[tuple[str, ...], float] = {}

    def set(self, value: float, labels: dict[str, str] | None) -> None:
        key = tuple((labels or {}).get(k, "") for k in self.label_names)
        self._samples[key] = float(value)

    def to_prometheus(self) -> GaugeMetricFamily:
        gmf = GaugeMetricFamily(self.name, self.description, labels=self.label_names if self.label_names else None)
        for label_vals, value in self._samples.items():
            gmf.add_metric(list(label_vals), value)
        return gmf


class InternetBoxCollector(Collector):
    """Prometheus custom collector for the Internet Box.

    Maintains a thread-safe Gauge registry. Registered callbacks are invoked
    every `interval` seconds on a background thread so scrapes always see
    fresh data.

    Args:
        client: An `InternetBoxClient` instance. The collector does not manage
            its lifecycle — callers must call `client.close()` on shutdown.
        interval: Seconds between collection cycles. Defaults to 30.
    """

    def __init__(self, client: InternetBoxClient, interval: int = 30) -> None:
        self._client = client
        self._interval = interval
        self._lock = threading.Lock()
        self._gauges: dict[str, _GaugeMetric] = {}
        self._callbacks: list[Callable[[InternetBoxCollector], None]] = []
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._run, name="ib-exporter", daemon=True)
        self.default_labels: dict[str, str] = {}

    # ── Metric registration ──────────────────────────────────────────

    def register_collector(self, fn: Callable[[InternetBoxCollector], None]) -> Callable[[InternetBoxCollector], None]:
        """Register a collection callback (also usable as a decorator).

        The callback receives this collector as its only argument and should
        call `update_gauge` to publish values. Exceptions are caught and
        logged so the collection loop continues.

        Args:
            fn: Callable that accepts this `InternetBoxCollector` instance.

        Returns:
            The original function, unchanged.

        Example::

            @collector.register_collector
            def my_metrics(col):
                col.update_gauge("my_metric", 42.0)
        """
        self._callbacks.append(fn)
        return fn

    # ── Metric update API ────────────────────────────────────────────

    def update_gauge(self, name: str, value: float, labels: dict[str, str] | None = None, description: str = "") -> None:
        """Create or update a Gauge metric sample.

        Args:
            name: Prometheus metric name (e.g. ``internetbox_wifi_noise_dbm``).
                Must be stable across calls for the same logical metric.
            value: Current numeric value.
            labels: Optional label name → value mapping. Label names are fixed
                on first call; only values may change on subsequent calls.
            description: Help string shown in ``/metrics`` output. Only used
                on first registration; later values are ignored.
        """
        merged = {**self.default_labels, **(labels or {})}
        label_names = sorted(merged.keys()) if merged else []
        with self._lock:
            if name not in self._gauges:
                self._gauges[name] = _GaugeMetric(name, description, label_names)
            self._gauges[name].set(value, merged)

    # ── Prometheus Collector protocol ────────────────────────────────

    def describe(self) -> list:  # type: ignore[override]
        # Returning an empty list tells the registry not to validate metric
        # names ahead of time, which avoids issues when metrics are registered
        # dynamically after the collector is added to the registry.
        return []

    def collect(self):  # type: ignore[override]
        """Yield current :class:`GaugeMetricFamily` objects for every metric."""
        with self._lock:
            gauges = list(self._gauges.values())
        for gauge in gauges:
            yield gauge.to_prometheus()

    # ── Background collection loop ───────────────────────────────────

    def _run_callbacks(self) -> None:
        """Invoke all registered callbacks, logging (not raising) errors."""
        for cb in self._callbacks:
            try:
                cb(self)
            except Exception:  # noqa: BLE001
                logger.exception("Error in collection callback %r — will retry next cycle.", cb.__name__ if hasattr(cb, "__name__") else cb)
                # If the session was invalidated (HTTP 401), reset the context
                # so the next cycle triggers automatic re-authentication.
                try:
                    self._client._sm.context_id = None  # type: ignore[attr-defined]
                except AttributeError:
                    pass

    def _run(self) -> None:
        """Background thread: collect immediately, then repeat every interval."""
        self._run_callbacks()
        while not self._stop_event.wait(self._interval):
            self._run_callbacks()

    def start(self) -> None:
        """Start the background collection thread.

        Call after all callbacks are registered so the first cycle runs
        with the complete set.
        """
        self._thread.start()

    def stop(self) -> None:
        """Signal the background thread to stop and wait for it to exit."""
        self._stop_event.set()
        self._thread.join(timeout=max(self._interval, 10))
