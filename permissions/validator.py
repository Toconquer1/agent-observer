"""
权限验证器核心

负责验证工具调用是否符合权限模型。
"""

import re
from pathlib import Path
from typing import Dict, Any, List, Optional
from .loader import PermissionModel, PermissionModelLoader


class ValidationResult:
    """验证结果"""

    def __init__(
        self,
        is_authorized: bool,
        permission_level: str,
        risk_level: str,
        violation_reason: Optional[str] = None,
        violated_rules: Optional[List[str]] = None
    ):
        self.is_authorized = is_authorized
        self.permission_level = permission_level  # allowed/restricted/dangerous/forbidden
        self.risk_level = risk_level  # low/medium/high/critical
        self.violation_reason = violation_reason
        self.violated_rules = violated_rules or []

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "is_authorized": self.is_authorized,
            "permission_level": self.permission_level,
            "risk_level": self.risk_level,
            "violation_reason": self.violation_reason,
            "violated_rules": self.violated_rules
        }


class PermissionValidator:
    """权限验证器"""

    def __init__(self, model: PermissionModel):
        """
        初始化验证器。

        Args:
            model: 权限模型
        """
        self.model = model

    def validate_tool_call(self, tool_call: Dict[str, Any]) -> ValidationResult:
        """
        验证单个工具调用。

        Args:
            tool_call: 工具调用信息，格式：
                {
                    "name": "工具名",
                    "arguments": {...}
                }

        Returns:
            验证结果
        """
        tool_name = tool_call.get("name", "unknown")
        arguments = tool_call.get("arguments", {})

        # 1. 检查工具是否在权限模型中
        tool_config = self.model.get_tool_permission(tool_name)

        if tool_config is None:
            return ValidationResult(
                is_authorized=False,
                permission_level="forbidden",
                risk_level="high",
                violation_reason=f"工具 {tool_name} 不在允许列表中",
                violated_rules=["tool_not_in_whitelist"]
            )

        # 2. 检查工具的基本权限级别
        permission = tool_config.get("permission", "forbidden")
        risk_level = tool_config.get("risk_level", "medium")

        if permission == "forbidden":
            return ValidationResult(
                is_authorized=False,
                permission_level="forbidden",
                risk_level="critical",
                violation_reason=f"工具 {tool_name} 被明确禁止",
                violated_rules=["tool_forbidden"]
            )

        # 3. 检查工具参数约束
        constraints = tool_config.get("constraints", {})
        constraint_result = self._check_constraints(tool_name, arguments, constraints)

        if not constraint_result.is_authorized:
            return constraint_result

        # 4. 检查全局危险操作
        dangerous_result = self._check_dangerous_operations(tool_name, arguments)

        if not dangerous_result.is_authorized:
            return dangerous_result

        # 5. 检查上下文规则
        context_result = self._check_context_rules(tool_name, arguments)

        if not context_result.is_authorized:
            return context_result

        # 6. 所有检查通过
        return ValidationResult(
            is_authorized=True,
            permission_level=permission,
            risk_level=risk_level
        )

    def _check_constraints(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        constraints: Dict[str, Any]
    ) -> ValidationResult:
        """检查参数约束"""

        for param_name, constraint_config in constraints.items():
            param_value = arguments.get(param_name)

            if param_value is None:
                continue

            constraint_type = constraint_config.get("type")

            # 路径黑名单检查
            if constraint_type == "path_blacklist":
                exclude_patterns = constraint_config.get("exclude_patterns", [])
                if self._matches_any_pattern(str(param_value), exclude_patterns):
                    return ValidationResult(
                        is_authorized=False,
                        permission_level="forbidden",
                        risk_level="high",
                        violation_reason=f"路径 {param_value} 在黑名单中",
                        violated_rules=[f"constraints.{param_name}.path_blacklist"]
                    )

            # 路径白名单检查
            elif constraint_type == "path_whitelist":
                patterns = constraint_config.get("patterns", [])
                exclude_patterns = constraint_config.get("exclude_patterns", [])

                if not self._matches_any_pattern(str(param_value), patterns):
                    return ValidationResult(
                        is_authorized=False,
                        permission_level="forbidden",
                        risk_level="medium",
                        violation_reason=f"路径 {param_value} 不在白名单中",
                        violated_rules=[f"constraints.{param_name}.path_whitelist"]
                    )

                if self._matches_any_pattern(str(param_value), exclude_patterns):
                    return ValidationResult(
                        is_authorized=False,
                        permission_level="forbidden",
                        risk_level="high",
                        violation_reason=f"路径 {param_value} 在排除列表中",
                        violated_rules=[f"constraints.{param_name}.exclude_patterns"]
                    )

            # 命令检查
            elif constraint_type == "command_check":
                forbidden_patterns = constraint_config.get("forbidden_patterns", [])
                dangerous_commands = constraint_config.get("dangerous_commands", [])

                # 检查禁止的模式
                for pattern in forbidden_patterns:
                    if re.search(pattern, str(param_value), re.IGNORECASE):
                        return ValidationResult(
                            is_authorized=False,
                            permission_level="forbidden",
                            risk_level="critical",
                            violation_reason=f"命令包含被禁止的模式: {pattern}",
                            violated_rules=[f"constraints.{param_name}.forbidden_patterns"]
                        )

                # 检查危险命令
                for cmd in dangerous_commands:
                    if re.search(r'\b' + re.escape(cmd) + r'\b', str(param_value)):
                        return ValidationResult(
                            is_authorized=False,
                            permission_level="dangerous",
                            risk_level="high",
                            violation_reason=f"命令包含危险操作: {cmd}",
                            violated_rules=[f"constraints.{param_name}.dangerous_commands"]
                        )

            # 内容检查
            elif constraint_type == "content_check":
                forbidden_patterns = constraint_config.get("forbidden_patterns", [])

                for pattern in forbidden_patterns:
                    if re.search(pattern, str(param_value), re.IGNORECASE):
                        return ValidationResult(
                            is_authorized=False,
                            permission_level="forbidden",
                            risk_level="high",
                            violation_reason=f"内容包含被禁止的模式: {pattern}",
                            violated_rules=[f"constraints.{param_name}.content_check"]
                        )

            # URL 检查
            elif constraint_type == "url_check":
                forbidden_patterns = constraint_config.get("forbidden_patterns", [])

                for pattern in forbidden_patterns:
                    if pattern in str(param_value).lower():
                        return ValidationResult(
                            is_authorized=False,
                            permission_level="forbidden",
                            risk_level="high",
                            violation_reason=f"URL 包含被禁止的模式: {pattern}",
                            violated_rules=[f"constraints.{param_name}.url_check"]
                        )

        return ValidationResult(
            is_authorized=True,
            permission_level="allowed",
            risk_level="low"
        )

    def _check_dangerous_operations(
        self,
        tool_name: str,
        arguments: Dict[str, Any]
    ) -> ValidationResult:
        """检查全局危险操作"""

        dangerous_ops = self.model.get_dangerous_operations()

        for op in dangerous_ops:
            op_tool = op.get("tool")
            op_pattern = op.get("pattern")
            op_risk_level = op.get("risk_level", "high")
            op_message = op.get("message", "危险操作")

            # 检查工具匹配
            if op_tool != "*" and op_tool != tool_name:
                continue

            # 检查模式匹配（在所有参数中搜索）
            for arg_value in arguments.values():
                if isinstance(arg_value, str):
                    if re.search(op_pattern, arg_value, re.IGNORECASE):
                        return ValidationResult(
                            is_authorized=False,
                            permission_level="forbidden",
                            risk_level=op_risk_level,
                            violation_reason=op_message,
                            violated_rules=["global_rules.dangerous_operations"]
                        )

        return ValidationResult(
            is_authorized=True,
            permission_level="allowed",
            risk_level="low"
        )

    def _check_context_rules(
        self,
        tool_name: str,
        arguments: Dict[str, Any]
    ) -> ValidationResult:
        """检查上下文规则"""

        context_rules = self.model.get_context_rules()

        for rule in context_rules:
            rule_name = rule.get("name", "unknown")
            condition = rule.get("condition", {})
            check = rule.get("check", {})
            violation_message = rule.get("violation_message", "违反上下文规则")
            risk_level = rule.get("risk_level", "medium")

            # 检查条件是否匹配
            if not self._matches_condition(tool_name, arguments, condition):
                continue

            # 执行检查
            if not self._passes_check(tool_name, arguments, check):
                # 检查是否只是警告
                warn_only = check.get("warn_only", False)

                return ValidationResult(
                    is_authorized=warn_only,
                    permission_level="dangerous" if warn_only else "forbidden",
                    risk_level=risk_level,
                    violation_reason=violation_message,
                    violated_rules=[f"context_rules.{rule_name}"]
                )

        return ValidationResult(
            is_authorized=True,
            permission_level="allowed",
            risk_level="low"
        )

    def _matches_condition(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        condition: Dict[str, Any]
    ) -> bool:
        """检查是否匹配条件"""

        # 检查工具名
        if "tool" in condition:
            if condition["tool"] != tool_name:
                return False

        if "tool_any" in condition:
            if tool_name not in condition["tool_any"]:
                return False

        # 检查参数包含
        if "command_contains" in condition:
            command = arguments.get("command", "")
            if condition["command_contains"] not in str(command):
                return False

        if "command_contains_any" in condition:
            command = arguments.get("command", "")
            if not any(s in str(command) for s in condition["command_contains_any"]):
                return False

        # 检查路径
        if "path_starts_with_any" in condition:
            path = arguments.get("file_path") or arguments.get("path", "")
            if not any(str(path).startswith(prefix) for prefix in condition["path_starts_with_any"]):
                return False

        return True

    def _passes_check(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        check: Dict[str, Any]
    ) -> bool:
        """执行检查"""

        # 总是拒绝
        if check.get("always_deny"):
            return False

        # 不包含检查
        if "not_contains" in check:
            command = arguments.get("command", "")
            for pattern in check["not_contains"]:
                if pattern in str(command):
                    return False

        return True

    def _matches_any_pattern(self, value: str, patterns: List[str]) -> bool:
        """检查值是否匹配任何模式"""
        from fnmatch import fnmatch

        for pattern in patterns:
            if fnmatch(value, pattern):
                return True

        return False


def validate_tool_calls(
    tool_calls: List[Dict[str, Any]],
    agent_name: str = "default"
) -> List[ValidationResult]:
    """
    验证多个工具调用的便捷函数。

    Args:
        tool_calls: 工具调用列表
        agent_name: agent 名称

    Returns:
        验证结果列表
    """
    loader = PermissionModelLoader()
    model = loader.load_model(agent_name)
    validator = PermissionValidator(model)

    results = []
    for tool_call in tool_calls:
        result = validator.validate_tool_call(tool_call)
        results.append(result)

    return results
