#!/usr/bin/env python3
"""
Command-line interface for agentob
"""
import sys
import argparse
from .wrapper import AgentWrapper


def main():
    """Main entry point for agentob CLI"""
    parser = argparse.ArgumentParser(
        description="Agent execution observation tool",
        usage="agentob [options] -- <command> [args...]"
    )

    parser.add_argument(
        "-o", "--output",
        default=".agentob",
        help="Output directory for mitm files and analysis results (default: .agentob)"
    )

    parser.add_argument(
        "-p", "--port",
        type=int,
        default=8080,
        help="Proxy port (default: 8080)"
    )

    parser.add_argument(
        "--no-analysis",
        action="store_true",
        help="Skip automatic analysis after agent execution"
    )

    # Parse known args to handle the -- separator
    args, remaining = parser.parse_known_args()

    # Find the -- separator
    if "--" in sys.argv:
        separator_idx = sys.argv.index("--")
        target_command = sys.argv[separator_idx + 1:]
    elif remaining:
        target_command = remaining
    else:
        parser.print_help()
        print("\nError: No target command specified")
        print("\nExamples:")
        print("  agentob -- claude")
        print("  agentob -- python script.py")
        print("  agentob -o ./output -- npm run dev")
        return 1

    if not target_command:
        print("Error: No command specified after '--'")
        return 1

    # Create and run wrapper
    wrapper = AgentWrapper(
        output_dir=args.output,
        proxy_port=args.port,
        auto_analysis=not args.no_analysis
    )

    return wrapper.run(target_command)


if __name__ == "__main__":
    sys.exit(main())
