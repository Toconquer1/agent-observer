#!/usr/bin/env python3
"""
AgentVisualizer 测试脚本
测试可视化生成功能
"""

import sys
from pathlib import Path

# 将父目录添加到路径
sys.path.insert(0, str(Path(__file__).parent))

from agentob.visualizer import AgentVisualizer


def test_visualizer():
    """使用已有测试数据测试可视化器"""
    print("=" * 60)
    print("测试 AgentVisualizer")
    print("=" * 60)

    # 使用父目录中的测试数据
    test_data_dir = Path(__file__).parent.parent / ".agentob" / "b844fa93" / "decoded_flows" / "analyzed"
    test_data_dir = test_data_dir.resolve()

    print(f"\n测试数据目录: {test_data_dir}")

    if not test_data_dir.exists():
        print(f"[失败] 测试数据目录未找到: {test_data_dir}")
        return False

    try:
        print("\n[测试] 创建可视化器...")
        visualizer = AgentVisualizer(str(test_data_dir))

        print("[测试] 生成 HTML 报告...")
        output_path = visualizer.generate()

        print(f"[通过] HTML 报告已生成: {output_path}")

        # 验证文件存在且有内容
        output_file = Path(output_path)
        if not output_file.exists():
            print(f"[失败] 输出文件未找到: {output_path}")
            return False

        file_size = output_file.stat().st_size
        print(f"[通过] 文件大小: {file_size} 字节")

        if file_size < 1000:
            print("[失败] 文件过小，可能不完整")
            return False

        print("\n[通过] 所有测试已通过！")
        print(f"\n在浏览器中打开报告:")
        print(f"  file:///{output_path}")

        return True

    except Exception as e:
        print(f"[失败] 测试出错: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_visualizer()
    sys.exit(0 if success else 1)
