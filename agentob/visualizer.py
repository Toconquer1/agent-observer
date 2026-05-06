"""
HTML visualization generator for agent execution analysis.

Generates an interactive, standalone HTML page to visualize agent execution traces.
"""

import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime


class AgentVisualizer:
    """Generates interactive HTML visualization of agent execution."""

    def __init__(self, analyzed_dir: str):
        """
        Initialize the visualizer.

        Args:
            analyzed_dir: Path to the analyzed directory
        """
        self.analyzed_dir = Path(analyzed_dir)
        self.output_file = self.analyzed_dir.parent / "visualization.html"

        # Load data
        self.prompts = self._load_prompts()
        self.tools = self._load_tools()
        self.call_trace = self._load_call_trace()
        self.analysis = self._load_analysis()

    def _load_prompts(self) -> str:
        """Load system prompts."""
        prompts_file = self.analyzed_dir / "prompts.txt"
        if not prompts_file.exists():
            return ""
        return prompts_file.read_text(encoding="utf-8")

    def _load_tools(self) -> Dict[str, Any]:
        """Load tools."""
        tools_file = self.analyzed_dir / "tools.json"
        if not tools_file.exists():
            return {}
        with open(tools_file, "r", encoding="utf-8") as f:
            return json.load(f)

    def _load_call_trace(self) -> List[Dict[str, Any]]:
        """Load call trace."""
        trace_file = self.analyzed_dir / "call_trace.json"
        if not trace_file.exists():
            return []
        with open(trace_file, "r", encoding="utf-8") as f:
            return json.load(f)

    def _load_analysis(self) -> Optional[Dict[str, Any]]:
        """Load LLM analysis if available."""
        analysis_file = self.analyzed_dir / "analyze.json"
        if not analysis_file.exists():
            return None
        with open(analysis_file, "r", encoding="utf-8") as f:
            return json.load(f)

    def _escape_html(self, text: str) -> str:
        """Escape HTML special characters."""
        return (text
                .replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace('"', "&quot;")
                .replace("'", "&#39;"))

    def _format_json(self, data: Any) -> str:
        """Format JSON data for display."""
        return json.dumps(data, ensure_ascii=False, indent=2)

    def _generate_html(self) -> str:
        """Generate the complete HTML document."""

        # Count statistics
        total_calls = len(self.call_trace)
        total_items = sum(len(call.get("information_list", [])) for call in self.call_trace)
        tool_count = len(self.tools) if isinstance(self.tools, dict) else len(self.tools)

        # Generate HTML
        html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Agent 执行分析 - agentob</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        :root {{
            --color-surface: #141416;
            --color-surface-raised: #27272a;
            --color-surface-overlay: #1c1c20;
            --color-border: rgba(255, 255, 255, 0.05);
            --color-border-emphasis: rgba(255, 255, 255, 0.1);
            --color-text: #fafafa;
            --color-text-secondary: #a1a1aa;
            --color-text-muted: #71717a;
            --color-accent: #3b82f6;
            --color-accent-hover: #2563eb;
            --color-success: #10b981;
            --color-warning: #f59e0b;
            --color-error: #ef4444;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background: var(--color-surface);
            color: var(--color-text);
            line-height: 1.6;
        }}

        .container {{
            max-width: 1400px;
            margin: 0 auto;
            padding: 2rem;
        }}

        header {{
            background: var(--color-surface-raised);
            border-bottom: 1px solid var(--color-border);
            padding: 1.5rem 2rem;
            margin-bottom: 2rem;
        }}

        h1 {{
            font-size: 1.875rem;
            font-weight: 600;
            margin-bottom: 0.5rem;
        }}

        .subtitle {{
            color: var(--color-text-secondary);
            font-size: 0.875rem;
        }}

        .stats {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1rem;
            margin-bottom: 2rem;
        }}

        .stat-card {{
            background: var(--color-surface-raised);
            border: 1px solid var(--color-border);
            border-radius: 0.5rem;
            padding: 1.25rem;
        }}

        .stat-label {{
            color: var(--color-text-secondary);
            font-size: 0.875rem;
            margin-bottom: 0.5rem;
        }}

        .stat-value {{
            font-size: 1.875rem;
            font-weight: 600;
            color: var(--color-accent);
        }}

        .section {{
            background: var(--color-surface-raised);
            border: 1px solid var(--color-border);
            border-radius: 0.5rem;
            margin-bottom: 1.5rem;
            overflow: hidden;
        }}

        .section-header {{
            padding: 1rem 1.5rem;
            border-bottom: 1px solid var(--color-border);
            display: flex;
            justify-content: space-between;
            align-items: center;
            cursor: pointer;
            user-select: none;
        }}

        .section-header:hover {{
            background: var(--color-surface-overlay);
        }}

        .section-title {{
            font-size: 1.125rem;
            font-weight: 600;
        }}

        .section-content {{
            padding: 1.5rem;
            display: none;
        }}

        .section-content.expanded {{
            display: block;
        }}

        .toggle-icon {{
            transition: transform 0.2s;
        }}

        .toggle-icon.expanded {{
            transform: rotate(90deg);
        }}

        pre {{
            background: var(--color-surface);
            border: 1px solid var(--color-border);
            border-radius: 0.375rem;
            padding: 1rem;
            overflow-x: auto;
            font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
            font-size: 0.875rem;
            line-height: 1.5;
        }}

        .call-item {{
            background: var(--color-surface);
            border: 1px solid var(--color-border);
            border-radius: 0.375rem;
            padding: 1rem;
            margin-bottom: 1rem;
        }}

        .call-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 0.75rem;
            padding-bottom: 0.75rem;
            border-bottom: 1px solid var(--color-border);
        }}

        .call-index {{
            font-weight: 600;
            color: var(--color-accent);
        }}

        .call-model {{
            color: var(--color-text-secondary);
            font-size: 0.875rem;
        }}

        .info-item {{
            background: var(--color-surface-overlay);
            border-left: 3px solid var(--color-border);
            padding: 0.75rem 1rem;
            margin-bottom: 0.75rem;
            border-radius: 0.25rem;
        }}

        .info-item.user {{
            border-left-color: var(--color-accent);
        }}

        .info-item.assistant {{
            border-left-color: var(--color-success);
        }}

        .info-item.tool {{
            border-left-color: var(--color-warning);
        }}

        .info-type {{
            font-size: 0.75rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--color-text-secondary);
            margin-bottom: 0.5rem;
        }}

        .info-content {{
            color: var(--color-text);
            font-size: 0.875rem;
        }}

        .tool-call {{
            background: var(--color-surface);
            border: 1px solid var(--color-border);
            border-radius: 0.25rem;
            padding: 0.75rem;
            margin-top: 0.5rem;
        }}

        .tool-name {{
            font-weight: 600;
            color: var(--color-warning);
            margin-bottom: 0.5rem;
        }}

        .tool-args {{
            font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
            font-size: 0.8125rem;
            color: var(--color-text-secondary);
        }}

        .analysis-section {{
            background: var(--color-surface-overlay);
            border: 1px solid var(--color-border-emphasis);
            border-radius: 0.375rem;
            padding: 1rem;
            margin-top: 1rem;
        }}

        .analysis-title {{
            font-weight: 600;
            color: var(--color-accent);
            margin-bottom: 0.5rem;
        }}

        .analysis-text {{
            color: var(--color-text);
            white-space: pre-wrap;
            line-height: 1.7;
        }}

        .badge {{
            display: inline-block;
            padding: 0.25rem 0.5rem;
            border-radius: 0.25rem;
            font-size: 0.75rem;
            font-weight: 500;
            background: var(--color-surface-overlay);
            color: var(--color-text-secondary);
            border: 1px solid var(--color-border);
        }}

        .badge.matched {{
            background: rgba(16, 185, 129, 0.1);
            color: var(--color-success);
            border-color: var(--color-success);
        }}

        .score {{
            display: inline-flex;
            align-items: center;
            gap: 0.25rem;
            padding: 0.25rem 0.5rem;
            border-radius: 0.25rem;
            font-size: 0.875rem;
            font-weight: 600;
            background: var(--color-surface);
            border: 1px solid var(--color-border);
        }}

        .score-value {{
            color: var(--color-accent);
        }}

        .empty-state {{
            text-align: center;
            padding: 3rem 1rem;
            color: var(--color-text-muted);
        }}

        .tools-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
            gap: 0.75rem;
        }}

        .tool-card {{
            background: var(--color-surface);
            border: 1px solid var(--color-border);
            border-radius: 0.375rem;
            padding: 0.75rem;
        }}

        .tool-card-name {{
            font-weight: 600;
            color: var(--color-text);
            margin-bottom: 0.25rem;
        }}

        .tool-card-desc {{
            font-size: 0.8125rem;
            color: var(--color-text-secondary);
            line-height: 1.4;
        }}
    </style>
</head>
<body>
    <header>
        <h1>🔍 Agent 执行分析</h1>
        <div class="subtitle">agentob - Agent Execution Observer</div>
    </header>

    <div class="container">
        <!-- Statistics -->
        <div class="stats">
            <div class="stat-card">
                <div class="stat-label">总调用次数</div>
                <div class="stat-value">{total_calls}</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">信息项总数</div>
                <div class="stat-value">{total_items}</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">可用工具数</div>
                <div class="stat-value">{tool_count}</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">生成时间</div>
                <div class="stat-value" style="font-size: 1rem;">{datetime.now().strftime("%Y-%m-%d %H:%M")}</div>
            </div>
        </div>

        {self._generate_analysis_section()}
        {self._generate_prompts_section()}
        {self._generate_tools_section()}
        {self._generate_trace_section()}
    </div>

    <script>
        // Toggle section expansion
        document.querySelectorAll('.section-header').forEach(header => {{
            header.addEventListener('click', () => {{
                const content = header.nextElementSibling;
                const icon = header.querySelector('.toggle-icon');
                content.classList.toggle('expanded');
                icon.classList.toggle('expanded');
            }});
        }});

        // Expand first section by default
        document.querySelector('.section-content')?.classList.add('expanded');
        document.querySelector('.toggle-icon')?.classList.add('expanded');
    </script>
</body>
</html>"""

        return html

    def _generate_analysis_section(self) -> str:
        """Generate LLM analysis section."""
        if not self.analysis:
            return ""

        system_analysis = self.analysis.get("system_prompt_analysis", "")
        tools_analysis = self.analysis.get("tools_analysis", "")
        overall_analysis = self.analysis.get("overall_analysis", "")
        call_analyses = self.analysis.get("call_analyses", [])

        has_content = any([system_analysis, tools_analysis, overall_analysis, call_analyses])
        if not has_content:
            return ""

        content = '<div class="section"><div class="section-header"><span class="section-title">📊 LLM 分析结果</span><span class="toggle-icon">▶</span></div><div class="section-content">'

        if system_analysis:
            content += f'<div class="analysis-section"><div class="analysis-title">系统提示词分析</div><div class="analysis-text">{self._escape_html(system_analysis)}</div></div>'

        if tools_analysis:
            content += f'<div class="analysis-section"><div class="analysis-title">工具列表分析</div><div class="analysis-text">{self._escape_html(tools_analysis)}</div></div>'

        if overall_analysis:
            content += f'<div class="analysis-section"><div class="analysis-title">整体分析报告</div><div class="analysis-text">{self._escape_html(overall_analysis)}</div></div>'

        content += '</div></div>'
        return content

    def _generate_prompts_section(self) -> str:
        """Generate system prompts section."""
        if not self.prompts:
            return '<div class="section"><div class="section-header"><span class="section-title">📝 系统提示词</span><span class="toggle-icon">▶</span></div><div class="section-content"><div class="empty-state">无系统提示词</div></div></div>'

        # Truncate if too long
        display_prompts = self.prompts[:5000] + ("..." if len(self.prompts) > 5000 else "")

        return f'''<div class="section">
            <div class="section-header">
                <span class="section-title">📝 系统提示词</span>
                <span class="toggle-icon">▶</span>
            </div>
            <div class="section-content">
                <pre>{self._escape_html(display_prompts)}</pre>
            </div>
        </div>'''

    def _generate_tools_section(self) -> str:
        """Generate tools section."""
        if not self.tools:
            return '<div class="section"><div class="section-header"><span class="section-title">🛠️ 可用工具</span><span class="toggle-icon">▶</span></div><div class="section-content"><div class="empty-state">无可用工具</div></div></div>'

        tools_html = '<div class="tools-grid">'

        if isinstance(self.tools, dict):
            for name, tool_data in list(self.tools.items())[:50]:  # Limit to 50 tools
                desc = ""
                if isinstance(tool_data, dict):
                    desc = tool_data.get("description", "")[:150]
                tools_html += f'''<div class="tool-card">
                    <div class="tool-card-name">{self._escape_html(name)}</div>
                    <div class="tool-card-desc">{self._escape_html(desc)}</div>
                </div>'''
        else:
            for tool in self.tools[:50]:
                name = tool.get("name", "Unknown")
                desc = tool.get("description", "")[:150]
                tools_html += f'''<div class="tool-card">
                    <div class="tool-card-name">{self._escape_html(name)}</div>
                    <div class="tool-card-desc">{self._escape_html(desc)}</div>
                </div>'''

        tools_html += '</div>'

        return f'''<div class="section">
            <div class="section-header">
                <span class="section-title">🛠️ 可用工具 ({len(self.tools)})</span>
                <span class="toggle-icon">▶</span>
            </div>
            <div class="section-content">
                {tools_html}
            </div>
        </div>'''

    def _generate_trace_section(self) -> str:
        """Generate call trace section."""
        if not self.call_trace:
            return '<div class="section"><div class="section-header"><span class="section-title">🔄 调用轨迹</span><span class="toggle-icon">▶</span></div><div class="section-content"><div class="empty-state">无调用轨迹</div></div></div>'

        trace_html = ''
        call_analyses = self.analysis.get("call_analyses", []) if self.analysis else []

        item_index = 0
        for call in self.call_trace:
            index = call.get("index", "?")
            model = call.get("model", "unknown")
            info_list = call.get("information_list", [])

            trace_html += f'''<div class="call-item">
                <div class="call-header">
                    <span class="call-index">调用 #{index}</span>
                    <span class="call-model">{self._escape_html(model)}</span>
                </div>'''

            for item in info_list:
                item_type = item.get("type", "unknown")
                trace_html += self._generate_info_item(item, item_type, call_analyses, item_index)
                item_index += 1

            trace_html += '</div>'

        return f'''<div class="section">
            <div class="section-header">
                <span class="section-title">🔄 调用轨迹</span>
                <span class="toggle-icon">▶</span>
            </div>
            <div class="section-content">
                {trace_html}
            </div>
        </div>'''

    def _generate_info_item(self, item: Dict[str, Any], item_type: str,
                           call_analyses: List[Dict[str, Any]], item_index: int) -> str:
        """Generate HTML for a single information item."""
        type_class = "user" if item_type == "user_message" else "assistant" if item_type == "assistant_text" else "tool"
        type_label = {
            "user_message": "用户消息",
            "assistant_text": "助手回复",
            "tool_calls": "工具调用",
            "tool_result": "工具结果"
        }.get(item_type, item_type)

        html = f'<div class="info-item {type_class}"><div class="info-type">{type_label}'

        # Add matched badge if applicable
        if item.get("matched_in_next_request"):
            html += ' <span class="badge matched">已匹配</span>'

        html += '</div>'

        # Add analysis if available
        if item_index < len(call_analyses):
            analysis = call_analyses[item_index]
            summary = analysis.get("summary", "")
            analysis_text = analysis.get("analysis", "")
            score = analysis.get("score", 0)

            if summary or analysis_text:
                html += f'<div class="analysis-section"><div class="analysis-title">分析 <span class="score">评分: <span class="score-value">{score}/5</span></span></div>'
                if summary:
                    html += f'<div style="margin-bottom: 0.5rem; font-weight: 600;">{self._escape_html(summary)}</div>'
                if analysis_text:
                    html += f'<div class="analysis-text">{self._escape_html(analysis_text)}</div>'
                html += '</div>'

        # Add content based on type
        if item_type == "user_message":
            content = item.get("content", [])
            if isinstance(content, list):
                for c in content[:3]:  # Limit to first 3 items
                    if isinstance(c, dict) and c.get("type") == "text":
                        text = c.get("text", "")[:500]
                        html += f'<div class="info-content">{self._escape_html(text)}</div>'
            else:
                html += f'<div class="info-content">{self._escape_html(str(content)[:500])}</div>'

        elif item_type == "assistant_text":
            content = item.get("content", "")[:500]
            html += f'<div class="info-content">{self._escape_html(content)}</div>'

        elif item_type == "tool_calls":
            calls = item.get("calls", [])
            for call in calls[:5]:  # Limit to first 5 calls
                name = call.get("name", "unknown")
                args = call.get("arguments", {})
                html += f'''<div class="tool-call">
                    <div class="tool-name">🔧 {self._escape_html(name)}</div>
                    <div class="tool-args">{self._escape_html(self._format_json(args)[:300])}</div>
                </div>'''

        elif item_type == "tool_result":
            content = str(item.get("content", ""))[:500]
            html += f'<div class="info-content">{self._escape_html(content)}</div>'

        html += '</div>'
        return html

    def generate(self) -> str:
        """
        Generate the HTML visualization.

        Returns:
            Path to the generated HTML file
        """
        html = self._generate_html()

        with open(self.output_file, "w", encoding="utf-8") as f:
            f.write(html)

        print(f"[agentob] Visualization generated: {self.output_file}")
        return str(self.output_file)


def generate_visualization(analyzed_dir: str) -> str:
    """
    Convenience function to generate visualization.

    Args:
        analyzed_dir: Path to analyzed directory

    Returns:
        Path to generated HTML file
    """
    visualizer = AgentVisualizer(analyzed_dir)
    return visualizer.generate()
