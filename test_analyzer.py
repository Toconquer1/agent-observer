"""
AgentAnalyzer 模块的测试脚本。

按要求测试失败场景（无 API 密钥）。
成功场景需要在 .env 文件中手动配置 API 密钥。
"""

import os
import sys
from pathlib import Path

# 将父目录添加到路径
sys.path.insert(0, str(Path(__file__).parent))

from agentob.analyzer import AgentAnalyzer


def test_analyzer_no_api_key():
    """测试无 API 密钥的情况（失败场景）"""
    print("=" * 60)
    print("测试 1：无 API 密钥的分析器（应优雅失败）")
    print("=" * 60)

    # 临时移除 API 密钥（如果存在）
    original_key = os.environ.pop("AGOB_API_KEY", None)

    try:
        # 测试数据位于父目录
        analyzed_dir = Path("../.agentob/b844fa93/decoded_flows/analyzed").resolve()

        if not analyzed_dir.exists():
            print(f"错误：测试数据目录未找到: {analyzed_dir}")
            return False

        print(f"使用测试数据: {analyzed_dir}")

        try:
            analyzer = AgentAnalyzer(str(analyzed_dir))
            print("错误：本应因缺少 API 密钥而抛出 ValueError")
            return False
        except ValueError as e:
            print(f"[通过] 正确抛出了 ValueError: {e}")
            return True

    finally:
        # 恢复原始密钥
        if original_key:
            os.environ["AGOB_API_KEY"] = original_key


def test_analyzer_with_invalid_api_key():
    """测试无效 API 密钥的情况（失败场景）"""
    print("\n" + "=" * 60)
    print("测试 2：无效 API 密钥的分析器（应优雅失败）")
    print("=" * 60)

    analyzed_dir = Path("../.agentob/b844fa93/decoded_flows/analyzed").resolve()

    if not analyzed_dir.exists():
        print(f"错误：测试数据目录未找到: {analyzed_dir}")
        return False

    print(f"使用测试数据: {analyzed_dir}")

    try:
        # 使用无效 API 密钥
        analyzer = AgentAnalyzer(str(analyzed_dir), api_key="invalid_key_12345")
        print("[通过] 使用无效密钥初始化分析器成功")

        # 尝试分析（应该失败但会生成空的 analyze.json）
        result = analyzer.analyze()

        # 检查 analyze.json 是否已创建
        output_file = analyzed_dir / "analyze.json"
        if output_file.exists():
            print(f"[通过] analyze.json 已创建: {output_file}")

            # 检查结构
            if "system_prompt_analysis" in result:
                print("[通过] 结果结构正确")
                print(f"  - system_prompt_analysis: {len(result['system_prompt_analysis'])} 字符")
                print(f"  - tools_analysis: {len(result['tools_analysis'])} 字符")
                print(f"  - call_analyses: {len(result['call_analyses'])} 项")
                print(f"  - overall_analysis: {len(result['overall_analysis'])} 字符")
                return True
            else:
                print("错误：结果缺少必要字段")
                return False
        else:
            print("错误：analyze.json 未创建")
            return False

    except Exception as e:
        print(f"[通过] 异常已被优雅处理: {e}")

        # 检查 analyze.json 是否仍然创建
        output_file = analyzed_dir / "analyze.json"
        if output_file.exists():
            print(f"[通过] 尽管出错，analyze.json 仍然创建")
            return True
        else:
            print("错误：analyze.json 未创建")
            return False


def test_load_input_files():
    """测试加载输入文件"""
    print("\n" + "=" * 60)
    print("测试 3：加载输入文件")
    print("=" * 60)

    analyzed_dir = Path("../.agentob/b844fa93/decoded_flows/analyzed").resolve()

    if not analyzed_dir.exists():
        print(f"错误：测试数据目录未找到: {analyzed_dir}")
        return False

    # 检查文件是否存在
    prompts_file = analyzed_dir / "prompts.txt"
    tools_file = analyzed_dir / "tools.json"
    trace_file = analyzed_dir / "call_trace.json"

    print(f"检查目录中的文件: {analyzed_dir}")
    print(f"  - prompts.txt: {'[通过]' if prompts_file.exists() else '[失败]'}")
    print(f"  - tools.json: {'[通过]' if tools_file.exists() else '[失败]'}")
    print(f"  - call_trace.json: {'[通过]' if trace_file.exists() else '[失败]'}")

    if not all([prompts_file.exists(), tools_file.exists(), trace_file.exists()]):
        print("错误：部分输入文件缺失")
        return False

    # 尝试使用虚拟 API 密钥加载
    try:
        analyzer = AgentAnalyzer(str(analyzed_dir), api_key="dummy_key")

        print(f"\n[通过] 已加载提示词: {len(analyzer.prompts)} 字符")
        print(f"[通过] 已加载工具: {len(analyzer.tools)} 个工具")
        print(f"[通过] 已加载调用轨迹: {len(analyzer.call_trace)} 次调用")

        # 显示详细信息
        if analyzer.call_trace:
            first_call = analyzer.call_trace[0]
            print(f"\n首次调用详情:")
            print(f"  - 索引: {first_call.get('index')}")
            print(f"  - 模型: {first_call.get('model')}")
            print(f"  - information_list 项数: {len(first_call.get('information_list', []))}")

        return True

    except Exception as e:
        print(f"错误：加载文件失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("AgentAnalyzer 测试套件")
    print("=" * 60)

    results = []

    # 测试 1：无 API 密钥
    results.append(("无 API 密钥", test_analyzer_no_api_key()))

    # 测试 2：无效 API 密钥
    results.append(("无效 API 密钥", test_analyzer_with_invalid_api_key()))

    # 测试 3：加载输入文件
    results.append(("加载输入文件", test_load_input_files()))

    # 摘要
    print("\n" + "=" * 60)
    print("测试摘要")
    print("=" * 60)

    for name, passed in results:
        status = "[通过]" if passed else "[失败]"
        print(f"{status}: {name}")

    total = len(results)
    passed = sum(1 for _, p in results if p)
    print(f"\n总计: {passed}/{total} 个测试通过")

    return all(p for _, p in results)


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
