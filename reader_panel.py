#!/usr/bin/env python3
"""
4 人读者评审团：用于全弧 / 全本评估。
每位读者一个不同 persona，评估**整本小说**而非单章。
读者间的**分歧**即编辑决策的着力点。

用法：python reader_panel.py
"""
import os
import sys
import json
import re
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env")

JUDGE_MODEL = os.environ.get("AUTONOVEL_JUDGE_MODEL", "claude-opus-4-6")

READERS = {
    "editor": {
        "name": "编辑",
        "system": (
            "你是某主流文学出版社（人民文学 / 十月文艺 / 磨铁 / 果麦类）的资深小说编辑，"
            "编过两百多部长篇。你关心散文质感、潜台词、句子层面的工艺，以及文风是否一贯且**当得起**。"
            "你能立刻看出叙述者在过度解释、对话写得像散文而不像活人话、比喻是借来的而非长出来的。"
            "你不残忍，但你精准。你见过太多合格的散文，因此分得清"
            "**好**与**活**之间的差。"
            "你只用合法 JSON 回复。JSON 的 key 保持英文，value 用中文。"
        ),
    },
    "genre_reader": {
        "name": "类型读者",
        "system": (
            "你是一个一年读 50+ 部小说的资深奇幻 / 科幻读者。你关心节奏、悬念、"
            "世界观回报、以及是否让人想继续翻页。漂亮但**不向前走**的散文会让你无聊。"
            "你能看出查案章节卡顿、张力平台化、作者比起讲故事更迷恋自己的世界。"
            "你常读的书涵盖刘慈欣、韩松、陈楸帆、双翅目的硬科幻；"
            "金庸、古龙、温瑞安的武侠；阿来、迟子建、莫言的乡土魔幻；"
            "以及 Le Guin、Jemisin 等英文奇幻经典。"
            "你对喜欢的作品慷慨，对让你无聊的直白。"
            "你只用合法 JSON 回复。JSON 的 key 保持英文，value 用中文。"
        ),
    },
    "writer": {
        "name": "作家",
        "system": (
            "你是一位出版过 5 部长篇小说的华语作家，曾入围华语科幻星云奖，"
            "也曾上过豆瓣年度小说榜。你以**手艺人**的眼光读书。"
            "你关注结构：节拍落在哪里、伏笔是否兑现、人物弧线是否完成。"
            "你能区分技巧**显形**还是**消失在故事里**。"
            "你给的最高赞美是「我读到忘了自己在读」。最坏的评语是「我能看见大纲」。"
            "你在意一部小说**意图**与**完成度**之间的差距。"
            "你只用合法 JSON 回复。JSON 的 key 保持英文，value 用中文。"
        ),
    },
    "first_reader": {
        "name": "普通读者",
        "system": (
            "你是一位有思考力的普通读者。不是作家，不是编辑，不是类型迷。"
            "你为体验而读。你知道你**感觉**到了什么，但不一定知道为什么。"
            "你能察觉自己被打动、被无聊、被困惑、想立刻找人推荐。"
            "你不用工艺术语。你会说「这一段我没什么感觉」或「这一场之后我得停下来缓一缓」。"
            "你的反馈是情绪的、诚实的，不是分析的。"
            "你只用合法 JSON 回复。JSON 的 key 保持英文，value 用中文。"
        ),
    },
}

READER_PROMPT = """你刚刚以摘要形式读完了一部完整的中文奇幻小说。
摘要包含逐章事件、各章首尾段落，以及关键对话。
全书共 **{total_chapters} 章 / 约 {novel_word_count} 字**。

{arc_summary}

现在请回答关于**整本小说**的问题。具体一些。能引用就引用。指明章节号。

请用 JSON 回复（**JSON 的 key 必须保持英文，原样照抄；只在 value 字段里写中文**）：
{{
  "momentum_loss": "故事在哪里失去推力？指明具体章节与拖累原因。如果从未失去，说明为什么。",

  "earned_ending": "结局是否被前面所有内容**应得**？高潮章（约第 {climax_chapter} 章）的关键选择**落地**了吗？最后一章（第 {final_chapter} 章）的终场画面是否与第 1 章互镜并令人满意？哪些地方感觉**未被挣得**？",

  "cut_candidate": "如果这部小说必须减掉 10%（约 {cut_target} 字），你最先动哪一章 / 哪一节？为什么？会失去什么？",

  "missing_scene": "是否存在小说**需要**但没写的场景？某场该发生的对话、某个被铺垫但未交付的瞬间、某个值得更多戏份的人物？请具体指明它该插在哪里。",

  "thinnest_character": "哪个人物到结尾仍显单薄？你想多了解谁？谁可以删去而不让小说受损？",

  "best_scene": "全书唯一最好的场景是哪一场？引用打动你的那个瞬间。它为什么有效？",

  "worst_scene": "全书唯一最弱的场景是哪一场？哪里出错？怎么修？",

  "would_recommend": "你会推荐这本书吗？给谁？用一句话说说它。",

  "haunts_you": "读完之后，是否有一句话或一个瞬间留在你脑海里？引用它。",

  "next_book": "你会读这位作者的下一本吗？为什么 / 为什么不？"
}}
"""


def _read_state():
    """从 state.json 读出当前小说参数；缺失时给合理默认。"""
    try:
        state = json.loads((BASE_DIR / "state.json").read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        state = {}
    return state


def _novel_metadata():
    """汇总评审 prompt 里要用的小说元数据：章数、字数、关键章节号等。"""
    state = _read_state()

    chapters_dir = BASE_DIR / "chapters"
    chapter_files = sorted(chapters_dir.glob("ch_*.md")) if chapters_dir.exists() else []
    total_chapters = state.get("chapters_total") or len(chapter_files) or "若干"

    # 字数：以中文字符为主，混合时近似
    novel_word_count = "未知"
    if chapter_files:
        total_chars = 0
        for f in chapter_files:
            text = f.read_text()
            total_chars += len(re.findall(r"[一-鿿]", text))
        if total_chars:
            novel_word_count = f"{total_chars:,}"

    # 高潮章 = 第 ~75-90% 章；终章 = 最后一章
    if isinstance(total_chapters, int) and total_chapters > 0:
        climax_chapter = max(1, int(total_chapters * 0.85))
        final_chapter = total_chapters
        cut_target = f"{int((total_chars if isinstance(novel_word_count, str) and novel_word_count != '未知' else 70000) * 0.1):,}" \
            if novel_word_count != "未知" else "约 7,000"
    else:
        climax_chapter = "倒数第二"
        final_chapter = "末"
        cut_target = "约 7,000"

    return {
        "total_chapters": total_chapters,
        "novel_word_count": novel_word_count,
        "climax_chapter": climax_chapter,
        "final_chapter": final_chapter,
        "cut_target": cut_target,
    }


def call_reader(reader_key, arc_summary):
    import llm_client
    reader = READERS[reader_key]
    meta = _novel_metadata()
    raw = llm_client.call(
        READER_PROMPT.format(arc_summary=arc_summary, **meta),
        model=JUDGE_MODEL,
        max_tokens=4000,
        temperature=0.7,  # 高温度保留个性
        system=reader["system"],
        timeout=300,
    )

    # 解析 JSON
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r'^```\w*\n?', '', raw)
        raw = re.sub(r'\n?```$', '', raw)
    start = raw.find('{')
    if start >= 0:
        depth = 0
        in_string = False
        escape = False
        for i in range(start, len(raw)):
            c = raw[i]
            if escape: escape = False; continue
            if c == '\\' and in_string: escape = True; continue
            if c == '"' and not escape: in_string = not in_string; continue
            if in_string: continue
            if c == '{': depth += 1
            elif c == '}':
                depth -= 1
                if depth == 0:
                    return json.loads(raw[start:i+1], strict=False)
    return json.loads(raw, strict=False)


def find_disagreements(results):
    """找读者意见分歧 —— 这才是编辑决策真正发生的地方。"""
    disagreements = []

    for question in ["momentum_loss", "cut_candidate", "thinnest_character", "worst_scene"]:
        answers = {k: v.get(question, "") for k, v in results.items()}
        # 抽取被提到的章节号（兼容 "Ch 5" / "Chapter 5" / "第 5 章" / "第五章"）
        chapters_mentioned = {}
        zh_to_arabic = str.maketrans("零一二三四五六七八九十", "0123456789十")
        for reader, answer in answers.items():
            chs = set()
            for m in re.finditer(r'(?:Ch(?:apter)?|第)\s*(\d+|[一二三四五六七八九十]+)\s*(?:章)?',
                                 answer, re.IGNORECASE):
                num = m.group(1).translate(zh_to_arabic)
                if num.isdigit():
                    chs.add(num)
                elif num == "十":
                    chs.add("10")
            chapters_mentioned[reader] = chs

        # 找仅部分读者标记的章节
        all_chs = set()
        for chs in chapters_mentioned.values():
            all_chs.update(chs)

        for ch in all_chs:
            flagged_by = [r for r, chs in chapters_mentioned.items() if ch in chs]
            not_flagged = [r for r, chs in chapters_mentioned.items() if ch not in chs]
            if flagged_by and not_flagged:
                disagreements.append({
                    "question": question,
                    "chapter": int(ch),
                    "flagged_by": flagged_by,
                    "not_flagged": not_flagged,
                    "details": {r: answers[r][:200] for r in flagged_by}
                })

    return disagreements


def main():
    arc_summary = (BASE_DIR / "arc_summary.md").read_text()

    results = {}
    for reader_key, reader_info in READERS.items():
        print(f"\n{'='*50}")
        print(f"读者：{reader_info['name']}")
        print(f"{'='*50}")

        try:
            result = call_reader(reader_key, arc_summary)
            results[reader_key] = result

            # 摘要打印
            print(f"  推力流失：{result.get('momentum_loss', '')[:150]}...")
            print(f"  最佳场景：{result.get('best_scene', '')[:150]}...")
            print(f"  是否推荐：{result.get('would_recommend', '')[:150]}...")
        except Exception as e:
            print(f"  错误：{e}")

    # 找分歧
    disagreements = find_disagreements(results)

    # 共识与分歧
    print(f"\n{'='*60}")
    print("读者评审团结果")
    print(f"{'='*60}")

    for question in ["momentum_loss", "earned_ending", "cut_candidate", "missing_scene",
                      "thinnest_character", "best_scene", "worst_scene", "would_recommend",
                      "haunts_you", "next_book"]:
        print(f"\n--- {question.upper()} ---")
        for reader_key in READERS:
            if reader_key in results:
                answer = results[reader_key].get(question, "N/A")
                print(f"  [{READERS[reader_key]['name']}]：{answer[:300]}")

    if disagreements:
        print(f"\n{'='*60}")
        print("分歧点（需要编辑决策）")
        print(f"{'='*60}")
        for d in disagreements:
            print(f"\n  {d['question']} —— 第 {d['chapter']} 章")
            print(f"    标记：{', '.join(d['flagged_by'])}")
            print(f"    未标记：{', '.join(d['not_flagged'])}")

    # 保存完整结果
    output = {
        "readers": results,
        "disagreements": disagreements,
        "timestamp": datetime.now().isoformat()
    }
    out_path = BASE_DIR / "edit_logs" / "reader_panel.json"
    out_path.parent.mkdir(exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"\n已保存到 {out_path}")

if __name__ == "__main__":
    main()
