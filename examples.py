"""
agentob 使用示例

展示如何通过编程方式使用 agentob 的各个模块
"""

# 示例 1：使用 Wrapper 执行命令
def example_wrapper():
    """使用 AgentWrapper 包装并执行命令"""
    from agentob import AgentWrapper

    wrapper = AgentWrapper(
        output_dir=".agentob",
        proxy_port=8080,
        auto_analysis=True
    )

    # 执行目标命令
    return_code = wrapper.run(["echo", "Hello, agentob!"])
    print(f"命令已退出，返回码: {return_code}")


# 示例 2：手动解码 mitm 文件
def example_decoder():
    """解码已有的 mitm 文件"""
    from agentob import MitmDecoder

    decoder = MitmDecoder(
        input_file="path/to/flows.mitm",
        output_dir="./decoded_output"
    )

    try:
        decoder.decode()
        print("解码成功完成！")
    except FileNotFoundError:
        print("错误：未找到 mitm 文件")
    except Exception as e:
        print(f"解码时出错: {e}")


# 示例 3：简化和解析已解码的请求
def example_simplifier_and_parser():
    """简化和解析已解码的请求文件"""
    from agentob import RequestSimplifier, CallTraceParser

    # 简化请求
    simplifier = RequestSimplifier(
        decoded_dir="./decoded_output"
    )

    try:
        simplifier.simplify()
        print("简化成功完成！")
    except FileNotFoundError:
        print("错误：未找到解码目录")
    except Exception as e:
        print(f"简化时出错: {e}")
        return

    # 解析调用轨迹
    parser = CallTraceParser(
        decoded_dir="./decoded_output"
    )

    try:
        parser.parse()
        print("调用轨迹解析成功完成！")
        print("请查看 'analyzed' 子目录中的结果")
    except FileNotFoundError:
        print("错误：未找到解码目录")
    except Exception as e:
        print(f"解析时出错: {e}")


# 示例 4：完整流程
def example_full_pipeline():
    """完整的捕获、解码、简化、解析流程"""
    from agentob import AgentWrapper, MitmDecoder, RequestSimplifier, CallTraceParser
    from pathlib import Path

    output_dir = Path(".agentob")

    # 步骤 1：执行命令并捕获流量
    print("步骤 1：正在捕获流量...")
    wrapper = AgentWrapper(
        output_dir=str(output_dir),
        proxy_port=8080,
        auto_analysis=False  # 手动控制分析流程
    )

    return_code = wrapper.run(["echo", "test"])

    if return_code != 0:
        print(f"命令执行失败，返回码 {return_code}")
        return

    # 步骤 2：解码 mitm 文件
    print("\n步骤 2：正在解码流量...")
    mitm_file = output_dir / "flows.mitm"
    decoded_dir = output_dir / "decoded_flows"

    if mitm_file.exists():
        decoder = MitmDecoder(str(mitm_file), str(decoded_dir))
        decoder.decode()
    else:
        print("警告：未找到 mitm 文件")
        return

    # 步骤 3：简化请求
    print("\n步骤 3：正在简化请求...")
    simplifier = RequestSimplifier(str(decoded_dir))
    simplifier.simplify()

    # 步骤 4：解析调用轨迹
    print("\n步骤 4：正在解析调用轨迹...")
    parser = CallTraceParser(str(decoded_dir))
    parser.parse()

    print("\n流水线完成！")
    print(f"结果保存在: {output_dir}")


# 示例 5：自定义分析
def example_custom_analysis():
    """自定义分析逻辑"""
    import json
    from pathlib import Path

    decoded_dir = Path("./decoded_output")

    # 读取所有请求文件
    request_files = sorted(decoded_dir.glob("*_request_*.json"))

    print(f"找到 {len(request_files)} 个请求文件")

    for req_file in request_files:
        with open(req_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        req_body = data.get("request_body", {})

        # 提取模型信息
        model = req_body.get("model", "unknown")

        # 统计消息数量
        messages = req_body.get("messages", [])
        msg_count = len(messages)

        # 统计工具数量
        tools = req_body.get("tools", [])
        tool_count = len(tools)

        print(f"\n{req_file.name}:")
        print(f"  模型: {model}")
        print(f"  消息: {msg_count}")
        print(f"  工具: {tool_count}")


# 示例 6：提取特定信息
def example_extract_thinking():
    """提取所有响应中的 thinking 内容"""
    import json
    from pathlib import Path

    decoded_dir = Path("./decoded_output")
    response_files = sorted(decoded_dir.glob("*_response_*.json"))

    all_thinking = []

    for res_file in response_files:
        with open(res_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        res_body = data.get("response_body", {})

        # 检查是否为 SSE 流式响应
        if res_body.get("is_sse_stream"):
            thinking = res_body.get("integrated_thinking", "")
            if thinking:
                all_thinking.append({
                    "file": res_file.name,
                    "thinking": thinking
                })

    print(f"找到 {len(all_thinking)} 个包含 thinking 的响应")

    for item in all_thinking:
        print(f"\n{item['file']}:")
        print(f"  {item['thinking'][:100]}...")  # 只显示前 100 字符


if __name__ == "__main__":
    print("agentob 使用示例")
    print("=" * 60)

    # 取消注释以运行不同的示例

    # example_wrapper()
    # example_decoder()
    # example_simplifier_and_parser()
    # example_full_pipeline()
    # example_custom_analysis()
    # example_extract_thinking()

    print("\n请取消注释相应的示例函数来运行")
