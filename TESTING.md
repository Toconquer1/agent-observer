# agentob 开发测试

## 安装和卸载

### 安装（开发模式）

```bash
cd agent-observer
pip install -e .
```

开发模式安装的特点：
- 代码修改后立即生效，无需重新安装
- 会在 Python 环境中注册 `agentob` 命令
- 创建 `.egg-info` 目录

### 卸载

```bash
pip uninstall agentob
```

卸载后：
- `agentob` 命令将不可用
- 但可以继续使用 `python -m agentob` 方式（如果在项目目录下）
- 不会删除项目源代码

### 完全清理

```bash
# 1. 卸载包
pip uninstall agentob -y

# 2. 清理构建文件
cd agent-observer
rm -rf agentob.egg-info
rm -rf agentob/__pycache__
rm -rf build dist

# 3. 清理测试输出（可选）
rm -rf .agentob
rm -rf test_output
```

### 重新安装（用于调试）

```bash
# 完全清理后重新安装
cd agent-observer
pip uninstall agentob -y
rm -rf agentob.egg-info agentob/__pycache__
pip install -e .
```

## 测试 CLI 帮助信息

```bash
cd agent-observer
python -m agentob --help
```

## 测试安装

```bash
cd agent-observer
pip install -e .
agentob --help
```

## 测试解码器（使用真实 mitm 文件）

```python
from agentob.decoder import MitmDecoder

decoder = MitmDecoder('path/to/flows.mitm', './output')
decoder.decode()
```

## 测试分析器

```python
from agentob.analyzer import RequestAnalyzer

analyzer = RequestAnalyzer('./output')
analyzer.analyze()
```

## 完整流程测试

```bash
# 1. 使用 agentob 包装一个简单的命令
agentob -- echo "test"

# 2. 检查输出目录
ls -la .agentob/

# 3. 如果有 flows.mitm 文件，会自动解析
```

## 当前状态

### 已完成
- ✅ 项目结构（pyproject.toml, __init__.py, __main__.py）
- ✅ CLI 接口（cli.py）
- ✅ Wrapper 核心逻辑（wrapper.py）
  - mitmproxy 安装检查
  - 后台启动代理
  - 环境变量注入
  - 子进程管理
  - 代理停止
- ✅ 解码器（decoder.py）
  - SSE 流式响应解析
  - LLM/MCP 请求识别
  - JSON 输出
- ✅ 分析器（analyzer.py）
  - 系统提示词提取
  - 工具列表提取
  - 历史消息去重
  - 执行轨迹生成
- ✅ 使用文档（README.md）

### 待测试
- ⏳ 使用真实 mitm 文件测试解码功能
- ⏳ 端到端测试完整流程

### 下一步（后续迭代）
- 基于大模型的 agent 调用分析
- 结果可视化
