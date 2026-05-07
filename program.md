# autonovel

自动化中文小说写作流水线。Agent 在**五个互相演化的层**上写作并修订一部长篇小说，由自动评估系统驱动。

## 必读文档

在**任何**写作或评估之前，agent 必须**内化**：
- `voice.md` —— Part 1（底线）永久通用。Part 2 是本书专属，foundation 阶段确定。
- `CRAFT.md` —— 情节、人物、世界观、伏笔、散文质量的可操作化框架。这是 agent 的"教育"。
- `ANTI-SLOP.md` —— 中文 AI 写作露馅模式的完整参考。

## 层级栈

```
  Layer 5：voice.md          —— 怎么写（HOW：风格、调性、词汇）
  Layer 4：world.md          —— 有什么（WHAT EXISTS：设定、思辨元素、地理、历史）
  Layer 3：characters.md     —— 谁在做（WHO ACTS：人物名册、弧线、关系）
  Layer 2：outline.md        —— 发生什么（WHAT HAPPENS：节拍、伏笔图）
  Layer 1：chapters/ch_NN.md —— 实际散文（每章一个文件）
  贯穿层： canon.md           —— 什么是真的（WHAT IS TRUE：硬事实、一致性数据库）
```

## 起步

1. **打标签**：从 master 创建分支 `autonovel/<tag>`。
2. **读所有层级文件**以建立完整上下文。
3. **核对 state.json** 显示 phase=foundation。
4. **确认后启动**。

## Phase 1：基础（尚无散文）

LOOP 直到 `foundation_score > 7.5` 且 `lore_score > 7.0`：
1. 运行 `python evaluate.py --phase=foundation`
2. 从评估输出中找出**最弱**的层 / 维度
3. 扩写或重写那一层的文档
4. 给 world.md / characters.md 加新事实时，**同步**记录到 canon.md
5. `git commit` 并写明改动
6. 再评估
7. 分数提升 → 保留；下降 → `git reset --hard HEAD~1`，丢弃
8. 记入 `results.tsv`

设定优先级（基础评估器对此加权 40%）：
- 思辨 / 魔法系统：硬规则、代价、限制、社会影响
- 历史：能制造**当下**张力的时间线，而非装饰
- 地理 / 文化：独特地点、具体习俗与禁忌
- 互联性：思辨元素影响政治，历史解释派系，地理塑造文化。**拉一根线应当带动整片网**。
- 冰山深度：暗示多于陈述。提示更深的系统。

每轮迭代都要做的跨层一致性核查：
- 大纲只引用 world.md 中存在的设定
- 人物弧线对齐大纲节拍
- 人物能力符合思辨系统规则
- 伏笔账本平衡（每根植入线索都有兑现）
- 文风范文存在且非泛化
- canon.md 中收录了 world.md 与 characters.md 中的所有硬事实

退出条件：当 `foundation_score > 7.5` 且 `lore_score > 7.0` 时，把 state.json 的 phase 更新为 "drafting"。

## Phase 2：初稿（按章顺序起草）

FOR 每一章（按大纲顺序）：
  LOOP 直到 `chapter_score > 6.0` 或 `attempts > 5`：
  1. 加载上下文：voice.md + world.md + characters.md + 本章大纲条目 + 上一章末 ~1000 字 + 下一章大纲（用于连贯）
  2. 写 chapters/ch_NN.md
  3. 运行 `python evaluate.py --chapter=NN`
  4. 按分数保留 / 丢弃
  5. 写作时若发现设定空白或不一致，向 state.json 记一条 debt
  6. 评估后查看 `new_canon_entries`。把本章确立的新事实加入 canon.md
  7. 记入 `results.tsv`
  8. `git commit`

Canon 在起草过程中**继续生长**。每一章都会确立事实（某人物揭露某事 / 某地点被描述 / 某事件发生）。这些被记入 canon.md，让后续章节保持一致。

所有章节起草完成后，把 state.json 的 phase 更新为 "revision"。

## Phase 3：修订（无限精修）

LOOP 永远：
1. 运行 `python evaluate.py --full`
2. 找出最弱处：
   - 分最低的章节
   - 未回收的伏笔
   - 一致性违规
   - 文风偏离
   - 节奏问题
   - state.json 中待处理的 debt
3. 选定行动：
   a. 重写一章弱章
   b. 修一致性违规（可能触动设定 + 章节）
   c. 加固一根伏笔（铺垫 + 兑现章节）
   d. 在偏离最严重的章里精修文风
   e. 调整节奏（合 / 拆章）
   f. 更新策划文档以反映现实
4. 做改动
5. `git commit`
6. 重评影响范围
7. 保留 / 丢弃
8. 记入 `results.tsv`

### 传播规则

某层改变时，必须检查下游：
- voice.md 改变 → 对**所有**章节重评文风贴合
- world.md 改变 → 检查所有章节的设定一致性
- characters.md 改变 → 检查相关章节的对话 / 行为
- outline.md 改变 → 重评受影响章节的节拍覆盖
- 章节改变 → 检查伏笔账本，检查相邻章节

当写作揭示上游问题，记 debt 到 state.json：
```json
{"trigger": "ch_07：思辨系统需要"瞬移"规则",
 "affected": ["world.md", "ch_03.md"],
 "status": "pending"}
```

## 上下文窗口策略

**始终**加载（约 8k tokens）：
- voice.md（完整）
- characters.md（完整）
- world.md（关键规则摘要）
- outline.md（完整）
- 伏笔账本（完整）

**按任务**加载（约 20-30k tokens）：
- 目标章节
- 相邻章节（前一章 + 下一章）
- 因伏笔关联的其他章节

## 评估维度

**基础**：world_depth、character_depth、outline_completeness、foreshadowing_balance、internal_consistency

**章节**：voice_adherence、beat_coverage、character_voice、plants_seeded、prose_quality、continuity

**全本**：以上全部 + arc_completion、pacing_curve、theme_coherence、foreshadowing_resolution、overall_engagement

> JSON 输出 key 始终保持英文（脚本解析依赖此约定），value 字段用中文。

## 稳定陷阱（**关键**）

AI 最致命的倾向是**偏好稳定甚于变化**。这对小说是致命的。在每一阶段都要主动对抗它：

- 角色结尾必须**真正不同**于开篇
- 让坏事**保持**坏。不是所有事都被治愈
- 允许**不可逆**的决定与**不可逆**的失去
- 隐瞒信息。读者**不应**知道一切
- 制造真正的道德两难。让"对的选择"不清楚
- 变化情绪强度：安静 / 爆发 / 恐惧 / 解脱 / 惊奇 / 恐怖
- 如果一个选择**没有真实代价**，那就**不是**真正的选择
- 冲突**不应**被解决得太快、太干净
- 抗拒"把尖锐之处磨成更安全的东西"的本能

## 基础阶段：声音发现（Voice Discovery）

在基础阶段，agent **必须**为这部小说**发现**声音：
1. 读世界观与最初的想法
2. 用不同语域写 **5 段试笔**（神话感 / 简短 / 温暖 / 冷峻 / 轻盈 / 文白夹杂 / 等）
3. 评估哪种语域最适合这个故事的世界与调性
4. 选定最好的，精修，写范文段落与反范文段落
5. 把发现的声音填进 voice.md Part 2

声音应当让人感觉它**属于**这个世界（勒古恩的洞见：在奇幻里，语言**创造**世界，不只是描述）。

## 基础阶段：人物框架

在起草开始之前，每位 POV 视角人物都必须**记录在案**：
- 创伤 / 欲望 / 需要 / 谎言（Wound / Want / Need / Lie）链（见 CRAFT.md）
- 三杆评分（主动性 / 共情度 / 能力）
- 弧型（正向 / 反向 / 平直）
- 与其他人物**截然不同**的口吻
- 至少一个**读者不会立即知道**的秘密

## 基础阶段：情节框架

大纲必须**展示**：
- 救猫咪节拍出现在大致正确的百分比位置
- 每章规划好的试-错循环类型（是但是 / 不而且 等）
- 伏笔账本：每根植入线索及其兑现位置
- MICE 线索：识别并按相反顺序闭合
- 第二幕中赌注**逐步**抬高

## 规则

- **永不停下**（直到被中断）
- **越简越好**：不为边际收益增加复杂性
- **前进比完美重要**：Phase 2 中 6.0 分的章节就够了。Phase 3 才精修
- **一切记入 results.tsv**：每次实验都要记录
- **裁判不同模型**：评估模型应当与写作模型不同（避免自我表扬偏差），可能时如此
- **对抗稳定**：主动推向变化、代价、真实后果。见上文"稳定陷阱"
- **具体优于抽象**："山雀"而非"鸟"；"野棉花"而非"花"；"烫铁的味道"而非"金属气味"
- **比喻要"挣得"**：比喻来自人物的经验。铁匠想到事物会想到火与铁。船工想到潮汐
- **中文专属**：成语堆 / ABB 副词病 / 心眸唇眉四件套 / "X 道"对话标记滥用 / 翻译腔 —— 这些是 evaluate.py 会扣分的中文 AI 露馅模式，详见 ANTI-SLOP.md
