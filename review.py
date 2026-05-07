#!/usr/bin/env python3
"""
通过 Opus 进行深度全本评审。

把整部小说送给 Claude Opus（或配置的同档模型）做**双角色**评审：
  1. 文学评论家（报纸书评风）
  2. 文学教授（针对具体瑕疵的可执行建议）

用法：
  python review.py                    # 评审，保存到 edit_logs/
  python review.py --output reviews.md  # 同时保存人类可读副本
  python review.py --parse            # 解析最近一次评审为可执行项
"""
import os
import sys
import json
import re
import argparse
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env", override=True)

# Use Opus for reviews — it's the best at literary analysis
REVIEW_MODEL = os.environ.get("AUTONOVEL_REVIEW_MODEL", "claude-opus-4-6")

CHAPTERS_DIR = BASE_DIR / "chapters"
LOGS_DIR = BASE_DIR / "edit_logs"

REVIEW_PROMPT = """阅读下面这部中文长篇小说《{title}》。请**先以文学评论家**的身份评论它（报纸书评的风格 —— 给星级、写一段评价、定调它在中文文学版图中的位置），再**以文学教授**的身份给出针对具体瑕疵的、**可执行**的修改建议。**公允但诚实**。你**不是必须**找瑕疵。

请用中文撰写评审。如果是真正出色的作品，就大方说出来；如果有结构性问题，就具体指出哪一章哪一段。**编号你的可执行修订项**（1. 2. 3. ...），每一项都给一句简短标题，再给具体的"改怎么改"。

{manuscript}"""


def call_opus(prompt, max_tokens=8000):
    """Call the configured review model with the full manuscript."""
    import llm_client
    print(f"Sending to {REVIEW_MODEL} ({len(prompt):,} chars)...", file=sys.stderr)
    return llm_client.call(
        prompt,
        model=REVIEW_MODEL,
        max_tokens=max_tokens,
        temperature=0.3,
        timeout=600,
        extra_beta=True,
    )


def get_title():
    """从 outline.md 或首章拿书名。"""
    outline = BASE_DIR / "outline.md"
    if outline.exists():
        first_line = outline.read_text().split("\n")[0]
        title = first_line.lstrip("# ").strip()
        if title:
            return title
    ch1 = CHAPTERS_DIR / "ch_01.md"
    if ch1.exists():
        first_line = ch1.read_text().split("\n")[0]
        return first_line.lstrip("# ").strip()
    return "未命名小说"


def build_manuscript():
    """把所有章节拼成一份完整文稿。"""
    chapters = sorted(CHAPTERS_DIR.glob("ch_*.md"))
    if not chapters:
        print("错误：未找到任何章节文件。", file=sys.stderr)
        sys.exit(1)

    parts = []
    for ch in chapters:
        parts.append(ch.read_text())

    manuscript = "\n\n---\n\n".join(parts)
    char_count = len(re.findall(r"[一-鿿]", manuscript))
    print(f"全稿：{len(chapters)} 章，约 {char_count:,} 字", file=sys.stderr)
    return manuscript


def parse_review(review_text):
    """把评审解析成结构化的可执行项。同时兼容中英文关键词。"""
    items = []

    # 分割"评论家"与"教授"两节（兼容中英文标记）
    # 中文常见格式："作为文学教授，..." / "现在以教授的身份..." / "## 教授视角" 等
    sections = re.split(
        r'(?:Professor|PROFESSOR|professor|教授(?:视角|的|身份)?|文学教授|作为(?:文学)?教授|以(?:文学)?教授)',
        review_text, maxsplit=1
    )

    critic_text = sections[0] if sections else review_text
    professor_text = sections[1] if len(sections) > 1 else ""

    # 抽取星级（★ 或 "4.5/5" 或 "4.5 颗星"）
    star_match = re.search(
        r'★+½?|(\d+(?:\.\d+)?)\s*(?:/|out of|颗星|星)\s*5?',
        critic_text
    )
    stars = None
    if star_match:
        star_str = star_match.group(0)
        if '★' in star_str:
            stars = star_str.count('★') + (0.5 if '½' in star_str else 0)
        elif star_match.group(1):
            try:
                stars = float(star_match.group(1))
            except ValueError:
                stars = None

    # 抽取"教授"段落下的编号项（支持 "1." / "1、" / "(1)" 等多种中文编号）
    prof_items = re.split(r'\n(?=(?:\d+[\.\、]|（\d+）|\(\d+\))\s+)', professor_text)

    for section in prof_items:
        if not section.strip():
            continue

        # 抽出编号 + 标题
        title_match = re.match(
            r'(?:(\d+)[\.\、]|（(\d+)）|\((\d+)\))\s+(.+?)(?:\n|$)',
            section
        )
        if not title_match:
            continue

        num_str = next(g for g in title_match.groups()[:3] if g)
        num = int(num_str)
        title = title_match.group(4).strip()

        text_lower = section.lower()
        # 严重度（中英双语）
        if any(w in text_lower for w in [
            'major', 'significant', 'primary', 'most important',
            '重大', '严重', '主要', '关键', '核心', '首要'
        ]):
            severity = "major"
        elif any(w in text_lower for w in [
            'minor', 'small', 'slight', 'cosmetic',
            '轻微', '次要', '小', '细节'
        ]):
            severity = "minor"
        else:
            severity = "moderate"

        # 修订类型（中英双语）
        if any(w in text_lower for w in [
            'cut', 'compress', 'trim', 'reduce', 'consolidate',
            '砍', '压缩', '删除', '精简', '合并', '收敛'
        ]):
            fix_type = "compression"
        elif any(w in text_lower for w in [
            'add', 'expand', 'introduce', 'give', 'more',
            '增加', '扩展', '加入', '增', '补充', '丰富', '展开'
        ]):
            fix_type = "addition"
        elif any(w in text_lower for w in [
            'repetit', 'recurring', 'frequency', 'tic', 'gesture',
            '重复', '反复', '出现', '套路', '癖好', '小动作'
        ]):
            fix_type = "mechanical"
        elif any(w in text_lower for w in [
            'restructur', 'rearrang', 'move', 'reorganiz',
            '重构', '重组', '调整', '重新安排', '挪动'
        ]):
            fix_type = "structural"
        else:
            fix_type = "revision"

        # 检查"qualified hedge"（边际收益信号；中英双语）
        qualified = any(phrase in text_lower for phrase in [
            'individually fine', 'largely successful', 'each instance works',
            'minor relative to', 'small complaint', 'costs of ambition',
            'not a flaw', 'deliberate choice', 'thematically coherent',
            '总体上', '整体上', '已属难得', '总体成功', '个别', '不算缺点',
            '是有意为之', '主题一致', '可以理解为', '从这个角度看',
        ])

        # 抽取具体建议
        suggestion = ""
        sugg_match = re.search(
            r'(?:Specific\s+)?(?:[Ss]uggestion[s]?|建议|具体建议|改法|可如此修改|怎么改)'
            r':?[:：]?\s*\n?(.*?)(?=\n(?:\d+[\.\、]|（\d+）|\(\d+\))|\n\n[一-鿿A-Z]|\Z)',
            section, re.DOTALL
        )
        if sugg_match:
            suggestion = sugg_match.group(1).strip()[:500]

        items.append({
            "number": num,
            "title": title,
            "severity": severity,
            "type": fix_type,
            "qualified": qualified,
            "suggestion": suggestion,
            "full_text": section.strip()[:1000],
        })

    return {
        "stars": stars,
        "critic_summary": critic_text.strip()[:500],
        "professor_items": items,
        "total_items": len(items),
        "major_items": sum(1 for i in items if i["severity"] == "major"),
        "qualified_items": sum(1 for i in items if i["qualified"]),
        "raw_text": review_text,
    }


def should_stop(parsed_review):
    """Determine if the novel is done being revised.
    
    Stopping conditions:
    - Stars >= 4
    - No major unqualified items
    - More than half the items are qualified/hedged
    """
    stars = parsed_review.get("stars", 0) or 0
    total = parsed_review["total_items"]
    major = parsed_review["major_items"]
    qualified = parsed_review["qualified_items"]
    
    if stars >= 4.5 and major == 0:
        return True, "★★★★½ 且无重大项"
    if stars >= 4 and total > 0 and qualified / total > 0.5:
        return True, f"★{'★' * int(stars)}，{qualified}/{total} 项已被边际化（qualified）"
    if total <= 2:
        return True, f"仅找到 {total} 项"

    return False, f"{major} 项重大问题，{total - qualified} 项未边际化"


def cmd_review(args):
    """Generate a review."""
    title = get_title()
    manuscript = build_manuscript()
    
    prompt = REVIEW_PROMPT.format(title=title, manuscript=manuscript)
    
    review_text = call_opus(prompt)
    
    # Save raw review
    LOGS_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = LOGS_DIR / f"{timestamp}_review.json"
    
    parsed = parse_review(review_text)
    parsed["timestamp"] = timestamp
    parsed["title"] = title
    parsed["word_count"] = len(manuscript.split())
    
    log_path.write_text(json.dumps(parsed, indent=2, default=str, ensure_ascii=False))
    print(f"\n评审已保存到 {log_path}", file=sys.stderr)

    # 保存人类可读副本
    if args.output:
        Path(args.output).write_text(review_text)
        print(f"人类可读副本：{args.output}", file=sys.stderr)

    # 摘要
    stop, reason = should_stop(parsed)
    print(f"\n{'='*50}")
    print(f"评审摘要")
    print(f"  星级：{parsed['stars']}")
    print(f"  条目：{parsed['total_items']}（其中重大 {parsed['major_items']}）")
    print(f"  已边际化：{parsed['qualified_items']}/{parsed['total_items']}")
    print(f"  是否停止修订？{'是 —— ' + reason if stop else '否 —— ' + reason}")
    print(f"{'='*50}")
    
    return parsed


def cmd_parse(args):
    """Parse the most recent review into actionable items."""
    LOGS_DIR.mkdir(exist_ok=True)
    reviews = sorted(LOGS_DIR.glob("*_review.json"), reverse=True)
    if not reviews:
        print("未找到评审记录。请先运行：review.py")
        sys.exit(1)

    latest = json.loads(reviews[0].read_text())

    print(f"最近一次评审：{latest.get('timestamp', '未知')}")
    print(f"星级：{latest.get('stars', '?')}")
    print(f"\n可执行项（{latest['total_items']}）：")

    for item in latest.get("professor_items", []):
        qual = "（边际化）" if item["qualified"] else ""
        print(f"\n  {item['number']}. [{item['severity'].upper()}] [{item['type']}]{qual}")
        print(f"     {item['title']}")
        if item["suggestion"]:
            print(f"     建议：{item['suggestion'][:120]}...")

    stop, reason = should_stop(latest)
    print(f"\n{'='*50}")
    print(f"是否停止修订？{'是 —— ' + reason if stop else '否 —— ' + reason}")
    print(f"{'='*50}")


def main():
    parser = argparse.ArgumentParser(description="通过 Opus 进行深度全本评审")
    parser.add_argument("--output", "-o", default=None, help="保存人类可读评审副本到文件")
    parser.add_argument("--parse", action="store_true", help="解析最近一次评审")
    
    args = parser.parse_args()
    
    import llm_client
    if not llm_client.API_KEY:
        print("错误：未设置 API key（ANTHROPIC_API_KEY / OPENAI_API_KEY / AUTONOVEL_API_KEY）",
              file=sys.stderr)
        sys.exit(1)
    
    if args.parse:
        cmd_parse(args)
    else:
        cmd_review(args)


if __name__ == "__main__":
    main()
