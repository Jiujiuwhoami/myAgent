"""
权限控制和行为合约系统

实现：
- 权限策略定义
- 行为合约执行
- 资源访问控制
- 操作审计
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set


class Permission(Enum):
    """权限枚举"""

    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    EXECUTE = "execute"
    ADMIN = "admin"


class ResourceType(Enum):
    """资源类型"""

    FILE = "file"
    DATABASE = "database"
    NETWORK = "network"
    MEMORY = "memory"
    TOOL = "tool"
    AGENT = "agent"


@dataclass
class Resource:
    """资源定义"""

    id: str
    type: ResourceType
    name: str
    owner: str
    permissions: Dict[Permission, Set[str]] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Policy:
    """权限策略"""

    id: str
    name: str
    description: str
    effect: str
    actions: Set[str]
    resources: Set[str]
    principals: Set[str]
    conditions: Optional[Callable] = None


@dataclass
class Contract:
    """行为合约"""

    id: str
    name: str
    description: str
    rules: List["ContractRule"]
    enabled: bool = True


@dataclass
class ContractRule:
    """合约规则"""

    id: str
    name: str
    condition: Callable[[], bool]
    action: Callable
    violation_handler: Optional[Callable] = None


@dataclass
class AuditEntry:
    """审计条目"""

    timestamp: datetime
    principal: str
    action: str
    resource: str
    decision: str
    reason: Optional[str] = None


class AccessDecision(Enum):
    """访问决策"""

    ALLOW = "allow"
    DENY = "deny"
    DENY_CONDITION = "deny_condition"


class ContractEngine:
    """
    行为合约引擎

    负责：
    - 合约验证
    - 规则执行
    - 违规处理
    """

    def __init__(self):
        self._contracts: Dict[str, Contract] = {}
        self._policies: Dict[str, Policy] = {}
        self._audit_log: List[AuditEntry] = []

    def add_contract(self, contract: Contract):
        """添加合约"""
        self._contracts[contract.id] = contract
        print(f"   ✅ 合约已添加: {contract.name}")

    def remove_contract(self, contract_id: str):
        """移除合约"""
        self._contracts.pop(contract_id, None)

    def get_contract(self, contract_id: str) -> Optional[Contract]:
        """获取合约"""
        return self._contracts.get(contract_id)

    def list_contracts(self) -> List[Contract]:
        """列出所有合约"""
        return [c for c in self._contracts.values() if c.enabled]

    def validate_action(
        self, principal: str, action: str, resource: str, context: Optional[Dict[str, Any]] = None
    ) -> AccessDecision:
        """验证动作是否允许"""
        context = context or {}

        for contract in self.list_contracts():
            for rule in contract.rules:
                if not rule.condition():
                    continue

                try:
                    rule.action()
                except Exception as e:
                    if rule.violation_handler:
                        rule.violation_handler(principal, action, resource, str(e))

                    self._audit_log.append(
                        AuditEntry(
                            timestamp=datetime.now(),
                            principal=principal,
                            action=action,
                            resource=resource,
                            decision=AccessDecision.DENY_CONDITION.value,
                            reason=str(e),
                        )
                    )

                    return AccessDecision.DENY_CONDITION

        self._audit_log.append(
            AuditEntry(
                timestamp=datetime.now(),
                principal=principal,
                action=action,
                resource=resource,
                decision=AccessDecision.ALLOW.value,
            )
        )

        return AccessDecision.ALLOW

    def enforce_contract(self, contract_id: str, context: Optional[Dict[str, Any]] = None) -> bool:
        """强制执行合约"""
        contract = self.get_contract(contract_id)
        if not contract:
            return False

        all_valid = True
        for rule in contract.rules:
            if not rule.condition():
                continue

            try:
                rule.action()
            except Exception as e:
                if rule.violation_handler:
                    rule.violation_handler(None, None, None, str(e))
                all_valid = False

        return all_valid

    def get_audit_log(self, limit: int = 100) -> List[AuditEntry]:
        """获取审计日志"""
        return self._audit_log[-limit:]

    def clear_audit_log(self):
        """清空审计日志"""
        self._audit_log = []


class PermissionManager:
    """
    权限管理器

    负责：
    - 角色权限分配
    - 资源访问控制
    - 权限验证
    """

    def __init__(self):
        self._roles: Dict[str, Set[Permission]] = {}
        self._principal_roles: Dict[str, Set[str]] = {}
        self._resources: Dict[str, Resource] = {}
        self._policy_engine = ContractEngine()

    def create_role(self, role: str, permissions: Set[Permission]):
        """创建角色"""
        self._roles[role] = permissions
        print(f"   ✅ 角色已创建: {role}")

    def assign_role(self, principal: str, role: str):
        """分配角色"""
        if role not in self._principal_roles:
            self._principal_roles[role] = set()
        self._principal_roles[role].add(principal)

    def add_resource(self, resource: Resource):
        """添加资源"""
        self._resources[resource.id] = resource

    def check_permission(self, principal: str, permission: Permission, resource_id: str) -> bool:
        """检查权限"""
        if principal not in self._principal_roles:
            return False

        resource = self._resources.get(resource_id)
        if not resource:
            return True

        allowed_roles = resource.permissions.get(permission, set())

        for role in self._principal_roles.get(principal, set()):
            if role in allowed_roles:
                return True

        return False

    def grant_permission(self, resource_id: str, permission: Permission, role: str):
        """授予权限"""
        resource = self._resources.get(resource_id)
        if resource:
            if permission not in resource.permissions:
                resource.permissions[permission] = set()
            resource.permissions[permission].add(role)

    def revoke_permission(self, resource_id: str, permission: Permission, role: str):
        """撤销权限"""
        resource = self._resources.get(resource_id)
        if resource and permission in resource.permissions:
            resource.permissions[permission].discard(role)


class BehavioralContract:
    """
    行为合约

    定义 Agent 的行为边界和约束。
    """

    def __init__(self, name: str, description: str = ""):
        self.id = str(uuid.uuid4())[:8]
        self.name = name
        self.description = description
        self.rules: List[ContractRule] = []
        self._violations: List[Dict] = []

    def add_rule(
        self,
        name: str,
        condition: Callable[[], bool],
        action: Callable,
        violation_handler: Optional[Callable] = None,
    ) -> "BehavioralContract":
        """添加规则"""
        rule = ContractRule(
            id=str(uuid.uuid4())[:8],
            name=name,
            condition=condition,
            action=action,
            violation_handler=violation_handler,
        )
        self.rules.append(rule)
        return self

    def restrict_tool(self, tool_name: str) -> "BehavioralContract":
        """限制工具使用"""

        def condition():
            return False

        def action():
            raise PermissionError(f"工具 {tool_name} 被禁止使用")

        self.add_rule(
            name=f"restrict_{tool_name}",
            condition=condition,
            action=action,
            violation_handler=lambda p, a, r, e: self._record_violation(tool_name, e),
        )
        return self

    def restrict_action(self, action: str) -> "BehavioralContract":
        """限制操作"""

        def condition():
            return False

        def action():
            raise PermissionError(f"操作 {action} 被禁止")

        self.add_rule(
            name=f"restrict_action_{action}",
            condition=condition,
            action=action,
            violation_handler=lambda p, a, r, e: self._record_violation(action, e),
        )
        return self

    def require_approval(self, action: str, approver: str) -> "BehavioralContract":
        """要求审批"""
        approvals: Dict[str, bool] = {}

        def condition():
            return approvals.get(action, False)

        def action():
            pass

        self.add_rule(name=f"require_approval_{action}", condition=condition, action=action)

        def approve():
            approvals[action] = True

        return self

    def _record_violation(self, action: str, error: str):
        """记录违规"""
        self._violations.append({"action": action, "error": error, "timestamp": datetime.now()})

    def get_violations(self) -> List[Dict]:
        """获取违规记录"""
        return self._violations.copy()

    def validate(self) -> bool:
        """验证合约"""
        for rule in self.rules:
            if not callable(rule.condition):
                return False
            if not callable(rule.action):
                return False
        return True


class SecurityMonitor:
    """
    安全监控器

    监控 Agent 的行为并检测潜在安全问题。
    """

    def __init__(self):
        self._threats: List[Dict] = []
        self._alerts: List[Dict] = []
        self._rate_limiter: Dict[str, List[datetime]] = {}

    def check_rate_limit(self, action: str, max_calls: int, window_seconds: float) -> bool:
        """检查速率限制"""
        now = datetime.now()
        if action not in self._rate_limiter:
            self._rate_limiter[action] = []

        self._rate_limiter[action] = [
            t for t in self._rate_limiter[action] if (now - t).total_seconds() < window_seconds
        ]

        if len(self._rate_limiter[action]) >= max_calls:
            self._record_threat(action, "rate_limit_exceeded")
            return False

        self._rate_limiter[action].append(now)
        return True

    def _record_threat(self, action: str, threat_type: str):
        """记录威胁"""
        self._threats.append({"action": action, "type": threat_type, "timestamp": datetime.now()})

    def check_pattern(self, action: str, pattern: str) -> bool:
        """检查行为模式"""
        if "DROP" in pattern.upper() or "DELETE" in pattern.upper():
            self._record_threat(action, "destructive_pattern")
            return False
        return True

    def get_threats(self) -> List[Dict]:
        """获取威胁记录"""
        return self._threats.copy()

    def create_alert(self, level: str, message: str):
        """创建告警"""
        self._alerts.append({"level": level, "message": message, "timestamp": datetime.now()})

    def get_alerts(self) -> List[Dict]:
        """获取告警"""
        return self._alerts.copy()


class ContractEnforcer:
    """
    合约执行器

    将合约规则与 Agent Runtime 集成。
    """

    def __init__(
        self,
        permission_manager: PermissionManager,
        contract_engine: ContractEngine,
        security_monitor: SecurityMonitor,
    ):
        self.permission_manager = permission_manager
        self.contract_engine = contract_engine
        self.security_monitor = security_monitor

    def before_tool_call(
        self, tool_name: str, parameters: Dict[str, Any], principal: str = "agent"
    ) -> bool:
        """工具调用前检查"""
        decision = self.contract_engine.validate_action(
            principal=principal,
            action=f"execute:{tool_name}",
            resource=f"tool:{tool_name}",
            context={"parameters": parameters},
        )

        if decision == AccessDecision.DENY:
            return False

        if not self.security_monitor.check_rate_limit(
            action=tool_name, max_calls=100, window_seconds=60
        ):
            return False

        return True

    def before_state_transition(
        self, from_state: str, to_state: str, principal: str = "agent"
    ) -> bool:
        """状态转换前检查"""
        decision = self.contract_engine.validate_action(
            principal=principal,
            action=f"transition:{from_state}->{to_state}",
            resource="state_machine",
            context={"from": from_state, "to": to_state},
        )

        return decision == AccessDecision.ALLOW

    def record_action(self, action: str, resource: str, success: bool):
        """记录动作"""
        pass
