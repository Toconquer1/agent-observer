# agentob 快速开始指南

## 安装

```bash
cd agent-observer
pip install -e .
```

## 基本使用

### 1. 观测 Claude Code

```bash
agentob -- claude
```

执行后：
- mitmproxy 会在后台启动（端口 8080）
- Claude Code 会在代理环境中运行
- 所有 API 请求会被捕获到 `.agentob/flows.mitm`
- 退出 Claude Code 后自动解析和分析

### 2. 查看结果

```bash
ls -la .agentob/
```

输出结构：
```
.agentob/
├── flows.mitm                    # 原始流量文件
└── decoded_flows/                # 解码后的数据
    ├── 1_request_*.json
    ├── 1_response_*.json
    └── analyzed/                 # 分析结果
        ├── prompts.txt           # 系统提示词
        ├── tools.json            # 工具定义
        └── call_trace.json       # 调用轨迹
```

### 3. 自定义选项

```bash
# 指定输出目录
agentob -o ./my_analysis -- claude

# 使用不同端口
agentob -p 9090 -- claude

# 跳过自动分析（只捕获流量）
agentob --no-analysis -- claude
```

## 观测其他 Agent 应用

### Python 脚本

```bash
agentob -- python my_agent.py
```

### Node.js 应用

```bash
agentob -- node app.js
```

### 任意命令

```bash
agentob -- npm run dev
agentob -- uv run main.py
```

## 手动解析已有的 mitm 文件

```python
from agentob.decoder import MitmDecoder
from agentob.simplify import RequestSimplifier
from agentob.parser import CallTraceParser

# 解码
decoder = MitmDecoder('flows.mitm', './output')
decoder.decode()

# 简化
simplifier = RequestSimplifier('./output')
simplifier.simplify()

# 解析调用轨迹
parser = CallTraceParser('./output')
parser.parse()
```

## 常见问题

### 代理无法启动

检查端口占用：
```bash
# Windows
netstat -ano | findstr 8080

# Linux/Mac
lsof -i :8080
```

使用其他端口：
```bash
agentob -p 9090 -- claude
```

### 没有捕获到请求

1. 检查 `.agentob/flows.mitm` 是否生成
2. 确认目标应用使用了代理环境变量
3. 某些应用可能需要额外配置

### 证书错误

首次运行 mitmproxy 会生成证书在 `~/.mitmproxy/`

对于 Node.js 应用，agentob 会自动设置 `NODE_TLS_REJECT_UNAUTHORIZED=0`

## 下一步

- 查看 [README.md](README.md) 了解详细文档
- 查看 [TESTING.md](TESTING.md) 了解测试方法
- 使用真实 mitm 文件测试解码功能
