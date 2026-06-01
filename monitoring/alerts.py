"""Alert 规则管理"""

import json
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional


class AlertSeverity(Enum):
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


@dataclass
class AlertRule:
    name: str
    expr: str
    description: str
    severity: AlertSeverity
    for_duration: str = "5m"
    labels: Dict[str, str] = None
    annotations: Dict[str, str] = None

    def to_dict(self) -> Dict:
        return {
            "alert": self.name,
            "expr": self.expr,
            "for": self.for_duration,
            "labels": self.labels or {"service": "agent-runtime"},
            "annotations": self.annotations or {"description": self.description},
        }


class AlertRulesManager:
    """
    Alert 规则管理器

    管理和生成 Prometheus Alert Rules

    示例:
        manager = AlertRulesManager()

        # 注册告警规则
        manager.add_rule(AlertRule(
            name="HighErrorRate",
            expr="rate(http_requests_total{status='5xx'}[5m]) > 0.05",
            description="Error rate is above 5%",
            severity=AlertSeverity.CRITICAL,
        ))

        # 导出 YAML
        yaml_output = manager.export_yaml()

        # 导出 JSON
        json_output = manager.export_json()
    """

    def __init__(self, service_name: str = "agent-runtime"):
        self.service_name = service_name
        self._rules: List[AlertRule] = []
        self._setup_default_rules()

    def _setup_default_rules(self):
        self._rules = [
            AlertRule(
                name="AgentAPIDown",
                expr="up{job='agent-api'} == 0",
                description="Agent API is down",
                severity=AlertSeverity.CRITICAL,
                for_duration="1m",
            ),
            AlertRule(
                name="HighErrorRate",
                expr="sum(rate(http_requests_total{status=~'5..'}[5m])) / sum(rate(http_requests_total[5m])) > 0.05",
                description="HTTP 5xx error rate is above 5%",
                severity=AlertSeverity.CRITICAL,
                for_duration="2m",
            ),
            AlertRule(
                name="HighLatency",
                expr="histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[5m])) by (le)) > 5",
                description="p95 latency is above 5 seconds",
                severity=AlertSeverity.WARNING,
                for_duration="5m",
            ),
            AlertRule(
                name="TaskQueueBacklog",
                expr="agent_queue_size > 100",
                description="Task queue size is above 100",
                severity=AlertSeverity.WARNING,
                for_duration="5m",
            ),
            AlertRule(
                name="HighTaskFailureRate",
                expr="sum(rate(agent_tasks_total{status='failure'}[5m])) / sum(rate(agent_tasks_total[5m])) > 0.1",
                description="Task failure rate is above 10%",
                severity=AlertSeverity.WARNING,
                for_duration="5m",
            ),
            AlertRule(
                name="ActiveTasksTooHigh",
                expr="agent_active_tasks > 1000",
                description="Number of active tasks is above 1000",
                severity=AlertSeverity.WARNING,
                for_duration="5m",
            ),
            AlertRule(
                name="MemoryUsageHigh",
                expr="agent_memory_usage_bytes > 2 * 1024 * 1024 * 1024",
                description="Memory usage is above 2GB",
                severity=AlertSeverity.WARNING,
                for_duration="5m",
            ),
            AlertRule(
                name="ToolLatencyHigh",
                expr="histogram_quantile(0.95, sum(rate(agent_tool_duration_seconds_bucket[5m])) by (le, tool_name)) > 30",
                description="Tool p95 latency is above 30 seconds",
                severity=AlertSeverity.WARNING,
                for_duration="5m",
            ),
        ]

    def add_rule(self, rule: AlertRule):
        self._rules.append(rule)

    def remove_rule(self, name: str):
        self._rules = [r for r in self._rules if r.name != name]

    def get_rule(self, name: str) -> Optional[AlertRule]:
        for rule in self._rules:
            if rule.name == name:
                return rule
        return None

    def list_rules(self) -> List[str]:
        return [r.name for r in self._rules]

    def export_dict(self) -> Dict[str, Any]:
        return {
            "groups": [
                {
                    "name": f"{self.service_name}-alerts",
                    "rules": [rule.to_dict() for rule in self._rules],
                }
            ]
        }

    def export_json(self) -> str:
        return json.dumps(self.export_dict(), indent=2)

    def export_yaml(self) -> str:
        lines = ["groups:", f"  - name: {self.service_name}-alerts", "    rules:"]
        for rule in self._rules:
            lines.append(f"      - alert: {rule.name}")
            lines.append(f"        expr: {rule.expr}")
            lines.append(f"        for: {rule.for_duration}")
            lines.append("        labels:")
            lines.append(f"          severity: {rule.severity.value}")
            lines.append(f"          service: {self.service_name}")
            lines.append("        annotations:")
            lines.append(f"          summary: {rule.name}")
            lines.append(f"          description: {rule.description}")
        return "\n".join(lines)

    def check_condition(self, rule_name: str, current_metrics: Dict[str, float]) -> bool:
        rule = self.get_rule(rule_name)
        if not rule:
            return False

        metric_name = (
            rule.expr.split("{")[0].split()[1] if "{" in rule.expr else rule.expr.split()[1]
        )
        threshold = float(rule.expr.split(">")[-1].strip()) if ">" in rule.expr else None

        if threshold is None or metric_name not in current_metrics:
            return False

        return current_metrics[metric_name] > threshold


def get_alert_manager() -> AlertRulesManager:
    return AlertRulesManager()
