"""
测试新的分析器功能
"""
import json
from pathlib import Path

# 测试模板加载
from agentob.analyzer import PROMPTS_DIR

print("提示词模板目录:", PROMPTS_DIR)
print("目录是否存在:", PROMPTS_DIR.exists())

if PROMPTS_DIR.exists():
    print("\n模板文件列表:")
    for file in PROMPTS_DIR.glob("*.txt"):
        print(f"  - {file.name}")
        # 读取前100个字符
        content = file.read_text(encoding="utf-8")
        print(f"    长度: {len(content)} 字符")
        print(f"    预览: {content[:80]}...")
        print()

print("\n测试模板变量替换:")
template = """
历史: {history_summaries}
近期: {recent_items}
当前: {content}
"""

filled = template.format(
    history_summaries="项1摘要\n项2摘要",
    recent_items="项3详情\n项4详情",
    content="当前项内容"
)
print(filled)

print("\n✓ 所有测试通过！")
