"""
解析器模块，将请求/响应对合成为统一的调用轨迹
"""
import json
import glob
from pathlib import Path
from typing import Dict, Any, List, Optional


class CallTraceParser:
    """将简化后的请求/响应对合成为统一调用轨迹的解析器"""

    def __init__(self, decoded_dir: str, output_dir: str):
        self.decoded_dir = Path(decoded_dir)
        self.output_dir = Path(output_dir)

    def _is_tool_result_content(self, content_item: Dict[str, Any]) -> bool:
        """检查内容项是否为工具结果"""
        return isinstance(content_item, dict) and content_item.get("type") == "tool_result"

    def _extract_user_messages(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """提取真正的用户消息（排除工具结果）"""
        user_messages = []
        for msg in messages:
            if msg.get("role") == "user":
                content = msg.get("content", [])
                if isinstance(content, list):
                    # 过滤掉 tool_result 项
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
        """从 user 角色消息中提取工具结果消息"""
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
        将响应内容与下一个请求进行比对，检测响应是否出现在下一请求中。
        标记已匹配的内容并附加差异。
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

        # 获取响应内容
        thinking = response_body.get("integrated_thinking", "")
        text = response_body.get("integrated_text", "")
        tool_calls = response_body.get("tool_calls", [])

        # 获取下一个请求的消息
        next_messages = next_request_body.get("messages", [])

        # 将下一个请求转为字符串以便比对
        next_request_str = json.dumps(next_messages, ensure_ascii=False, sort_keys=True)

        # 检查思考内容是否出现在下一个请求中
        if thinking and thinking in next_request_str:
            result["thinking_matched"] = True

        # 检查文本是否出现在下一个请求中
        if text and text in next_request_str:
            result["text_matched"] = True

        # 检查工具调用是否出现在下一个请求中
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
        """从请求/响应对构建单个调用轨迹项"""
        req_body = request_data.get("request_body", {})
        res_body = response_data.get("response_body", {}) if response_data else {}

        # 提取消息
        messages = req_body.get("messages", [])
        user_messages = self._extract_user_messages(messages)
        tool_results = self._extract_tool_results(messages)

        # 提取助手响应
        thinking = res_body.get("integrated_thinking", "")
        text = res_body.get("integrated_text", "")
        tool_calls = res_body.get("tool_calls", [])
        usage = res_body.get("usage", {})
        stop_reason = res_body.get("stop_reason", "")

        # 与下一个请求比对
        next_req_body = next_request_data.get("request_body", {}) if next_request_data else None
        comparison = self._compare_response_with_next_request(res_body, next_req_body)

        # 构建包含 information_list 结构的轨迹项
        trace_item = {
            "index": index,
            "model": req_body.get("model", ""),
            "information_list": []
        }

        # 添加用户消息
        for user_msg in user_messages:
            trace_item["information_list"].append({
                "type": "user_message",
                "content": user_msg["content"]
            })

        # 添加工具结果（来自前序助手的工具调用）
        for tool_result in tool_results:
            trace_item["information_list"].append({
                "type": "tool_result",
                "tool_use_id": tool_result.get("tool_use_id"),
                "content": tool_result.get("content")
            })

        # 添加助手思考内容
        if thinking:
            trace_item["information_list"].append({
                "type": "assistant_thinking",
                "content": thinking,
                "matched_in_next_request": comparison["thinking_matched"]
            })

        # 添加助手文本回复
        if text:
            trace_item["information_list"].append({
                "type": "assistant_text",
                "content": text,
                "matched_in_next_request": comparison["text_matched"]
            })

        # 添加工具调用
        if tool_calls:
            trace_item["information_list"].append({
                "type": "tool_calls",
                "calls": tool_calls,
                "matched_in_next_request": comparison["tool_calls_matched"]
            })

        # 添加用量和停止原因
        trace_item["usage"] = usage
        trace_item["stop_reason"] = stop_reason

        return trace_item

    def parse(self):
        """主解析函数，生成统一的调用轨迹"""
        if not self.decoded_dir.exists():
            raise FileNotFoundError(f"解码目录未找到: {self.decoded_dir}")

        self.output_dir.mkdir(parents=True, exist_ok=True)

        print(f"[parser] 开始从 {self.decoded_dir} 解析调用轨迹...")

        # 查找所有请求文件
        search_pattern = str(self.decoded_dir / "*_request_*.json")
        request_files = glob.glob(search_pattern)

        if not request_files:
            print("[parser] 未找到请求文件")
            return

        # 按索引排序
        try:
            request_files.sort(key=lambda x: int(Path(x).name.split('_')[0]))
        except ValueError:
            request_files.sort()

        # 构建调用轨迹
        call_trace = []

        for i, req_file in enumerate(request_files):
            req_path = Path(req_file)
            index = int(req_path.name.split('_')[0])

            # 加载请求
            with open(req_path, 'r', encoding='utf-8') as f:
                request_data = json.load(f)

            # 查找对应的响应
            res_pattern = str(self.decoded_dir / f"{index}_response_*.json")
            res_files = glob.glob(res_pattern)
            response_data = None
            if res_files:
                with open(res_files[0], 'r', encoding='utf-8') as f:
                    response_data = json.load(f)

            # 获取下一个请求用于比对
            next_request_data = None
            if i + 1 < len(request_files):
                with open(request_files[i + 1], 'r', encoding='utf-8') as f:
                    next_request_data = json.load(f)

            # 构建轨迹项
            trace_item = self._build_call_trace_item(
                index,
                request_data,
                response_data,
                next_request_data
            )

            call_trace.append(trace_item)
            print(f"[parser] 已解析调用轨迹项 {index}")

        # 写入调用轨迹
        trace_path = self.output_dir / "call_trace.json"
        with open(trace_path, 'w', encoding='utf-8') as f:
            json.dump(call_trace, f, ensure_ascii=False, indent=4)

        print(f"[parser] 包含 {len(call_trace)} 项的调用轨迹已保存至 call_trace.json")
