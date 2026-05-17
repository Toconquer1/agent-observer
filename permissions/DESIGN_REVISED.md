# 权限验证系统设计（修订版）

## 核心理念

**权限建模 = 读取并解析 agent 自身的权限配置**

不是我们主观定义规则，而是：
1. 读取 agent 的配置文件（如 Claude Code 的 `.claude/settings.json`）
2. 解析其中的权限设置
3. 根据实际配置进行验证

## Claude Code 权限来源

### 1. settings.json 中的 permissions 配置

```json
{
  "permissions": {
    "allowed": [
      {
        "tool": "Read",
        "prompt": "read files"
      },
      {
        "tool": "Bash",
        "prompt": "run git commands",
        "match": "git.*"
      }
    ],
    "global": [
      {
        "tool": "Glob",
        "prompt": "search for files"
      }
    ]
  }
}
```

### 2. 工作空间限制

Claude Code 有工作空间（workspace）的概念：
- 只能访问当前工作目录及其子目录
- 访问工作空间外的文件需要特殊权限

### 3. 危险操作提示

Claude Code 会对某些操作进行确认：
- 删除文件
- 执行可能危险的命令
- 访问敏感路径

## OpenClaw 权限来源

OpenClaw 基于 Anthropic Computer Use API，其权限由：
1. API 本身的限制
2. 系统级别的权限控制
3. 用户配置的安全策略

## 正确的实现方式

### 1. 配置文件解析器

```python
class ClaudeCodeConfigParser:
    """解析 Claude Code 的 settings.json"""
    
    def parse_settings(self, settings_path):
        # 读取 .claude/settings.json
        # 提取 permissions 配置
        # 构建权限模型
        pass
```

### 2. 工作空间检测

```python
class WorkspaceValidator:
    """验证文件路径是否在工作空间内"""
    
    def __init__(self, workspace_path):
        self.workspace_path = workspace_path
    
    def is_within_workspace(self, file_path):
        # 检查路径是否在工作空间内
        pass
```

### 3. 动态权限模型

```python
class DynamicPermissionModel:
    """基于实际配置的动态权限模型"""
    
    def __init__(self, agent_type, config_path):
        self.agent_type = agent_type
        self.config = self._load_config(config_path)
        self.workspace = self._detect_workspace()
    
    def _load_config(self, config_path):
        # 根据 agent 类型加载对应的配置文件
        if self.agent_type == "claude_code":
            return self._parse_claude_settings(config_path)
        elif self.agent_type == "openclaw":
            return self._parse_openclaw_config(config_path)
```

## 需要读取的配置文件

### Claude Code
- `.claude/settings.json` - 用户权限配置
- `.claude/settings.local.json` - 本地覆盖配置
- 工作目录路径 - 从环境或配置中获取

### OpenClaw
- 配置文件路径（需要调研）
- 系统权限设置

## 验证逻辑

### 1. 工具调用验证

```python
def validate_tool_call(self, tool_call):
    tool_name = tool_call["name"]
    arguments = tool_call["arguments"]
    
    # 1. 检查工具是否在 allowed 或 global 列表中
    if not self._is_tool_allowed(tool_name):
        return ValidationResult(
            is_authorized=False,
            reason=f"工具 {tool_name} 未在 settings.json 的 permissions 中配置"
        )
    
    # 2. 检查参数约束（如果配置中有 match 规则）
    if not self._matches_permission_pattern(tool_name, arguments):
        return ValidationResult(
            is_authorized=False,
            reason=f"工具调用不匹配配置的 match 模式"
        )
    
    # 3. 检查工作空间限制
    if tool_name in ["Read", "Write", "Edit"]:
        file_path = arguments.get("file_path")
        if not self._is_within_workspace(file_path):
            return ValidationResult(
                is_authorized=False,
                reason=f"文件 {file_path} 在工作空间外"
            )
    
    return ValidationResult(is_authorized=True)
```

### 2. 基于实际配置的规则

不是我们定义"rm -rf 危险"，而是：
- 如果 settings.json 中没有配置允许 `rm` 命令，则拒绝
- 如果配置了 `match: "git.*"`，则只允许 git 开头的命令

## 架构修订

```
permissions/
├── DESIGN.md                    # 本设计文档
├── parsers/                     # 配置文件解析器
│   ├── __init__.py
│   ├── claude_code.py          # Claude Code settings.json 解析器
│   └── openclaw.py             # OpenClaw 配置解析器
├── validators/                  # 验证器
│   ├── __init__.py
│   ├── workspace.py            # 工作空间验证
│   └── permission.py           # 权限验证
├── loader.py                   # 动态加载器
└── models/                     # 不再是静态配置，而是示例
    └── examples/               # 示例配置
```

## 实现步骤

1. **研究 Claude Code 的 settings.json 格式**
   - 读取实际的配置文件
   - 理解 permissions 结构
   - 理解 allowed/global 的区别

2. **实现配置解析器**
   - 解析 settings.json
   - 提取权限规则
   - 构建动态模型

3. **实现工作空间检测**
   - 检测当前工作目录
   - 验证路径是否在工作空间内

4. **实现权限验证**
   - 基于实际配置验证
   - 不添加主观规则

## 示例

### 实际的 Claude Code settings.json

```json
{
  "permissions": {
    "allowed": [
      {
        "tool": "Bash",
        "prompt": "run git commands",
        "match": "git.*"
      }
    ]
  }
}
```

### 验证结果

```python
# 这个会通过（匹配 git.* 模式）
validate({
    "name": "Bash",
    "arguments": {"command": "git status"}
})
# => is_authorized: True

# 这个会被拒绝（不匹配 git.* 模式）
validate({
    "name": "Bash",
    "arguments": {"command": "ls -la"}
})
# => is_authorized: False
# => reason: "Bash 命令不匹配配置的 match 模式 'git.*'"

# 这个会被拒绝（工具未配置）
validate({
    "name": "Write",
    "arguments": {"file_path": "/tmp/test.txt"}
})
# => is_authorized: False
# => reason: "工具 Write 未在 settings.json 的 permissions 中配置"
```

## 总结

**错误的做法**：我们定义"rm -rf 危险"、"sudo 危险"

**正确的做法**：
1. 读取 Claude Code 的 settings.json
2. 如果 settings.json 中没有允许 Bash 工具，则所有 Bash 命令都被拒绝
3. 如果允许了 Bash 但有 match 规则，则只允许匹配的命令
4. 检查文件路径是否在工作空间内

这才是真正的"权限建模"——基于 agent 自身的配置，而不是我们的主观判断。
