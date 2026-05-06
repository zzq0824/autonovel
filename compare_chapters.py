#!/usr/bin/env python3
"""
对比排序：让 judge 模型两两对决章节。
裁判挑出胜者，并引用决定性瞬间。瑞士轮 / 循环赛产出真实排名。

用法：python compare_chapters.py          # 全本锦标赛
       python compare_chapters.py 1 10     # 单场对决
"""
import os
import sys
import json
import re
import random
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env")

JUDGE_MODEL = os.environ.get("AUTONOVEL_JUDGE_MODEL", "claude-opus-4-6")
CHAPTERS_DIR = BASE_DIR / "chapters"

def call_judge(prompt, max_tokens=4000):
    import llm_client
    return llm_client.call(
        prompt,
        model=JUDGE_MODEL,
        max_tokens=max_tokens,
        temperature=0.2,
        system=(
            "你是一位对比同一部小说两章的文学编辑。"
            "你**必须**挑出更好的一章。**不允许**判平。"
            "你引用具体段落以证明选择。"
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
        raise ValueError("No JSON found")
    try:
        return json.loads(text[start:], strict=False)
    except json.JSONDecodeError:
        depth = 0
        in_string = False
        escape = False
        for i in range(start, len(text)):
            c = text[i]
            if escape: escape = False; continue
            if c == '\\' and in_string: escape = True; continue
            if c == '"' and not escape: in_string = not in_string; continue
            if in_string: continue
            if c == '{': depth += 1
            elif c == '}':
                depth -= 1
                if depth == 0:
                    return json.loads(text[start:i+1], strict=False)
        return json.loads(text[start:], strict=False)

COMPARE_PROMPT = """对比同一部中文小说的这两章。两者都是初稿。挑出**更好**的一章。**必须**挑出胜者 —— 不允许平局。

CHAPTER A（第 {ch_a} 章）：
{text_a}

CHAPTER B（第 {ch_b} 章）：
{text_b}

对比维度：
- 哪一章散文更**锐利**（更具体，更少泛化）？
- 哪一章对话更好（像活人说话，不像写出来的散文）？
- 哪一章制造了更**真实**的张力或惊讶？
- 哪一章更**信任读者**（更少过度解释）？
- 哪一章 AI 写作模式更少（成语堆 / ABB 副词病 / 心眸唇眉 / "X 道"滥用 / 翻译腔）？

你**必须**挑出一个。如果两者相近，挑出含**单个最佳瞬间**的那一章 —— 那种你**希望自己写出来**的句子。

请用 JSON 回复（**JSON 的 key 必须保持英文，原样照抄；只在 value 字段里写中文**）：
{{
  "winner": "A" 或 "B",
  "winner_chapter": N,
  "margin": "clear / slight / razor-thin（明显 / 微弱 / 毫厘之间）",
  "decisive_moment": "引用决定性段落 —— 从**胜者**章节中",
  "winner_strength": "胜者做了败者没做的事",
  "loser_weakness": "败者的具体拖累",
  "best_sentence_a": "A 章节最好的一句",
  "best_sentence_b": "B 章节最好的一句"
}}
"""

def compare(ch_a, ch_b):
    text_a = (CHAPTERS_DIR / f"ch_{ch_a:02d}.md").read_text()
    text_b = (CHAPTERS_DIR / f"ch_{ch_b:02d}.md").read_text()

    # 截到 ~5000 中文字符以装下 context（中文比英文紧约 1.5x，故阈值放宽）
    if len(text_a) > 5000:
        text_a = text_a[:5000] + "\n[已截断]"
    if len(text_b) > 5000:
        text_b = text_b[:5000] + "\n[已截断]"
    
    prompt = COMPARE_PROMPT.format(
        ch_a=ch_a, ch_b=ch_b,
        text_a=text_a, text_b=text_b
    )
    raw = call_judge(prompt)
    result = parse_json(raw)
    result["ch_a"] = ch_a
    result["ch_b"] = ch_b
    return result

def run_tournament(chapters):
    """Swiss-style tournament: pair by similar Elo, run enough rounds to rank."""
    # Initialize Elo ratings
    elo = {ch: 1500 for ch in chapters}
    K = 32
    matchups = []
    
    # Run 3-4 rounds of Swiss pairings
    n_rounds = 4
    for round_num in range(n_rounds):
        # Sort by Elo, pair adjacent
        ranked = sorted(chapters, key=lambda c: elo[c], reverse=True)
        pairs = []
        used = set()
        for i in range(0, len(ranked) - 1, 2):
            a, b = ranked[i], ranked[i+1]
            if (a, b) not in used and (b, a) not in used:
                pairs.append((a, b))
                used.add((a, b))
        
        print(f"\n--- 第 {round_num + 1} 轮（{len(pairs)} 场对决） ---")
        for ch_a, ch_b in pairs:
            try:
                result = compare(ch_a, ch_b)
                winner = result.get("winner_chapter", result.get("winner"))
                margin = result.get("margin", "?")

                # 处理 "A"/"B" 与章节编号
                if winner == "A":
                    winner = ch_a
                elif winner == "B":
                    winner = ch_b
                else:
                    winner = int(winner)

                # 更新 Elo
                exp_a = 1 / (1 + 10 ** ((elo[ch_b] - elo[ch_a]) / 400))
                score_a = 1.0 if winner == ch_a else 0.0
                elo[ch_a] += K * (score_a - exp_a)
                elo[ch_b] += K * ((1 - score_a) - (1 - exp_a))

                result["winner_resolved"] = winner
                matchups.append(result)

                print(f"  第 {ch_a} 章 vs 第 {ch_b} 章：胜者第 {winner} 章 ({margin})")

            except Exception as e:
                print(f"  第 {ch_a} 章 vs 第 {ch_b} 章：错误（{e}）")
    
    # Final ranking
    ranking = sorted(chapters, key=lambda c: elo[c], reverse=True)
    
    return ranking, elo, matchups

def _all_chapter_numbers():
    """从 chapters/ 扫出已存在的章节编号。"""
    nums = []
    for p in sorted(CHAPTERS_DIR.glob("ch_*.md")):
        m = re.match(r"ch_(\d+)\.md", p.name)
        if m:
            nums.append(int(m.group(1)))
    return nums


def main():
    if len(sys.argv) == 3:
        # 单场对决
        ch_a, ch_b = int(sys.argv[1]), int(sys.argv[2])
        result = compare(ch_a, ch_b)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        # 全本锦标赛
        chapters = _all_chapter_numbers()
        if not chapters:
            print("错误：chapters/ 目录下没有任何 ch_*.md 文件")
            sys.exit(1)
        ranking, elo, matchups = run_tournament(chapters)

        print(f"\n{'='*50}")
        print("最终排名")
        print(f"{'='*50}")
        for i, ch in enumerate(ranking):
            print(f"  {i+1:2d}. 第 {ch:2d} 章  (Elo: {elo[ch]:.0f})")

        # 保存结果
        results = {
            "ranking": ranking,
            "elo": {str(k): round(v) for k, v in elo.items()},
            "matchups": matchups,
            "timestamp": datetime.now().isoformat()
        }
        out_path = BASE_DIR / "edit_logs" / "tournament_results.json"
        out_path.parent.mkdir(exist_ok=True)
        with open(out_path, "w") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        print(f"\n已保存到 {out_path}")

if __name__ == "__main__":
    main()
