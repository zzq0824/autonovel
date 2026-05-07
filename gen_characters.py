#!/usr/bin/env python3
"""
foundation 阶段的一次性 characters.md 生成器。
读取 seed.txt + voice.md + world.md + CRAFT.md，调用 writer 模型。
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
            "你是一位精通「创伤 / 欲望 / 需要 / 谎言」框架、桑德森三杆、"
            "对话辨识度的中文文学小说人物设计师。你创造的角色"
            "**像活人**——带着矛盾、秘密、能听见的口吻。"
            "你绝不用 AI slop 成语。你的散文干净、直接。"
        ),
        timeout=300,
    )

seed = (BASE_DIR / "seed.txt").read_text()
world = (BASE_DIR / "world.md").read_text()

# 仅取 voice.md Part 2（本书专属声音）
voice = (BASE_DIR / "voice.md").read_text()
voice_lines = voice.split('\n')
part2_start = next(i for i, l in enumerate(voice_lines) if 'Part 2' in l)
voice_part2 = '\n'.join(voice_lines[part2_start:])

prompt = f"""为这部小说构建完整的人物名册。这份就是 CHARACTERS.MD —— 关于这个故事里**有谁**、**他们被什么驱动**、**他们怎么说话**、**他们藏着什么秘密**的最权威参考。

SEED CONCEPT（种子概念）：
{seed}

WORLD BIBLE（人物所栖居的世界）：
{world}

VOICE IDENTITY（本书的调性）：
{voice_part2}

人物塑造要求（来自 CRAFT.md）：

### 桑德森三杆（Three Sliders）
每个人物有三根独立旋钮（0-10）：
  PROACTIVITY（主动性）—— 他们驱动剧情还是被剧情推动？
  LIKABILITY（共情度）—— 读者是否同情他们？
  COMPETENCE（能力）—— 他们做事在行吗？
规则：有吸引力 = 至少两根偏高，或一根偏高且其他在成长。

### 创伤 / 欲望 / 需要 / 谎言（Wound / Want / Need / Lie）
一条因果链：
  GHOST（背景损伤事件）→ WOUND（持续的情感损伤）→ LIE（应付创伤的虚假信念）
    → WANT（由谎言驱动的外部目标）→ NEED（与谎言对立的内在真相）
规则：欲望与需要必须**处于张力**。「谎言」必须能一句话说清。「真相」必须是它的直接对立面。

### 对话辨识度（8 维）
1. 词汇等级（用字深浅）  2. 句长（短促 vs 缠绕）  3. 文白程度与正式度
4. 口头禅 / 语癖  5. 问句 vs 陈述句比例  6. 打断模式
7. 比喻领域（士兵用兵器，工匠用器物）  8. 直白 vs 迂回
测试：去掉对话标记，能仅凭句法分辨说话人吗？

请构建至少包含以下角色的名册（角色姓名应符合本书的世界观与文化背景，不要套用英美名字也不要写成"主角 1 / 配角 2"，要给每个人**真名**）：

1. **主角 / POV 视角人物**
   - 完整的"创伤 / 欲望 / 需要 / 谎言"链
   - 三杆评分（含说明）
   - 弧型（正向 / 反向 / 平直）
   - 详细的口吻（八维度）
   - 身体习惯与小动作（unconscious tells）
   - 至少 2 个秘密
   - 主要人际关系图
   - 与种子概念里"代价"机制的具体绑定（这个人物如何承受 / 体验那项代价？）

2. **直接亲属或朝夕相处者**
   - 和主角同样深度
   - 与种子里某项历史 / 创伤事件的具体牵连
   - 知道什么 / 隐瞒什么

3. **缺席但重要的人物**
   - 即便此人物在故事中长期不在场，也应有完整深度
   - 他 / 她**在缺席中的存在**怎样塑造了主角

4. **拮抗者 / 对手**
   - **不是**反派，而是**利益与主角冲突的人**
   - 拥有自己完整的"创伤 / 欲望 / 需要 / 谎言" —— 应当**可被理解**

5. **机构性 / 系统性的拮抗**
   - 制度化身的人物 —— 系统的脸
   - 他 / 她相信自己在保护什么？这种信念如何让位于伤害？

6. **来自系统外的视角**
   - 边缘人 / 反叛者 / 局外人
   - 他 / 她在主题层面**代表**什么？

7. **至少 1-2 位故事必需的额外角色**
   - 主角的同辈 / 朋友？
   - 知情的次要角色？
   - 立场分裂的内部人？

每位角色都需包含：
- 姓名、年龄、身份
- 创伤 / 欲望 / 需要 / 谎言（主要角色必填）
- 三杆评分（含数字与说明）
- 弧型与轨迹
- 八维度的口吻（每维都给一两句**实例台词**）
- 外貌（具体，不要「绝美」「深邃」这种泛化形容）
- 身体习惯与无意识的小动作
- 秘密（读者不会立即知道的）
- 关键人际关系（映射到其他角色）
- 主题作用（这个人物**化身**了什么问题？）

要求：
- 人物之间必须**互联**。他们的"欲望"应当**互相冲突**
- 每个秘密一旦被揭，应**改变**故事走向
- 口吻必须有足够辨识度，能通过"无标记测试"
- 给主角与种子里的核心机制具体的身体绑定（如何感受、何处疼、何种习惯）
- 拮抗者必须像主角一样饱满 —— 是一个**配得上**的对手
- 目标 ~3000-4000 字。密度高，不要注水。
"""

print("正在调用 writer 模型...", file=sys.stderr)
result = call_writer(prompt)
print(result)
