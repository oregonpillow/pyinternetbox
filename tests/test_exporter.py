"""Tests for the Prometheus exporter collector."""

from __future__ import annotations

from unittest.mock import MagicMock

from prometheus_client import CollectorRegistry, generate_latest

from internetbox_client.exporter import InternetBoxCollector


def _metrics_text(collector: InternetBoxCollector) -> str:
    registry = CollectorRegistry()
    registry.register(collector)
    return generate_latest(registry).decode()


class TestInternetBoxCollector:
    def test_gauge_output(self) -> None:
        col = InternetBoxCollector(client=MagicMock())
        col.update_gauge("test_temp_celsius", 42, labels={"sensor": "cpu"}, description="Temp")
        text = _metrics_text(col)
        assert "# TYPE test_temp_celsius gauge" in text
        assert 'test_temp_celsius{sensor="cpu"} 42.0' in text

    def test_counter_output(self) -> None:
        col = InternetBoxCollector(client=MagicMock())
        col.update_counter("test_rx_bytes", 1234, labels={"interface": "veip0"}, description="Bytes")
        text = _metrics_text(col)
        assert "# TYPE test_rx_bytes_total counter" in text
        assert 'test_rx_bytes_total{interface="veip0"} 1234.0' in text

    def test_stale_samples_pruned_after_successful_callback(self) -> None:
        col = InternetBoxCollector(client=MagicMock())
        devices = ["phone", "laptop"]

        @col.register_collector
        def collect(c: InternetBoxCollector) -> None:
            for name in devices:
                c.update_gauge("test_device_up", 1, labels={"Name": name})

        col._run_callbacks()
        assert 'Name="laptop"' in _metrics_text(col)

        devices.remove("laptop")
        col._run_callbacks()
        text = _metrics_text(col)
        assert 'Name="phone"' in text
        assert 'Name="laptop"' not in text

    def test_samples_kept_when_callback_fails(self) -> None:
        col = InternetBoxCollector(client=MagicMock())
        fail = False

        @col.register_collector
        def collect(c: InternetBoxCollector) -> None:
            if fail:
                raise RuntimeError("router unreachable")
            c.update_gauge("test_device_up", 1, labels={"Name": "phone"})

        col._run_callbacks()
        fail = True
        col._run_callbacks()
        assert 'Name="phone"' in _metrics_text(col)

    def test_other_callbacks_not_pruned(self) -> None:
        col = InternetBoxCollector(client=MagicMock())

        @col.register_collector
        def first(c: InternetBoxCollector) -> None:
            c.update_gauge("test_a", 1)

        @col.register_collector
        def second(c: InternetBoxCollector) -> None:
            c.update_gauge("test_b", 2)

        col._run_callbacks()
        text = _metrics_text(col)
        assert "test_a 1.0" in text
        assert "test_b 2.0" in text

    def test_samples_set_outside_callbacks_never_pruned(self) -> None:
        col = InternetBoxCollector(client=MagicMock())
        col.update_gauge("test_static", 7)
        col._run_callbacks()
        col._run_callbacks()
        assert "test_static 7.0" in _metrics_text(col)
