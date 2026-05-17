# 权限验证系统设计

## 概述

本系统为 agentob 提供动态的工具调用权限验证功能。通过对不同 agent 进行运行时权限建模，可以检测和标记未授权或危险的工具调用。

## 核心概念

### 1. 权限模型（Permission Model）

每个 agent 都有自己的权限模型，定义了：
- **允许的工具**：agent 可以调用的工具列表
- **工具参数约束**：对工具参数的限制（如路径白名单、值范围等）
- **危险操作**：需要特别标记的高风险操作
- **上下文规则**：基于上下文的动态权限判断

### 2. 权限级别

- **allowed**：明确允许的操作
- **restricted**：受限操作，需要满足特定条件
- **dangerous**：危险操作，需要特别审查
- **forbidden**：明确禁止的操作

### 3. 验证结果

每个工具调用的验证结果包含：
- `is_authorized`: 是否授权
- `permission_level`: 权限级别
- `violation_reason`: 违规原因（如果未授权）
- `risk_level`: 风险等级（low/medium/high/critical）

## 架构设计

```
permissions/
├── DESIGN.md                    # 本设计文档
├── models/                      # 权限模型配置
│   ├── claude_code.json        # Claude Code 权限模型
│   ├── openclaw.json           # OpenClaw 权限模型
│   └── default.json            # 默认权限模型
├── validator.py                # 权限验证器核心
├── loader.py                   # 权限模型加载器
└── rules.py                    # 权限规则引擎
```

## 权限模型配置格式

```json
{
  "agent_name": "claude_code",
  "version": "1.0",
  "description": "Claude Code 权限模型",
  
  "tools": {
    "Read": {
      "permission": "allowed",
      "constraints": {
        "file_path": {
          "type": "path_whitelist",
          "patterns": ["**/*.py", "**/*.md", "**/*.json"],
          "exclude_patterns": ["**/secrets/**", "**/.env"]
        }
      }
    },
    
    "Write": {
      "permission": "restricted",
      "risk_level": "medium",
      "constraints": {
        "file_path": {
          "type": "path_whitelist",
          "patterns": ["**/*.py", "**/*.md"],
          "exclude_patterns": ["**/system/**", "**/etc/**"]
        }
      }
    },
    
    "Bash": {
      "permission": "restricted",
      "risk_level": "high",
      "constraints": {
        "command": {
          "type": "command_whitelist",
          "allowed_commands": ["ls", "cat", "grep", "git"],
          "forbidden_patterns": ["rm -rf", "sudo", "chmod 777"]
        }
      }
    },
    
    "Edit": {
      "permission": "allowed",
      "risk_level": "low"
    }
  },
  
  "global_rules": {
    "max_file_size": 10485760,
    "forbidden_paths": [
      "/etc/passwd",
      "/etc/shadow",
      "~/.ssh/id_rsa"
    ],
    "dangerous_operations": [
      {
        "tool": "Bash",
        "pattern": "rm.*-rf",
        "risk_level": "critical"
      },
      {
        "tool": "Write",
        "pattern": ".*\\.sh$",
        "risk_level": "high"
      }
    ]
  },
  
  "context_rules": [
    {
      "name": "prevent_recursive_deletion",
      "condition": {
        "tool": "Bash",
        "command_contains": "rm"
      },
      "check": {
        "not_contains": ["-rf", "-r -f"]
      },
      "violation_message": "递归删除操作被禁止"
    }
  ]
}
```

## 验证流程

```
工具调用
    ↓
加载 Agent 权限模型
    ↓
检查工具是否在允许列表
    ↓
验证参数约束
    ↓
应用上下文规则
    ↓
检查全局规则
    ↓
生成验证结果
    ↓
返回 {is_authorized, permission_level, risk_level, violation_reason}
```

## 集成到分析流程

在分析器的 `_analyze_single_item` 方法中，对于 `tool_calls` 类型的项：

1. 加载对应 agent 的权限模型
2. 对每个工具调用进行权限验证
3. 将验证结果添加到 `error_analysis` 中
4. 如果发现未授权调用，设置 `flag` 为 `error`

## 可扩展性

### 添加新 Agent

1. 在 `permissions/models/` 创建新的 JSON 配置文件
2. 定义该 agent 的工具权限和约束
3. 系统自动加载，无需修改代码

### 自定义规则

支持通过 Python 插件扩展规则引擎：

```python
# permissions/custom_rules/my_rule.py
from permissions.rules import Rule

class MyCustomRule(Rule):
    def validate(self, tool_call, context):
        # 自定义验证逻辑
        return ValidationResult(...)
```

### 动态权限

支持基于运行时上下文的动态权限判断：

```json
{
  "context_rules": [
    {
      "name": "allow_write_in_project_dir",
      "condition": {
        "tool": "Write",
        "file_path_starts_with": "${PROJECT_DIR}"
      },
      "action": "allow"
    }
  ]
}
```

## 安全考虑

1. **默认拒绝**：未明确允许的操作默认拒绝
2. **最小权限原则**：只授予必要的最小权限
3. **审计日志**：记录所有权限验证结果
4. **分层防御**：全局规则 + 工具规则 + 上下文规则
5. **可配置性**：用户可以自定义权限模型

## 使用场景

### 1. 安全审计
检测 agent 是否尝试执行未授权操作。

### 2. 合规检查
确保 agent 的行为符合组织的安全策略。

### 3. 风险评估
识别高风险操作，提供风险等级评分。

### 4. 调试辅助
帮助开发者理解 agent 的权限需求。

## 输出格式

在 `analyze.json` 中，每个工具调用会包含权限验证结果：

```json
{
  "summary": "调用 Bash 执行 rm -rf /tmp/test",
  "error_analysis": {
    "is_correct": false,
    "is_necessary": false,
    "reasoning": "该操作尝试执行危险的递归删除命令",
    "flag": "error"
  },
  "permission_check": {
    "is_authorized": false,
    "permission_level": "forbidden",
    "risk_level": "critical",
    "violation_reason": "命令包含被禁止的模式: rm -rf",
    "violated_rules": [
      "global_rules.dangerous_operations[0]",
      "context_rules.prevent_recursive_deletion"
    ]
  }
}
```

## 可视化

在 HTML 可视化中：
- 未授权的工具调用显示**红色边框**
- 高风险操作显示**橙色警告图标**
- 权限验证详情显示在分析框中

## 性能考虑

1. **缓存权限模型**：避免重复加载
2. **延迟加载**：只在需要时加载规则
3. **并行验证**：对多个工具调用并行验证
4. **规则优化**：使用索引加速规则匹配

## 未来扩展

1. **机器学习**：基于历史数据学习权限模式
2. **实时监控**：在 attach 模式下实时验证
3. **权限建议**：自动生成最小权限配置
4. **多租户支持**：不同用户不同权限
5. **权限继承**：支持权限模型继承和覆盖
