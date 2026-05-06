"""
Test script for the AgentAnalyzer module.

This tests the failure scenario (no API key) as requested.
For success scenarios, you need to manually configure the API key in .env file.
"""

import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from agentob.analyzer import AgentAnalyzer


def test_analyzer_no_api_key():
    """Test analyzer without API key (failure scenario)"""
    print("=" * 60)
    print("Test 1: Analyzer without API key (should fail gracefully)")
    print("=" * 60)

    # Temporarily remove API key if it exists
    original_key = os.environ.pop("ANTHROPIC_API_KEY", None)

    try:
        # Test data is in parent directory
        analyzed_dir = Path("../.agentob/b844fa93/decoded_flows/analyzed").resolve()

        if not analyzed_dir.exists():
            print(f"Error: Test data directory not found: {analyzed_dir}")
            return False

        print(f"Using test data from: {analyzed_dir}")

        try:
            analyzer = AgentAnalyzer(str(analyzed_dir))
            print("ERROR: Should have raised ValueError for missing API key")
            return False
        except ValueError as e:
            print(f"[OK] Correctly raised ValueError: {e}")
            return True

    finally:
        # Restore original key
        if original_key:
            os.environ["ANTHROPIC_API_KEY"] = original_key


def test_analyzer_with_invalid_api_key():
    """Test analyzer with invalid API key (failure scenario)"""
    print("\n" + "=" * 60)
    print("Test 2: Analyzer with invalid API key (should fail gracefully)")
    print("=" * 60)

    analyzed_dir = Path("../.agentob/b844fa93/decoded_flows/analyzed").resolve()

    if not analyzed_dir.exists():
        print(f"Error: Test data directory not found: {analyzed_dir}")
        return False

    print(f"Using test data from: {analyzed_dir}")

    try:
        # Use invalid API key
        analyzer = AgentAnalyzer(str(analyzed_dir), api_key="invalid_key_12345")
        print("[OK] Analyzer initialized with invalid key")

        # Try to analyze (should fail but generate empty analyze.json)
        result = analyzer.analyze()

        # Check if analyze.json was created
        output_file = analyzed_dir / "analyze.json"
        if output_file.exists():
            print(f"[OK] analyze.json created at: {output_file}")

            # Check structure
            if "system_prompt_analysis" in result:
                print("[OK] Result has correct structure")
                print(f"  - system_prompt_analysis: {len(result['system_prompt_analysis'])} chars")
                print(f"  - tools_analysis: {len(result['tools_analysis'])} chars")
                print(f"  - call_analyses: {len(result['call_analyses'])} items")
                print(f"  - overall_analysis: {len(result['overall_analysis'])} chars")
                return True
            else:
                print("ERROR: Result missing expected fields")
                return False
        else:
            print("ERROR: analyze.json not created")
            return False

    except Exception as e:
        print(f"[OK] Exception handled gracefully: {e}")

        # Check if analyze.json was still created
        output_file = analyzed_dir / "analyze.json"
        if output_file.exists():
            print(f"[OK] analyze.json created despite error")
            return True
        else:
            print("ERROR: analyze.json not created")
            return False


def test_load_input_files():
    """Test loading input files"""
    print("\n" + "=" * 60)
    print("Test 3: Load input files")
    print("=" * 60)

    analyzed_dir = Path("../.agentob/b844fa93/decoded_flows/analyzed").resolve()

    if not analyzed_dir.exists():
        print(f"Error: Test data directory not found: {analyzed_dir}")
        return False

    # Check files exist
    prompts_file = analyzed_dir / "prompts.txt"
    tools_file = analyzed_dir / "tools.json"
    trace_file = analyzed_dir / "call_trace.json"

    print(f"Checking files in: {analyzed_dir}")
    print(f"  - prompts.txt: {'[OK]' if prompts_file.exists() else '[FAIL]'}")
    print(f"  - tools.json: {'[OK]' if tools_file.exists() else '[FAIL]'}")
    print(f"  - call_trace.json: {'[OK]' if trace_file.exists() else '[FAIL]'}")

    if not all([prompts_file.exists(), tools_file.exists(), trace_file.exists()]):
        print("ERROR: Some input files are missing")
        return False

    # Try to load with dummy API key
    try:
        analyzer = AgentAnalyzer(str(analyzed_dir), api_key="dummy_key")

        print(f"\n[OK] Loaded prompts: {len(analyzer.prompts)} chars")
        print(f"[OK] Loaded tools: {len(analyzer.tools)} tools")
        print(f"[OK] Loaded call trace: {len(analyzer.call_trace)} calls")

        # Show some details
        if analyzer.call_trace:
            first_call = analyzer.call_trace[0]
            print(f"\nFirst call details:")
            print(f"  - index: {first_call.get('index')}")
            print(f"  - model: {first_call.get('model')}")
            print(f"  - information_list items: {len(first_call.get('information_list', []))}")

        return True

    except Exception as e:
        print(f"ERROR: Failed to load files: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests"""
    print("\n" + "=" * 60)
    print("AgentAnalyzer Test Suite")
    print("=" * 60)

    results = []

    # Test 1: No API key
    results.append(("No API key", test_analyzer_no_api_key()))

    # Test 2: Invalid API key
    results.append(("Invalid API key", test_analyzer_with_invalid_api_key()))

    # Test 3: Load input files
    results.append(("Load input files", test_load_input_files()))

    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)

    for name, passed in results:
        status = "[PASS]" if passed else "[FAIL]"
        print(f"{status}: {name}")

    total = len(results)
    passed = sum(1 for _, p in results if p)
    print(f"\nTotal: {passed}/{total} tests passed")

    return all(p for _, p in results)


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
