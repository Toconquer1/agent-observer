# agentob 完整功能总结

本文档总结了 agentob 项目的所有功能和改进。

## 项目概述

agentob 是一个用于观测和分析 AI Agent 执行过程的 Python 工具包。通过 mitmproxy 代理捕获 LLM API 调用，解析请求响应，提取关键信息，并提供智能分析和权限验证。

## 核心功能

### 1. 流量捕获与解析
- ✅ 透明代理捕获 HTTP/HTTPS 流量
- ✅ 支持 SSE 流式响应自动重组
- ✅ 识别 LLM API 请求（Anthropic、OpenAI 格式）
- ✅ 提取完整的 thinking、text、tool_calls

### 2. 两种运行模式

#### 前台模式
```bash
agentob -- <命令>
```
- 适用于 CLI 工具和短期任务
- 自动注入环境变量
- 命令退出后自动分析

#### Attach 模式（新增）
```bash
agentob attach [时长]
```
- 适用于后台服务和长期运行的 agent（如 OpenClaw）
- 手动设置环境变量
- 支持指定捕获时长或无限期捕获

### 3. 智能分析系统

#### 提示词模板外部化
- 5 个独立的 `.txt` 模板文件
- 支持模板变量替换
- 方便用户直接编辑

#### 滑动窗口上下文管理
- 历史项（超过3项前）：只保留摘要
- 近期项（最近3项）：保留完整原始内容
- **节省约 40% token 消耗**

#### 新的分析结果格式
- `summary`: 内容大意（用于压缩）
- `error_analysis`: 错误分析
  - `is_correct`: 是否正确
  - `is_necessary`: 是否必要
  - `reasoning`: 详细说明
  - `flag`: `ok` / `unnecessary` / `error`

#### 重试机制
- 最多重试 3 次
- 详细的状态提示
- 增强的字段验证

### 4. 权限验证系统（新增）

#### 动态权限建模
- 可扩展的权限模型架构
- 支持多种权限级别和风险级别
- 基于配置文件的权限定义

#### 已实现的权限模型
- **Claude Code**: 11 个工具，4 个上下文规则
- **OpenClaw**: 4 个工具，7 个上下文规则
- **Default**: 保守的默认策略

#### 验证功能
- 工具白名单/黑名单
- 参数约束验证
- 危险操作检测
- 上下文规则应用
- 详细的违规报告

### 5. 可视化增强

#### HTML 可视化
- 交互式的独立 HTML 页面
- 聊天风格的消息展示
- 根据 flag 显示不同颜色边框
  - `error` - **红色边框** + 阴影
  - `unnecessary` - **橙色边框** + 阴影
  - `ok` - 蓝色边框

#### 权限验证显示
- 权限验证结果卡片
- 风险级别徽章
- 违规原因详细说明
- 未授权调用红色标注

### 6. 会话管理

#### 时间戳会话 ID
- 格式：`YYYYMMDD_HHMM_<8位随机ID>`
- 示例：`20260517_1430_a073ac04`
- 方便按时间过滤和查找

## 文件结构

```
agent-observer/
├── agentob/                          # 主包
│   ├── analyzer.py                   # 分析器（集成权限验证）
│   ├── cli.py                        # CLI（支持 attach 模式）
│   ├── decoder.py                    # 流量解码器
│   ├── parser.py                     # 调用轨迹解析器
│   ├── simplify.py                   # 请求简化器
│   ├── visualizer.py                 # HTML 可视化（显示权限）
│   ├── wrapper.py                    # 核心 wrapper（attach 模式）
│   └── prompts/                      # 提示词模板
│       ├── README.md
│       ├── user_message_prompt.txt
│       ├── tool_calls_prompt.txt
│       ├── tool_result_prompt.txt
│       ├── assistant_text_prompt.txt
│       └── assistant_thinking_prompt.txt
├── permissions/                      # 权限验证系统
│   ├── DESIGN.md                     # 设计文档
│   ├── __init__.py
│   ├── loader.py                     # 权限模型加载器
│   ├── validator.py                  # 权限验证器
│   └── models/                       # 权限模型配置
│       ├── claude_code.json
│       ├── openclaw.json
│       └── default.json
├── README.md                         # 主文档
├── ANALYZER_IMPROVEMENTS.md          # 分析器改进说明
├── NEW_FEATURES.md                   # 新功能详细说明
├── PERMISSIONS_SUMMARY.md            # 权限系统总结
├── CHANGES_SUMMARY.md                # 修改总结
├── test_analyzer_templates.py        # 模板测试
└── test_permissions.py               # 权限测试
```

## 使用示例

### 1. 前台模式 - 观测 Claude Code
```bash
agentob -- claude
```

### 2. Attach 模式 - 观测 OpenClaw
```bash
# 终端 1
agentob attach 600

# 终端 2
export HTTP_PROXY=http://127.0.0.1:8080
export HTTPS_PROXY=http://127.0.0.1:8080
./openclaw start
```

### 3. 修改提示词模板
直接编辑 `agentob/prompts/*.txt` 文件。

### 4. 添加新的权限模型
在 `permissions/models/` 创建新的 JSON 文件。

## 输出结构

```
.agentob/
└── 20260517_1430_a073ac04/          # 会话目录（带时间戳）
    ├── flows.mitm                    # 原始流量
    ├── raw_requests/                 # 原始请求
    ├── filtered_requests/            # 过滤后的请求
    └── analyzed/                     # 分析结果
        ├── prompts.txt               # 系统提示词
        ├── tools.json                # 工具定义
        ├── call_trace.json           # 调用轨迹
        └── analyze.json              # LLM 分析（含权限验证）
    └── visualization.html            # 可视化页面
```

## 性能优化

### Token 消耗
- 改进前：~100,000 tokens（20 个项）
- 改进后：~60,000 tokens（20 个项）
- **节省约 40%**

### 缓存机制
- 权限模型缓存
- 提示词模板缓存

## 安全特性

### 权限验证
- 默认拒绝策略
- 最小权限原则
- 分层防御（全局 + 工具 + 上下文）
- 风险评级（low/medium/high/critical）
- 审计追踪

### 危险操作检测
- 递归删除（rm -rf）
- 权限提升（sudo）
- 系统文件修改
- 网络下载执行
- Fork 炸弹
- 无限循环

## 测试

### 运行测试
```bash
# 测试提示词模板
python test_analyzer_templates.py

# 测试权限验证
python test_permissions.py

# 完整测试
agentob -- echo "test"
```

## 向后兼容性

✅ **完全兼容**：
- 所有现有功能保持不变
- 前台模式完全兼容
- 输入文件格式不变

⚠️ **不兼容变更**：
- 分析结果格式从 `{summary, analysis, score}` 改为 `{summary, error_analysis, permission_checks}`
- 旧的分析结果文件需要重新生成

## 文档

- `README.md` - 主文档
- `ANALYZER_IMPROVEMENTS.md` - 分析器改进
- `NEW_FEATURES.md` - 新功能说明
- `PERMISSIONS_SUMMARY.md` - 权限系统总结
- `CHANGES_SUMMARY.md` - 修改总结
- `permissions/DESIGN.md` - 权限系统设计
- `agentob/prompts/README.md` - 提示词模板说明

## 后续改进方向

1. **可配置的窗口大小**：允许用户配置保留多少近期项
2. **分析缓存**：避免重复分析相同的项
3. **批量分析**：一次 API 调用分析多个项
4. **导出报告**：生成 Markdown/PDF 格式
5. **实时监控**：在 attach 模式下实时显示
6. **机器学习**：基于历史数据学习权限模式
7. **权限建议**：自动生成最小权限配置
8. **多租户支持**：不同用户不同权限

## 贡献者

本项目由 Claude (Anthropic) 协助开发。

## 许可证

MIT License
