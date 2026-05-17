# 分析器改进说明

## 修改概述

本次修改对 agentob 的分析器进行了重大改进，主要包括三个方面：

### 1. 提示词模板外部化

**改进前**：提示词硬编码在 `analyzer.py` 中，难以修改和维护。

**改进后**：
- 创建 `agentob/prompts/` 目录
- 每种分析类型对应一个独立的 `.txt` 文件：
  - `user_message_prompt.txt` - 用户消息分析
  - `tool_calls_prompt.txt` - 工具调用分析
  - `tool_result_prompt.txt` - 工具结果分析
  - `assistant_text_prompt.txt` - 助手回复分析
  - `assistant_thinking_prompt.txt` - 模型思考分析
- 支持模板变量：`{history_summaries}`, `{recent_items}`, `{content}`
- 修改提示词无需重新编译，直接编辑 `.txt` 文件即可

### 2. 滑动窗口上下文管理

**改进前**：每次分析包含前 5 个项的完整内容，导致上下文爆炸。

**改进后**：
- **历史项**（超过 3 项之前的）：只保留摘要（summary）
- **近期项**（最近 3 项）：保留完整原始内容
- **当前项**：正在分析的项

**优势**：
- 避免 token 消耗过大
- 保持足够的上下文信息
- 每次分析成本相对固定

**实现**：
- 新增 `_build_context_for_analysis()` 方法
- 移除旧的 `_get_context_items()` 方法
- 修改 `_analyze_single_item()` 方法签名

### 3. 新的分析结果格式

**改进前**：
```json
{
  "summary": "摘要",
  "analysis": "详细分析",
  "score": 3
}
```

**改进后**：
```json
{
  "summary": "内容大意（用于后续压缩）",
  "error_analysis": {
    "is_correct": true/false,
    "is_necessary": true/false,
    "reasoning": "详细说明",
    "flag": "error/unnecessary/ok"
  }
}
```

**字段说明**：
- `summary`: 简短概括，用于后续作为历史项摘要
- `error_analysis.is_correct`: 该步骤是否正确
- `error_analysis.is_necessary`: 该步骤是否必要
- `error_analysis.reasoning`: 详细分析理由
- `error_analysis.flag`: 标记类型
  - `"ok"` - 正确且必要（绿色）
  - `"unnecessary"` - 不必要或冗余（橙色边框）
  - `"error"` - 有错误（红色边框）

### 4. 可视化增强

**改进**：
- 根据 `flag` 类型显示不同颜色的边框：
  - `error` - 红色边框 + 阴影
  - `unnecessary` - 橙色边框 + 阴影
  - `ok` - 蓝色边框（默认）
- 显示 `is_correct` 和 `is_necessary` 状态
- 使用图标标识不同状态（✅ ⚠️ ❌）

## 文件变更

### 新增文件
```
agentob/prompts/
├── README.md                      # 提示词模板使用说明
├── user_message_prompt.txt        # 用户消息分析模板
├── tool_calls_prompt.txt          # 工具调用分析模板
├── tool_result_prompt.txt         # 工具结果分析模板
├── assistant_text_prompt.txt      # 助手回复分析模板
└── assistant_thinking_prompt.txt  # 模型思考分析模板
```

### 修改文件
- `agentob/analyzer.py` - 核心分析逻辑
  - 新增 `_load_prompt_templates()` 方法
  - 新增 `_build_context_for_analysis()` 方法
  - 重写 `_analyze_single_item()` 方法
  - 更新 `analyze()` 方法调用方式

- `agentob/visualizer.py` - HTML 可视化
  - 更新 CSS 样式，支持错误标记
  - 修改 `_generate_message()` 方法，适配新的分析结果格式
  - 添加错误/冗余标记的视觉效果

## 使用示例

### 修改提示词模板

直接编辑 `agentob/prompts/tool_calls_prompt.txt`：

```markdown
## 上下文

### 历史项摘要（仅保留大意）
{history_summaries}

### 近期项详情（最近3项原始内容）
{recent_items}

## 当前分析项

**类型**: 工具调用

**调用详情**:
```json
{content}
```

## 分析要求

请分析当前工具调用...
```

### 运行分析

```python
from agentob.analyzer import AgentAnalyzer

analyzer = AgentAnalyzer(
    analyzed_dir="path/to/analyzed",
    api_key="your-api-key"
)
result = analyzer.analyze()
```

### 生成可视化

```python
from agentob.visualizer import generate_visualization

html_path = generate_visualization("path/to/analyzed")
print(f"可视化已生成: {html_path}")
```

## 向后兼容性

**不兼容变更**：
- 分析结果格式从 `{summary, analysis, score}` 改为 `{summary, error_analysis}`
- 旧的分析结果文件需要重新生成

**兼容性保持**：
- 输入文件格式（`prompts.txt`, `tools.json`, `call_trace.json`）保持不变
- 可视化 HTML 仍然可以正常生成（只是显示效果不同）

## 性能优化

### Token 消耗对比

假设分析 20 个项：

**改进前**：
- 第 1 项：0 个历史项
- 第 6 项：5 个历史项完整内容（~5000 tokens）
- 第 20 项：5 个历史项完整内容（~5000 tokens）
- **总计**：~100,000 tokens

**改进后**：
- 第 1 项：0 个历史项
- 第 6 项：2 个历史摘要（~200 tokens）+ 3 个近期项（~3000 tokens）
- 第 20 项：16 个历史摘要（~1600 tokens）+ 3 个近期项（~3000 tokens）
- **总计**：~60,000 tokens

**节省约 40% 的 token 消耗**

## 测试

运行测试脚本验证功能：

```bash
cd agent-observer
python test_analyzer_templates.py
```

## 后续改进建议

1. **可配置的窗口大小**：允许用户配置保留多少近期项
2. **分析缓存**：避免重复分析相同的项
3. **批量分析**：一次 API 调用分析多个项
4. **自定义评判标准**：允许用户在模板中定义自己的评判维度
5. **导出报告**：生成 Markdown/PDF 格式的分析报告

## 相关文档

- [提示词模板说明](agentob/prompts/README.md)
- [项目总结](PROJECT_SUMMARY.md)
- [测试说明](TESTING.md)
