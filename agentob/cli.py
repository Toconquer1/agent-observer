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
        usage="agentob [选项] -- <命令> [参数...]\n       agentob attach [选项] [时长]"
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

    # 检查是否是 attach 模式
    if len(sys.argv) > 1 and sys.argv[1] == "attach":
        # attach 模式
        parser.add_argument(
            "duration",
            nargs="?",
            type=int,
            default=None,
            help="可选的捕获时长（秒），不指定则无限期直到 Ctrl+C"
        )

        # 移除 "attach" 参数后再解析
        args = parser.parse_args(sys.argv[2:] if len(sys.argv) > 2 else [])

        # 创建 wrapper
        wrapper = AgentWrapper(
            output_dir=args.output,
            proxy_port=args.port,
            auto_analysis=not args.no_analysis
        )

        return wrapper.attach(duration=args.duration)

    else:
        # 正常模式：运行命令
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
            print("\n使用方式:")
            print("  1. 前台模式（运行命令）:")
            print("     agentob -- <命令>")
            print("     例如: agentob -- claude")
            print("           agentob -- python script.py")
            print()
            print("  2. Attach 模式（观测后台 agent）:")
            print("     agentob attach [时长]")
            print("     例如: agentob attach          # 无限期，直到 Ctrl+C")
            print("           agentob attach 300      # 捕获 300 秒")
            print()
            print("  Attach 模式使用步骤:")
            print("    1. 运行 agentob attach")
            print("    2. 按提示设置环境变量")
            print("    3. 启动你的后台 agent（如 OpenClaw）")
            print("    4. 按 Ctrl+C 停止捕获并分析")
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
