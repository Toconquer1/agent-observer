"""
解码器模块，用于解析 mitmproxy 流量文件
"""
import os
import json
import datetime
from pathlib import Path
from typing import Dict, Any, Optional
from mitmproxy import io
from mitmproxy.exceptions import FlowReadException


class MitmDecoder:
    """mitmproxy 流量文件解码器"""

    def __init__(self, input_file: str, output_dir: str):
        self.input_file = Path(input_file)
        self.output_dir = Path(output_dir)

    def _parse_sse(self, content: str) -> Dict[str, Any]:
        """
        解析 SSE（Server-Sent Events）并将所有关键信息
        （文本、思考、工具调用、用量）整合在一起。
        """
        combined_text = ""
        combined_thinking = ""
        tool_calls = {}  # 以 index 为键临时存储工具调用片段
        usage = {}
        stop_reason = None

        lines = content.split('\n')

        for line in lines:
            if line.startswith('data:'):
                data_str = line[5:].strip()
                if not data_str or data_str == "[DONE]":
                    continue

                try:
                    data_json = json.loads(data_str)
                    event_type = data_json.get("type", "")

                    # 1. 拦截 content_block_start（主要用于捕获工具调用初始化信息）
                    if event_type == "content_block_start":
                        index = data_json.get("index")
                        cb = data_json.get("content_block", {})
                        if cb.get("type") == "tool_use":
                            tool_calls[index] = {
                                "id": cb.get("id"),
                                "name": cb.get("name"),
                                "arguments": ""  # 占位符，后续由 json_delta 填充
                            }

                    # 2. 拦截 content_block_delta（拼接文本、思考过程和工具参数）
                    elif event_type == "content_block_delta":
                        index = data_json.get("index")
                        delta = data_json.get("delta", {})
                        delta_type = delta.get("type", "")

                        if delta_type == "thinking_delta":
                            combined_thinking += delta.get("thinking") or ""
                        elif delta_type == "text_delta":
                            combined_text += delta.get("text") or ""
                        elif delta_type == "input_json_delta":
                            if index in tool_calls:
                                tool_calls[index]["arguments"] += delta.get("partial_json") or ""

                    # 3. 拦截 message_delta（捕获停止原因和 token 用量）
                    elif event_type == "message_delta":
                        delta = data_json.get("delta", {})
                        if "stop_reason" in delta:
                            stop_reason = delta["stop_reason"]
                        if "usage" in data_json:
                            usage = data_json["usage"]

                    # --- OpenAI 格式兼容的回退逻辑 ---
                    elif "choices" in data_json and len(data_json["choices"]) > 0:
                        delta = data_json["choices"][0].get("delta", {})
                        if "content" in delta:
                            combined_text += delta.get("content") or ""
                        if "reasoning_content" in delta:
                            combined_thinking += delta.get("reasoning_content") or ""

                except json.JSONDecodeError:
                    pass

        # 后处理：尝试将拼接后的工具参数解析为实际的 JSON 字典
        formatted_tool_calls = []
        for tc in tool_calls.values():
            try:
                if tc["arguments"]:
                    tc["arguments"] = json.loads(tc["arguments"])
            except json.JSONDecodeError:
                pass  # 解析失败则保留原始字符串
            formatted_tool_calls.append(tc)

        return {
            "is_sse_stream": True,
            "integrated_thinking": combined_thinking,
            "integrated_text": combined_text,
            "tool_calls": formatted_tool_calls,  # 完整组装的工具调用列表
            "usage": usage,  # Token 用量统计
            "stop_reason": stop_reason  # 例如 "tool_use" 或 "end_turn"
        }

    def _extract_body(self, content_bytes: Optional[bytes]) -> Any:
        """从字节中提取 body 内容"""
        if not content_bytes:
            return ""
        try:
            content_str = content_bytes.decode('utf-8', errors='ignore')
            return json.loads(content_str)
        except (UnicodeDecodeError, json.JSONDecodeError):
            return content_bytes.decode('utf-8', errors='ignore')

    def _is_llm_request(self, url: str) -> bool:
        """检查请求是否为 LLM API 调用"""
        llm_patterns = [
            "/v1/messages",
            "/v1/chat/completions",
        ]
        return any(pattern in url for pattern in llm_patterns)

    def _is_mcp_request(self, url: str) -> bool:
        """检查请求是否为 MCP 调用"""
        mcp_patterns = [
            "/mcp/",
            "/mcp-",
        ]
        return any(pattern in url for pattern in mcp_patterns)

    def decode(self):
        """解码 mitmproxy 流量文件"""
        if not self.input_file.exists():
            raise FileNotFoundError(f"Input file not found: {self.input_file}")

        self.output_dir.mkdir(parents=True, exist_ok=True)

        print(f"[decoder] 开始解码 {self.input_file.name}...")

        with open(self.input_file, "rb") as logfile:
            freader = io.FlowReader(logfile)
            index = 1
            error_count = 0

            try:
                for flow in freader.stream():
                    try:
                        if not flow.request:
                            continue

                        url = flow.request.pretty_url
                        req_time = datetime.datetime.fromtimestamp(
                            flow.request.timestamp_start
                        ).strftime("%Y%m%d_%H%M%S")

                        # 判断请求类型
                        req_type = "unknown"
                        if self._is_llm_request(url):
                            req_type = "llm"
                        elif self._is_mcp_request(url):
                            req_type = "mcp"

                        # 提取请求 body
                        req_body = self._extract_body(flow.request.content)
                        req_data = {
                            "type": req_type,
                            "url": url,
                            "method": flow.request.method,
                            "headers": dict(flow.request.headers),
                            "request_body": req_body
                        }

                        req_filename = self.output_dir / f"{index}_request_{req_time}.json"
                        with open(req_filename, 'w', encoding='utf-8') as f:
                            json.dump(req_data, f, ensure_ascii=False, indent=4)

                        # 提取响应（如果存在）
                        if flow.response:
                            res_time = datetime.datetime.fromtimestamp(
                                flow.response.timestamp_start
                            ).strftime("%Y%m%d_%H%M%S")
                            content_type = flow.response.headers.get("content-type", "")
                            res_str = flow.response.content.decode('utf-8', errors='ignore') if flow.response.content else ""

                            if "text/event-stream" in content_type or res_str.startswith("event:"):
                                res_body = self._parse_sse(res_str)
                            else:
                                res_body = self._extract_body(flow.response.content)

                            res_data = {
                                "type": req_type,
                                "status_code": flow.response.status_code,
                                "headers": dict(flow.response.headers),
                                "response_body": res_body
                            }

                            res_filename = self.output_dir / f"{index}_response_{res_time}.json"
                            with open(res_filename, 'w', encoding='utf-8') as f:
                                json.dump(res_data, f, ensure_ascii=False, indent=4)

                        print(f"[decoder] 已导出 {req_type} 请求/响应对 {index} ({req_time})")
                        index += 1

                    except Exception as e:
                        error_count += 1
                        print(f"[decoder] 警告：处理流 {index} 失败: {e}")
                        continue

            except FlowReadException as e:
                print(f"[decoder] 流读取异常（文件末尾出现此异常是正常的）: {e}")
            except Exception as e:
                print(f"[decoder] 意外错误: {e}")

        success_count = index - 1
        print(f"[decoder] 解码完成！共提取 {success_count} 个请求/响应对")
        if error_count > 0:
            print(f"[decoder] {error_count} 个流因错误被跳过")
