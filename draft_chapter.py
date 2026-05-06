#!/usr/bin/env python3
"""
用 writer 模型起草单章。
用法：python draft_chapter.py 1
"""
import os
import re
import sys
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env")

WRITER_MODEL = os.environ.get("AUTONOVEL_WRITER_MODEL", "claude-sonnet-4-6")
CHAPTERS_DIR = BASE_DIR / "chapters"


def _novel_title():
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
            "你是一位起草中文奇幻 / 科幻长篇章节的文学小说作家。"
            "你按 voice.md 中规定的 POV / 时态写作（默认第三人称限知，过去时或零时态）。"
            "你**严格遵循**文风定义。你击中大纲中的每一个节拍。"
            "你绝不使用禁词表（成语堆砌、ABB 副词、心眸唇眉四件套等）里的词。"
            "你**展示**情绪，不**陈述**情绪。"
            "你的散文具体、感官、接地。比喻来自人物的经验。你**变化**句长。你**信任读者**。"
            "你写**完整**的一章 —— 不要截断，不要概述，不要跳过。"
        ),
        timeout=600,
        extra_beta=True,
    )


def load_file(path):
    try:
        return Path(path).read_text()
    except FileNotFoundError:
        return ""


def extract_chapter_outline(outline_text, chapter_num):
    """抽取某一章的大纲条目（兼容 ### Ch N: 与 ### 第 N 章: 两种锚）。"""
    pattern = (
        rf'###\s*(?:Ch|第)\s*{chapter_num}\s*(?:章)?[:：]?.*?'
        rf'(?=###\s*(?:Ch|第)\s*{chapter_num + 1}\s*(?:章)?[:：]?'
        rf'|## Foreshadowing|## 伏笔|$)'
    )
    match = re.search(pattern, outline_text, re.DOTALL)
    return match.group(0).strip() if match else "（未找到本章大纲条目）"


def extract_next_chapter_outline(outline_text, chapter_num):
    """抽取下一章大纲（仅前 10 行用于连贯）。"""
    next_entry = extract_chapter_outline(outline_text, chapter_num + 1)
    if next_entry == "（未找到本章大纲条目）":
        return "（末章）"
    lines = next_entry.split('\n')[:10]
    return '\n'.join(lines)


def main():
    chapter_num = int(sys.argv[1])

    # 加载所有上下文
    voice = load_file(BASE_DIR / "voice.md")
    world = load_file(BASE_DIR / "world.md")
    characters = load_file(BASE_DIR / "characters.md")
    outline = load_file(BASE_DIR / "outline.md")
    canon = load_file(BASE_DIR / "canon.md")

    # 章节相关上下文
    chapter_outline = extract_chapter_outline(outline, chapter_num)
    next_chapter = extract_next_chapter_outline(outline, chapter_num)

    # 上一章（如有）
    prev_path = CHAPTERS_DIR / f"ch_{chapter_num - 1:02d}.md"
    if prev_path.exists():
        prev_text = prev_path.read_text()
        prev_tail = prev_text[-2000:] if len(prev_text) > 2000 else prev_text
    else:
        prev_tail = "（首章 —— 无前章）"

    title = _novel_title()
    prompt = f"""请写《{title}》的第 {chapter_num} 章。

VOICE DEFINITION（**严格遵循**这份文风定义）：
{voice}

本章大纲（**击中每一个节拍**）：
{chapter_outline}

下一章大纲（用于连贯 —— 本章末尾要能流入下一章）：
{next_chapter}

上一章末尾（从这里继续）：
{prev_tail}

WORLD BIBLE（世界观参考）：
{world}

CHARACTER REGISTRY（人物口吻与行为参考）：
{characters}

写作指令：
1. 写**完整**的一章。**目标 ~3,200 字（中文字符）**。不要截断，不要概述。
2. 按 voice.md 规定的 POV / 时态（默认第三人称限知，锁在大纲指明的 POV 视角人物身上）。
3. **依序击中**大纲列出的所有数字节拍。
4. **植入**"Plants（铺垫）"中列出的所有伏笔元素。
5. 展示感官细节：人物听到 / 闻到 / 身体感受到什么。
6. 种子里的"代价"机制要落到**具体的身体感觉**（针扎在左眼后方，而不是模糊的"不适"）。
7. 对话遵循 characters.md 中定义的口吻。
8. 不使用 voice.md Part 1 禁词表里的词（璀璨 / 斑斓 / 鳞次栉比 / 美轮美奂 / 气势磅礴 等）。
9. 不使用中文 AI tells：不要"心头一颤"、"嘴角微微上扬"、"眸光流转"、"目光如炬"、"倒吸一口冷气"。
10. **变化句长**。短句制造冲击。长句构建。
11. 比喻应来自人物的**经验**：他 / 她做什么手艺、活在什么物质里，比喻就从那里来。
12. **信任读者**。不要解释场景的含义。让它落下来。
13. **场景开头**，不要用陈述铺垫。**收在一个瞬间**上，不要用总结结尾。

要避免的模式（前几章里多次出现，本章必须刹住）：
14. **不要**三联感官列表（X、Y、Z 三件并列）。合并两件、删一件、或重构。
15. **不要**用"他不曾 / 她没有 / 我未"类否定句两次以上。改为主动表达或直接删。
16. **不要**用"他想到 X 想到 Y 想到 Z"枚举式内心戏。代之以：把那个念头拆成断句、用一个身体动作、或一句对话。
17. **不要**用"X 那样地 Y"作比喻连接超过两次。换比喻结构或直接删比喻。
18. **不要**展示完之后再用叙述者重申。让场景自己说话。
19. **不要**把分节符号（`---`）当节奏拐杖。仅在**真正**的时间 / 地点跳跃时使用。**每章 ≤ 2 处**。
20. **刻意变化段长**。连续 3 段以上的段落不应长度相近。每章至少有一段是 1-2 句的短段，至少有一段是 6 句以上的长段。
21. **结尾要有变化**。不要用与前几章雷同的结构性收束（同一种"望着远方"、"沉默良久"、"轻轻关上门"）。找出**只属于这一章**的结尾。
22. **至少有一个意外瞬间** —— 某人说错话、情感节拍提前或推迟到达、某个不合常规模式的细节。可预测的优秀仍然是可预测的。
23. **场景重于概述**。本章至少 **70%** 在场景里（一刻一刻，有对话有动作），少用概述（叙述者压缩时间）。
24. **对话要像活人说话**，不像写出来的散文。人物偶尔会**结巴 / 打断 / 拖音 / 说点不太对的话**。一个 14 岁少年不会用工整的对仗发表见解。
25. **不要**让"心 / 眸 / 唇 / 眉"四件套出现 3 次以上（合计）。
26. **"X 道"对话标记每章 ≤ 2 处**。默认裸引号 + 动作。
27. **删 ABB 副词**：「深深地凝视」「紧紧地握住」「缓缓地走来」—— 让动词独立。
28. **删"忍不住 / 不由地 / 下意识地 / 不禁"** 这类拐杖词。

现在开始写。从开篇到结尾，全文。
"""

    print(f"正在起草第 {chapter_num} 章...", file=sys.stderr)
    result = call_writer(prompt)

    # 保存
    out_path = CHAPTERS_DIR / f"ch_{chapter_num:02d}.md"
    out_path.parent.mkdir(exist_ok=True)
    out_path.write_text(result)
    char_count = len(re.findall(r"[一-鿿]", result))
    print(f"已保存到 {out_path}", file=sys.stderr)
    print(f"字数（中文字符）：{char_count}", file=sys.stderr)
    print(result)


if __name__ == "__main__":
    main()
