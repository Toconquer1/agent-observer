"""
用于 agent 执行分析的 HTML 可视化生成器。

生成一个交互式的独立 HTML 页面来可视化 agent 执行轨迹。
"""

import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime


class AgentVisualizer:
    """生成 agent 执行的交互式 HTML 可视化。"""

    def __init__(self, analyzed_dir: str):
        """
        初始化可视化器。

        Args:
            analyzed_dir: 分析目录路径
        """
        self.analyzed_dir = Path(analyzed_dir)
        self.output_file = self.analyzed_dir.parent / "visualization.html"

        # 加载数据
        self.prompts = self._load_prompts()
        self.tools = self._load_tools()
        self.call_trace = self._load_call_trace()
        self.analysis = self._load_analysis()

    def _load_prompts(self) -> str:
        """加载系统提示词。"""
        prompts_file = self.analyzed_dir / "prompts.txt"
        if not prompts_file.exists():
            return ""
        return prompts_file.read_text(encoding="utf-8")

    def _load_tools(self) -> Dict[str, Any]:
        """加载工具列表。"""
        tools_file = self.analyzed_dir / "tools.json"
        if not tools_file.exists():
            return {}
        with open(tools_file, "r", encoding="utf-8") as f:
            return json.load(f)

    def _load_call_trace(self) -> List[Dict[str, Any]]:
        """加载调用轨迹。"""
        trace_file = self.analyzed_dir / "call_trace.json"
        if not trace_file.exists():
            return []
        with open(trace_file, "r", encoding="utf-8") as f:
            return json.load(f)

    def _load_analysis(self) -> Optional[Dict[str, Any]]:
        """加载 LLM 分析结果（如果存在）。"""
        analysis_file = self.analyzed_dir / "analyze.json"
        if not analysis_file.exists():
            return None
        with open(analysis_file, "r", encoding="utf-8") as f:
            return json.load(f)

    def _escape_html(self, text: str) -> str:
        """转义 HTML 特殊字符。"""
        return (text
                .replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace('"', "&quot;")
                .replace("'", "&#39;"))

    def _format_json(self, data: Any) -> str:
        """格式化 JSON 数据以便显示。"""
        return json.dumps(data, ensure_ascii=False, indent=2)

    def _generate_html(self) -> str:
        """生成完整的 HTML 文档。"""

        # 统计信息
        total_calls = len(self.call_trace)
        total_items = sum(len(call.get("information_list", [])) for call in self.call_trace)
        tool_count = len(self.tools) if isinstance(self.tools, dict) else len(self.tools)

        # 生成 HTML
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
            --color-surface: #f8f9fa;
            --color-surface-raised: #ffffff;
            --color-surface-overlay: #e9ecef;
            --color-border: rgba(0, 0, 0, 0.08);
            --color-text: #1a1a2e;
            --color-text-secondary: #495057;
            --color-text-muted: #868e96;
            --color-accent: #2563eb;
            --color-user: #7c3aed;
            --color-assistant: #059669;
            --color-tool: #d97706;
            --sidebar-width: 320px;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background: var(--color-surface);
            color: var(--color-text);
            line-height: 1.6;
            display: flex;
            height: 100vh;
            overflow: hidden;
        }}

        /* Sidebar */
        .sidebar {{
            width: var(--sidebar-width);
            background: var(--color-surface-raised);
            border-right: 1px solid var(--color-border);
            display: flex;
            flex-direction: column;
            overflow-y: auto;
        }}

        .sidebar-header {{
            padding: 1.5rem;
            border-bottom: 1px solid var(--color-border);
        }}

        .sidebar-title {{
            font-size: 1.125rem;
            font-weight: 600;
            margin-bottom: 0.5rem;
        }}

        .sidebar-subtitle {{
            font-size: 0.75rem;
            color: var(--color-text-secondary);
        }}

        .stats {{
            padding: 1rem;
            border-bottom: 1px solid var(--color-border);
        }}

        .stat-item {{
            display: flex;
            justify-content: space-between;
            padding: 0.5rem 0;
            font-size: 0.875rem;
        }}

        .stat-label {{
            color: var(--color-text-secondary);
        }}

        .stat-value {{
            color: var(--color-accent);
            font-weight: 600;
        }}

        .sidebar-section {{
            border-bottom: 1px solid var(--color-border);
        }}

        .sidebar-section-header {{
            padding: 1rem;
            font-size: 0.875rem;
            font-weight: 600;
            color: var(--color-text-secondary);
            cursor: pointer;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}

        .sidebar-section-header:hover {{
            background: var(--color-surface-overlay);
        }}

        .sidebar-section-content {{
            max-height: 0;
            overflow: hidden;
            transition: max-height 0.3s ease;
        }}

        .sidebar-section-content.expanded {{
            max-height: 500px;
            overflow-y: auto;
        }}

        .sidebar-section-body {{
            padding: 1rem;
            font-size: 0.8125rem;
            color: var(--color-text-secondary);
            line-height: 1.5;
        }}

        .tool-list {{
            display: flex;
            flex-direction: column;
            gap: 0.5rem;
        }}

        .tool-item {{
            padding: 0.5rem;
            background: var(--color-surface-overlay);
            border-radius: 0.25rem;
            font-size: 0.8125rem;
        }}

        .tool-item-name {{
            font-weight: 600;
            color: var(--color-text);
            margin-bottom: 0.25rem;
        }}

        .tool-item-desc {{
            color: var(--color-text-muted);
            font-size: 0.75rem;
            line-height: 1.3;
            display: -webkit-box;
            -webkit-line-clamp: 2;
            -webkit-box-orient: vertical;
            overflow: hidden;
        }}

        .toggle-icon {{
            transition: transform 0.2s;
        }}

        .toggle-icon.expanded {{
            transform: rotate(90deg);
        }}

        /* Main content */
        .main-content {{
            flex: 1;
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }}

        .main-header {{
            padding: 1.5rem 2rem;
            border-bottom: 1px solid var(--color-border);
            background: var(--color-surface-raised);
        }}

        .main-title {{
            font-size: 1.5rem;
            font-weight: 600;
            margin-bottom: 0.25rem;
        }}

        .main-subtitle {{
            font-size: 0.875rem;
            color: var(--color-text-secondary);
        }}

        /* Chat container */
        .chat-container {{
            flex: 1;
            overflow-y: auto;
            padding: 2rem;
        }}

        .chat-messages {{
            max-width: 900px;
            margin: 0 auto;
        }}

        /* Message bubbles */
        .message {{
            display: flex;
            margin-bottom: 1.5rem;
            gap: 1rem;
        }}

        .message.user {{
            flex-direction: row-reverse;
        }}

        .message-avatar {{
            width: 36px;
            height: 36px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.125rem;
            flex-shrink: 0;
        }}

        .message.user .message-avatar {{
            background: linear-gradient(135deg, var(--color-user), #a78bfa);
        }}

        .message.assistant .message-avatar {{
            background: linear-gradient(135deg, var(--color-assistant), #34d399);
        }}

        .message.tool .message-avatar {{
            background: linear-gradient(135deg, var(--color-tool), #fbbf24);
        }}

        .message-content {{
            flex: 1;
            max-width: 70%;
        }}

        .message.user .message-content {{
            display: flex;
            flex-direction: column;
            align-items: flex-end;
        }}

        .message-bubble {{
            background: var(--color-surface-raised);
            border: 1px solid var(--color-border);
            border-radius: 1rem;
            padding: 1rem 1.25rem;
            margin-bottom: 0.5rem;
            width: fit-content;
            max-width: 100%;
        }}

        .message.user .message-bubble {{
            background: linear-gradient(135deg, rgba(139, 92, 246, 0.15), rgba(167, 139, 250, 0.1));
            border-color: rgba(139, 92, 246, 0.3);
        }}

        .message-header {{
            display: flex;
            align-items: center;
            gap: 0.5rem;
            margin-bottom: 0.5rem;
            font-size: 0.8125rem;
        }}

        .message-type {{
            font-weight: 600;
            color: var(--color-text-secondary);
        }}

        .message.user .message-type {{
            color: var(--color-user);
        }}

        .message.assistant .message-type {{
            color: var(--color-assistant);
        }}

        .message.tool .message-type {{
            color: var(--color-tool);
        }}

        .message-badge {{
            padding: 0.125rem 0.5rem;
            border-radius: 0.25rem;
            font-size: 0.6875rem;
            font-weight: 500;
            background: rgba(16, 185, 129, 0.15);
            color: var(--color-assistant);
            border: 1px solid rgba(16, 185, 129, 0.3);
        }}

        .message-text {{
            color: var(--color-text);
            font-size: 0.9375rem;
            line-height: 1.6;
            white-space: pre-wrap;
            word-wrap: break-word;
        }}

        .message-text + .message-text {{
            margin-top: 0.75rem;
            padding-top: 0.75rem;
            border-top: 1px solid var(--color-border);
        }}

        /* Thinking bubble */
        .thinking-bubble {{
            border-style: dashed;
            opacity: 0.85;
        }}

        .thinking-bubble .message-text {{
            font-style: italic;
            color: var(--color-text-secondary);
        }}

        /* Tool calls */
        .tool-call {{
            background: var(--color-surface-overlay);
            border: 1px solid var(--color-border);
            border-radius: 0.5rem;
            padding: 1rem;
            margin-top: 0.75rem;
        }}

        .tool-call-header {{
            display: flex;
            align-items: center;
            gap: 0.5rem;
            margin-bottom: 0.75rem;
        }}

        .tool-call-icon {{
            font-size: 1.125rem;
        }}

        .tool-call-name {{
            font-weight: 600;
            color: var(--color-tool);
            font-size: 0.9375rem;
        }}

        .tool-call-args {{
            background: var(--color-surface);
            border: 1px solid var(--color-border);
            border-radius: 0.375rem;
            padding: 0.75rem;
            font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
            font-size: 0.8125rem;
            color: var(--color-text-secondary);
            overflow-x: auto;
            line-height: 1.5;
        }}

        /* Analysis box */
        .analysis-box {{
            background: linear-gradient(135deg, rgba(59, 130, 246, 0.1), rgba(37, 99, 235, 0.05));
            border: 1px solid rgba(59, 130, 246, 0.3);
            border-radius: 0.5rem;
            padding: 1rem;
            margin-top: 0.75rem;
        }}

        .analysis-header {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 0.5rem;
        }}

        .analysis-title {{
            font-weight: 600;
            color: var(--color-accent);
            font-size: 0.875rem;
        }}

        .analysis-score {{
            padding: 0.25rem 0.5rem;
            border-radius: 0.25rem;
            font-size: 0.75rem;
            font-weight: 600;
            background: rgba(59, 130, 246, 0.2);
            color: var(--color-accent);
        }}

        .analysis-summary {{
            font-weight: 600;
            color: var(--color-text);
            margin-bottom: 0.5rem;
            font-size: 0.875rem;
        }}

        .analysis-text {{
            color: var(--color-text-secondary);
            font-size: 0.8125rem;
            line-height: 1.6;
        }}

        /* Scrollbar */
        ::-webkit-scrollbar {{
            width: 8px;
            height: 8px;
        }}

        ::-webkit-scrollbar-track {{
            background: var(--color-surface);
        }}

        ::-webkit-scrollbar-thumb {{
            background: var(--color-surface-overlay);
            border-radius: 4px;
        }}

        ::-webkit-scrollbar-thumb:hover {{
            background: #adb5bd;
        }}
    </style>
</head>
<body>
    <!-- Sidebar -->
    <div class="sidebar">
        <div class="sidebar-header">
            <div class="sidebar-title">🔍 Agent 分析</div>
            <div class="sidebar-subtitle">agentob</div>
        </div>

        <div class="stats">
            <div class="stat-item">
                <span class="stat-label">调用次数</span>
                <span class="stat-value">{total_calls}</span>
            </div>
            <div class="stat-item">
                <span class="stat-label">消息数</span>
                <span class="stat-value">{total_items}</span>
            </div>
            <div class="stat-item">
                <span class="stat-label">工具数</span>
                <span class="stat-value">{tool_count}</span>
            </div>
            <div class="stat-item">
                <span class="stat-label">生成时间</span>
                <span class="stat-value">{datetime.now().strftime("%H:%M")}</span>
            </div>
        </div>

        {self._generate_sidebar_analysis()}
        {self._generate_sidebar_tools()}
        {self._generate_sidebar_prompts()}
    </div>

    <!-- Main content -->
    <div class="main-content">
        <div class="main-header">
            <div class="main-title">调用轨迹</div>
            <div class="main-subtitle">Agent 执行过程的完整记录</div>
        </div>

        <div class="chat-container">
            <div class="chat-messages">
                {self._generate_chat_messages()}
            </div>
        </div>
    </div>

    <script>
        // Toggle sidebar sections
        document.querySelectorAll('.sidebar-section-header').forEach(header => {{
            header.addEventListener('click', () => {{
                const content = header.nextElementSibling;
                const icon = header.querySelector('.toggle-icon');
                content.classList.toggle('expanded');
                icon.classList.toggle('expanded');
            }});
        }});
    </script>
</body>
</html>"""

        return html

    def _generate_sidebar_analysis(self) -> str:
        """生成侧边栏分析部分。"""
        if not self.analysis:
            return ""

        overall = self.analysis.get("overall_analysis", "")
        if not overall:
            return ""

        # 如果太长则截断
        display_text = overall[:300] + ("..." if len(overall) > 300 else "")

        return f'''<div class="sidebar-section">
            <div class="sidebar-section-header">
                <span>📊 整体分析</span>
                <span class="toggle-icon">▶</span>
            </div>
            <div class="sidebar-section-content">
                <div class="sidebar-section-body">{self._escape_html(display_text)}</div>
            </div>
        </div>'''

    def _generate_sidebar_tools(self) -> str:
        """生成侧边栏工具部分。"""
        if not self.tools:
            return ""

        tools_html = '<div class="tool-list">'

        if isinstance(self.tools, dict):
            for name, tool_data in list(self.tools.items())[:20]:  # 最多显示 20 个
                desc = ""
                if isinstance(tool_data, dict):
                    desc = tool_data.get("description", "")[:80]
                tools_html += f'''<div class="tool-item">
                    <div class="tool-item-name">{self._escape_html(name)}</div>
                    <div class="tool-item-desc">{self._escape_html(desc)}</div>
                </div>'''
        else:
            for tool in self.tools[:20]:
                name = tool.get("name", "Unknown")
                desc = tool.get("description", "")[:80]
                tools_html += f'''<div class="tool-item">
                    <div class="tool-item-name">{self._escape_html(name)}</div>
                    <div class="tool-item-desc">{self._escape_html(desc)}</div>
                </div>'''

        tools_html += '</div>'

        return f'''<div class="sidebar-section">
            <div class="sidebar-section-header">
                <span>🛠️ 可用工具 ({len(self.tools)})</span>
                <span class="toggle-icon">▶</span>
            </div>
            <div class="sidebar-section-content">
                <div class="sidebar-section-body">{tools_html}</div>
            </div>
        </div>'''

    def _generate_sidebar_prompts(self) -> str:
        """生成侧边栏提示词部分。"""
        if not self.prompts:
            return ""

        # 截断
        display_text = self.prompts[:500] + ("..." if len(self.prompts) > 500 else "")

        return f'''<div class="sidebar-section">
            <div class="sidebar-section-header">
                <span>📝 系统提示词</span>
                <span class="toggle-icon">▶</span>
            </div>
            <div class="sidebar-section-content">
                <div class="sidebar-section-body" style="font-family: monospace; font-size: 0.75rem; line-height: 1.4;">{self._escape_html(display_text)}</div>
            </div>
        </div>'''

    def _generate_chat_messages(self) -> str:
        """生成聊天风格的消息。"""
        if not self.call_trace:
            return '<div style="text-align: center; padding: 3rem; color: var(--color-text-muted);">无调用轨迹</div>'

        messages_html = ''
        call_analyses = self.analysis.get("call_analyses", []) if self.analysis else []
        item_index = 0

        for call in self.call_trace:
            info_list = call.get("information_list", [])

            for item in info_list:
                item_type = item.get("type", "unknown")
                messages_html += self._generate_message(item, item_type, call_analyses, item_index)
                item_index += 1

        return messages_html

    def _generate_message(self, item: Dict[str, Any], item_type: str,
                         call_analyses: List[Dict[str, Any]], item_index: int) -> str:
        """生成单条聊天消息。"""

        # 确定消息样式类别和头像
        if item_type == "user_message":
            msg_class = "user"
            avatar = "👤"
            type_label = "用户"
        elif item_type == "assistant_text":
            msg_class = "assistant"
            avatar = "🤖"
            type_label = "助手"
        elif item_type == "tool_calls":
            msg_class = "tool"
            avatar = "🔧"
            type_label = "工具调用"
        elif item_type == "assistant_thinking":
            msg_class = "assistant"
            avatar = "💭"
            type_label = "思考"
        elif item_type == "tool_result":
            msg_class = "tool"
            avatar = "✅"
            type_label = "工具结果"
        else:
            msg_class = "assistant"
            avatar = "💬"
            type_label = item_type

        html = f'<div class="message {msg_class}">'
        html += f'<div class="message-avatar">{avatar}</div>'
        html += '<div class="message-content">'

        # 获取分析结果（如果存在）
        analysis = None
        if item_index < len(call_analyses):
            analysis = call_analyses[item_index]

        # 根据类型生成消息气泡
        if item_type == "user_message":
            content = item.get("content", [])
            if isinstance(content, list):
                for c in content:
                    if isinstance(c, dict) and c.get("type") == "text":
                        text = c.get("text", "")
                        html += '<div class="message-bubble">'
                        html += f'<div class="message-header"><span class="message-type">{type_label}</span>'
                        if item.get("matched_in_next_request"):
                            html += '<span class="message-badge">已匹配</span>'
                        html += '</div>'
                        html += f'<div class="message-text">{self._escape_html(text)}</div>'
                        html += '</div>'
            else:
                html += '<div class="message-bubble">'
                html += f'<div class="message-header"><span class="message-type">{type_label}</span></div>'
                html += f'<div class="message-text">{self._escape_html(str(content))}</div>'
                html += '</div>'

        elif item_type == "assistant_text":
            content = item.get("content", "")
            html += '<div class="message-bubble">'
            html += f'<div class="message-header"><span class="message-type">{type_label}</span>'
            if item.get("matched_in_next_request"):
                html += '<span class="message-badge">已匹配</span>'
            html += '</div>'
            html += f'<div class="message-text">{self._escape_html(content)}</div>'
            html += '</div>'

        elif item_type == "tool_calls":
            calls = item.get("calls", [])
            html += '<div class="message-bubble">'
            html += f'<div class="message-header"><span class="message-type">{type_label}</span></div>'

            for call in calls:
                name = call.get("name", "unknown")
                args = call.get("arguments", {})
                html += '<div class="tool-call">'
                html += f'<div class="tool-call-header"><span class="tool-call-icon">🔧</span><span class="tool-call-name">{self._escape_html(name)}</span></div>'
                html += f'<div class="tool-call-args">{self._escape_html(self._format_json(args))}</div>'
                html += '</div>'

            html += '</div>'

        elif item_type == "assistant_thinking":
            content = item.get("content", "")
            html += '<div class="message-bubble thinking-bubble">'
            html += f'<div class="message-header"><span class="message-type">{type_label}</span>'
            if item.get("matched_in_next_request"):
                html += '<span class="message-badge">已匹配</span>'
            html += '</div>'
            html += f'<div class="message-text">{self._escape_html(content)}</div>'
            html += '</div>'

        elif item_type == "tool_result":
            content = str(item.get("content", ""))
            html += '<div class="message-bubble">'
            html += f'<div class="message-header"><span class="message-type">{type_label}</span></div>'
            html += f'<div class="message-text">{self._escape_html(content)}</div>'
            html += '</div>'

        # 如果有分析结果则添加分析框
        if analysis:
            summary = analysis.get("summary", "")
            analysis_text = analysis.get("analysis", "")
            score = analysis.get("score", 0)

            if summary or analysis_text:
                html += '<div class="analysis-box">'
                html += '<div class="analysis-header">'
                html += '<span class="analysis-title">💡 AI 分析</span>'
                html += f'<span class="analysis-score">{score}/5</span>'
                html += '</div>'
                if summary:
                    html += f'<div class="analysis-summary">{self._escape_html(summary)}</div>'
                if analysis_text:
                    html += f'<div class="analysis-text">{self._escape_html(analysis_text)}</div>'
                html += '</div>'

        html += '</div></div>'
        return html

    def generate(self) -> str:
        """
        生成 HTML 可视化。

        Returns:
            生成的 HTML 文件路径
        """
        html = self._generate_html()

        with open(self.output_file, "w", encoding="utf-8") as f:
            f.write(html)

        print(f"[agentob] Visualization generated: {self.output_file}")
        return str(self.output_file)


def generate_visualization(analyzed_dir: str) -> str:
    """
    生成可视化的便捷函数。

    Args:
        analyzed_dir: 分析目录路径

    Returns:
        生成的 HTML 文件路径
    """
    visualizer = AgentVisualizer(analyzed_dir)
    return visualizer.generate()
