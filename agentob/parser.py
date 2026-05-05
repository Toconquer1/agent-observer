"""
Parser module for synthesizing request/response pairs into unified call traces
"""
import json
import glob
from pathlib import Path
from typing import Dict, Any, List, Optional


class CallTraceParser:
    """Parser for synthesizing simplified request/response pairs into unified call traces"""

    def __init__(self, decoded_dir: str):
        self.decoded_dir = Path(decoded_dir)
        self.output_dir = self.decoded_dir / "analyzed"

    def _is_tool_result_content(self, content_item: Dict[str, Any]) -> bool:
        """Check if a content item is a tool result"""
        return isinstance(content_item, dict) and content_item.get("type") == "tool_result"

    def _extract_user_messages(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract genuine user messages (excluding tool results)"""
        user_messages = []
        for msg in messages:
            if msg.get("role") == "user":
                content = msg.get("content", [])
                if isinstance(content, list):
                    # Filter out tool_result items
                    genuine_content = [
                        item for item in content
                        if not self._is_tool_result_content(item)
                    ]
                    if genuine_content:
                        user_messages.append({
                            "role": "user",
                            "content": genuine_content
                        })
                elif isinstance(content, str):
                    user_messages.append({
                        "role": "user",
                        "content": content
                    })
        return user_messages

    def _extract_tool_results(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract tool result messages from user role messages"""
        tool_results = []
        for msg in messages:
            if msg.get("role") == "user":
                content = msg.get("content", [])
                if isinstance(content, list):
                    for item in content:
                        if self._is_tool_result_content(item):
                            tool_results.append(item)
        return tool_results

    def _compare_response_with_next_request(
        self,
        response_body: Dict[str, Any],
        next_request_body: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Compare response content with next request to detect if response appears in next request.
        Mark matched content and append differences.
        """
        result = {
            "thinking_matched": False,
            "text_matched": False,
            "tool_calls_matched": False,
            "thinking_diff": None,
            "text_diff": None,
            "tool_calls_diff": None
        }

        if not next_request_body:
            return result

        # Get response content
        thinking = response_body.get("integrated_thinking", "")
        text = response_body.get("integrated_text", "")
        tool_calls = response_body.get("tool_calls", [])

        # Get next request messages
        next_messages = next_request_body.get("messages", [])

        # Convert next request to string for comparison
        next_request_str = json.dumps(next_messages, ensure_ascii=False, sort_keys=True)

        # Check if thinking appears in next request
        if thinking and thinking in next_request_str:
            result["thinking_matched"] = True

        # Check if text appears in next request
        if text and text in next_request_str:
            result["text_matched"] = True

        # Check if tool calls appear in next request
        if tool_calls:
            tool_calls_str = json.dumps(tool_calls, ensure_ascii=False, sort_keys=True)
            if tool_calls_str in next_request_str:
                result["tool_calls_matched"] = True

        return result

    def _build_call_trace_item(
        self,
        index: int,
        request_data: Dict[str, Any],
        response_data: Optional[Dict[str, Any]],
        next_request_data: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Build a single call trace item from request/response pair"""
        req_body = request_data.get("request_body", {})
        res_body = response_data.get("response_body", {}) if response_data else {}

        # Extract messages
        messages = req_body.get("messages", [])
        user_messages = self._extract_user_messages(messages)
        tool_results = self._extract_tool_results(messages)

        # Extract assistant response
        thinking = res_body.get("integrated_thinking", "")
        text = res_body.get("integrated_text", "")
        tool_calls = res_body.get("tool_calls", [])
        usage = res_body.get("usage", {})
        stop_reason = res_body.get("stop_reason", "")

        # Compare with next request
        next_req_body = next_request_data.get("request_body", {}) if next_request_data else None
        comparison = self._compare_response_with_next_request(res_body, next_req_body)

        # Build trace item with information list structure
        trace_item = {
            "index": index,
            "model": req_body.get("model", ""),
            "information_list": []
        }

        # Add user messages
        for user_msg in user_messages:
            trace_item["information_list"].append({
                "type": "user_message",
                "content": user_msg["content"]
            })

        # Add tool results (from previous assistant tool calls)
        for tool_result in tool_results:
            trace_item["information_list"].append({
                "type": "tool_result",
                "tool_use_id": tool_result.get("tool_use_id"),
                "content": tool_result.get("content")
            })

        # Add assistant thinking
        if thinking:
            trace_item["information_list"].append({
                "type": "assistant_thinking",
                "content": thinking,
                "matched_in_next_request": comparison["thinking_matched"]
            })

        # Add assistant text
        if text:
            trace_item["information_list"].append({
                "type": "assistant_text",
                "content": text,
                "matched_in_next_request": comparison["text_matched"]
            })

        # Add tool calls
        if tool_calls:
            trace_item["information_list"].append({
                "type": "tool_calls",
                "calls": tool_calls,
                "matched_in_next_request": comparison["tool_calls_matched"]
            })

        # Add usage and stop reason
        trace_item["usage"] = usage
        trace_item["stop_reason"] = stop_reason

        return trace_item

    def parse(self):
        """Main parsing function to generate unified call trace"""
        if not self.decoded_dir.exists():
            raise FileNotFoundError(f"Decoded directory not found: {self.decoded_dir}")

        self.output_dir.mkdir(parents=True, exist_ok=True)

        print(f"[parser] Starting to parse call traces from {self.decoded_dir}...")

        # Find all request files
        search_pattern = str(self.decoded_dir / "*_request_*.json")
        request_files = glob.glob(search_pattern)

        if not request_files:
            print("[parser] No request files found")
            return

        # Sort by index
        try:
            request_files.sort(key=lambda x: int(Path(x).name.split('_')[0]))
        except ValueError:
            request_files.sort()

        # Build call trace
        call_trace = []

        for i, req_file in enumerate(request_files):
            req_path = Path(req_file)
            index = int(req_path.name.split('_')[0])

            # Load request
            with open(req_path, 'r', encoding='utf-8') as f:
                request_data = json.load(f)

            # Find corresponding response
            res_pattern = str(self.decoded_dir / f"{index}_response_*.json")
            res_files = glob.glob(res_pattern)
            response_data = None
            if res_files:
                with open(res_files[0], 'r', encoding='utf-8') as f:
                    response_data = json.load(f)

            # Get next request for comparison
            next_request_data = None
            if i + 1 < len(request_files):
                with open(request_files[i + 1], 'r', encoding='utf-8') as f:
                    next_request_data = json.load(f)

            # Build trace item
            trace_item = self._build_call_trace_item(
                index,
                request_data,
                response_data,
                next_request_data
            )

            call_trace.append(trace_item)
            print(f"[parser] Parsed call trace item {index}")

        # Write call trace
        trace_path = self.output_dir / "call_trace.json"
        with open(trace_path, 'w', encoding='utf-8') as f:
            json.dump(call_trace, f, ensure_ascii=False, indent=4)

        print(f"[parser] Call trace with {len(call_trace)} items saved to call_trace.json")
