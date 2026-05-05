"""
Simplify module for simplifying and extracting information from decoded requests
"""
import os
import json
import glob
from pathlib import Path
from typing import Dict, Any, List, Optional
import copy


class RequestSimplifier:
    """Simplifier for simplifying decoded request/response pairs"""

    def __init__(self, decoded_dir: str):
        self.decoded_dir = Path(decoded_dir)
        self.output_dir = self.decoded_dir / "analyzed"
        self.mapping = {}
        self.next_idx = 0
        self.all_extracted_tools = {}
        self.all_extracted_skills = {}
        self.global_message_pool = {}

    def _get_placeholder(self, index: int) -> str:
        """Generate uppercase letter placeholders: A, B, C... Z, AA, AB..."""
        res = ""
        while index >= 0:
            res = chr(65 + (index % 26)) + res
            index = index // 26 - 1
        return res

    def _get_simplified_text(self, text: str) -> str:
        """Get or create placeholder for long text"""
        if text not in self.mapping:
            placeholder = self._get_placeholder(self.next_idx)
            self.mapping[text] = f"[{placeholder}]"
            self.next_idx += 1
        return self.mapping[text]

    def _sanitize_message(self, data: Any) -> Any:
        """
        Recursively clean dictionary, removing transient fields that LLM discards
        in historical sessions (like cache_control, signature, etc.),
        ensuring hash consistency between current and historical requests.
        """
        if isinstance(data, dict):
            cleaned = {}
            for k, v in data.items():
                # Filter out troublesome fields
                if k in ["cache_control", "signature"]:
                    continue
                cleaned[k] = self._sanitize_message(v)
            return cleaned
        elif isinstance(data, list):
            return [self._sanitize_message(item) for item in data]
        else:
            return data

    def _is_tool_result_message(self, msg: Dict[str, Any]) -> bool:
        """
        Check if a message is a tool result (appears as user role but contains tool_result)
        """
        if not isinstance(msg, dict):
            return False

        if msg.get("role") != "user":
            return False

        content = msg.get("content", [])
        if isinstance(content, list):
            for item in content:
                if isinstance(item, dict) and item.get("type") == "tool_result":
                    return True

        return False

    def _extract_mcp_info(self, req_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract MCP server information from request"""
        # This is a placeholder - actual MCP format needs to be determined
        # based on real MCP request structure
        return None

    def _simplify_request(self, filepath: Path, file_index: str) -> bool:
        """Simplify a single request file"""
        with open(filepath, 'r', encoding='utf-8') as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                return False

        req_body = data.get("request_body", {})
        if not isinstance(req_body, dict):
            return False

        modified = False
        req_type = data.get("type", "unknown")

        # If no type field, assume it's an LLM request if it has messages/system/tools
        if req_type == "unknown" and any(k in req_body for k in ["messages", "system", "tools"]):
            req_type = "llm"
            data["type"] = "llm"
            modified = True

        # Only process LLM requests for now
        if req_type != "llm":
            return False

        # 1. Simplify and deduplicate message history
        if "messages" in req_body and isinstance(req_body["messages"], list):
            simplified_messages = []

            for i, msg in enumerate(req_body["messages"]):
                if not isinstance(msg, dict):
                    simplified_messages.append(msg)
                    continue

                # Mark tool result messages
                if self._is_tool_result_message(msg):
                    msg["_is_tool_result"] = True

                # Clean message before comparison
                clean_msg = self._sanitize_message(msg)

                try:
                    # Generate comparison string using cleaned object
                    msg_str = json.dumps(clean_msg, sort_keys=True, ensure_ascii=False, separators=(',', ':'))
                except Exception:
                    msg_str = str(clean_msg)

                if msg_str in self.global_message_pool:
                    simplified_messages.append({
                        "role": "history_placeholder",
                        "content": self.global_message_pool[msg_str],
                        "_original_role": msg.get("role")
                    })
                    modified = True
                else:
                    origin_marker = f"[History origin: Request {file_index}, Msg {i}]"
                    self.global_message_pool[msg_str] = origin_marker
                    # Keep original message with all its fields
                    simplified_messages.append(msg)

            req_body["messages"] = simplified_messages

        # 2. Simplify system field
        if "system" in req_body:
            system_data = req_body["system"]
            if isinstance(system_data, str) and len(system_data) > 50:
                req_body["system"] = self._get_simplified_text(system_data)
                modified = True
            elif isinstance(system_data, list):
                for item in system_data:
                    if isinstance(item, dict) and "text" in item and isinstance(item["text"], str):
                        if len(item["text"]) > 50:
                            item["text"] = self._get_simplified_text(item["text"])
                            modified = True

        # 3. Extract and simplify tools
        if "tools" in req_body and isinstance(req_body["tools"], list):
            simplified_tools = []
            for tool in req_body["tools"]:
                if isinstance(tool, dict) and "name" in tool:
                    tool_name = tool["name"]
                    self.all_extracted_tools[tool_name] = tool
                    simplified_tools.append({
                        "name": tool_name,
                        "extracted": True
                    })
                    modified = True
                else:
                    simplified_tools.append(tool)
            req_body["tools"] = simplified_tools

        if modified:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)

        return modified

    def _build_trace(self) -> List[Dict[str, Any]]:
        """Build execution trace from request/response pairs"""
        trace = []

        search_pattern = str(self.decoded_dir / "*_request_*.json")
        request_files = glob.glob(search_pattern)

        if not request_files:
            return trace

        # Sort by index
        try:
            request_files.sort(key=lambda x: int(os.path.basename(x).split('_')[0]))
        except ValueError:
            request_files.sort()

        for req_file in request_files:
            req_path = Path(req_file)
            index = req_path.name.split('_')[0]

            # Find corresponding response
            res_pattern = str(self.decoded_dir / f"{index}_response_*.json")
            res_files = glob.glob(res_pattern)

            with open(req_path, 'r', encoding='utf-8') as f:
                req_data = json.load(f)

            res_data = None
            if res_files:
                with open(res_files[0], 'r', encoding='utf-8') as f:
                    res_data = json.load(f)

            trace_item = {
                "index": int(index),
                "type": req_data.get("type", "unknown"),
                "request": req_data,
                "response": res_data
            }

            trace.append(trace_item)

        return trace

    def analyze(self):
        """Main analysis function"""
        if not self.decoded_dir.exists():
            raise FileNotFoundError(f"Decoded directory not found: {self.decoded_dir}")

        self.output_dir.mkdir(parents=True, exist_ok=True)

        print(f"[analyzer] Starting analysis of {self.decoded_dir}...")

        # Find all request files
        search_pattern = str(self.decoded_dir / "*_request_*.json")
        request_files = glob.glob(search_pattern)

        if not request_files:
            print("[analyzer] No request files found")
            return

        # Sort by index
        try:
            request_files.sort(key=lambda x: int(os.path.basename(x).split('_')[0]))
        except ValueError:
            request_files.sort()

        # Simplify each request
        modified_count = 0
        for filepath in request_files:
            file_path = Path(filepath)
            filename = file_path.name
            file_index = filename.split('_')[0]

            if self._simplify_request(file_path, file_index):
                modified_count += 1
                print(f"[analyzer] Simplified: {filename}")

        print(f"[analyzer] Simplified {modified_count} request files")

        # Write extracted prompts
        if self.mapping:
            prompts_path = self.output_dir / "prompts.txt"
            with open(prompts_path, 'w', encoding='utf-8') as f:
                for text, placeholder in self.mapping.items():
                    f.write(f"================ {placeholder} ================\n")
                    f.write(text)
                    f.write("\n\n")
            print(f"[analyzer] Extracted {len(self.mapping)} system prompts to prompts.txt")

        # Write extracted tools
        if self.all_extracted_tools:
            tools_path = self.output_dir / "tools.json"
            with open(tools_path, 'w', encoding='utf-8') as f:
                json.dump(self.all_extracted_tools, f, ensure_ascii=False, indent=4)
            print(f"[analyzer] Extracted {len(self.all_extracted_tools)} tools to tools.json")

        # Build execution trace
        trace = self._build_trace()
        if trace:
            trace_path = self.output_dir / "execution_trace.json"
            with open(trace_path, 'w', encoding='utf-8') as f:
                json.dump(trace, f, ensure_ascii=False, indent=4)
            print(f"[analyzer] Built execution trace with {len(trace)} steps")

        print("[analyzer] Analysis completed!")
