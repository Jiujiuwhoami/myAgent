"""Prometheus 监控集成"""

import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, Optional


class MetricType(Enum):
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"


@dataclass
class MetricConfig:
    name: str
    description: str
    metric_type: MetricType
    labels: list[str] = field(default_factory=list)
    buckets: Optional[list[float]] = None


class Counter:
    def __init__(self, name: str, description: str, labels: list[str] = None):
        self.name = name
        self.description = description
        self.labels = labels or []
        self._values: Dict[str, float] = defaultdict(float)
        self._lock = threading.Lock()

    def inc(self, value: float = 1, **label_values):
        key = self._labels_to_key(label_values)
        with self._lock:
            self._values[key] += value

    def get(self, **label_values) -> float:
        key = self._labels_to_key(label_values)
        return self._values.get(key, 0)

    def _labels_to_key(self, label_values: Dict) -> str:
        if not self.labels:
            return "_global_"
        sorted_labels = sorted(self.labels)
        return "|".join(f"{k}={label_values.get(k, 'unknown')}" for k in sorted_labels)

    def collect(self) -> Dict:
        return {
            "name": self.name,
            "description": self.description,
            "type": "counter",
            "values": dict(self._values),
        }


class Gauge:
    def __init__(self, name: str, description: str, labels: list[str] = None):
        self.name = name
        self.description = description
        self.labels = labels or []
        self._values: Dict[str, float] = defaultdict(float)
        self._lock = threading.Lock()

    def set(self, value: float, **label_values):
        key = self._labels_to_key(label_values)
        with self._lock:
            self._values[key] = value

    def inc(self, value: float = 1, **label_values):
        key = self._labels_to_key(label_values)
        with self._lock:
            self._values[key] += value

    def dec(self, value: float = 1, **label_values):
        key = self._labels_to_key(label_values)
        with self._lock:
            self._values[key] -= value

    def get(self, **label_values) -> float:
        key = self._labels_to_key(label_values)
        return self._values.get(key, 0)

    def _labels_to_key(self, label_values: Dict) -> str:
        if not self.labels:
            return "_global_"
        sorted_labels = sorted(self.labels)
        return "|".join(f"{k}={label_values.get(k, 'unknown')}" for k in sorted_labels)

    def collect(self) -> Dict:
        return {
            "name": self.name,
            "description": self.description,
            "type": "gauge",
            "values": dict(self._values),
        }


class Histogram:
    def __init__(
        self,
        name: str,
        description: str,
        labels: list[str] = None,
        buckets: list[float] = None,
    ):
        self.name = name
        self.description = description
        self.labels = labels or []
        self.buckets = buckets or [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
        self._counts: Dict[str, list[int]] = defaultdict(lambda: [0] * (len(self.buckets) + 1))
        self._sums: Dict[str, float] = defaultdict(float)
        self._totals: Dict[str, int] = defaultdict(int)
        self._lock = threading.Lock()

    def observe(self, value: float, **label_values):
        key = self._labels_to_key(label_values)
        with self._lock:
            self._sums[key] += value
            self._totals[key] += 1
            for i, bucket in enumerate(self.buckets):
                if value <= bucket:
                    self._counts[key][i] += 1
            self._counts[key][-1] += 1

    def _labels_to_key(self, label_values: Dict) -> str:
        if not self.labels:
            return "_global_"
        sorted_labels = sorted(self.labels)
        return "|".join(f"{k}={label_values.get(k, 'unknown')}" for k in sorted_labels)

    def collect(self) -> Dict:
        return {
            "name": self.name,
            "description": self.description,
            "type": "histogram",
            "buckets": self.buckets,
            "counts": dict(self._counts),
            "sums": dict(self._sums),
            "totals": dict(self._totals),
        }


class Timer:
    def __init__(self, histogram: Histogram, **label_values):
        self.histogram = histogram
        self.label_values = label_values
        self.start_time = None

    def __enter__(self):
        self.start_time = time.time()
        return self

    def __exit__(self, *args):
        duration = time.time() - self.start_time
        self.histogram.observe(duration, **self.label_values)


class PrometheusMetrics:
    """
    Prometheus 指标收集器

    提供应用级监控指标

    示例:
        metrics = PrometheusMetrics()

        # 计数器
        metrics.counter("http_requests_total", "Total HTTP requests", ["method", "endpoint"])
        metrics.inc("http_requests_total", method="GET", endpoint="/api/users")

        # 仪表
        metrics.gauge("active_users", "Number of active users")
        metrics.set("active_users", 42)

        # 直方图
        metrics.histogram("request_duration_seconds", "Request duration", ["endpoint"])
        with metrics.timer("request_duration_seconds", endpoint="/api/users"):
            do_work()

        # 获取所有指标 (Prometheus 格式)
        output = metrics.output()
    """

    def __init__(self):
        self._counters: Dict[str, Counter] = {}
        self._gauges: Dict[str, Gauge] = {}
        self._histograms: Dict[str, Histogram] = {}
        self._lock = threading.Lock()

    def counter(self, name: str, description: str = "", labels: list[str] = None) -> Counter:
        with self._lock:
            if name not in self._counters:
                self._counters[name] = Counter(name, description, labels)
            return self._counters[name]

    def gauge(self, name: str, description: str = "", labels: list[str] = None) -> Gauge:
        with self._lock:
            if name not in self._gauges:
                self._gauges[name] = Gauge(name, description, labels)
            return self._gauges[name]

    def histogram(
        self,
        name: str,
        description: str = "",
        labels: list[str] = None,
        buckets: list[float] = None,
    ) -> Histogram:
        with self._lock:
            if name not in self._histograms:
                self._histograms[name] = Histogram(name, description, labels, buckets)
            return self._histograms[name]

    def inc(self, name: str, value: float = 1, **labels):
        if name in self._counters:
            self._counters[name].inc(value, **labels)

    def set(self, name: str, value: float, **labels):
        if name in self._gauges:
            self._gauges[name].set(value, **labels)

    def observe(self, name: str, value: float, **labels):
        if name in self._histograms:
            self._histograms[name].observe(value, **labels)

    def timer(self, name: str, **labels) -> Timer:
        if name in self._histograms:
            return Timer(self._histograms[name], **labels)
        return Timer(self.histogram(name), **labels)

    def output(self) -> str:
        lines = []

        for counter in self._counters.values():
            data = counter.collect()
            lines.append(f"# HELP {data['name']} {data['description']}")
            lines.append(f"# TYPE {data['name']} {data['type']}")
            for key, value in data["values"].items():
                if key == "_global_":
                    lines.append(f"{data['name']} {value}")
                else:
                    label_str = ",".join(key.split("|"))
                    lines.append(f"{data['name']}{{{label_str}}} {value}")

        for gauge in self._gauges.values():
            data = gauge.collect()
            lines.append(f"# HELP {data['name']} {data['description']}")
            lines.append(f"# TYPE {data['name']} {data['type']}")
            for key, value in data["values"].items():
                if key == "_global_":
                    lines.append(f"{data['name']} {value}")
                else:
                    label_str = ",".join(key.split("|"))
                    lines.append(f"{data['name']}{{{label_str}}} {value}")

        for hist in self._histograms.values():
            data = hist.collect()
            lines.append(f"# HELP {data['name']} {data['description']}")
            lines.append(f"# TYPE {data['name']} {data['type']}")
            for key in data["counts"].keys():
                label_str = ",".join(key.split("|")) if key != "_global_" else ""
                label_prefix = f"{label_str}," if label_str else ""
                for i, bucket in enumerate(data["buckets"]):
                    bucket_value = data["counts"][key][i]
                    lines.append(
                        f"{data['name']}_bucket{{{label_prefix}le=\"{bucket}\"}} {bucket_value}"
                    )
                lines.append(
                    f"{data['name']}_bucket{{{label_prefix}le=\"+Inf\"}} {data['counts'][key][-1]}"
                )
                lines.append(f"{data['name']}_sum{{{label_str}}} {data['sums'].get(key, 0)}")
                lines.append(f"{data['name']}_count{{{label_str}}} {data['totals'].get(key, 0)}")

        return "\n".join(lines)

    def json(self) -> Dict:
        return {
            "counters": {name: c.collect() for name, c in self._counters.items()},
            "gauges": {name: g.collect() for name, g in self._gauges.items()},
            "histograms": {name: h.collect() for name, h in self._histograms.items()},
            "timestamp": datetime.now().isoformat(),
        }


_global_metrics = PrometheusMetrics()


def get_metrics() -> PrometheusMetrics:
    return _global_metrics


class MetricsMiddleware:
    """
    FastAPI 中间件 - 自动记录 HTTP 指标
    """

    def __init__(self, app):
        self.app = app
        self.metrics = get_metrics()

        self.metrics.counter(
            "http_requests_total",
            "Total HTTP requests",
            ["method", "endpoint", "status"],
        )
        self.metrics.histogram(
            "http_request_duration_seconds",
            "HTTP request duration in seconds",
            ["method", "endpoint"],
            buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
        )

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        method = scope.get("method", "GET")
        path = scope.get("path", "/")

        timer = self.metrics.timer("http_request_duration_seconds", method=method, endpoint=path)

        status_code = 500
        with timer:

            async def wrapped_send(message):
                nonlocal status_code
                if message["type"] == "http.response.start":
                    status_code = message["status"]
                await send(message)

            try:
                await self.app(scope, receive, wrapped_send)
            except Exception:
                status_code = 500
                raise

        self.metrics.inc(
            "http_requests_total",
            method=method,
            endpoint=path,
            status=str(status_code),
        )


class AgentMetrics:
    """
    Agent 特有指标

    记录 Agent Runtime 的核心指标
    """

    def __init__(self):
        self.metrics = get_metrics()
        self._setup_metrics()

    def _setup_metrics(self):
        self.metrics.counter("agent_tasks_total", "Total tasks processed", ["status"])
        self.metrics.counter("agent_tool_calls_total", "Total tool calls", ["tool_name", "status"])
        self.metrics.histogram("agent_task_duration_seconds", "Task duration", ["task_type"])
        self.metrics.histogram("agent_tool_duration_seconds", "Tool call duration", ["tool_name"])
        self.metrics.gauge("agent_active_tasks", "Number of active tasks")
        self.metrics.gauge("agent_queue_size", "Task queue size")
        self.metrics.gauge("agent_memory_usage_bytes", "Memory usage estimate", ["memory_type"])

    def record_task(self, status: str, task_type: str = "general", duration: float = None):
        self.metrics.inc("agent_tasks_total", status=status)
        if duration is not None:
            self.metrics.observe("agent_task_duration_seconds", duration, task_type=task_type)

    def record_tool_call(self, tool_name: str, status: str, duration: float = None):
        self.metrics.inc("agent_tool_calls_total", tool_name=tool_name, status=status)
        if duration is not None:
            self.metrics.observe("agent_tool_duration_seconds", duration, tool_name=tool_name)

    def set_active_tasks(self, count: int):
        self.metrics.set("agent_active_tasks", count)

    def set_queue_size(self, size: int):
        self.metrics.set("agent_queue_size", size)

    def record_memory(self, memory_type: str, bytes_used: int):
        self.metrics.set("agent_memory_usage_bytes", bytes_used, memory_type=memory_type)


def get_agent_metrics() -> AgentMetrics:
    return AgentMetrics()
