#!/usr/bin/env python3
"""续写余下章节 + 伏笔账本。

当 gen_outline.py 因 max_tokens 限制中途截断时使用本脚本接续：
读取 outline.md（或 /tmp/outline_output.md，如存在），让模型续写剩余章节并补全 Foreshadowing Ledger。
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
        temperature=0.5,
        system=(
            "你是一位接续大纲的小说架构师。以与前文章节**完全相同**的格式续写。"
            "每章必须包含：POV / 地点 / Save the Cat 节拍 / % 标 / 情感弧 / 试-错循环 / "
            "节拍 / 铺垫 / 兑现 / 人物移动 / 谎言 / 字数目标。"
        ),
        timeout=600,
    )

# 优先读 outline.md；若不存在但有 /tmp/outline_output.md 则用它（旧约定）
outline_path = BASE_DIR / "outline.md"
if outline_path.exists() and outline_path.read_text().strip():
    part1 = outline_path.read_text()
else:
    fallback = Path("/tmp/outline_output.md")
    if fallback.exists():
        part1 = fallback.read_text()
    else:
        print("错误：找不到 outline.md 或 /tmp/outline_output.md，无法续写", file=sys.stderr)
        sys.exit(1)

mystery_path = BASE_DIR / "MYSTERY.md"
mystery = mystery_path.read_text() if mystery_path.exists() else ""

prompt = f"""下面是这部小说目前已生成的章节大纲（可能在某一章中途被截断）。请：

1. 把**最后一个未写完的章节补完整**（如果有）
2. **续写剩余章节直至全书结束**，保持与前文一致的章数与节拍计划
3. 如果伏笔账本（Foreshadowing Ledger）尚未写完，**用一张表把它补全**

请使用与前文相同的格式：`### Ch N: 中文标题`（英文锚 + 中文标题）。

THE OUTLINE SO FAR（已有部分）：
{part1}

THE CENTRAL MYSTERY（中心谜团，作者所知）：
{mystery}

最后写：

## Foreshadowing Ledger（伏笔账本）

| # | 线索 | 铺垫（章） | 加固（章） | 兑现（章） | 类型 |
|---|------|----------|-----------|-----------|------|

至少 15 根线索。类型：object / dialogue / action / symbolic / structural。
铺垫到兑现距离至少 3 章。

要点：
- 高潮必须**仅用已确立的规则**解决（桑德森第一定律），不能引入新魔法
- "稳定陷阱"对策：坏事保留为坏。不要所有事都干净收束。允许不可逆的失去。
- 主角的"谎言"必须在高潮前被彻底击碎
- 终场画面应当与第 1 章的开场画面互镜，但展现**转变**
- 末段至少留一章"安静"章，让情绪沉淀
"""

print("正在调用 writer 模型续写...", file=sys.stderr)
result = call_writer(prompt)
print(result)
