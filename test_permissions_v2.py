"""
测试基于实际配置的权限验证系统
"""

import sys
from pathlib import Path

# 添加父目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from permissions import PermissionValidator


def test_claude_code_permissions():
    """测试 Claude Code 权限验证"""
    print("=" * 60)
    print("测试 Claude Code 权限验证（基于实际配置）")
    print("=" * 60)

    validator = PermissionValidator("claude_code", "E:\\master_code\\agob_workspace")

    print("\n当前配置文件:")
    print("  - 全局: ~/.claude/settings.json")
    print("  - 项目: .claude/settings.json")
    print("  - 本地: .claude/settings.local.json")

    print("\n当前权限规则:")
    if validator.config and validator.config.permissions:
        for rule in validator.config.permissions:
            print(f"  - {rule.tool_name}" + (f"({rule.pattern})" if rule.pattern else ""))
    else:
        print("  (无配置，默认允许所有)")

    print("\n" + "=" * 60)
    print("测试用例")
    print("=" * 60)

    test_cases = [
        {
            "category": "Bash 命令",
            "cases": [
                {
                    "name": "python3 test.py (应该允许)",
                    "tool_call": {
                        "name": "Bash",
                        "arguments": {"command": "python3 test.py"}
                    },
                    "expected": True
                },
                {
                    "name": "python script.py (应该允许)",
                    "tool_call": {
                        "name": "Bash",
                        "arguments": {"command": "python script.py"}
                    },
                    "expected": True
                },
                {
                    "name": "python3 -m pytest (应该允许)",
                    "tool_call": {
                        "name": "Bash",
                        "arguments": {"command": "python3 -m pytest"}
                    },
                    "expected": True
                },
                {
                    "name": "ls -la (应该拒绝)",
                    "tool_call": {
                        "name": "Bash",
                        "arguments": {"command": "ls -la"}
                    },
                    "expected": False
                },
                {
                    "name": "git status (应该拒绝)",
                    "tool_call": {
                        "name": "Bash",
                        "arguments": {"command": "git status"}
                    },
                    "expected": False
                },
                {
                    "name": "rm -rf / (应该拒绝)",
                    "tool_call": {
                        "name": "Bash",
                        "arguments": {"command": "rm -rf /"}
                    },
                    "expected": False
                },
            ]
        },
        {
            "category": "文件操作",
            "cases": [
                {
                    "name": "Read 工作空间内文件 (应该拒绝 - 未配置)",
                    "tool_call": {
                        "name": "Read",
                        "arguments": {"file_path": "E:\\master_code\\agob_workspace\\test.py"}
                    },
                    "expected": False
                },
                {
                    "name": "Read 工作空间外文件 (应该拒绝)",
                    "tool_call": {
                        "name": "Read",
                        "arguments": {"file_path": "C:\\Windows\\System32\\config\\sam"}
                    },
                    "expected": False
                },
                {
                    "name": "Write 工作空间内文件 (应该拒绝 - 未配置)",
                    "tool_call": {
                        "name": "Write",
                        "arguments": {"file_path": "E:\\master_code\\agob_workspace\\test.py"}
                    },
                    "expected": False
                },
            ]
        }
    ]

    total_tests = 0
    passed_tests = 0

    for category_data in test_cases:
        print(f"\n{category_data['category']}:")
        print("-" * 60)

        for test_case in category_data['cases']:
            total_tests += 1
            result = validator.validate_tool_call(test_case['tool_call'])

            # 检查是否符合预期
            is_correct = result.is_authorized == test_case['expected']
            if is_correct:
                passed_tests += 1

            status = "PASS" if is_correct else "FAIL"
            auth_status = "允许" if result.is_authorized else "拒绝"

            print(f"\n  [{status}] {test_case['name']}")
            print(f"    结果: {auth_status}")
            print(f"    风险级别: {result.risk_level}")
            if result.reason:
                print(f"    原因: {result.reason}")
            if result.violated_rules:
                print(f"    违反规则: {', '.join(result.violated_rules)}")

    print("\n" + "=" * 60)
    print(f"测试结果: {passed_tests}/{total_tests} 通过")
    print("=" * 60)

    return passed_tests == total_tests


def test_add_permission():
    """演示如何添加权限"""
    print("\n" + "=" * 60)
    print("如何添加权限")
    print("=" * 60)

    print("""
要允许更多工具或命令，编辑配置文件：

1. 项目级别权限（推荐）：
   编辑: .claude/settings.local.json

   {
     "permissions": {
       "allow": [
         "Bash(python3 *)",
         "Bash(python *)",
         "Bash(git *)",        // 允许所有 git 命令
         "Read",               // 允许所有 Read 操作
         "Write",              // 允许所有 Write 操作
         "Glob"                // 允许文件搜索
       ]
     }
   }

2. 全局权限：
   编辑: ~/.claude/settings.json

   格式相同，但会影响所有项目

3. 权限规则格式：
   - "ToolName" - 允许该工具的所有调用
   - "ToolName(pattern)" - 只允许匹配模式的调用
   - pattern 中 * 表示任意字符

4. 工作空间限制：
   - 文件操作（Read/Write/Edit/Glob）会自动检查路径
   - 只能访问当前工作目录及其子目录
   - 访问工作空间外的文件会被拒绝
""")


if __name__ == "__main__":
    success = test_claude_code_permissions()
    test_add_permission()

    if success:
        print("\n所有测试通过！")
        sys.exit(0)
    else:
        print("\n部分测试失败！")
        sys.exit(1)
