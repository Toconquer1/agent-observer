"""
Decoder module for parsing mitmproxy flow files
"""
import os
import json
import datetime
from pathlib import Path
from typing import Dict, Any, Optional
from mitmproxy import io
from mitmproxy.exceptions import FlowReadException


class MitmDecoder:
    """Decoder for mitmproxy flow files"""

    def __init__(self, input_file: str, output_dir: str):
        self.input_file = Path(input_file)
        self.output_dir = Path(output_dir)

    def _parse_sse(self, content: str) -> Dict[str, Any]:
        """
        Parse SSE (Server-Sent Events) and consolidate all key information
        (text, thinking, tool calls, usage) together.
        """
        combined_text = ""
        combined_thinking = ""
        tool_calls = {}  # Use index as key to temporarily store tool call fragments
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

                    # 1. Intercept content block start (primarily for capturing tool call initialization)
                    if event_type == "content_block_start":
                        index = data_json.get("index")
                        cb = data_json.get("content_block", {})
                        if cb.get("type") == "tool_use":
                            tool_calls[index] = {
                                "id": cb.get("id"),
                                "name": cb.get("name"),
                                "arguments": ""  # Placeholder for subsequent json_delta
                            }

                    # 2. Intercept content block delta (concatenate text, thinking process, and tool arguments)
                    elif event_type == "content_block_delta":
                        index = data_json.get("index")
                        delta = data_json.get("delta", {})
                        delta_type = delta.get("type", "")

                        if delta_type == "thinking_delta":
                            combined_thinking += delta.get("thinking", "")
                        elif delta_type == "text_delta":
                            combined_text += delta.get("text", "")
                        elif delta_type == "input_json_delta":
                            if index in tool_calls:
                                # Concatenate fragmented tool call JSON arguments
                                tool_calls[index]["arguments"] += delta.get("partial_json", "")

                    # 3. Intercept message-level delta (capture stop reason and token usage)
                    elif event_type == "message_delta":
                        delta = data_json.get("delta", {})
                        if "stop_reason" in delta:
                            stop_reason = delta["stop_reason"]
                        if "usage" in data_json:
                            usage = data_json["usage"]

                    # --- Fallback logic for OpenAI format compatibility ---
                    elif "choices" in data_json and len(data_json["choices"]) > 0:
                        delta = data_json["choices"][0].get("delta", {})
                        if "content" in delta:
                            combined_text += delta.get("content", "")
                        if "reasoning_content" in delta:
                            combined_thinking += delta.get("reasoning_content", "")

                except json.JSONDecodeError:
                    pass

        # Post-processing: Attempt to parse concatenated tool arguments into actual JSON dictionaries
        formatted_tool_calls = []
        for tc in tool_calls.values():
            try:
                if tc["arguments"]:
                    tc["arguments"] = json.loads(tc["arguments"])
            except json.JSONDecodeError:
                pass  # Keep as raw string if parsing fails
            formatted_tool_calls.append(tc)

        return {
            "is_sse_stream": True,
            "integrated_thinking": combined_thinking,
            "integrated_text": combined_text,
            "tool_calls": formatted_tool_calls,  # Fully assembled list of tool calls
            "usage": usage,  # Token usage statistics
            "stop_reason": stop_reason  # e.g., "tool_use" or "end_turn"
        }

    def _extract_body(self, content_bytes: Optional[bytes]) -> Any:
        """Extract body from bytes"""
        if not content_bytes:
            return ""
        try:
            content_str = content_bytes.decode('utf-8', errors='ignore')
            return json.loads(content_str)
        except (UnicodeDecodeError, json.JSONDecodeError):
            return content_bytes.decode('utf-8', errors='ignore')

    def _is_llm_request(self, url: str) -> bool:
        """Check if the request is an LLM API call"""
        llm_patterns = [
            "api.anthropic.com",
            "api.openai.com",
            "/v1/messages",
            "/v1/chat/completions",
        ]
        return any(pattern in url for pattern in llm_patterns)

    def _is_mcp_request(self, url: str) -> bool:
        """Check if the request is an MCP call"""
        mcp_patterns = [
            "/mcp/",
            "/mcp-",
        ]
        return any(pattern in url for pattern in mcp_patterns)

    def decode(self):
        """Decode mitmproxy flow file"""
        if not self.input_file.exists():
            raise FileNotFoundError(f"Input file not found: {self.input_file}")

        self.output_dir.mkdir(parents=True, exist_ok=True)

        print(f"[decoder] Starting to decode {self.input_file.name}...")

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

                        # Determine request type
                        req_type = "unknown"
                        if self._is_llm_request(url):
                            req_type = "llm"
                        elif self._is_mcp_request(url):
                            req_type = "mcp"

                        # Extract request body
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

                        # Extract response if exists
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

                        print(f"[decoder] Exported {req_type} request/response pair {index} ({req_time})")
                        index += 1

                    except Exception as e:
                        error_count += 1
                        print(f"[decoder] Warning: Failed to process flow {index}: {e}")
                        continue

            except FlowReadException as e:
                print(f"[decoder] Flow read exception (this is normal at end of file): {e}")
            except Exception as e:
                print(f"[decoder] Unexpected error: {e}")

        success_count = index - 1
        print(f"[decoder] Decoding completed! {success_count} request/response pairs extracted")
        if error_count > 0:
            print(f"[decoder] {error_count} flows skipped due to errors")
