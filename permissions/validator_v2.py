"""
权限验证器（基于实际配置）

根据 agent 的实际配置文件进行权限验证
"""

from typing import Dict, Any, Optional
from dataclasses import dataclass
from pathlib import Path

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from permissions.parsers.claude_code import ClaudeCodeConfigParser, ClaudeCodeConfig


@dataclass
class ValidationResult:
    """验证结果"""
    is_authorized: bool
    reason: Optional[str] = None
    risk_level: str = "unknown"  # low, medium, high, critical
    violated_rules: list = None

    def __post_init__(self):
        if self.violated_rules is None:
            self.violated_rules = []


class PermissionValidator:
    """权限验证器"""

    def __init__(self, agent_name: str, workspace_path: str):
        """
        初始化权限验证器

        Args:
            agent_name: agent 名称（如 "claude_code"）
            workspace_path: 工作空间路径
        """
        self.agent_name = agent_name
        self.workspace_path = Path(workspace_path)
        self.config = None

        # 根据 agent 类型加载配置
        if agent_name == "claude_code":
            self._load_claude_code_config()
        else:
            print(f"[permissions] 未知的 agent 类型: {agent_name}，使用默认配置")

    def _load_claude_code_config(self):
        """加载 Claude Code 配置"""
        try:
            parser = ClaudeCodeConfigParser(str(self.workspace_path))
            self.config = parser.parse()
            print(f"[permissions] 已加载 Claude Code 配置，{len(self.config.permissions)} 个权限规则")
        except Exception as e:
            print(f"[permissions] 加载 Claude Code 配置失败: {e}")
            self.config = None

    def validate_tool_call(self, tool_call: Dict[str, Any]) -> ValidationResult:
        """
        验证工具调用

        Args:
            tool_call: 工具调用，格式 {"name": "ToolName", "arguments": {...}}

        Returns:
            ValidationResult
        """
        tool_name = tool_call.get("name")
        arguments = tool_call.get("arguments", {})

        if not tool_name:
            return ValidationResult(
                is_authorized=False,
                reason="工具名称为空",
                risk_level="high"
            )

        # 如果没有加载配置，默认允许（宽松模式）
        if self.config is None:
            return ValidationResult(
                is_authorized=True,
                reason="未加载配置，默认允许",
                risk_level="unknown"
            )

        # 1. 检查工具权限
        allowed, reason = self.config.is_tool_allowed(tool_name, arguments)
        if not allowed:
            return ValidationResult(
                is_authorized=False,
                reason=reason,
                risk_level="high",
                violated_rules=["permissions.allow"]
            )

        # 2. 检查文件路径（针对文件操作工具）
        if tool_name in ["Read", "Write", "Edit", "Glob"]:
            file_path = arguments.get("file_path") or arguments.get("path")
            if file_path:
                in_workspace, reason = self.config.is_path_in_workspace(file_path)
                if not in_workspace:
                    return ValidationResult(
                        is_authorized=False,
                        reason=reason,
                        risk_level="medium",
                        violated_rules=["workspace_boundary"]
                    )

        # 3. 所有检查通过
        return ValidationResult(
            is_authorized=True,
            risk_level="low"
        )


if __name__ == "__main__":
    # 测试
    validator = PermissionValidator("claude_code", "E:\\master_code\\agob_workspace")

    print("\n测试工具调用验证:")

    test_cases = [
        {
            "name": "允许的 python3 命令",
            "tool_call": {
                "name": "Bash",
                "arguments": {"command": "python3 test.py"}
            }
        },
        {
            "name": "允许的 python 命令",
            "tool_call": {
                "name": "Bash",
                "arguments": {"command": "python script.py"}
            }
        },
        {
            "name": "不允许的 ls 命令",
            "tool_call": {
                "name": "Bash",
                "arguments": {"command": "ls -la"}
            }
        },
        {
            "name": "不允许的 rm 命令",
            "tool_call": {
                "name": "Bash",
                "arguments": {"command": "rm -rf /"}
            }
        },
        {
            "name": "工作空间内的文件读取",
            "tool_call": {
                "name": "Read",
                "arguments": {"file_path": "E:\\master_code\\agob_workspace\\test.py"}
            }
        },
        {
            "name": "工作空间外的文件读取",
            "tool_call": {
                "name": "Read",
                "arguments": {"file_path": "C:\\Windows\\System32\\config\\sam"}
            }
        },
    ]

    for test_case in test_cases:
        print(f"\n测试: {test_case['name']}")
        result = validator.validate_tool_call(test_case['tool_call'])

        print(f"  授权: {result.is_authorized}")
        print(f"  风险级别: {result.risk_level}")
        if result.reason:
            print(f"  原因: {result.reason}")
        if result.violated_rules:
            print(f"  违反规则: {', '.join(result.violated_rules)}")
