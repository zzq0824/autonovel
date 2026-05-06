#!/usr/bin/env python3
"""
foundation 阶段的一次性 world.md 生成器。
读取 seed.txt + voice.md，调用 writer 模型，输出 world.md 内容。
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
        temperature=0.7,
        system=(
            "你是一位精通桑德森魔法定律、勒古恩散文哲学，以及 TTRPG 级世界观设计的"
            "中文奇幻 / 科幻世界观构建者。你写的世界观文档**具体、互联、暗示出超过表面所述的深度**。"
            "你绝不用 AI slop 成语（璀璨 / 斑斓 / 鳞次栉比 / 美轮美奂 / 气势磅礴 / 叹为观止 等）。"
            "你的文字干净、直接。每一条规则都有代价。每一处文化细节都暗示一段历史。"
            "每一个地点都有独特的感官签名。"
        ),
        timeout=300,
    )

seed = (BASE_DIR / "seed.txt").read_text()
voice = (BASE_DIR / "voice.md").read_text()
craft = (BASE_DIR / "CRAFT.md").read_text()

# Extract voice Part 2 only (the novel-specific voice)
voice_lines = voice.split('\n')
part2_start = next(i for i, l in enumerate(voice_lines) if 'Part 2' in l)
voice_part2 = '\n'.join(voice_lines[part2_start:])

prompt = f"""为这部小说构建一份完整的世界观文档（World Bible）。这份就是 WORLD.MD —— 关于这个世界**存在**着什么的最权威参考。一位作者应当**仅凭此文档**就能解答任何世界观问题。

SEED CONCEPT（种子概念）：
{seed}

VOICE IDENTITY（本书的调性与语域）：
{voice_part2}

CRAFT 要求（来自 CRAFT.md，必须遵守）：
- 魔法 / 思辨系统需要**硬规则**，带**代价**与**限制**（桑德森第二定律）
- 限制在叙事篇幅上 ≥ 能力
- 魔法的影响必须辐射到社会、经济、法律、宗教
- 至少深入探讨 2-3 项社会影响
- 历史必须制造**当下**张力以驱动剧情，不只是背景板
- 地理必须**具体**且**有感官**（不要泛化奇幻）
- 冰山原则：暗示多于陈述
- 互联性：拉一根线应该带动整片网

请按下列结构组织文档（章节标题保留中文）：

## 宇宙观与历史
重大事件的时间线。重点放在**能造成当下张力**的事件。包括：开端神话、关键转折、与剧情有关的近期事件。

## 思辨 / 魔法系统
### 硬规则
具体、可测试的规则。每条规则下要附**代价**与**限制**。
规则被违反时会发生什么？什么是这个系统**做不到**的？

### 软规则 / 神秘元素（如适用）
不被全然解释、但有内部一致逻辑的部分。
软规则应当**制造问题**，不应解决问题。

### 社会影响
该思辨元素如何塑造：治理、商业、教育、阶级结构、犯罪、家庭生活、童年、衰老、残疾？至少 3 项要写到具体细节。

## 地理
主要场所的物理布局、街区或聚落、独特的物理 / 声学 / 气候特征。
邻近地点（至少 2-3 处）。每个地点要有独特**感官签名**（什么气味？什么声音？什么颜色？）。

## 派系与政治
谁握有权力，谁想要权力，谁被权力压在底下。
至少 3-4 个利益对立的派系。

## 自然世界（动植物 / 怪物）
本地的自然界**有什么独特之处**？

## 文化细节
习俗、禁忌、节日、食物、衣着、成人礼。让日常生活**具体**起来。
（吃早饭的味道是什么？孩子们玩什么？老人抱怨什么？）

## 内部一致性规则
作者**绝不可违反**的硬约束。这个世界的物理 / 形而上学。
什么可能，什么不可能。

重要：
- **要具体**。不是"城市有几个街区"，而是给街区起名、描述、给出感官签名
- 每条规则都要附上一处**代价**或**限制**
- 每节中包含 2-3 项**未被解释**的事实，暗示更深的系统（冰山深度）
- 事实要**互联**：魔法影响政治，地理塑造文化，历史解释当前的派系冲突
- 散文要干净、直接。不要 AI slop（不要 "璀璨"，不要 "斑斓"，不要 "鳞次栉比"）
- 世界应当**接地**、**有人住过**，而不是被想象出来的。想想：早饭闻起来怎样？孩子们玩什么游戏？老人抱怨些什么？
- 目标 ~3000-4000 字。密度高，不要注水。
"""

print("正在调用 writer 模型...", file=sys.stderr)
result = call_writer(prompt)
print(result)
