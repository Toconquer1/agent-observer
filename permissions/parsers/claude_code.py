"""
Claude Code 配置解析器

读取和解析 Claude Code 的 settings.json 配置文件
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass


@dataclass
class PermissionRule:
    """权限规则"""
    tool_name: str
    pattern: Optional[str] = None  # 参数模式，如 "python3 *"

    def matches(self, tool_name: str, arguments: Dict[str, Any]) -> bool:
        """检查工具调用是否匹配此规则"""
        if self.tool_name != tool_name:
            return False

        if self.pattern is None:
            # 没有模式限制，允许所有调用
            return True

        # 对于 Bash 工具，检查 command 参数
        if tool_name == "Bash":
            command = arguments.get("command", "")
            # 将模式转换为正则表达式
            # "python3 *" -> "^python3 .*$"
            regex_pattern = self.pattern.replace("*", ".*")
            if not regex_pattern.startswith("^"):
                regex_pattern = "^" + regex_pattern
            if not regex_pattern.endswith("$"):
                regex_pattern = regex_pattern + "$"

            return bool(re.match(regex_pattern, command))

        # 其他工具的模式匹配可以在这里扩展
        return True


@dataclass
class ClaudeCodeConfig:
    """Claude Code 配置"""
    permissions: List[PermissionRule]
    workspace_path: Path
    skip_dangerous_prompt: bool = False

    def is_tool_allowed(self, tool_name: str, arguments: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """
        检查工具调用是否被允许

        Returns:
            (is_allowed, reason)
        """
        # 检查是否有匹配的权限规则
        for rule in self.permissions:
            if rule.matches(tool_name, arguments):
                return True, None

        # 没有匹配的规则
        if self.permissions:
            return False, f"工具 {tool_name} 未在 settings.json 的 permissions.allow 中配置"
        else:
            # 如果没有配置任何权限，默认允许（宽松模式）
            return True, None

    def is_path_in_workspace(self, file_path: str) -> tuple[bool, Optional[str]]:
        """检查文件路径是否在工作空间内"""
        try:
            path = Path(file_path).resolve()
            workspace = self.workspace_path.resolve()

            # 检查是否在工作空间内
            try:
                path.relative_to(workspace)
                return True, None
            except ValueError:
                return False, f"文件 {file_path} 在工作空间 {workspace} 外"
        except Exception as e:
            return False, f"路径解析错误: {e}"


class ClaudeCodeConfigParser:
    """Claude Code 配置解析器"""

    def __init__(self, workspace_path: str):
        self.workspace_path = Path(workspace_path)

    def parse(self) -> ClaudeCodeConfig:
        """
        解析 Claude Code 配置

        读取顺序：
        1. 全局 settings.json (~/.claude/settings.json)
        2. 项目 settings.json (.claude/settings.json)
        3. 本地 settings.local.json (.claude/settings.local.json)

        后面的配置会覆盖前面的
        """
        config_data = {}

        # 1. 读取全局配置
        global_settings = self._read_global_settings()
        if global_settings:
            config_data.update(global_settings)

        # 2. 读取项目配置
        project_settings = self._read_project_settings()
        if project_settings:
            config_data = self._merge_config(config_data, project_settings)

        # 3. 读取本地配置
        local_settings = self._read_local_settings()
        if local_settings:
            config_data = self._merge_config(config_data, local_settings)

        # 解析权限规则
        permissions = self._parse_permissions(config_data.get("permissions", {}))

        # 获取其他配置
        skip_dangerous_prompt = config_data.get("skipDangerousModePermissionPrompt", False)

        return ClaudeCodeConfig(
            permissions=permissions,
            workspace_path=self.workspace_path,
            skip_dangerous_prompt=skip_dangerous_prompt
        )

    def _read_global_settings(self) -> Optional[Dict]:
        """读取全局 settings.json"""
        # Windows: %USERPROFILE%\.claude\settings.json
        # Linux/Mac: ~/.claude/settings.json
        home = Path.home()
        settings_path = home / ".claude" / "settings.json"

        return self._read_json_file(settings_path)

    def _read_project_settings(self) -> Optional[Dict]:
        """读取项目 settings.json"""
        settings_path = self.workspace_path / ".claude" / "settings.json"
        return self._read_json_file(settings_path)

    def _read_local_settings(self) -> Optional[Dict]:
        """读取本地 settings.local.json"""
        settings_path = self.workspace_path / ".claude" / "settings.local.json"
        return self._read_json_file(settings_path)

    def _read_json_file(self, path: Path) -> Optional[Dict]:
        """读取 JSON 文件"""
        try:
            if path.exists():
                with open(path, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            print(f"[permissions] 读取配置文件 {path} 失败: {e}")
        return None

    def _merge_config(self, base: Dict, override: Dict) -> Dict:
        """合并配置（深度合并）"""
        result = base.copy()

        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_config(result[key], value)
            else:
                result[key] = value

        return result

    def _parse_permissions(self, permissions_config: Dict) -> List[PermissionRule]:
        """
        解析权限配置

        格式：
        {
          "allow": [
            "Bash(python3 *)",
            "Bash(python *)",
            "Read",
            "Write"
          ]
        }
        """
        rules = []
        allow_list = permissions_config.get("allow", [])

        for item in allow_list:
            # 解析格式：ToolName(pattern) 或 ToolName
            match = re.match(r'^(\w+)(?:\((.*)\))?$', item)
            if match:
                tool_name = match.group(1)
                pattern = match.group(2) if match.group(2) else None
                rules.append(PermissionRule(tool_name=tool_name, pattern=pattern))
            else:
                print(f"[permissions] 无法解析权限规则: {item}")

        return rules


if __name__ == "__main__":
    # 测试
    parser = ClaudeCodeConfigParser("E:\\master_code\\agob_workspace")
    config = parser.parse()

    print(f"工作空间: {config.workspace_path}")
    print(f"跳过危险提示: {config.skip_dangerous_prompt}")
    print(f"权限规则数量: {len(config.permissions)}")

    for rule in config.permissions:
        print(f"  - {rule.tool_name}" + (f"({rule.pattern})" if rule.pattern else ""))

    # 测试权限检查
    print("\n测试权限检查:")

    test_cases = [
        ("Bash", {"command": "python3 test.py"}),
        ("Bash", {"command": "python test.py"}),
        ("Bash", {"command": "ls -la"}),
        ("Read", {"file_path": "test.py"}),
    ]

    for tool_name, arguments in test_cases:
        allowed, reason = config.is_tool_allowed(tool_name, arguments)
        status = "PASS" if allowed else "FAIL"
        print(f"  {tool_name}({arguments}): {status} {reason or ''}")
