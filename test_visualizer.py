#!/usr/bin/env python3
"""
Test script for AgentVisualizer
Tests the visualization generation functionality
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from agentob.visualizer import AgentVisualizer


def test_visualizer():
    """Test visualizer with existing test data"""
    print("=" * 60)
    print("Testing AgentVisualizer")
    print("=" * 60)

    # Use the test data from parent directory
    test_data_dir = Path(__file__).parent.parent / ".agentob" / "b844fa93" / "decoded_flows" / "analyzed"
    test_data_dir = test_data_dir.resolve()

    print(f"\nTest data directory: {test_data_dir}")

    if not test_data_dir.exists():
        print(f"[FAIL] Test data directory not found: {test_data_dir}")
        return False

    try:
        print("\n[TEST] Creating visualizer...")
        visualizer = AgentVisualizer(str(test_data_dir))

        print("[TEST] Generating HTML report...")
        output_path = visualizer.generate()

        print(f"[OK] HTML report generated: {output_path}")

        # Verify the file exists and has content
        output_file = Path(output_path)
        if not output_file.exists():
            print(f"[FAIL] Output file not found: {output_path}")
            return False

        file_size = output_file.stat().st_size
        print(f"[OK] File size: {file_size} bytes")

        if file_size < 1000:
            print("[FAIL] File seems too small, might be incomplete")
            return False

        print("\n[OK] All tests passed!")
        print(f"\nOpen the report in your browser:")
        print(f"  file:///{output_path}")

        return True

    except Exception as e:
        print(f"[FAIL] Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_visualizer()
    sys.exit(0 if success else 1)
