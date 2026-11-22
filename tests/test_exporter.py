"""Tests for the Prometheus exporter collector."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

from prometheus_client import CollectorRegistry, generate_latest

from internetbox_client.exporter import InternetBoxCollector
from internetbox_client.metrics import register_metrics


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


# Shape of DNS/Server:getMetrics on an Internet Box 4, with a second DNS server added.
_DNS_METRICS = {
    "dns_cache_inserted": 0,
    "dns_cache_live_freed": 0,
    "dns_queries_forwarded": 1484,
    "dns_auth_answered": 0,
    "dns_local_answered": 134574,
    "fallback": 0,
    "192.168.0.53": {"dns_queries_sent": 1484, "dns_queries_failed_or_retried": 2, "dns_queries_failed": 0, "dns_queries_retried": 2},
    "9.9.9.9": {"dns_queries_sent": 10, "dns_queries_failed_or_retried": 1, "dns_queries_failed": 1, "dns_queries_retried": 0},
}


class TestDnsQueryMetrics:
    @staticmethod
    def _collect(status: dict) -> str:
        client = MagicMock()
        client.devices.get.return_value = json.dumps({"status": []})
        client.dns.metrics.return_value = json.dumps({"status": status})
        col = InternetBoxCollector(client=client)
        register_metrics(col, client)
        col._callbacks = [cb for cb in col._callbacks if cb.__name__ == "collect_dns_queries"]
        col._run_callbacks()
        return _metrics_text(col)

    def test_totals_are_counters(self) -> None:
        text = self._collect(_DNS_METRICS)
        assert "# TYPE internetbox_dns_local_answered_total counter" in text
        assert "internetbox_dns_local_answered_total 134574.0" in text
        assert "internetbox_dns_queries_forwarded_total 1484.0" in text
        assert "internetbox_dns_cache_inserted_total 0.0" in text
        assert "internetbox_dns_cache_live_freed_total 0.0" in text

    def test_per_server_counters(self) -> None:
        text = self._collect(_DNS_METRICS)
        assert 'internetbox_dns_queries_sent_total{server="192.168.0.53"} 1484.0' in text
        assert 'internetbox_dns_queries_retried_total{server="192.168.0.53"} 2.0' in text
        assert 'internetbox_dns_queries_sent_total{server="9.9.9.9"} 10.0' in text
        assert 'internetbox_dns_queries_failed_total{server="9.9.9.9"} 1.0' in text

    def test_unclear_and_combined_counts_not_exported(self) -> None:
        text = self._collect(_DNS_METRICS)
        assert "auth_answered" not in text
        assert "fallback" not in text
        assert "failed_or_retried" not in text

    def test_missing_counts_skipped(self) -> None:
        text = self._collect({"dns_queries_forwarded": 5})
        assert "internetbox_dns_queries_forwarded_total 5.0" in text
        assert "internetbox_dns_local_answered" not in text
        assert "internetbox_dns_queries_sent" not in text


def test_boots_are_a_counter() -> None:
    client = MagicMock()
    client.devices.get.return_value = json.dumps({"status": []})
    # Shape of NMC/Reboot:get on an Internet Box 4.
    client.nmc.reboot_info.return_value = json.dumps(
        {"status": {"Flush": False, "BootCounter": 33, "WatchdogRebootCounter": 20, "RebootSinceLastUpgrade": 1}}
    )
    col = InternetBoxCollector(client=client)
    register_metrics(col, client)
    col._callbacks = [cb for cb in col._callbacks if cb.__name__ == "collect_boots"]
    col._run_callbacks()
    text = _metrics_text(col)
    assert "# TYPE internetbox_boots_total counter" in text
    assert "internetbox_boots_total 33.0" in text
