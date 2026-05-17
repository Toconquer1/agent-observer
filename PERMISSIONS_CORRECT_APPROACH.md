# 权限验证系统 - 正确实现方式

## 核心理念

**权限建模 = 读取 agent 自身的配置文件，而不是主观定义规则**

## 错误的做法 ❌

之前的实现是主观定义规则：

```json
{
  "tools": {
    "Bash": {
      "permission": "restricted",
      "constraints": {
        "command": {
          "forbidden_patterns": ["rm\\s+-rf\\s+/", "sudo.*"],
          "dangerous_commands": ["sudo", "rm", "dd"]
        }
      }
    }
  }
}
```

**问题**：
- 这是我们主观认为"rm -rf 危险"、"sudo 危险"
- 不是基于 agent 的实际配置
- 无法反映用户的真实权限设置

## 正确的做法 ✅

读取 Claude Code 的实际配置文件：

### 1. 配置文件位置

```
~/.claude/settings.json              # 全局配置
<workspace>/.claude/settings.json    # 项目配置
<workspace>/.claude/settings.local.json  # 本地配置（优先级最高）
```

### 2. 配置文件格式

```json
{
  "permissions": {
    "allow": [
      "Bash(python3 *)",
      "Bash(python *)",
      "Bash(git *)",
      "Read",
      "Write",
      "Glob"
    ]
  },
  "skipDangerousModePermissionPrompt": true
}
```

### 3. 权限规则格式

- `"ToolName"` - 允许该工具的所有调用
- `"ToolName(pattern)"` - 只允许匹配模式的调用
- `pattern` 中 `*` 表示任意字符

### 4. 验证逻辑

```python
# 1. 检查工具是否在 allow 列表中
if tool not in allow_list:
    return False, "工具未在 settings.json 的 permissions.allow 中配置"

# 2. 如果有模式限制，检查是否匹配
if has_pattern and not matches_pattern:
    return False, "工具调用不匹配配置的 match 模式"

# 3. 检查文件路径是否在工作空间内
if is_file_operation and not in_workspace:
    return False, "文件在工作空间外"
```

## 实现架构

```
permissions/
├── parsers/                         # 配置文件解析器
│   ├── __init__.py
│   └── claude_code.py              # Claude Code settings.json 解析器
│       ├── ClaudeCodeConfigParser  # 解析配置文件
│       ├── ClaudeCodeConfig        # 配置数据模型
│       └── PermissionRule          # 权限规则
├── validator_v2.py                 # 权限验证器
│   ├── PermissionValidator         # 验证工具调用
│   └── ValidationResult            # 验证结果
└── __init__.py                     # 模块导出
```

## 使用示例

### 1. 当前配置（示例）

`.claude/settings.local.json`:
```json
{
  "permissions": {
    "allow": [
      "Bash(python3 *)",
      "Bash(python *)"
    ]
  }
}
```

### 2. 验证结果

```python
validator = PermissionValidator("claude_code", "/path/to/workspace")

# ✅ 允许 - 匹配 "python3 *"
validator.validate_tool_call({
    "name": "Bash",
    "arguments": {"command": "python3 test.py"}
})
# => is_authorized: True

# ❌ 拒绝 - 不匹配任何规则
validator.validate_tool_call({
    "name": "Bash",
    "arguments": {"command": "ls -la"}
})
# => is_authorized: False
# => reason: "工具 Bash 未在 settings.json 的 permissions.allow 中配置"

# ❌ 拒绝 - 工具未配置
validator.validate_tool_call({
    "name": "Read",
    "arguments": {"file_path": "/tmp/test.txt"}
})
# => is_authorized: False
# => reason: "工具 Read 未在 settings.json 的 permissions.allow 中配置"
```

### 3. 添加权限

要允许更多操作，编辑 `.claude/settings.local.json`:

```json
{
  "permissions": {
    "allow": [
      "Bash(python3 *)",
      "Bash(python *)",
      "Bash(git *)",        // 允许所有 git 命令
      "Read",               // 允许所有 Read 操作
      "Write",              // 允许所有 Write 操作
      "Glob"                // 允许文件搜索
    ]
  }
}
```

## 测试结果

运行 `test_permissions_v2.py`:

```
测试结果: 9/9 通过

✅ python3 test.py - 允许（匹配配置）
✅ python script.py - 允许（匹配配置）
✅ python3 -m pytest - 允许（匹配配置）
✅ ls -la - 拒绝（不匹配配置）
✅ git status - 拒绝（不匹配配置）
✅ rm -rf / - 拒绝（不匹配配置）
✅ Read 工作空间内文件 - 拒绝（工具未配置）
✅ Read 工作空间外文件 - 拒绝（工具未配置）
✅ Write 工作空间内文件 - 拒绝（工具未配置）
```

## 关键特性

### 1. 基于实际配置
- 不是我们定义"什么危险"
- 而是读取用户的实际权限设置
- 反映用户的真实意图

### 2. 工作空间限制
- 自动检测工作目录
- 文件操作只能在工作空间内
- 访问工作空间外的文件会被拒绝

### 3. 配置优先级
```
全局配置 < 项目配置 < 本地配置
```

### 4. 宽松模式
- 如果没有配置文件，默认允许所有操作
- 避免破坏现有工作流

## 与之前实现的对比

| 方面 | 错误实现 | 正确实现 |
|------|---------|---------|
| 规则来源 | 主观定义 | 读取实际配置 |
| 危险判断 | 我们定义 | 用户配置决定 |
| 可扩展性 | 需要修改代码 | 只需修改配置文件 |
| 准确性 | 可能不符合实际 | 完全符合实际权限 |
| 维护成本 | 高（需要维护规则） | 低（自动读取配置） |

## 后续扩展

### 1. 支持更多 agent
- OpenClaw: 读取其配置文件
- 其他 agent: 实现对应的配置解析器

### 2. 更多验证规则
- 网络访问限制
- 资源使用限制
- 时间限制

### 3. 配置建议
- 分析实际使用情况
- 生成最小权限配置建议

## 总结

**正确的权限建模**：
1. 读取 agent 的实际配置文件
2. 解析权限设置
3. 根据实际配置进行验证
4. 不添加主观判断

这才是真正的"建模"——基于现实，而不是假设。
