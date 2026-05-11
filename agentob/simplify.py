"""
简化模块，用于简化和提取解码后请求中的信息
"""
import os
import json
import glob
from pathlib import Path
from typing import Dict, Any, List, Optional
import copy


class RequestSimplifier:
    """解码后请求/响应对的简化器"""

    def __init__(self, decoded_dir: str, output_dir: str):
        self.decoded_dir = Path(decoded_dir)
        self.output_dir = Path(output_dir)
        self.mapping = {}
        self.next_idx = 0
        self.all_extracted_tools = {}
        self.all_extracted_skills = {}
        self.global_message_pool = {}

    def _get_placeholder(self, index: int) -> str:
        """生成大写字母占位符：A, B, C... Z, AA, AB..."""
        res = ""
        while index >= 0:
            res = chr(65 + (index % 26)) + res
            index = index // 26 - 1
        return res

    def _get_simplified_text(self, text: str) -> str:
        """获取或创建长文本的占位符"""
        if text not in self.mapping:
            placeholder = self._get_placeholder(self.next_idx)
            self.mapping[text] = f"[{placeholder}]"
            self.next_idx += 1
        return self.mapping[text]

    def _sanitize_message(self, data: Any) -> Any:
        """
        递归清理字典，移除 LLM 在历史会话中会丢弃的瞬态字段
        （如 cache_control、signature 等），
        确保当前请求与历史请求之间的哈希一致性。
        """
        if isinstance(data, dict):
            cleaned = {}
            for k, v in data.items():
                # 过滤掉有问题的字段
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
        检查消息是否为工具结果（表现为 user 角色但包含 tool_result）
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
        """从请求中提取 MCP 服务器信息"""
        # 占位函数 - 实际 MCP 格式需要根据真实的 MCP 请求结构来确定
        return None

    def _simplify_request(self, filepath: Path, file_index: str) -> bool:
        """简化单个请求文件"""
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

        # 如果没有 type 字段，但包含 messages/system/tools，则假定为 LLM 请求
        if req_type == "unknown" and any(k in req_body for k in ["messages", "system", "tools"]):
            req_type = "llm"
            data["type"] = "llm"
            modified = True

        # 目前只处理 LLM 请求
        if req_type != "llm":
            return False

        # 1. 简化并去重消息历史
        if "messages" in req_body and isinstance(req_body["messages"], list):
            simplified_messages = []

            for i, msg in enumerate(req_body["messages"]):
                if not isinstance(msg, dict):
                    simplified_messages.append(msg)
                    continue

                # 标记工具结果消息
                if self._is_tool_result_message(msg):
                    msg["_is_tool_result"] = True

                # 在比对前清理消息
                clean_msg = self._sanitize_message(msg)

                try:
                    # 使用清理后的对象生成比对字符串
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
                    # 保留原始消息及其所有字段
                    simplified_messages.append(msg)

            req_body["messages"] = simplified_messages

        # 2. 简化 system 字段
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

        # 2b. 从 OpenAI 格式的 messages 中提取 system 角色消息
        if "messages" in req_body and isinstance(req_body["messages"], list):
            for msg in req_body["messages"]:
                if isinstance(msg, dict) and msg.get("role") == "system":
                    content = msg.get("content", "")
                    if isinstance(content, str) and len(content) > 50:
                        msg["content"] = self._get_simplified_text(content)
                        modified = True

        # 3. 提取并简化 tools
        if "tools" in req_body and isinstance(req_body["tools"], list):
            simplified_tools = []
            for tool in req_body["tools"]:
                if isinstance(tool, dict):
                    # Anthropic 格式: {"name": "Bash", "description": "..."}
                    if "name" in tool:
                        tool_name = tool["name"]
                        self.all_extracted_tools[tool_name] = tool
                        simplified_tools.append({
                            "name": tool_name,
                            "extracted": True
                        })
                        modified = True
                    # OpenAI 格式: {"type": "function", "function": {"name": "bash", ...}}
                    elif "function" in tool:
                        func = tool.get("function", {})
                        if isinstance(func, dict) and "name" in func:
                            tool_name = func["name"]
                            self.all_extracted_tools[tool_name] = func
                            simplified_tools.append({
                                "type": "function",
                                "name": tool_name,
                                "extracted": True
                            })
                            modified = True
                        else:
                            simplified_tools.append(tool)
                    else:
                        simplified_tools.append(tool)
                else:
                    simplified_tools.append(tool)
            req_body["tools"] = simplified_tools

        if modified:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)

        return modified

    def simplify(self):
        """主分析函数"""
        if not self.decoded_dir.exists():
            raise FileNotFoundError(f"解码目录未找到: {self.decoded_dir}")

        self.output_dir.mkdir(parents=True, exist_ok=True)

        print(f"[analyzer] 开始分析 {self.decoded_dir}...")

        # 查找所有请求文件
        search_pattern = str(self.decoded_dir / "*_request_*.json")
        request_files = glob.glob(search_pattern)

        if not request_files:
            print("[analyzer] 未找到请求文件")
            return

        # 按索引排序
        try:
            request_files.sort(key=lambda x: int(os.path.basename(x).split('_')[0]))
        except ValueError:
            request_files.sort()

        # 逐个简化请求
        modified_count = 0
        for filepath in request_files:
            file_path = Path(filepath)
            filename = file_path.name
            file_index = filename.split('_')[0]

            if self._simplify_request(file_path, file_index):
                modified_count += 1
                print(f"[analyzer] 已简化: {filename}")

        print(f"[analyzer] 已简化 {modified_count} 个请求文件")

        # 写入提取的提示词
        if self.mapping:
            prompts_path = self.output_dir / "prompts.txt"
            with open(prompts_path, 'w', encoding='utf-8') as f:
                for text, placeholder in self.mapping.items():
                    f.write(f"================ {placeholder} ================\n")
                    f.write(text)
                    f.write("\n\n")
            print(f"[analyzer] 已提取 {len(self.mapping)} 个系统提示词到 prompts.txt")

        # 写入提取的工具
        if self.all_extracted_tools:
            tools_path = self.output_dir / "tools.json"
            with open(tools_path, 'w', encoding='utf-8') as f:
                json.dump(self.all_extracted_tools, f, ensure_ascii=False, indent=4)
            print(f"[analyzer] 已提取 {len(self.all_extracted_tools)} 个工具到 tools.json")

        print("[analyzer] 简化完成！")
