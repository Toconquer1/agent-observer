#!/usr/bin/env python3
"""
agentob 命令行界面
"""
import sys
import argparse
from .wrapper import AgentWrapper


def main():
    """agentob CLI 主入口"""
    parser = argparse.ArgumentParser(
        description="Agent 执行观测工具",
        usage="agentob [选项] -- <命令> [参数...]"
    )

    parser.add_argument(
        "-o", "--output",
        default=".agentob",
        help="mitm 文件和分析结果的输出目录（默认: .agentob）"
    )

    parser.add_argument(
        "-p", "--port",
        type=int,
        default=8080,
        help="代理端口（默认: 8080）"
    )

    parser.add_argument(
        "--no-analysis",
        action="store_true",
        help="跳过 agent 执行后的自动分析"
    )

    # 解析已知参数以处理 -- 分隔符
    args, remaining = parser.parse_known_args()

    # 查找 -- 分隔符
    if "--" in sys.argv:
        separator_idx = sys.argv.index("--")
        target_command = sys.argv[separator_idx + 1:]
    elif remaining:
        target_command = remaining
    else:
        parser.print_help()
        print("\n错误：未指定目标命令")
        print("\nExamples:")
        print("  agentob -- claude")
        print("  agentob -- python script.py")
        print("  agentob -o ./output -- npm run dev")
        return 1

    if not target_command:
        print("错误：'--' 之后未指定命令")
        return 1

    # 创建并运行 wrapper
    wrapper = AgentWrapper(
        output_dir=args.output,
        proxy_port=args.port,
        auto_analysis=not args.no_analysis
    )

    return wrapper.run(target_command)


if __name__ == "__main__":
    sys.exit(main())
