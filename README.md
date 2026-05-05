# agentob - Agent Execution Observer

一个用于观测和分析 AI Agent 执行过程的 Python 工具包。通过代理捕获 LLM API 调用，解析请求响应，提取系统提示词、工具调用等关键信息。

## 功能特性

- 🔍 **透明代理**：通过 mitmproxy 捕获所有 LLM API 请求
- 📊 **自动解析**：支持 SSE 流式响应和标准 JSON 响应
- 🧩 **信息提取**：自动提取系统提示词、工具列表、历史消息
- 📝 **执行轨迹**：生成完整的 Agent 执行轨迹
- 🌐 **跨平台**：支持 Windows 和 Linux 系统
- 🔌 **多 API 兼容**：支持 OpenAI 和 Anthropic 兼容的接口

## 安装

### 从源码安装

```bash
cd agent-observer
pip install -e .
```

安装后会自动安装 `mitmproxy` 依赖，并注册 `agentob` 命令。

### 依赖要求

- Python >= 3.8
- mitmproxy >= 10.0.0

## 使用方法

### 基本用法

```bash
# 使用 agentob 命令
agentob -- <目标命令>

# 或使用 Python 模块方式
python -m agentob -- <目标命令>
```

### 示例

```bash
# 观测 Claude Code CLI
agentob -- claude

# 观测 Python 脚本
agentob -- python my_agent.py

# 观测 Node.js 应用
agentob -- node app.js

# 指定输出目录
agentob -o ./my_output -- claude

# 指定代理端口
agentob -p 9090 -- python script.py

# 跳过自动分析
agentob --no-analysis -- claude
```

### 命令行参数

- `-o, --output <dir>`: 指定输出目录（默认：`.agentob`）
- `-p, --port <port>`: 指定代理端口（默认：`8080`）
- `--no-analysis`: 跳过执行后的自动分析

## 工作原理

1. **启动代理**：在后台启动 mitmproxy，监听指定端口（默认 8080）
2. **生成会话 ID**：为每次执行生成唯一的 8 字符会话 ID
3. **注入环境变量**：设置 `HTTP_PROXY`、`HTTPS_PROXY`、`NODE_EXTRA_CA_CERTS` 等环境变量
4. **执行目标命令**：在代理环境中启动目标 Agent 应用
5. **捕获流量**：mitmproxy 记录所有 HTTP/HTTPS 请求到 `.mitm` 文件
6. **解析流量**：将 `.mitm` 文件解析为 JSON 格式的请求响应对
7. **过滤请求**：只保留 LLM API 请求（包含 `/v1/messages` 或 `/v1/chat/completions`）
8. **分析提取**：提取系统提示词、工具列表、执行轨迹等信息

## 输出结构

执行完成后，会在输出目录（默认 `.agentob`）生成以下文件：

```
.agentob/
└── {session_id}/                       # 会话目录（如 a073ac04）
    ├── flows.mitm                      # 原始流量文件
    └── decoded_flows/                  # 解码后的请求响应
        ├── 1_request_20260505_143022.json
        ├── 1_response_20260505_143023.json
        ├── 2_request_20260505_143025.json
        ├── 2_response_20260505_143026.json
        └── analyzed/                   # 分析结果
            ├── prompts.txt             # 提取的系统提示词
            ├── tools.json              # 提取的工具定义
            └── execution_trace.json    # 执行轨迹
```

### 文件说明

#### 1. 请求文件 (`*_request_*.json`)

包含原始请求信息，经过简化处理：

```json
{
    "type": "llm",
    "url": "https://api.anthropic.com/v1/messages",
    "method": "POST",
    "headers": {...},
    "request_body": {
        "model": "claude-opus-4",
        "messages": [
            {
                "role": "user",
                "content": "Hello"
            },
            {
                "role": "history_placeholder",
                "content": "[History origin: Request 1, Msg 2]",
                "_original_role": "assistant"
            }
        ],
        "system": "[A]",  // 简化后的占位符，原文在 prompts.txt
        "tools": [
            {"name": "Read", "extracted": true}  // 完整定义在 tools.json
        ]
    }
}
```

**简化逻辑：**
- **消息去重**：重复的历史消息替换为 `history_placeholder`，标注首次出现位置
- **系统提示词**：长文本（>50字符）替换为 `[A]`, `[B]` 等占位符
- **工具定义**：提取完整定义，原位置保留 `{name, extracted: true}`

#### 2. 响应文件 (`*_response_*.json`)

对于 SSE 流式响应，自动重组为完整结构：

```json
{
    "type": "llm",
    "status_code": 200,
    "headers": {...},
    "response_body": {
        "is_sse_stream": true,
        "integrated_thinking": "完整的思考过程文本",
        "integrated_text": "完整的回复文本",
        "tool_calls": [
            {
                "id": "toolu_xxx",
                "name": "Read",
                "arguments": {"file_path": "..."}
            }
        ],
        "usage": {"input_tokens": 100, "output_tokens": 50},
        "stop_reason": "tool_use"
    }
}
```

**解析逻辑：**
- **SSE 流重组**：从 `content_block_start`, `content_block_delta`, `message_delta` 事件中提取并合并
- **thinking 提取**：从 `thinking_delta` 事件累积完整思考过程
- **text 提取**：从 `text_delta` 事件累积完整回复文本
- **tool_calls 重组**：从 `input_json_delta` 事件累积并解析完整的工具调用参数

#### 3. 系统提示词 (`prompts.txt`)

```
================ [A] ================
You are Claude, an AI assistant...

================ [B] ================
Another system prompt...
```

#### 4. 工具定义 (`tools.json`)

```json
{
    "Read": {
        "name": "Read",
        "description": "Reads a file...",
        "input_schema": {...}
    },
    "Write": {...}
}
```

#### 5. 执行轨迹 (`execution_trace.json`)

```json
[
    {
        "index": 1,
        "type": "llm",
        "request": {...},
        "response": {...}
    },
    {
        "index": 2,
        "type": "llm",
        "request": {...},
        "response": {...}
    }
]
```

## 支持的 API

### LLM API

通过 URL 路径识别 LLM 请求：
- `/v1/messages` - Anthropic Claude API 格式
- `/v1/chat/completions` - OpenAI API 格式
- 支持任何兼容上述格式的第三方 API（如自定义代理地址）

**注意**：当前版本只分析 LLM 请求，MCP 请求会被过滤掉。

## 环境变量

agentob 会自动注入以下环境变量：

```bash
# 代理设置
HTTP_PROXY=http://127.0.0.1:8080
HTTPS_PROXY=http://127.0.0.1:8080

# Node.js 应用（如 Claude Code）
NODE_TLS_REJECT_UNAUTHORIZED=0

# Python 应用（如 LangChain）
REQUESTS_CA_BUNDLE=~/.mitmproxy/mitmproxy-ca-cert.pem
SSL_CERT_FILE=~/.mitmproxy/mitmproxy-ca-cert.pem
```

## 证书配置

首次运行 mitmproxy 时，会在 `~/.mitmproxy/` 目录生成 CA 证书。对于某些应用，可能需要手动信任该证书。

### Windows

```powershell
# 导入证书到受信任的根证书颁发机构
certutil -addstore -f "ROOT" %USERPROFILE%\.mitmproxy\mitmproxy-ca-cert.cer
```

### Linux

```bash
# 复制证书到系统证书目录
sudo cp ~/.mitmproxy/mitmproxy-ca-cert.pem /usr/local/share/ca-certificates/mitmproxy.crt
sudo update-ca-certificates
```

## 故障排查

### 代理无法启动

- 检查端口 8080 是否被占用：`netstat -ano | findstr 8080` (Windows) 或 `lsof -i :8080` (Linux)
- 尝试使用其他端口：`agentob -p 9090 -- <命令>`

### 证书错误

- 确保 mitmproxy 证书已生成：检查 `~/.mitmproxy/` 目录
- 对于 Node.js 应用，`NODE_TLS_REJECT_UNAUTHORIZED=0` 会跳过证书验证
- 对于 Python 应用，确保证书路径正确

### 没有捕获到请求

- 检查目标应用是否使用了系统代理
- 某些应用可能忽略环境变量，需要在应用配置中手动设置代理
- 检查 `.agentob/flows.mitm` 文件是否生成

## 开发

### 项目结构

```
agent-observer/
├── agentob/
│   ├── __init__.py       # 包初始化
│   ├── cli.py            # 命令行接口
│   ├── wrapper.py        # 核心 wrapper 逻辑
│   ├── decoder.py        # mitm 文件解码
│   └── analyzer.py       # 请求分析和信息提取
├── pyproject.toml        # 项目配置
└── README.md             # 本文档
```

### 运行测试

```bash
# 使用示例 mitm 文件测试解码功能
cd agent-observer
python -c "
from agentob.decoder import MitmDecoder
decoder = MitmDecoder('../analyze-claude-flows-example/flows_no_skill_prompts.mitm', './test_output')
decoder.decode()
"
```

## 限制

- 当前版本仅支持 HTTP/HTTPS 流量捕获
- MCP 请求识别基于 URL 模式匹配，可能需要根据实际情况调整
- 大模型分析和可视化功能将在后续版本实现

## 许可证

MIT License

## 贡献

欢迎提交 Issue 和 Pull Request！