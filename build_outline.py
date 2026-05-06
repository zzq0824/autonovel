#!/usr/bin/env python3
"""
从实际章节重建 outline.md。
读取每一章，让 LLM 生成结构化摘要，再装配成"反映成稿后小说"的大纲。
"""
import os
import sys
import json
import re
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env")

JUDGE_MODEL = os.environ.get("AUTONOVEL_JUDGE_MODEL", "claude-sonnet-4-6")
CHAPTERS_DIR = BASE_DIR / "chapters"


def call_model(prompt, max_tokens=1500):
    import llm_client
    text = llm_client.call(
        prompt,
        model=JUDGE_MODEL,
        max_tokens=max_tokens,
        temperature=0.1,
        system=(
            "你为中文小说章节生成结构化的大纲条目。"
            "精确说明**发生了什么 / 改变了什么 / 哪些线索被植入或回收**。"
            "你只输出合法 JSON。JSON 的 key 保持英文，value 用中文。"
        ),
        timeout=120,
    )
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r'^```\w*\n?', '', text)
        text = re.sub(r'\n?```$', '', text)
    return json.loads(text)


def _novel_title():
    """从已有 outline.md 第一行 / state.json 推断书名。"""
    outline_path = BASE_DIR / "outline.md"
    if outline_path.exists():
        first = outline_path.read_text().split("\n", 1)[0].lstrip("# ").strip()
        if first:
            return first
    state_path = BASE_DIR / "state.json"
    if state_path.exists():
        try:
            state = json.loads(state_path.read_text())
            if state.get("title"):
                return state["title"]
        except Exception:
            pass
    return "未命名小说"


def _all_chapter_numbers():
    nums = []
    for p in sorted(CHAPTERS_DIR.glob("ch_*.md")):
        m = re.match(r"ch_(\d+)\.md", p.name)
        if m:
            nums.append(int(m.group(1)))
    return nums


def main():
    # 用人物文档做上下文
    characters_path = BASE_DIR / "characters.md"
    characters = characters_path.read_text()[:3000] if characters_path.exists() else ""

    entries = []
    chapters = _all_chapter_numbers()
    if not chapters:
        print("错误：chapters/ 目录下没有 ch_*.md 文件", file=sys.stderr)
        sys.exit(1)

    for ch in chapters:
        path = CHAPTERS_DIR / f"ch_{ch:02d}.md"
        text = path.read_text()
        char_count = len(re.findall(r"[一-鿿]", text))

        title_line = text.strip().split('\n')[0].lstrip('# ').strip()

        prompt = f"""分析这一章并产出结构化大纲条目。

第 {ch} 章："{title_line}"（约 {char_count} 字）

{text}

返回 JSON，包含以下字段（**key 保持英文**）：
- "title"：章节标题（string）
- "location"：主要场景（string）
- "characters"：出场人物（list of strings）
- "summary"：2-3 句概述本章发生的事（string）
- "beats"：按顺序排列的 3-5 个关键节拍（list of strings）
- "try_fail"：试-错循环类型："yes-but" / "no-and" / "yes-and" / "no-but"（string）
- "plants"：本章**植入**的伏笔线索（list of strings）
- "harvests"：本章**回收**的伏笔线索（list of strings）
- "emotional_arc"：用一句话描述情感弧（string）
- "chapter_question"：章末留下的问题（string）

只输出 JSON，不要其他内容。"""

        data = call_model(prompt)
        data["num"] = ch
        data["chars"] = char_count
        entries.append(data)
        print(f"  {ch:2d}. {title_line}（约 {char_count} 字）")

    # 装配新大纲
    title = _novel_title()
    total_chars = sum(e["chars"] for e in entries)

    lines = []
    lines.append(f"# 《{title}》")
    lines.append("## 章节大纲（依据实际成稿章节重建）")
    lines.append("")
    lines.append(f"**共 {len(entries)} 章，约 {total_chars:,} 字**")
    lines.append("")
    lines.append("---")
    lines.append("")

    for e in entries:
        lines.append(f"### Ch {e['num']}: {e['title']}")
        lines.append(f"**约 {e['chars']} 字** | **场景：** {e.get('location', '未注明')}")
        lines.append(f"- **人物：** {', '.join(e.get('characters', []))}")
        lines.append(f"- **试-错循环：** {e.get('try_fail', '未注明')}")
        lines.append(f"- **情感弧：** {e.get('emotional_arc', '未注明')}")
        lines.append("")
        lines.append(f"**摘要：** {e.get('summary', '未注明')}")
        lines.append("")
        lines.append("**节拍：**")
        for b in e.get("beats", []):
            lines.append(f"1. {b}")
        lines.append("")
        if e.get("plants"):
            lines.append("**铺垫：**")
            for p in e["plants"]:
                lines.append(f"- {p}")
            lines.append("")
        if e.get("harvests"):
            lines.append("**回收：**")
            for h in e["harvests"]:
                lines.append(f"- {h}")
            lines.append("")
        lines.append(f"**章末问题：** {e.get('chapter_question', '未注明')}")
        lines.append("")
        lines.append("---")
        lines.append("")

    # 伏笔账本
    lines.append("## 伏笔账本（FORESHADOWING LEDGER）")
    lines.append("")
    lines.append("| 线索 | 铺垫 | 回收 |")
    lines.append("|------|------|------|")

    all_plants = {}
    all_harvests = {}
    for e in entries:
        for p in e.get("plants", []):
            key = p[:60]
            if key not in all_plants:
                all_plants[key] = []
            all_plants[key].append(e["num"])
        for h in e.get("harvests", []):
            key = h[:60]
            if key not in all_harvests:
                all_harvests[key] = []
            all_harvests[key].append(e["num"])

    all_threads = set(list(all_plants.keys()) + list(all_harvests.keys()))
    for thread in sorted(all_threads):
        planted = ", ".join(f"第 {n} 章" for n in all_plants.get(thread, []))
        harvested = ", ".join(f"第 {n} 章" for n in all_harvests.get(thread, []))
        lines.append(f"| {thread} | {planted} | {harvested} |")

    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(f"*大纲依据成稿重建，{datetime.now().strftime('%Y-%m-%d')}。*")

    out = '\n'.join(lines)
    (BASE_DIR / "outline.md").write_text(out)
    print(f"\n已保存 outline.md（约 {len(re.findall(r'[一-鿿]', out)):,} 字）")


if __name__ == "__main__":
    main()
