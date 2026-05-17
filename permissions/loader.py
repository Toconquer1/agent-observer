"""
权限模型加载器

负责从配置文件加载和管理权限模型。
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional
import re


class PermissionModel:
    """权限模型类"""

    def __init__(self, config: Dict[str, Any]):
        self.agent_name = config.get("agent_name", "unknown")
        self.version = config.get("version", "1.0")
        self.description = config.get("description", "")
        self.tools = config.get("tools", {})
        self.global_rules = config.get("global_rules", {})
        self.context_rules = config.get("context_rules", [])

    def get_tool_permission(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """获取工具的权限配置"""
        # 精确匹配
        if tool_name in self.tools:
            return self.tools[tool_name]

        # 通配符匹配
        if "*" in self.tools:
            return self.tools["*"]

        return None

    def get_dangerous_operations(self) -> list:
        """获取危险操作列表"""
        return self.global_rules.get("dangerous_operations", [])

    def get_forbidden_paths(self) -> list:
        """获取禁止访问的路径列表"""
        return self.global_rules.get("forbidden_paths", [])

    def get_context_rules(self) -> list:
        """获取上下文规则列表"""
        return self.context_rules


class PermissionModelLoader:
    """权限模型加载器"""

    def __init__(self, models_dir: Optional[Path] = None):
        """
        初始化加载器。

        Args:
            models_dir: 权限模型配置目录，默认为 permissions/models/
        """
        if models_dir is None:
            models_dir = Path(__file__).parent / "models"

        self.models_dir = Path(models_dir)
        self._cache: Dict[str, PermissionModel] = {}

    def load_model(self, agent_name: str) -> PermissionModel:
        """
        加载指定 agent 的权限模型。

        Args:
            agent_name: agent 名称（如 "claude_code", "openclaw"）

        Returns:
            权限模型对象
        """
        # 检查缓存
        if agent_name in self._cache:
            return self._cache[agent_name]

        # 规范化 agent 名称
        normalized_name = self._normalize_agent_name(agent_name)

        # 尝试加载对应的配置文件
        model_file = self.models_dir / f"{normalized_name}.json"

        if not model_file.exists():
            print(f"[permissions] 未找到 {agent_name} 的权限模型，使用默认模型")
            model_file = self.models_dir / "default.json"

        try:
            with open(model_file, "r", encoding="utf-8") as f:
                config = json.load(f)

            model = PermissionModel(config)
            self._cache[agent_name] = model

            print(f"[permissions] 已加载权限模型: {model.agent_name} v{model.version}")
            return model

        except Exception as e:
            print(f"[permissions] 加载权限模型失败: {e}")
            # 返回空的默认模型
            return PermissionModel({
                "agent_name": agent_name,
                "version": "1.0",
                "tools": {"*": {"permission": "restricted", "risk_level": "high"}},
                "global_rules": {},
                "context_rules": []
            })

    def _normalize_agent_name(self, agent_name: str) -> str:
        """
        规范化 agent 名称。

        将各种可能的名称格式转换为标准格式：
        - "Claude Code" -> "claude_code"
        - "OpenClaw" -> "openclaw"
        - "claude-code" -> "claude_code"
        """
        # 转小写
        name = agent_name.lower()

        # 替换空格和连字符为下划线
        name = re.sub(r'[\s-]+', '_', name)

        # 移除特殊字符
        name = re.sub(r'[^\w_]', '', name)

        return name

    def detect_agent_from_tools(self, tool_names: list) -> str:
        """
        根据工具列表推断 agent 类型。

        Args:
            tool_names: 工具名称列表

        Returns:
            推断的 agent 名称
        """
        tool_set = set(tool_names)

        # Claude Code 特征工具
        claude_code_tools = {"Read", "Write", "Edit", "Bash", "Glob", "Grep", "Agent"}
        if tool_set & claude_code_tools:
            if len(tool_set & claude_code_tools) >= 3:
                return "claude_code"

        # OpenClaw 特征工具
        openclaw_tools = {"computer", "bash", "str_replace_editor", "text_editor"}
        if tool_set & openclaw_tools:
            if len(tool_set & openclaw_tools) >= 2:
                return "openclaw"

        # 默认
        return "default"

    def list_available_models(self) -> list:
        """列出所有可用的权限模型"""
        models = []
        for model_file in self.models_dir.glob("*.json"):
            try:
                with open(model_file, "r", encoding="utf-8") as f:
                    config = json.load(f)
                models.append({
                    "file": model_file.name,
                    "agent_name": config.get("agent_name", "unknown"),
                    "version": config.get("version", "1.0"),
                    "description": config.get("description", "")
                })
            except Exception as e:
                print(f"[permissions] 读取 {model_file.name} 失败: {e}")

        return models
