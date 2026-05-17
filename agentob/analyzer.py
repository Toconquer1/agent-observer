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

# 提示词模板目录
PROMPTS_DIR = Path(__file__).parent / "prompts"


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

        # 加载提示词模板
        self.prompt_templates = self._load_prompt_templates()

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

    @staticmethod
    def _extract_text_from_response(response) -> str:
        """Extract text from API response, handling both TextBlock and ThinkingBlock."""
        for block in response.content:
            if hasattr(block, "text"):
                return block.text
        return ""

    def _load_call_trace(self) -> List[Dict[str, Any]]:
        """从 call_trace.json 加载调用轨迹。"""
        trace_file = self.analyzed_dir / "call_trace.json"
        if not trace_file.exists():
            return []
        with open(trace_file, "r", encoding="utf-8") as f:
            return json.load(f)

    def _load_prompt_templates(self) -> Dict[str, str]:
        """加载所有提示词模板。"""
        templates = {}
        template_files = {
            "user_message": "user_message_prompt.txt",
            "tool_calls": "tool_calls_prompt.txt",
            "tool_result": "tool_result_prompt.txt",
            "assistant_text": "assistant_text_prompt.txt",
            "assistant_thinking": "assistant_thinking_prompt.txt"
        }

        for key, filename in template_files.items():
            template_path = PROMPTS_DIR / filename
            if template_path.exists():
                templates[key] = template_path.read_text(encoding="utf-8")
            else:
                print(f"Warning: Template file not found: {template_path}")
                templates[key] = ""

        return templates

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
            return self._extract_text_from_response(response)
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
            return self._extract_text_from_response(response)
        except Exception as e:
            print(f"Error analyzing tools: {e}")
            return ""

    def _build_context_for_analysis(self, current_index: int, all_items: List[Dict[str, Any]],
                                    previous_analyses: List[Dict[str, Any]]) -> tuple[str, str]:
        """
        构建分析上下文，实现滑动窗口：
        - 历史项（超过3项之前的）：只保留摘要
        - 近期项（最近3项）：保留完整原始内容

        Returns:
            (history_summaries, recent_items) 两个字符串
        """
        # 历史项摘要（当前项之前超过3项的所有项）
        history_summaries = ""
        if current_index > 3:
            history_summaries = "以下是更早的历史项摘要：\n"
            for i in range(0, current_index - 3):
                if i < len(previous_analyses):
                    summary = previous_analyses[i].get("summary", "无摘要")
                    history_summaries += f"{i+1}. {summary}\n"

        # 近期项详情（最近3项的原始内容）
        recent_items = ""
        start_index = max(0, current_index - 3)
        if start_index < current_index:
            recent_items = "以下是最近3项的详细内容：\n\n"
            for i in range(start_index, current_index):
                if i < len(all_items):
                    item = all_items[i]
                    item_type = item.get("type", "unknown")
                    recent_items += f"### 项 {i+1} - {item_type}\n"

                    if item_type == "user_message":
                        content = item.get("content", "")
                        if isinstance(content, list):
                            content = json.dumps(content, ensure_ascii=False, indent=2)[:800]
                        else:
                            content = str(content)[:800]
                        recent_items += f"```\n{content}\n```\n\n"

                    elif item_type == "tool_calls":
                        calls = item.get("calls", [])
                        recent_items += f"```json\n{json.dumps(calls, ensure_ascii=False, indent=2)[:800]}\n```\n\n"

                    elif item_type == "tool_result":
                        content = str(item.get("content", ""))[:500]
                        recent_items += f"```\n{content}\n```\n\n"

                    elif item_type == "assistant_text":
                        text = item.get("content", "")[:500]
                        recent_items += f"```\n{text}\n```\n\n"

                    elif item_type == "assistant_thinking":
                        text = item.get("content", "")[:500]
                        recent_items += f"```\n{text}\n```\n\n"

        return history_summaries, recent_items

    def _analyze_single_item(self, item: Dict[str, Any], current_index: int,
                            all_items: List[Dict[str, Any]],
                            previous_analyses: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        分析单个信息项。

        Returns:
            包含 'summary' 和 'error_analysis' 键的字典
        """
        item_type = item.get("type", "unknown")

        # 获取对应的提示词模板
        template = self.prompt_templates.get(item_type, "")
        if not template:
            return {
                "summary": f"未知类型: {item_type}",
                "error_analysis": {
                    "is_correct": False,
                    "is_necessary": False,
                    "reasoning": "无法分析此类型的项目",
                    "flag": "error"
                }
            }

        # 构建上下文
        history_summaries, recent_items = self._build_context_for_analysis(
            current_index, all_items, previous_analyses
        )

        # 准备当前项内容
        if item_type == "user_message":
            raw_content = item.get("content", "")
            if isinstance(raw_content, list):
                content = json.dumps(raw_content, ensure_ascii=False, indent=2)[:1000]
            else:
                content = str(raw_content)[:1000]

        elif item_type == "tool_calls":
            calls = item.get("calls", [])
            content = json.dumps(calls, ensure_ascii=False, indent=2)[:1000]

        elif item_type == "tool_result":
            content = str(item.get("content", ""))[:800]

        elif item_type == "assistant_text":
            content = item.get("content", "")[:800]

        elif item_type == "assistant_thinking":
            content = item.get("content", "")[:800]

        else:
            content = str(item.get("content", ""))[:800]

        # 填充模板
        prompt = template.format(
            history_summaries=history_summaries if history_summaries else "（无历史项）",
            recent_items=recent_items if recent_items else "（无近期项）",
            content=content
        )

        # 重试最多 3 次
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=1024,  # 增加 token 限制，避免截断
                    messages=[{"role": "user", "content": prompt}]
                )

                # 解析 JSON 响应
                result_text = self._extract_text_from_response(response)

                # 尝试从响应中提取 JSON（支持 markdown 代码块）
                json_text = result_text

                # 如果包含 markdown 代码块，提取其中的内容
                if "```json" in result_text:
                    start = result_text.index("```json") + 7
                    end = result_text.index("```", start)
                    json_text = result_text[start:end].strip()
                elif "```" in result_text:
                    start = result_text.index("```") + 3
                    end = result_text.index("```", start)
                    json_text = result_text[start:end].strip()

                # 尝试解析 JSON
                try:
                    # 找到第一个 { 和匹配的 }
                    if "{" in json_text:
                        start = json_text.index("{")
                        # 使用括号匹配找到对应的右括号
                        depth = 0
                        end = -1
                        for i in range(start, len(json_text)):
                            if json_text[i] == "{":
                                depth += 1
                            elif json_text[i] == "}":
                                depth -= 1
                                if depth == 0:
                                    end = i + 1
                                    break

                        if end > start:
                            json_str = json_text[start:end]
                            result = json.loads(json_str)

                            # 验证必需字段
                            if "summary" in result and "error_analysis" in result:
                                error_analysis = result["error_analysis"]
                                # 验证 error_analysis 的必需字段
                                required_fields = ["is_correct", "is_necessary", "reasoning", "flag"]
                                if all(field in error_analysis for field in required_fields):
                                    # 解析成功，返回结果
                                    if attempt > 0:
                                        print(f"  ✓ 重试成功 (第 {attempt + 1} 次尝试)")
                                    return result
                                else:
                                    raise ValueError(f"Missing required fields in error_analysis: {required_fields}")
                            else:
                                raise ValueError("Missing required fields (summary or error_analysis) in JSON response")
                        else:
                            raise ValueError("Could not find matching closing brace")
                    else:
                        raise ValueError("No JSON object found in response")

                except (json.JSONDecodeError, ValueError) as e:
                    if attempt < max_retries - 1:
                        print(f"  ⚠ 解析失败 (第 {attempt + 1} 次尝试): {e}")
                        print(f"  响应预览: {result_text[:150]}...")
                        print(f"  正在重试...")
                        continue  # 重试
                    else:
                        # 最后一次尝试也失败了
                        print(f"  ✗ 解析失败 (已重试 {max_retries} 次): {e}")
                        print(f"  响应文本: {result_text[:200]}...")
                        return {
                            "summary": f"{item_type} - 分析失败（响应格式错误）",
                            "error_analysis": {
                                "is_correct": False,
                                "is_necessary": False,
                                "reasoning": f"LLM 返回格式错误，已重试 {max_retries} 次。原始响应: {result_text[:200]}",
                                "flag": "error"
                            }
                        }

            except Exception as e:
                if attempt < max_retries - 1:
                    print(f"  ⚠ API 调用失败 (第 {attempt + 1} 次尝试): {e}")
                    print(f"  正在重试...")
                    continue  # 重试
                else:
                    # 最后一次尝试也失败了
                    print(f"  ✗ API 调用失败 (已重试 {max_retries} 次): {e}")
                    return {
                        "summary": f"{item_type} - 分析失败（API 错误）",
                        "error_analysis": {
                            "is_correct": False,
                            "is_necessary": False,
                            "reasoning": f"API 调用失败，已重试 {max_retries} 次: {str(e)}",
                            "flag": "error"
                        }
                    }

        # 理论上不会到这里，但为了安全起见
        return {
            "summary": f"{item_type} - 分析失败",
            "error_analysis": {
                "is_correct": False,
                "is_necessary": False,
                "reasoning": "未知错误",
                "flag": "error"
            }
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
            return self._extract_text_from_response(response)
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
                    content = item.get("content")
                    if isinstance(content, list):
                        # Expand list content into individual sub-items
                        for sub in content:
                            if isinstance(sub, dict) and "text" in sub:
                                expanded = dict(item)
                                expanded["content"] = sub["text"]
                                expanded["_parent_content"] = content
                                all_items.append(expanded)
                    else:
                        all_items.append(item)

            item_analyses = []
            for i, item in enumerate(all_items):
                print(f"  Analyzing item {i+1}/{len(all_items)}...")
                analysis = self._analyze_single_item(item, i, all_items, item_analyses)
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
