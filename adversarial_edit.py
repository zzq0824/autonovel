#!/usr/bin/env python3
"""
对抗式编辑：让 judge 模型从每章里"砍 500 字"。
被砍掉的部分就揭示出最弱处。这份切口清单**本身**就是修订计划。

用法：python adversarial_edit.py 1        # 单章
       python adversarial_edit.py all      # 所有章
"""
import os
import sys
import json
import re
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env")

JUDGE_MODEL = os.environ.get("AUTONOVEL_JUDGE_MODEL", "claude-opus-4-6")
CHAPTERS_DIR = BASE_DIR / "chapters"
EDIT_LOG_DIR = BASE_DIR / "edit_logs"
EDIT_LOG_DIR.mkdir(exist_ok=True)

def call_judge(prompt, max_tokens=8000):
    import llm_client
    return llm_client.call(
        prompt,
        model=JUDGE_MODEL,
        max_tokens=max_tokens,
        temperature=0.3,
        system=(
            "你是一位**冷酷**的文学编辑。你从散文里砍掉肥肉。"
            "对于「还算可以」的句子你**毫无怜悯** —— 如果一句话挣不到自己的位置，就要走。"
            "你**严格引用**原文。绝不编造，绝不改写式引用。"
            "你只用合法 JSON 回复。JSON 的 key 保持英文，value 用中文。"
        ),
        timeout=300,
    )

def parse_json(text):
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r'^```\w*\n?', '', text)
        text = re.sub(r'\n?```$', '', text)
    start = text.find('{')
    if start == -1:
        start = text.find('[')
    if start == -1:
        raise ValueError("No JSON found")
    # Try direct parse first
    try:
        return json.loads(text[start:], strict=False)
    except json.JSONDecodeError:
        # Find matching brace
        depth = 0
        in_string = False
        escape = False
        open_char = text[start]
        close_char = '}' if open_char == '{' else ']'
        for i in range(start, len(text)):
            c = text[i]
            if escape:
                escape = False
                continue
            if c == '\\' and in_string:
                escape = True
                continue
            if c == '"' and not escape:
                in_string = not in_string
                continue
            if in_string:
                continue
            if c == open_char:
                depth += 1
            elif c == close_char:
                depth -= 1
                if depth == 0:
                    return json.loads(text[start:i+1], strict=False)
        return json.loads(text[start:], strict=False)

EDIT_PROMPT = """你正在编辑一章中文小说。你的任务：精确指出要**砍掉**或**重写**什么，让这章更紧、更锐、更**活**。

THE CHAPTER（约 {word_count} 字）：
{chapter_text}

YOUR TASK：
1. 找出 10-20 处具体段落，应当被**砍掉**或**重写**。
   每一处都要：
   - **逐字引用**原文（至少 10 字，避免歧义）
   - 解释**为什么**它弱
   - 分类（见下）

2. 分类（每条切口必须打上下列标签之一）：
   - FAT（肥肉）：什么也没加，删了也没损失
   - REDUNDANT（重复）：重申了前一句 / 前一场已经展示过的事
   - OVER-EXPLAIN（过度解释）：场景已展示，叙述者还在解释
   - GENERIC（泛化）：可以出现在任何小说里，与本书的世界 / 人物无关
   - TELL（陈述）：直接命名情绪 / 状态，而非展示
   - STRUCTURAL（结构性）：影响节奏 / 韵律的整段或区块

3. 对于"REWRITE"（重写）类候选（而非"CUT"切除），给出具体的改写文。

4. 估计**总共可被砍掉**多少字，且本章不丢失任何**必需**之物。

请用 JSON 回复（**JSON 的 key 必须保持英文，原样照抄；只在 value 字段里写中文**）：
{{
  "cuts": [
    {{
      "quote": "原文中至少 10 字的精确引用",
      "type": "FAT|REDUNDANT|OVER-EXPLAIN|GENERIC|TELL|STRUCTURAL",
      "reason": "为什么它该走",
      "action": "CUT 或 REWRITE",
      "rewrite": "若 action 为 REWRITE，给出替换文；否则 null"
    }}
  ],
  "total_cuttable_words": N,
  "tightest_passage": "本章最紧的 2-3 句 —— 你绝不会碰的那些",
  "loosest_passage": "本章最松的 2-3 句 —— 最需要工作的那些",
  "overall_fat_percentage": N,
  "one_sentence_verdict": "用一句话说出本章哪里出色、哪里拖累"
}}
"""

def edit_chapter(ch_num):
    ch_path = CHAPTERS_DIR / f"ch_{ch_num:02d}.md"
    text = ch_path.read_text()
    char_count = len(re.findall(r"[一-鿿]", text))

    prompt = EDIT_PROMPT.format(chapter_text=text, word_count=char_count)
    raw = call_judge(prompt)
    result = parse_json(raw)

    # 保存日志
    log_path = EDIT_LOG_DIR / f"ch{ch_num:02d}_cuts.json"
    with open(log_path, "w") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    return result, char_count


def _all_chapter_numbers():
    """从 chapters/ 目录扫出已存在的章节编号，避免硬编码 24 章。"""
    nums = []
    for p in sorted(CHAPTERS_DIR.glob("ch_*.md")):
        m = re.match(r"ch_(\d+)\.md", p.name)
        if m:
            nums.append(int(m.group(1)))
    return nums


def main():
    if len(sys.argv) < 2:
        print("用法：python adversarial_edit.py <chapter_num|all>")
        sys.exit(1)

    if sys.argv[1] == "all":
        chapters = _all_chapter_numbers()
        if not chapters:
            print("错误：chapters/ 目录下没有找到任何 ch_*.md 文件")
            sys.exit(1)
    else:
        chapters = [int(sys.argv[1])]

    for ch in chapters:
        print(f"\n{'='*50}")
        print(f"编辑第 {ch} 章")
        print(f"{'='*50}")

        try:
            result, wc = edit_chapter(ch)
        except Exception as e:
            print(f"  错误：{e}")
            continue

        cuts = result.get("cuts", [])
        cuttable = result.get("total_cuttable_words", 0)
        fat_pct = result.get("overall_fat_percentage", 0)
        verdict = result.get("one_sentence_verdict", "")

        # 按类型计数
        type_counts = {}
        for c in cuts:
            t = c.get("type", "?")
            type_counts[t] = type_counts.get(t, 0) + 1

        print(f"  字数：{wc}")
        print(f"  发现切口：{len(cuts)}")
        print(f"  可砍字数：~{cuttable}（脂肪比例 {fat_pct}%）")
        print(f"  按类型：{type_counts}")
        print(f"  评语：{verdict}")
        print(f"  最紧：{result.get('tightest_passage', '')[:100]}...")
        print(f"  最松：{result.get('loosest_passage', '')[:100]}...")

if __name__ == "__main__":
    main()
