#!/usr/bin/env python3
"""从 seed + world + characters + mystery + craft 生成 outline.md。"""
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
            "你是一位精通救猫咪节拍表（Save the Cat）、桑德森情节理论、"
            "哈蒙故事圆环（Story Circle）、MICE 框架的中文小说架构师。"
            "你写的大纲让作者**直接动笔时不需再发明结构**。"
            "每章都有节拍、情感弧、试-错循环类型。"
            "你绝不用 AI slop 成语。你的散文干净、直接。"
        ),
        timeout=600,
        extra_beta=True,
    )

seed = (BASE_DIR / "seed.txt").read_text()
world = (BASE_DIR / "world.md").read_text()
characters = (BASE_DIR / "characters.md").read_text()
mystery = (BASE_DIR / "MYSTERY.md").read_text()
craft = (BASE_DIR / "CRAFT.md").read_text()

# 仅取 voice.md Part 2
voice = (BASE_DIR / "voice.md").read_text()
voice_lines = voice.split('\n')
part2_start = next(i for i, l in enumerate(voice_lines) if 'Part 2' in l)
voice_part2 = '\n'.join(voice_lines[part2_start:])

prompt = f"""为这部小说构建完整的章节大纲。**目标：22-26 章，共 ~80,000 字（每章约 3,000-4,000 字）**。

SEED CONCEPT（种子概念）：
{seed}

THE CENTRAL MYSTERY（中心谜团 —— 作者所知，读者渐次发现）：
{mystery}

WORLD BIBLE（世界观）：
{world}

CHARACTER REGISTRY（人物名册）：
{characters}

VOICE（调性与语域）：
{voice_part2}

CRAFT REFERENCE（要遵循的结构理论）：
{craft}

构建大纲，包含：

## 幕结构（Act Structure）
划分第一幕（0-23%）、第二幕上半（23-50%）、第二幕下半（50-77%）、第三幕（77-100%）。
明确给出本书各关键节拍的百分比位置。

## 章节大纲（Chapter-by-Chapter Outline）

每章给出（请使用如下英文锚点 `### Ch N: 标题`，因为下游脚本以此为正则锚 —— 标题用中文）：
### Ch N: [中文标题]
- **POV：**（哪一位 POV 视角人物，几人称几时态请保持与 voice.md 一致）
- **Location（地点）：**
- **Save the Cat 节拍：** 本章服务的是哪个节拍（开场画面 / 铺垫 / 触发事件 / ...）
- **% 标：** 在全书中的位置
- **情感弧：** 起始情绪 → 结束情绪
- **试-错循环：** 是但是 / 不而且 / 不但是 / 是并且
- **节拍：** 3-5 项必须发生的具体场景节拍
- **铺垫（Plants）：** 本章植入的伏笔
- **兑现（Payoffs）：** 本章兑现的前文伏笔
- **人物移动：** 本章末，主要人物身上发生了什么变化
- **谎言：** 主角的"谎言"在本章如何被强化或挑战
- **字数目标：** 用于节奏控制

## 伏笔账本（Foreshadowing Ledger）

追踪每一根植入线索的表：
| 线索 | 铺垫（章） | 加固（章） | 兑现（章） | 类型 |

至少 **15** 根线索。类型：object / dialogue / action / symbolic / structural（物 / 对话 / 行动 / 象征 / 结构）。

关键剧情骨架：

第一幕（约 Ch 1-6）：立起 POV 视角人物的世界、他 / 她的痛楚、他 / 她与种子里"代价"机制的具体绑定。早早植入中心谜团（埋下三件以上将在后文兑现的具体物 / 言 / 习惯）。**触发事件**：某外因迫使主角开始介入。

第二幕上半（约 Ch 7-12）：调查 / 探索 / 学习。主角积累线索与关系。**中点**：得到部分真相，转换路径（假胜利或假失败）。

第二幕下半（约 Ch 13-18）：压力累积。拮抗者出招。"谎言"日渐难以维持。**全部失去**：主角面对最深的代价。

第三幕（约 Ch 19-24）：主角理解了那个真问题，必须做出选择。高潮以**已确立的规则**机械可解 —— 不能凭空冒出新魔法。结局展现选择的余波。

约束：
- 高潮必须**仅用已确立的规则**（按桑德森第一定律）解决
- "稳定陷阱"对策：坏事**应当**保留为坏。不要所有事都干净收束。允许不可逆的失去。
- 关键人物即便部分章节缺席，也必须**至少出现在一章里亲自登场**，而不仅是回忆 / 信件
- 至少 3 章应当是"安静"章 —— 以人物为重，少动作，情感丰盈
- 试-错类型要混合：中段 60%+ 应当是"是但是"或"不而且"
- 伏笔账本里"铺垫到兑现"的距离至少 3 章
- **不要**给所有章节都按上对仗工整的中文章回标题（"林冲风雪山神庙，陆虞侯火烧草料场"那种）；现代长篇用更克制、不规则的章名
"""

print("正在调用 writer 模型...", file=sys.stderr)
result = call_writer(prompt)
print(result)
