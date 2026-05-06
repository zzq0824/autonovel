#!/usr/bin/env python3
"""
从 world.md + characters.md 中抽取所有硬事实，生成 canon.md。
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env")

WRITER_MODEL = os.environ.get("AUTONOVEL_WRITER_MODEL", "claude-sonnet-4-6")

def call_writer(prompt, max_tokens=16000):
    import llm_client
    return llm_client.call(
        prompt,
        model=WRITER_MODEL,
        max_tokens=max_tokens,
        temperature=0.2,  # Low temp for factual extraction
        system=(
            "你是从中文小说策划文档中**抽取硬事实**的连续性编辑（continuity editor）。"
            "你**精确、详尽**，绝不发明源材料里没有的事实。每一条记录都必须能"
            "**追溯到源文档中的具体陈述**。"
        ),
        timeout=300,
    )

world = (BASE_DIR / "world.md").read_text()
characters = (BASE_DIR / "characters.md").read_text()
seed = (BASE_DIR / "seed.txt").read_text()

prompt = f"""从这些策划文档中抽取**每一项硬事实**，整理成结构化的 canon 数据库。
"硬事实" = 作者**不可违反**的任何事项：人名、年龄、日期、外貌、魔法 / 思辨系统规则、地理、关系、已确立的事件。

源文档：

=== SEED.TXT ===
{seed}

=== WORLD.MD ===
{world}

=== CHARACTERS.MD ===
{characters}

请按下列分类，以 CANON.MD 格式输出：

## Geography（地理）
- 关于地点、距离、物理特性的具体事实

## Timeline（时间线）
- 已注明日期的事件、年龄、持续时间

## Magic / Speculative System Rules（思辨系统规则）
- 硬规则的具体条款（区间、代价、限制）
- 特殊能力的具体表现与边界

## Character Facts（人物事实）
- 年龄、外貌、习惯、关系
- 一条事实一行（不要写成段落）

## Political / Factional（政治 / 派系）
- 谁掌握什么、联盟、冲突、契约

## Cultural（文化）
- 习俗、禁忌、法律、节日、食物、衣着

## Established In-Story（故事中已发生）
- 故事开始之前**已经发生**的事件
- 关键背景事件、历史枢纽时刻等

规则：
- **一条事实一项 bullet**。简短、具体、可核查。
- 每条事实后用括号注明来源（world.md 或 characters.md）。
- 至少 **80-120 条**记录。要详尽。
- 若两份文档给出略有不同的细节，**标记差异**。
- **不要**发明事实。只记录明确陈述过的内容。
"""

print("正在调用 writer 模型...", file=sys.stderr)
result = call_writer(prompt)
print(result)
