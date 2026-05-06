# agentob 项目总结

## 项目概述

agentob 是一个用于观测和分析 AI Agent 执行过程的 Python 工具。通过 mitmproxy 代理捕获 LLM API 调用，解析请求响应，提取系统提示词、工具调用等关键信息。

## 项目结构

```
agent-observer/
├── agentob/                      # 主包目录
│   ├── __init__.py              # 包初始化，导出主要类
│   ├── __main__.py              # 支持 python -m agentob 调用
│   ├── cli.py                   # 命令行接口，参数解析
│   ├── wrapper.py               # 核心 wrapper，管理代理和子进程
│   ├── decoder.py               # mitm 文件解码器
│   └── analyzer.py              # 请求分析器，提取信息
├── pyproject.toml               # 项目配置和依赖
├── README.md                    # 完整文档
├── QUICKSTART.md                # 快速开始指南
├── TESTING.md                   # 测试说明
├── LICENSE                      # MIT 许可证
├── .gitignore                   # Git 忽略文件
```

## 核心模块说明

### 1. cli.py - 命令行接口

**功能**：
- 解析命令行参数（输出目录、端口、是否自动分析）
- 处理 `--` 分隔符，提取目标命令
- 创建 AgentWrapper 实例并执行

**关键参数**：
- `-o, --output`: 输出目录（默认 `.agentob`）
- `-p, --port`: 代理端口（默认 `8080`）
- `--no-analysis`: 跳过自动分析

**调用方式**：
```bash
agentob -- <命令>
python -m agentob -- <命令>
```

### 2. wrapper.py - 核心 Wrapper

**功能**：
- 检查并安装 mitmproxy
- 后台启动 mitmdump 代理
- 注入代理环境变量
- 执行目标命令
- 停止代理
- 触发自动分析

**关键方法**：
- `_ensure_mitmproxy_installed()`: 检查/安装 mitmproxy
- `_start_mitmproxy()`: 启动代理进程
- `_stop_mitmproxy()`: 停止代理进程
- `_build_env()`: 构建环境变量
- `_run_target_command()`: 执行目标命令
- `_analyze_flows()`: 分析捕获的流量
- `run()`: 主执行流程

**环境变量注入**：
```python
HTTP_PROXY=http://127.0.0.1:8080
HTTPS_PROXY=http://127.0.0.1:8080
NODE_TLS_REJECT_UNAUTHORIZED=0  # Node.js 应用
REQUESTS_CA_BUNDLE=~/.mitmproxy/mitmproxy-ca-cert.pem  # Python 应用
SSL_CERT_FILE=~/.mitmproxy/mitmproxy-ca-cert.pem
```

### 3. decoder.py - 流量解码器

**功能**：
- 读取 mitmproxy 的 `.mitm` 文件
- 解析 HTTP 请求和响应
- 识别 LLM/MCP 请求类型
- 处理 SSE 流式响应
- 输出 JSON 格式的请求响应对

**关键方法**：
- `_parse_sse()`: 解析 SSE 流式响应，合并 thinking、text、tool_calls
- `_extract_body()`: 提取请求/响应体
- `_is_llm_request()`: 判断是否为 LLM 请求
- `_is_mcp_request()`: 判断是否为 MCP 请求
- `decode()`: 主解码流程

**SSE 解析**：
- 合并 `thinking_delta` 为完整 thinking
- 合并 `text_delta` 为完整 text
- 合并 `input_json_delta` 为完整 tool call arguments
- 提取 token usage 和 stop_reason

**输出格式**：
```json
{
    "type": "llm",
    "url": "https://api.anthropic.com/v1/messages",
    "method": "POST",
    "headers": {...},
    "request_body": {...}
}
```

### 4. simplify.py - 请求简化器

**功能**：
- 简化系统提示词（提取为占位符）
- 提取工具定义
- 历史消息去重

**关键方法**：
- `_get_placeholder()`: 生成占位符（A, B, C, ..., Z, AA, AB, ...）
- `_sanitize_message()`: 清理消息中的瞬态字段（cache_control, signature）
- `_is_tool_result_message()`: 识别工具结果消息
- `_simplify_request()`: 简化单个请求文件
- `simplify()`: 主简化流程

**输出文件**：
- `prompts.txt`: 提取的系统提示词
- `tools.json`: 提取的工具定义

### 5. parser.py - 调用轨迹解析器

**功能**：
- 从简化后的请求响应对生成统一的调用轨迹
- 提取用户消息、工具结果、助手思考、助手文本、工具调用
- 比较响应内容与下一个请求的匹配情况

**关键方法**：
- `_extract_user_messages()`: 提取真实用户消息（排除工具结果）
- `_extract_tool_results()`: 提取工具结果消息
- `_compare_response_with_next_request()`: 比较响应与下一个请求
- `_build_call_trace_item()`: 构建单个调用轨迹项
- `parse()`: 主解析流程

**输出文件**：
- `call_trace.json`: 完整调用轨迹

## 工作流程

```
用户执行命令
    ↓
agentob CLI 解析参数
    ↓
AgentWrapper 启动 mitmproxy
    ↓
注入环境变量（HTTP_PROXY 等）
    ↓
执行目标命令（如 claude）
    ↓
mitmproxy 捕获所有 API 请求 → flows.mitm
    ↓
目标命令退出
    ↓
停止 mitmproxy
    ↓
MitmDecoder 解码 flows.mitm → decoded_flows/*.json
    ↓
RequestSimplifier 简化请求 → analyzed/prompts.txt, tools.json
    ↓
CallTraceParser 解析轨迹 → analyzed/call_trace.json
    ↓
完成
```

## 使用场景

### 1. 观测 Claude Code 执行

```bash
agentob -- claude
```

捕获 Claude Code 的所有 API 调用，分析：
- 系统提示词的变化
- 工具调用序列
- Token 使用情况
- 思考过程（thinking）

### 2. 调试 Agent 应用

```bash
agentob -- python my_agent.py
```

观测自己开发的 Agent 应用，了解：
- API 调用频率
- 请求响应内容
- 错误和异常

### 3. 学习 Agent 设计

通过分析成熟 Agent 的执行轨迹，学习：
- 系统提示词设计
- 工具定义方式
- 多轮对话策略

## 技术特点

### 1. 透明代理
- 无需修改目标应用代码
- 通过环境变量注入代理
- 支持 HTTP/HTTPS

### 2. 流式响应处理
- 完整支持 SSE（Server-Sent Events）
- 自动合并分片数据
- 提取完整的 thinking 和 tool calls

### 3. 智能分析
- 自动识别重复的系统提示词
- 历史消息去重（基于内容哈希）
- 工具定义提取和复用

### 4. 跨平台支持
- Windows/Linux/Mac
- 自动处理平台差异（进程管理、信号处理）

## 当前限制

1. **mitm 文件格式**：当前示例 mitm 文件格式有问题，需要使用真实捕获的文件测试
2. **MCP 识别**：基于 URL 模式匹配，可能需要根据实际情况调整
3. **大模型分析**：尚未实现（后续迭代）
4. **可视化**：尚未实现（后续迭代）

## 测试建议

### 1. 安装测试

```bash
cd agent-observer
pip install -e .
agentob --help
```

### 2. 基本功能测试

```bash
# 测试简单命令
agentob -- echo "test"

# 检查输出目录
ls -la .agentob/
```

### 3. 真实场景测试

```bash
# 观测 Claude Code
agentob -- claude

# 执行一些简单操作（如读取文件、执行命令）
# 退出后检查 .agentob/ 目录
```

### 4. 解码器测试

使用真实的 mitm 文件：
```python
from agentob.decoder import MitmDecoder
decoder = MitmDecoder('real_flows.mitm', './output')
decoder.decode()
```

### 5. 简化器和解析器测试

```python
from agentob.simplify import RequestSimplifier
from agentob.parser import CallTraceParser

# 简化请求
simplifier = RequestSimplifier('./output')
simplifier.simplify()

# 解析调用轨迹
parser = CallTraceParser('./output')
parser.parse()
```

## 后续改进方向

1. **增强 mitm 解码**：处理更多边界情况和错误
2. **MCP 深度分析**：提取 MCP 服务器信息、工具调用关系
3. **大模型分析**：使用 LLM 分析执行轨迹，生成洞察
4. **可视化**：生成交互式的执行流程图
5. **性能优化**：大文件处理、流式解析
6. **更多 API 支持**：OpenAI、其他兼容 API

## 依赖说明

- **mitmproxy >= 10.0.0**: 核心代理功能
- **Python >= 3.8**: 基础运行环境

## 许可证

MIT License - 可自由使用、修改和分发
