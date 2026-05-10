"""
基于 LLM 的 agent 调用分析模块。

此模块使用 LLM API 分析解码和解析后的 agent 执行轨迹，
生成关于系统提示词、工具和各个调用轨迹的分析洞察。
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Any, Optional
import anthropic
from dotenv import load_dotenv

# 加载 .env 文件（如果存在）
load_dotenv()


class AgentAnalyzer:
    """使用 LLM 分析 agent 执行轨迹。"""

    def __init__(self, analyzed_dir: str, api_key: Optional[str] = None, api_url: Optional[str] = None):
        """
        初始化分析器。

        Args:
            analyzed_dir: 包含 prompts.txt、tools.json、call_trace.json 的分析目录路径
            api_key: Anthropic API 密钥（也可从 .env 读取）
            api_url: API 基础 URL（也可从 .env 读取，默认使用 Anthropic 官方 API）
        """
        self.analyzed_dir = Path(analyzed_dir)
        self.output_file = self.analyzed_dir / "analyze.json"

        # 加载 API 配置
        self.api_key = api_key or os.getenv("AGOB_API_KEY")
        self.api_url = api_url or os.getenv("AGOB_API_URL", "https://api.anthropic.com")
        self.model = os.getenv("AGOB_MODEL", "claude-sonnet-4-6")

        if not self.api_key:
            raise ValueError("API key not provided. Set AGOB_API_KEY environment variable or pass api_key parameter.")

        # 初始化 Anthropic 客户端
        self.client = anthropic.Anthropic(
            api_key=self.api_key,
            base_url=self.api_url
        )

        # 加载输入文件
        self.prompts = self._load_prompts()
        self.tools = self._load_tools()
        self.call_trace = self._load_call_trace()

    def _load_prompts(self) -> str:
        """从 prompts.txt 加载系统提示词。"""
        prompts_file = self.analyzed_dir / "prompts.txt"
        if not prompts_file.exists():
            return ""
        return prompts_file.read_text(encoding="utf-8")

    def _load_tools(self) -> List[Dict[str, Any]]:
        """从 tools.json 加载工具列表。"""
        tools_file = self.analyzed_dir / "tools.json"
        if not tools_file.exists():
            return []
        with open(tools_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            # tools.json 可能是列表或字典
            if isinstance(data, list):
                return data
            elif isinstance(data, dict):
                # 将字典转换为工具列表
                return [{"name": name, **tool_data} if isinstance(tool_data, dict) else {"name": name, "description": str(tool_data)}
                        for name, tool_data in data.items()]
            else:
                return []

    def _load_call_trace(self) -> List[Dict[str, Any]]:
        """从 call_trace.json 加载调用轨迹。"""
        trace_file = self.analyzed_dir / "call_trace.json"
        if not trace_file.exists():
            return []
        with open(trace_file, "r", encoding="utf-8") as f:
            return json.load(f)

    def _analyze_system_prompt(self) -> str:
        """分析系统提示词，理解 agent 的工作模式。"""
        if not self.prompts:
            return ""

        prompt = f"""请分析以下系统提示词，总结出当前 agent 的工作模式、能力范围和行为特征。

系统提示词：
{self.prompts[:8000]}  # 限制长度以避免超出 token 上限

请用中文简要总结（200-300字）：
1. Agent 的主要角色和定位
2. Agent 的核心能力
3. Agent 的工作方式和限制
"""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.content[0].text
        except Exception as e:
            print(f"Error analyzing system prompt: {e}")
            return ""

    def _analyze_tools(self) -> str:
        """分析可用工具并总结其功能。"""
        if not self.tools:
            return ""

        # 提取工具名称和描述
        tool_summary = []
        for tool in self.tools[:50]:  # 最多取前 50 个工具
            name = tool.get("name", "Unknown")
            desc = tool.get("description", "")[:200]  # 限制描述长度
            tool_summary.append(f"- {name}: {desc}")

        tools_text = "\n".join(tool_summary)

        prompt = f"""请分析以下工具列表，简要总结这些工具的功能类别和用途。

可用工具（共 {len(self.tools)} 个）：
{tools_text}

请用中文简要总结（100-150字）：
1. 工具的主要类别
2. Agent 可以完成的任务类型
"""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=512,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.content[0].text
        except Exception as e:
            print(f"Error analyzing tools: {e}")
            return ""

    def _get_context_items(self, current_index: int, all_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """获取当前项及最多前 5 个项作为上下文。"""
        # 在扁平化列表中查找当前项的位置
        flat_items = []
        for call in self.call_trace:
            for item in call.get("information_list", []):
                flat_items.append({
                    "call_index": call.get("index"),
                    "model": call.get("model"),
                    **item
                })

        # 查找当前项位置
        current_pos = -1
        for i, item in enumerate(flat_items):
            if item == all_items[current_index]:
                current_pos = i
                break

        if current_pos == -1:
            return [all_items[current_index]]

        # 取最多 5 个前序项 + 当前项
        start = max(0, current_pos - 5)
        return flat_items[start:current_pos + 1]

    def _analyze_single_item(self, item: Dict[str, Any], context: List[Dict[str, Any]],
                            previous_analysis: List[Dict[str, Any]]) -> Dict[str, str]:
        """
        分析单个信息项。

        Returns:
            包含 'summary' 和 'analysis' 键的字典
        """
        item_type = item.get("type", "unknown")

        # 构建上下文摘要
        context_text = "前序上下文：\n"
        for ctx_item in context[:-1]:  # 排除当前项
            ctx_type = ctx_item.get("type", "unknown")
            if ctx_type == "user_message":
                content = str(ctx_item.get("content", ""))[:200]
                context_text += f"- 用户消息: {content}...\n"
            elif ctx_type == "tool_calls":
                calls = ctx_item.get("calls", [])
                context_text += f"- 工具调用: {len(calls)} 个工具\n"
            elif ctx_type == "tool_result":
                context_text += f"- 工具结果\n"
            elif ctx_type == "assistant_text":
                text = ctx_item.get("content", "")[:100]
                context_text += f"- 助手回复: {text}...\n"

        # 构建前序分析摘要
        prev_summary = ""
        if previous_analysis:
            prev_summary = "之前的分析摘要：\n"
            for prev in previous_analysis[-3:]:  # 最近 3 条分析
                prev_summary += f"- {prev.get('summary', '')}...\n"

        # 根据项类型创建分析提示词
        if item_type == "user_message":
            content = json.dumps(item.get("content", []), ensure_ascii=False, indent=2)[:1000]
            prompt = f"""{context_text}

{prev_summary}

当前项（用户消息）：
{content}

请分析：
1. 用户的意图和需求（一句话概括，作为摘要）
2. 这个消息在整个调用流程中的作用和重要性（2-3句话）
3. 评分（1-5分，5分表示非常重要的转折点或关键操作）

请以JSON格式返回：
{{"summary": "摘要", "analysis": "详细分析", "score": 分数}}
"""

        elif item_type == "tool_calls":
            calls = item.get("calls", [])
            calls_text = json.dumps(calls, ensure_ascii=False, indent=2)[:1000]
            prompt = f"""{context_text}

{prev_summary}

当前项（工具调用）：
{calls_text}

请分析：
1. 调用的工具和参数（保留原始参数，作为摘要）
2. 调用意图和预期效果（2-3句话）
3. 评分（1-5分，5分表示关键操作）

请以JSON格式返回：
{{"summary": "工具: {calls[0].get('name', 'unknown')} - 参数: ...", "analysis": "详细分析", "score": 分数}}
"""

        elif item_type == "tool_result":
            content = str(item.get("content", ""))[:500]
            prompt = f"""{context_text}

{prev_summary}

当前项（工具结果）：
{content}

请分析：
1. 工具执行结果概要（一句话）
2. 结果的意义和对后续流程的影响（2-3句话）
3. 评分（1-5分）

请以JSON格式返回：
{{"summary": "摘要", "analysis": "详细分析", "score": 分数}}
"""

        elif item_type == "assistant_text":
            text = item.get("content", "")[:500]
            prompt = f"""{context_text}

{prev_summary}

当前项（助手回复）：
{text}

请分析：
1. 助手回复的主要内容（一句话）
2. 回复的质量和完整性（2-3句话）
3. 评分（1-5分）

请以JSON格式返回：
{{"summary": "摘要", "analysis": "详细分析", "score": 分数}}
"""

        else:
            # 未知类型
            return {
                "summary": f"未知类型: {item_type}",
                "analysis": "无法分析此类型的项目",
                "score": 0
            }

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=512,
                messages=[{"role": "user", "content": prompt}]
            )

            # 解析 JSON 响应
            result_text = response.content[0].text
            # 尝试从响应中提取 JSON
            if "{" in result_text and "}" in result_text:
                start = result_text.index("{")
                end = result_text.rindex("}") + 1
                result = json.loads(result_text[start:end])
                return result
            else:
                return {
                    "summary": result_text[:100],
                    "analysis": result_text,
                    "score": 3
                }
        except Exception as e:
            print(f"Error analyzing item: {e}")
            return {
                "summary": f"{item_type} 分析失败",
                "analysis": f"分析过程中出现错误: {str(e)}",
                "score": 0
            }

    def _generate_overall_analysis(self, item_analyses: List[Dict[str, Any]]) -> str:
        """基于所有项的分析生成整体分析报告。"""
        # 构建所有分析的摘要
        summary_text = "各项调用分析摘要：\n"
        for i, analysis in enumerate(item_analyses[:20]):  # 最多取前 20 条
            summary_text += f"{i+1}. {analysis.get('summary', '')} (评分: {analysis.get('score', 0)})\n"

        prompt = f"""基于以下 agent 调用过程的分析，请生成一份整体分析报告。

{summary_text}

请用中文生成报告（300-500字），包括：
1. 整体执行流程概述
2. 关键操作和决策点
3. Agent 的表现评价（效率、准确性、完整性）
4. 可能的改进建议
"""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=2048,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.content[0].text
        except Exception as e:
            print(f"Error generating overall analysis: {e}")
            return ""

    def analyze(self) -> Dict[str, Any]:
        """
        执行完整分析并生成 analyze.json。

        Returns:
            分析结果字典
        """
        result = {
            "system_prompt_analysis": "",
            "tools_analysis": "",
            "call_analyses": [],
            "overall_analysis": ""
        }

        try:
            # 1. 分析系统提示词
            print("正在分析系统提示词...")
            result["system_prompt_analysis"] = self._analyze_system_prompt()

            # 2. 分析工具
            print("正在分析工具...")
            result["tools_analysis"] = self._analyze_tools()

            # 3. 分析每个调用项
            print("正在分析调用轨迹项...")
            all_items = []
            for call in self.call_trace:
                for item in call.get("information_list", []):
                    all_items.append(item)

            item_analyses = []
            for i, item in enumerate(all_items):
                print(f"  Analyzing item {i+1}/{len(all_items)}...")
                context = self._get_context_items(i, all_items)
                analysis = self._analyze_single_item(item, context, item_analyses)
                item_analyses.append(analysis)

            result["call_analyses"] = item_analyses

            # 4. 生成整体分析
            print("正在生成整体分析...")
            result["overall_analysis"] = self._generate_overall_analysis(item_analyses)

        except Exception as e:
            print(f"Error during analysis: {e}")
            # 保留部分结果

        # 保存结果
        with open(self.output_file, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        print(f"Analysis saved to {self.output_file}")
        return result


def analyze_agent_execution(analyzed_dir: str, api_key: Optional[str] = None,
                            api_url: Optional[str] = None) -> Dict[str, Any]:
    """
    分析 agent 执行的便捷函数。

    Args:
        analyzed_dir: 分析目录路径
        api_key: Anthropic API 密钥
        api_url: API 基础 URL

    Returns:
        分析结果字典
    """
    analyzer = AgentAnalyzer(analyzed_dir, api_key, api_url)
    return analyzer.analyze()
