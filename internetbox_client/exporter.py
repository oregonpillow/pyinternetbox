"""Prometheus exporter for the Internet Box.

Provides `InternetBoxCollector`, a custom Prometheus Collector that polls
the router on a background thread. Metrics are published by registering
collection callbacks that call `InternetBoxCollector.update_gauge` (or
`InternetBoxCollector.update_counter`).

Samples that a callback stops reporting (e.g. a device that disconnected) are
dropped after the callback's next successful run, so stale label sets do not
linger until the exporter restarts.

The session authenticates lazily and logs in again by itself when the
router ends it, e.g. after a while without requests.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from typing import TYPE_CHECKING

from prometheus_client.core import CounterMetricFamily, GaugeMetricFamily
from prometheus_client.registry import Collector

if TYPE_CHECKING:
    from internetbox_client import InternetBoxClient

logger = logging.getLogger(__name__)


class _GaugeMetric:
    """Internal representation of a single named Gauge (or Counter) metric.

    Stores one sample per unique label-value combination, together with the
    collection cycle in which it was last set.
    """

    __slots__ = ("name", "description", "label_names", "kind", "owner", "_samples", "_cycles")

    def __init__(self, name: str, description: str, label_names: list[str], kind: str = "gauge", owner: object = None) -> None:
        self.name = name
        self.description = description
        self.label_names = list(label_names)
        self.kind = kind
        # Callback that created this metric; its samples are pruned after that callback runs
        self.owner = owner
        # Map of label-value tuple -> float sample
        self._samples: dict[tuple[str, ...], float] = {}
        # Map of label-value tuple -> collection cycle in which the sample was last set
        self._cycles: dict[tuple[str, ...], int] = {}

    def set(self, value: float, labels: dict[str, str] | None, cycle: int = 0) -> None:
        key = tuple((labels or {}).get(k, "") for k in self.label_names)
        self._samples[key] = float(value)
        self._cycles[key] = cycle

    def prune(self, cycle: int) -> None:
        """Drop samples that were not set during *cycle*."""
        for key in [k for k, c in self._cycles.items() if c != cycle]:
            del self._samples[key]
            del self._cycles[key]

    def to_prometheus(self) -> GaugeMetricFamily | CounterMetricFamily:
        family = CounterMetricFamily if self.kind == "counter" else GaugeMetricFamily
        mf = family(self.name, self.description, labels=self.label_names if self.label_names else None)
        for label_vals, value in self._samples.items():
            mf.add_metric(list(label_vals), value)
        return mf


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
        self._cycle = 0
        self._current_callback: Callable[[InternetBoxCollector], None] | None = None
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
        self._update(name, value, labels, description, kind="gauge")

    def update_counter(self, name: str, value: float, labels: dict[str, str] | None = None, description: str = "") -> None:
        """Create or update a Counter metric sample.

        Use for values that only ever increase (e.g. cumulative byte counts read
        from the router). Pass *name* without the ``_total`` suffix; it is added
        automatically in the ``/metrics`` output.

        Args:
            name: Prometheus metric name (e.g. ``internetbox_wan_rx_bytes``).
            value: Current cumulative value.
            labels: Optional label name → value mapping.
            description: Help string shown in ``/metrics`` output.
        """
        self._update(name, value, labels, description, kind="counter")

    def _update(self, name: str, value: float, labels: dict[str, str] | None, description: str, kind: str) -> None:
        merged = {**self.default_labels, **(labels or {})}
        label_names = sorted(merged.keys()) if merged else []
        with self._lock:
            if name not in self._gauges:
                self._gauges[name] = _GaugeMetric(name, description, label_names, kind=kind, owner=self._current_callback)
            self._gauges[name].set(value, merged, cycle=self._cycle)

    # ── Prometheus Collector protocol ────────────────────────────────

    def describe(self) -> list:  # type: ignore[override]
        # Returning an empty list tells the registry not to validate metric
        # names ahead of time, which avoids issues when metrics are registered
        # dynamically after the collector is added to the registry.
        return []

    def collect(self):  # type: ignore[override]
        """Yield current :class:`GaugeMetricFamily` objects for every metric."""
        with self._lock:
            families = [gauge.to_prometheus() for gauge in self._gauges.values()]
        yield from families

    # ── Background collection loop ───────────────────────────────────

    def _run_callbacks(self) -> None:
        """Invoke all registered callbacks, logging (not raising) errors.

        After a callback succeeds, samples it did not report this cycle are
        removed. If a callback fails, its previous samples are kept.
        """
        with self._lock:
            self._cycle += 1
        for cb in self._callbacks:
            self._current_callback = cb
            try:
                cb(self)
                with self._lock:
                    for gauge in self._gauges.values():
                        if gauge.owner is cb:
                            gauge.prune(self._cycle)
            except Exception:  # noqa: BLE001
                logger.exception("Error in collection callback %r — will retry next cycle.", cb.__name__ if hasattr(cb, "__name__") else cb)
            finally:
                self._current_callback = None

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
