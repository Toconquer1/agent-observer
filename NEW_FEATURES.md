# agentob 新功能说明

## 1. 会话 ID 时间戳

### 改进内容
会话 ID 现在包含分钟级时间戳，格式为：`YYYYMMDD_HHMM_<8位随机ID>`

### 示例
- 旧格式：`a073ac04`
- 新格式：`20260517_1430_a073ac04`

### 优势
- 可以按时间快速过滤和查找会话
- 一眼就能看出会话的创建时间
- 便于按时间顺序组织和清理旧会话

### 目录结构示例
```
.agentob/
├── 20260517_0915_abc12345/
├── 20260517_1023_def67890/
├── 20260517_1430_a073ac04/
└── 20260518_0830_xyz98765/
```

## 2. Attach 模式（支持后台 Agent）

### 使用场景
适用于观测已经在后台运行的 agent 应用，如 OpenClaw、自定义后台服务等。

### 使用方法

#### 方式一：无限期捕获（直到 Ctrl+C）
```bash
agentob attach
```

#### 方式二：指定捕获时长（秒）
```bash
agentob attach 300  # 捕获 300 秒后自动停止
```

### 完整使用流程

**步骤 1：启动 agentob attach**
```bash
cd your-project
agentob attach
```

你会看到类似输出：
```
============================================================
[agentob] Attach 模式已启动
[agentob] 会话 ID: 20260517_1430_a073ac04
[agentob] 代理地址: http://127.0.0.1:8080

[agentob] 请在你的 agent 应用中设置以下环境变量：
[agentob]   export HTTP_PROXY=http://127.0.0.1:8080
[agentob]   export HTTPS_PROXY=http://127.0.0.1:8080

[agentob] 对于 Node.js 应用，还需要：
[agentob]   export NODE_EXTRA_CA_CERTS=/home/user/.mitmproxy/mitmproxy-ca-cert.pem

[agentob] 对于 Python 应用，还需要：
[agentob]   export REQUESTS_CA_BUNDLE=/home/user/.mitmproxy/mitmproxy-ca-cert.pem
[agentob]   export SSL_CERT_FILE=/home/user/.mitmproxy/mitmproxy-ca-cert.pem

[agentob] 按 Ctrl+C 停止捕获
============================================================
```

**步骤 2：在另一个终端设置环境变量并启动你的 agent**

对于 Linux/Mac：
```bash
export HTTP_PROXY=http://127.0.0.1:8080
export HTTPS_PROXY=http://127.0.0.1:8080
export NODE_EXTRA_CA_CERTS=~/.mitmproxy/mitmproxy-ca-cert.pem

# 启动你的后台 agent
./openclaw start
# 或
python my_agent.py
```

对于 Windows PowerShell：
```powershell
$env:HTTP_PROXY="http://127.0.0.1:8080"
$env:HTTPS_PROXY="http://127.0.0.1:8080"
$env:NODE_EXTRA_CA_CERTS="$env:USERPROFILE\.mitmproxy\mitmproxy-ca-cert.pem"

# 启动你的后台 agent
.\openclaw.exe start
```

对于 Windows CMD：
```cmd
set HTTP_PROXY=http://127.0.0.1:8080
set HTTPS_PROXY=http://127.0.0.1:8080
set NODE_EXTRA_CA_CERTS=%USERPROFILE%\.mitmproxy\mitmproxy-ca-cert.pem

REM 启动你的后台 agent
openclaw.exe start
```

**步骤 3：让 agent 运行一段时间**

在这期间，所有 HTTP/HTTPS 请求都会被 agentob 捕获。

**步骤 4：停止捕获**

回到运行 `agentob attach` 的终端，按 `Ctrl+C`：
```
^C
[agentob] 收到 Ctrl+C，正在停止...
[agentob] mitmproxy 已停止

============================================================
[agentob] 开始流量分析...
============================================================
...
```

agentob 会自动分析捕获的流量并生成可视化报告。

### 与前台模式的对比

| 特性 | 前台模式 | Attach 模式 |
|------|---------|------------|
| 命令 | `agentob -- <命令>` | `agentob attach [时长]` |
| 适用场景 | CLI 工具、短期任务 | 后台服务、长期运行 |
| 环境变量 | 自动注入 | 手动设置 |
| 启动方式 | agentob 启动目标程序 | 用户手动启动 |
| 停止方式 | 目标程序退出 | Ctrl+C 或超时 |

### 示例：观测 OpenClaw

```bash
# 终端 1：启动 agentob
agentob attach 600  # 捕获 10 分钟

# 终端 2：启动 OpenClaw
export HTTP_PROXY=http://127.0.0.1:8080
export HTTPS_PROXY=http://127.0.0.1:8080
export NODE_EXTRA_CA_CERTS=~/.mitmproxy/mitmproxy-ca-cert.pem
./openclaw start

# 让 OpenClaw 运行一段时间...

# 终端 1：10 分钟后自动停止，或提前按 Ctrl+C
# 分析结果会保存在 .agentob/20260517_1430_xxxxxxxx/
```

### 高级选项

指定输出目录和端口：
```bash
agentob -o ./my-analysis -p 9090 attach 300
```

跳过自动分析（只捕获流量）：
```bash
agentob --no-analysis attach
```

### 注意事项

1. **证书问题**：如果遇到 SSL 错误，确保正确设置了证书路径，或者对于 Node.js 应用使用 `NODE_TLS_REJECT_UNAUTHORIZED=0`（仅用于测试）

2. **端口冲突**：如果 8080 端口被占用，使用 `-p` 参数指定其他端口

3. **多个 agent**：可以同时观测多个 agent，只要它们都使用相同的代理设置

4. **性能影响**：代理会略微增加延迟，但对大多数应用影响很小

## 更新日志

### v0.2.0 (2026-05-17)

**新增功能**：
- ✨ 会话 ID 包含分钟级时间戳（格式：`YYYYMMDD_HHMM_<随机ID>`）
- ✨ Attach 模式支持观测后台运行的 agent
- ✨ 支持指定捕获时长或无限期捕获

**改进**：
- 📝 更新 CLI 帮助信息，包含两种使用模式
- 📝 改进错误提示和使用说明

**向后兼容**：
- ✅ 所有现有功能保持不变
- ✅ 前台模式（`agentob -- <命令>`）完全兼容
