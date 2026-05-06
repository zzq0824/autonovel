#!/usr/bin/env python3
"""
修订章节生成器。根据具体的修订 brief 重写某一章。
用法：python gen_revision.py <chapter_num> <brief_file>
"""
import os
import re
import sys
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env")

WRITER_MODEL = os.environ.get("AUTONOVEL_WRITER_MODEL", "claude-sonnet-4-6")


def _novel_title():
    """从 outline.md 第一行或 state.json 推断书名。失败则返回占位。"""
    outline = BASE_DIR / "outline.md"
    if outline.exists():
        first = outline.read_text().split("\n", 1)[0].lstrip("# ").strip()
        if first:
            return first
    return "本书"


def call_writer(prompt, max_tokens=16000):
    import llm_client
    return llm_client.call(
        prompt,
        model=WRITER_MODEL,
        max_tokens=max_tokens,
        temperature=0.8,
        system=(
            "你正在根据具体的修订 brief 重写一章中文小说。"
            "**严格按 brief 执行**。在做指定的结构性改动的同时，"
            "**保留**既有草稿的文风、世界观与人物特征。"
            "你写完**整章**。不要截断，不要概述。"
        ),
        timeout=600,
        extra_beta=True,
    )

def main():
    ch_num = int(sys.argv[1])
    brief_file = sys.argv[2]

    voice = (BASE_DIR / "voice.md").read_text()
    characters = (BASE_DIR / "characters.md").read_text()
    world = (BASE_DIR / "world.md").read_text()
    brief = Path(brief_file).read_text()

    # 加载相邻章节以保连续性
    prev_path = BASE_DIR / "chapters" / f"ch_{ch_num - 1:02d}.md"
    next_path = BASE_DIR / "chapters" / f"ch_{ch_num + 1:02d}.md"
    prev_tail = prev_path.read_text()[-2000:] if prev_path.exists() else "（首章）"
    next_head = next_path.read_text()[:1500] if next_path.exists() else "（末章）"

    # 加载旧版（如有）
    old_path = BASE_DIR / "chapters" / f"ch_{ch_num:02d}.md"
    old_text = old_path.read_text() if old_path.exists() else "（无既有草稿）"

    title = _novel_title()
    prompt = f"""请重写《{title}》第 {ch_num} 章。

REVISION BRIEF（严格按此执行）：
{brief}

VOICE DEFINITION（文风定义）：
{voice}

CHARACTER REGISTRY（人物名册）：
{characters}

WORLD BIBLE（世界观）：
{world}

PREVIOUS CHAPTER ENDING（保持连续性）：
{prev_tail}

NEXT CHAPTER OPENING（末尾要能流入下一章）：
{next_head}

THE EXISTING DRAFT（作为原料 —— 保留奏效部分，砍掉不奏效部分）：
{old_text}

反模式规则（中文）：
- **不要**使用三联感官列表（X、Y、Z）
- **不要**使用"他不曾 / 他没有"否定句两次以上
- **不要**用"他想到 X / 他想到 Y / 他想到 Z"这种枚举式内心戏
- **不要**用"X 那样地 Y"句式两次以上
- **不要**在叙述里使用"不是 X，而是 Y"这种修辞癖
- **不要**在已经展示过情绪后再用叙述者的语气重申
- **每章最多 2 个分节符号**（`---`）
- 至少有一个让读者**真正意外**的瞬间
- **70%+ 在场景里**（有对话有动作），少用概述
- 对话应当像活人说话，不像写出来的散文
- "心 / 眸 / 唇 / 眉"四件套全章合计 ≤ 3 次
- "X 道"对话标记每章 ≤ 2 处
- 不堆砌成语（璀璨 / 斑斓 / 鳞次栉比 / 美轮美奂 / 气势磅礴 等）
- 删 ABB 副词（深深地 / 紧紧地 / 缓缓地 + 动词）

现在写出**完整**的修订章。"""

    print(f"正在重写第 {ch_num} 章...", file=sys.stderr)
    result = call_writer(prompt)

    out_path = BASE_DIR / "chapters" / f"ch_{ch_num:02d}.md"
    out_path.write_text(result)
    char_count = len(re.findall(r"[一-鿿]", result))
    print(f"已保存到 {out_path}", file=sys.stderr)
    print(f"字数（中文字符）：{char_count}", file=sys.stderr)

if __name__ == "__main__":
    main()
