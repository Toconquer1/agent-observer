"""
测试集成后的权限验证
"""

import sys
import json
from pathlib import Path

# 添加父目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from agentob.analyzer import AgentAnalyzer


def test_integration():
    """测试权限验证集成到分析器"""
    print("=" * 60)
    print("测试权限验证集成")
    print("=" * 60)

    # 创建测试数据
    test_dir = Path(__file__).parent / ".agentob" / "test_session"
    test_dir.mkdir(parents=True, exist_ok=True)

    # 创建测试文件
    (test_dir / "prompts.txt").write_text("Test system prompt", encoding="utf-8")
    (test_dir / "tools.json").write_text(json.dumps([
        {"name": "Bash", "description": "Execute bash commands"},
        {"name": "Read", "description": "Read files"}
    ]), encoding="utf-8")

    # 创建测试调用轨迹
    call_trace = [
        {
            "type": "tool_calls",
            "content": [
                {
                    "name": "Bash",
                    "arguments": {"command": "python3 test.py"}
                }
            ]
        },
        {
            "type": "tool_calls",
            "content": [
                {
                    "name": "Bash",
                    "arguments": {"command": "ls -la"}
                }
            ]
        },
        {
            "type": "tool_calls",
            "content": [
                {
                    "name": "Read",
                    "arguments": {"file_path": "test.py"}
                }
            ]
        }
    ]

    (test_dir / "call_trace.json").write_text(
        json.dumps(call_trace, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    print("\n测试数据已创建")
    print(f"测试目录: {test_dir}")

    # 测试权限验证
    print("\n测试权限验证:")

    try:
        from permissions import PermissionValidator

        validator = PermissionValidator("claude_code", str(Path(__file__).parent))

        for i, item in enumerate(call_trace):
            if item["type"] == "tool_calls":
                print(f"\n调用 {i + 1}:")
                for call in item["content"]:
                    result = validator.validate_tool_call(call)
                    print(f"  工具: {call['name']}")
                    print(f"  参数: {call['arguments']}")
                    print(f"  授权: {result.is_authorized}")
                    print(f"  风险级别: {result.risk_level}")
                    if result.reason:
                        print(f"  原因: {result.reason}")

        print("\n✓ 权限验证集成测试成功")

    except Exception as e:
        print(f"\n✗ 权限验证集成测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    test_integration()
