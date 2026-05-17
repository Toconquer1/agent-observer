"""
权限验证系统（基于实际配置）

从 agent 的实际配置文件中读取权限设置，而不是主观定义规则
"""

from .validator_v2 import PermissionValidator, ValidationResult
from .parsers.claude_code import ClaudeCodeConfigParser, ClaudeCodeConfig, PermissionRule

__all__ = [
    'PermissionValidator',
    'ValidationResult',
    'ClaudeCodeConfigParser',
    'ClaudeCodeConfig',
    'PermissionRule',
]
