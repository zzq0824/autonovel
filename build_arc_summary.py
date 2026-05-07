#!/usr/bin/env python3
"""
为全本评估构建一份"压缩弧线摘要"。
每章：开篇 150 字、结尾 150 字、加上若干对话。
让读者评审团能在不读完整 80k 字的情况下评估"弧"。
"""
import os
import re
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env")

WRITER_MODEL = os.environ.get("AUTONOVEL_WRITER_MODEL", "claude-sonnet-4-6")
CHAPTERS_DIR = BASE_DIR / "chapters"


def call_writer(prompt, max_tokens=4000):
    import llm_client
    return llm_client.call(
        prompt,
        model=WRITER_MODEL,
        max_tokens=max_tokens,
        temperature=0.1,
        system="你精确地概括小说章节。**只**陈述发生了什么 / 改变了什么 / 留下什么问题。不评价，不夸赞。仅事件与转折。",
        timeout=120,
    )


def extract_key_passages(text):
    """取章节的开场、收尾、几段对话。"""
    # 中文按字符切，避免 split 把整段当一个 token
    char_only = re.sub(r"\s+", "", text)
    opening_chars = char_only[:150]
    closing_chars = char_only[-150:]

    # 抽取对话（中文常用 "" 或 「」 或 『』；同时兼容英文 "..."）
    dialogue = re.findall(
        r'(?:["""]([^"""\n]{10,})["""])'
        r'|(?:「([^」\n]{10,})」)'
        r'|(?:『([^』\n]{10,})』)',
        text,
    )
    # 拍平
    flat = [next(filter(None, t)) for t in dialogue if any(t)]
    flat.sort(key=len, reverse=True)
    return opening_chars, closing_chars, flat[:3]


def _all_chapter_numbers():
    nums = []
    for p in sorted(CHAPTERS_DIR.glob("ch_*.md")):
        m = re.match(r"ch_(\d+)\.md", p.name)
        if m:
            nums.append(int(m.group(1)))
    return nums


def _novel_title():
    outline = BASE_DIR / "outline.md"
    if outline.exists():
        first = outline.read_text().split("\n", 1)[0].lstrip("# ").strip()
        if first:
            return first
    return "未命名小说"


def _premise_block():
    """从 seed.txt 第一段（直到第一个空行）拿故事的"前提"，避免硬编码。"""
    seed_path = BASE_DIR / "seed.txt"
    if not seed_path.exists():
        return "（未找到 seed.txt，请人工填写本书的前提概要。）"
    seed = seed_path.read_text().strip()
    # 取首段（首个空行前）
    first_block = seed.split("\n\n", 1)[0].strip()
    return first_block or seed[:600]


def main():
    summaries = []
    chapters = _all_chapter_numbers()
    if not chapters:
        print("错误：chapters/ 目录下没有 ch_*.md 文件")
        return

    for ch in chapters:
        path = CHAPTERS_DIR / f"ch_{ch:02d}.md"
        text = path.read_text()
        char_count = len(re.findall(r"[一-鿿]", text))
        opening, closing, dialogue = extract_key_passages(text)

        # 让模型给一份 ~100 字摘要
        summary = call_writer(
            f"用恰好 3 句话概括这一章。说明：发生了什么 / 改变了什么 / 留下什么问题。\n\n第 {ch} 章：\n{text}",
            max_tokens=300
        )

        entry = f"""### 第 {ch} 章（约 {char_count} 字）
**摘要：** {summary}

**开篇：** {opening}……

**结尾：** ……{closing}

**关键对话：**
"""
        for d in dialogue:
            entry += f'> "{d}"\n\n'

        summaries.append(entry)
        print(f"第 {ch} 章：已概括（{char_count} 字）")

    # 总字数
    total_chars = 0
    for c in chapters:
        text = (CHAPTERS_DIR / f"ch_{c:02d}.md").read_text()
        total_chars += len(re.findall(r"[一-鿿]", text))

    title = _novel_title()
    premise = _premise_block()

    full = f"""# 《{title}》
## 全弧线摘要（供读者评审团）

本文档包含全部 {len(chapters)} 章的章节摘要、首尾段落、关键对话。
全书约 **{total_chars:,} 字**。

前提（PREMISE，来自 seed.txt 首段）：
{premise}

---

"""
    full += '\n---\n\n'.join(summaries)

    out_path = BASE_DIR / "arc_summary.md"
    out_path.write_text(full)
    out_chars = len(re.findall(r"[一-鿿]", full))
    print(f"\n已保存到 {out_path}（约 {out_chars:,} 字）")


if __name__ == "__main__":
    main()
