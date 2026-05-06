#!/usr/bin/env python3
"""
seed.py —— 生成中文奇幻 / 科幻小说的种子概念。

用法：
  uv run python seed.py              # 生成 10 个概念，挑一个
  uv run python seed.py --count=5    # 生成 5 个
  uv run python seed.py --riff "魔法以记忆为代价"  # 在已有想法上演变
"""

import argparse
import json
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env")

WRITER_MODEL = os.environ.get("AUTONOVEL_WRITER_MODEL", "claude-sonnet-4-6-20250217")


def call_writer(prompt, max_tokens=4000):
    import llm_client
    return llm_client.call(
        prompt,
        model=WRITER_MODEL,
        max_tokens=max_tokens,
        temperature=1.0,  # high temp for creative diversity
        system=(
            "你是一位深谙中外幻想小说传统的小说家。你熟悉中国古典与当代的奇想叙事 "
            "——《镜花缘》《聊斋志异》《山海经》、还珠楼主的剑仙、莫言的魔幻乡土、"
            "阿来的高原叙事、马伯庸的历史架空、刘慈欣与韩松的科幻冷峻、"
            "双翅目的概念实验，也熟悉西方幻想的格式严密 —— Le Guin、Wolfe、"
            "Jemisin、Susanna Clarke。你创造的小说概念**具体、出人意表、结构严谨**。"
            "你绝不提议「中世纪欧洲 + 精灵 / 矮人 / 兽人」或「修真升级打怪爽文」这类俗套。"
            "每个概念都该让读者觉得「这种东西我从没见过」。"
        ),
        timeout=120,
        extra_beta=True,
    )


GENERATE_PROMPT = """生成 {count} 个中文奇幻 / 科幻小说的种子概念。每一个都应当是一份**可以由此动笔写出整部长篇**的前提。

对**每一个**概念，给出：

编号. 书名（暂定名 —— 有意象，不要泛化）
HOOK: 一句话钩子，能让人把书拿下来。要**具体、出人意表**，不要"在一个 X 的世界..."这种老套开头。
WORLD: 这个世界**不一样**在哪？不只是"有魔法"，而是**哪一项具体的、罕见的设定**定义了这个地方？要**具体**——盐田群岛、倒生的塔、会迁徙的城、能记忆的海，等等。要**有感官**。
MAGIC/COST: 核心的思辨元素是什么？它的**代价**是什么？按桑德森第二定律：**限制 > 能力**。代价应当制造**有意思的两难**。
TENSION: 中心冲突是什么？必须**同时**是**私人的**（某个具体人物的具体困境）与**宇宙的**（影响整个世界）。这两层必须**互相牵扯**。
THEME: 这个故事在**追问**什么？不是要传递的"道理"，而是一个**没有简单答案**的真问题。
WHY IT'S NOT GENERIC: 一句话说清它**为什么不像**普通奇幻 / 网文。

请让 {count} 个概念之间**有差异**：
  - 至少一个**非人类中心**的世界
  - 至少一个**文学性 / 安静**的，而非史诗的
  - 至少一个**叙事结构本身**就有想法的
  - 至少一个**不是欧洲奇幻 / 修真**的设定 —— 可以是中亚草原、东南亚岛屿、海底、大气层、北极、中世纪伊斯兰、明清市井、近未来城市等
  - 调性混合：阴郁、温暖、怪异、忧郁、轻盈

**不要**生成：
  - 天选之子预言型剧情（除非以有趣的方式被颠覆）
  - 黑暗领主 / 终极邪恶作为主反派
  - 中世纪欧洲 + 精灵 / 矮人 / 兽人
  - "学院 / 修真宗门"作为主舞台
  - 三角恋作为主线
  - 修真升级 / 龙傲天 / 重生爽文
"""

RIFF_PROMPT = """我有一个奇幻小说的种子想法：

"{idea}"

请基于这个想法生成 5 个变体。保留核心想法的有趣之处，但**朝不同方向推**。每个变体给出：

编号. 书名
HOOK: 一句话钩子
HOW IT DIFFERS: 你从原种子里改了什么？为什么？
WORLD: 具体、感官的世界细节
MAGIC/COST: 思辨元素及其代价
TENSION: 私人 + 宇宙双层冲突
THEME: 它追问的问题

让 5 个变体之间**真正不同** —— 不是只改表面细节。改主角、改设定、改调性、改结构、改主题焦点。
"""


def main():
    parser = argparse.ArgumentParser(description="生成小说种子概念")
    parser.add_argument("--count", type=int, default=10,
                        help="生成多少个概念（默认 10）")
    parser.add_argument("--riff", type=str, default=None,
                        help="基于已有想法演变")
    args = parser.parse_args()

    import llm_client
    if not llm_client.API_KEY:
        print("错误：请先在 .env 中设置 ANTHROPIC_API_KEY（或 OPENAI_API_KEY / AUTONOVEL_API_KEY）")
        sys.exit(1)

    if args.riff:
        print(f"基于此想法演变：{args.riff}\n")
        prompt = RIFF_PROMPT.format(idea=args.riff)
    else:
        print(f"正在生成 {args.count} 个种子概念...\n")
        prompt = GENERATE_PROMPT.format(count=args.count)

    result = call_writer(prompt, max_tokens=8000)
    print(result)
    print("\n" + "=" * 60)
    print("挑一个喜欢的概念，写进 seed.txt：")
    print("  nano seed.txt")
    print("或把几个概念混合成你自己的种子。")
    print("然后进入 WORKFLOW.md 的第 2 步。")


if __name__ == "__main__":
    main()
