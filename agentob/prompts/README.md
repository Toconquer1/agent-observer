# 分析提示词模板

本目录包含用于分析 Agent 执行轨迹的提示词模板。每个模板对应一种信息类型。

## 模板文件

- `user_message_prompt.txt` - 分析用户消息
- `tool_calls_prompt.txt` - 分析工具调用
- `tool_result_prompt.txt` - 分析工具执行结果
- `assistant_text_prompt.txt` - 分析助手回复
- `assistant_thinking_prompt.txt` - 分析模型思考过程

## 模板变量

每个模板支持以下占位符，会在运行时自动填充：

- `{history_summaries}` - 历史项摘要（超过3项之前的所有项，只保留大意）
- `{recent_items}` - 近期项详情（最近3项的完整原始内容）
- `{content}` - 当前分析项的内容

## 滑动窗口机制

为了避免上下文爆炸，分析器采用滑动窗口机制：

1. **历史项**（当前项之前超过3项的）：只保留摘要（summary），不包含原始内容
2. **近期项**（最近3项）：保留完整的原始内容
3. **当前项**：正在分析的项

这样可以确保：
- 分析时有足够的上下文信息
- 不会因为历史项过多导致 token 消耗过大
- 每次分析的成本相对固定

## 分析结果格式

每个模板要求 LLM 返回以下 JSON 格式：

```json
{
  "summary": "内容的一句话概括（用于后续上下文压缩）",
  "error_analysis": {
    "is_correct": true/false,
    "is_necessary": true/false,
    "reasoning": "详细说明步骤是否正确、是否必要",
    "flag": "error/unnecessary/ok"
  }
}
```

### 字段说明

- `summary`: 简短概括，用于后续作为历史项摘要
- `error_analysis.is_correct`: 该步骤是否正确（没有错误）
- `error_analysis.is_necessary`: 该步骤是否必要（对任务完成有帮助）
- `error_analysis.reasoning`: 详细分析理由
- `error_analysis.flag`: 标记类型
  - `"ok"` - 正确且必要
  - `"unnecessary"` - 不必要或冗余
  - `"error"` - 有错误或会导致问题

## 修改提示词

你可以直接编辑这些 `.txt` 文件来调整分析逻辑：

1. 修改评判标准
2. 调整输出格式要求
3. 添加特定领域的分析维度
4. 改变分析的详细程度

修改后无需重新编译，下次运行分析时会自动加载新的模板。

## 示例

假设当前正在分析第 5 项（一个工具调用），则：

- `{history_summaries}` 包含第 1 项的摘要
- `{recent_items}` 包含第 2、3、4 项的完整内容
- `{content}` 是第 5 项的工具调用详情

这样 LLM 可以：
- 了解整体流程（通过历史摘要）
- 看到最近的详细操作（通过近期项）
- 分析当前操作是否合理（基于上下文）
