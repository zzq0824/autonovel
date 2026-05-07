# AUTONOVEL：可复现的中文小说流水线

## 概述

本文档完整记录"从种子概念到完整中文长篇小说"的自动化流水线。

**目标**：用户给出一个种子概念，其余全部自动化。

> 详细人工分步指南见 [WORKFLOW.md](WORKFLOW.md)；agent 指令见 [program.md](program.md)；叙事手艺见 [CRAFT.md](CRAFT.md)；AI 露馅模式见 [ANTI-SLOP.md](ANTI-SLOP.md) 与 [ANTI-PATTERNS.md](ANTI-PATTERNS.md)。

---

## 主分支（框架）

主分支不含特定故事内容。它是**可复用的基底**。

```
FRAMEWORK（可复用，流水线不会修改）：
  README.md            —— 项目概览
  WORKFLOW.md          —— 人工分步指南
  PIPELINE.md          —— 本文件（自动化规范）
  program.md           —— 各阶段的 agent 指令
  CRAFT.md             —— 叙事手艺教育（情节、人物、世界观、散文）
  ANTI-SLOP.md         —— 词级 AI 露馅检测
  ANTI-PATTERNS.md     —— 结构性 AI 模式检测
  llm_client.py        —— 统一 LLM 客户端（Anthropic + OpenAI 兼容）

TEMPLATES（空壳，每部小说在分支上填写）：
  voice.md             —— Part 1（底线）永久；Part 2 空白
  world.md             —— 仅含章节标题
  characters.md        —— 仅含结构模板
  outline.md           —— 仅含结构模板
  canon.md             —— 空，含说明
  MYSTERY.md           —— 空白模板
  state.json           —— {phase: "foundation", iteration: 0, debts: []}

TOOLS（流水线机器）：
  Foundation：
    seed.py              —— 生成 10 个种子概念
    gen_world.py         —— seed → world.md
    gen_characters.py    —— seed + world → characters.md
    gen_outline.py       —— seed + world + chars → outline.md（part 1）
    gen_outline_part2.py —— outline + chars → 续写 + 伏笔账本
    gen_canon.py         —— world + chars → canon.md（硬事实）
    voice_fingerprint.py —— 文风量化分析

  Drafting：
    draft_chapter.py     —— 写一章（带反模式规则）
    run_drafts.py        —— 批量按序写章

  Evaluation：
    evaluate.py          —— 机械 slop 扫描 + LLM 裁判
                            模式：--phase=foundation, --chapter=N, --full

  Revision：
    adversarial_edit.py  —— "砍 500 字"裁判 → 分类切口
    compare_chapters.py  —— 章节两两 Elo 锦标赛
    reader_panel.py      —— 4 人读者评审团
    gen_revision.py      —— 按修订 brief 重写章节
    build_arc_summary.py —— 从章节重建 arc_summary.md
    build_outline.py     —— 从章节重建 outline.md

  Export：
    typeset/novel.tex    —— LaTeX 模板（xeCJK + 思源宋体）
    typeset/build_tex.py —— chapters/*.md → chapters_content.tex

  Orchestrator：
    run_pipeline.py      —— 完整自动化编排器
```

---

## 每部小说分支（自动生成）

下面这些都在分支上自动创建：

```
seed.txt               —— 选定的种子概念
world.md               —— 填好的世界观
characters.md          —— 填好的人物名册
outline.md             —— 填好的章节大纲 + 伏笔账本
voice.md Part 2        —— 发现的文风身份
canon.md               —— 累积的硬事实
MYSTERY.md             —— 中心谜团（仅作者）
chapters/ch_*.md       —— 散文
state.json             —— 当前阶段、分数、债务
results.tsv            —— 实验日志（每次 keep / discard）
arc_summary.md         —— 供评审团使用的章节摘要
edit_logs/*.json       —— 对抗式切口、评审团结果、锦标赛
eval_logs/*.json       —— 完整评估结果
briefs/*.md            —— 修订 brief（输入 gen_revision.py）
typeset/novel.pdf      —— 排版好的 PDF
```

---

## 流水线

### Phase 0：准备

```
INPUT：seed.txt（用户提供，或经 seed.py 生成）
OUTPUT：分支已建，.env 已配

1. git checkout -b autonovel/<tag>
2. 核对 .env 含一个 LLM API key（ANTHROPIC_API_KEY 或 OPENAI_API_KEY）
3. 核对 seed.txt 存在且**足够具体**
   （世界差异点、中心张力、代价 / 限制、感官钩子）
```

### Phase 1：基础

```
INPUT：seed.txt
OUTPUT：world.md, characters.md, outline.md, voice.md, canon.md, MYSTERY.md
EXIT：foundation_score > 7.5 且 lore_score > 7.0

LOOP：
  1. gen_world.py        → world.md（设定、思辨系统、地理、派系）
  2. gen_characters.py   → characters.md（创伤 / 欲望 / 需要 / 谎言、口吻、三杆）
  3. gen_outline.py      → outline.md part 1（节拍、章节结构）
  4. gen_outline_part2.py → outline.md part 2（伏笔账本）
  5. 文风发现：以不同语域写 5 段试笔，选最佳，填 voice.md Part 2
     —— 范文段落 + 反范文段落
  6. 定 MYSTERY.md（读者将逐渐发现的中心秘密）
  7. gen_canon.py        → canon.md（交叉核对所有硬事实）
  8. evaluate.py --phase=foundation
  9. 分数提升 → git commit。下降 → git reset --hard HEAD~1。
  10. 找出最弱维度 → 下一轮针对它。

经验要点：
  - 基础阶段通常需要 5-15 轮
  - 评估器对**设定互联**加权 40% —— 思辨系统必须影响政治，历史必须解释派系，
    地理必须塑造文化
  - 每轮都要做跨层一致性核查
  - canon 在退出基础阶段前应至少有 400+ 条
  - 文风发现是**子循环**：写试笔，评估，选定，精修
```

### Phase 2：初稿

```
INPUT：所有基础文档
OUTPUT：chapters/ch_01.md ... ch_NN.md
EXIT：所有章节起草完毕，每章 score > 6.0

FOR 每一章（按大纲顺序）：
  1. 加载上下文：
     - voice.md（完整）
     - world.md（完整）
     - characters.md（完整）
     - 本章大纲条目
     - 上一章末 ~1000 字
     - 下一章大纲（用于连贯）
  2. draft_chapter.py → chapters/ch_NN.md
  3. evaluate.py --chapter=NN
  4. score > 6.0 → 保留，commit；< 6.0 → 丢弃，重试（最多 5 次）
  5. 从评估输出中抽取新事实 → 追加到 canon.md
  6. 记入 results.tsv

起草后清理：
  7. 机械 slop 扫描（evaluate.py 正则）扫所有章节
  8. 修复早期章节中已识别的 AI 模式（这些模式会**累积** —— 修订前先修它们）
  9. 把 state.json phase 更新为 "revision"

经验要点：
  - **前进比完美重要**。6.0 分够了。
  - 早段（Ch 1-6）通常比后段（7+）分数高（"新鲜感衰减"）。
    Ch 6 之后给 writer prompt 加更严格的反模式规则。
  - 后半批量起草（Ch 11+） —— 速度更快，质量足够稳。
  - 机械 slop 扫描会捕获约 200 处 Tier 1 禁词、双破折号过度、句长齐整。
  - 起草总时长：25 章约 8-16 小时 API 时间。
```

### Phase 3：修订

真正的质量提升在这里。3-6 个循环，每个循环有具体焦点。**连续 2 个循环分数稳定即停**。

```
循环 1：基线诊断

  1. adversarial_edit.py all
     → edit_logs/chNN_cuts.json（所有章节）
     → 识别系统性模式（OVER-EXPLAIN 通常占 30-35%）
  2. compare_chapters.py
     → edit_logs/tournament_results.json（Elo 排名）
  3. 应用顶层切口：
     重点：OVER-EXPLAIN + REDUNDANT（合计约 55-60%）
     目标：脂肪率 > 17% 的章节
     方法：自动引用匹配删除
     预期：砍 ~2000-3000 字（约小说 3-4%）
  4. reader_panel.py
     → edit_logs/reader_panel.json
     4 个 persona：编辑、类型读者、作家、普通读者
     每位回答：推力流失、应得结尾、可砍候选、缺失场景、
       最薄人物、最佳场景、最弱场景、是否推荐、留下回响、下一本
  5. 找**共识项**（3/4 或 4/4 同意）：
     这些是修订优先级。
  6. git commit："循环 1：对抗式 + 评审团基线"
```

```
循环 2-3：结构性修订（处理评审团共识）

  对每个共识项，按优先级：
    a. 可砍候选（4/4 同意）：
       写压缩 brief → gen_revision.py
       目标：砍掉本章 40-60% 字数
       保留：评审团识别出的 2-3 个核心节拍
       警告：**别压缩过度**。任何章节 1700 字以下都太薄。
       甜点：被压缩章节 2200-3000 字。

    b. 缺失场景（4/4 同意）：
       为目标章写扩展 brief → gen_revision.py
       或：< 400 字的场景做外科补丁
       要点：brief 必须明确说明**保留**什么（既有的好部分）和**新加**什么

    c. 薄人物（4/4 同意）：
       找出 1-2 个该人物已出现的场景
       添加一处主角能捕捉到的私人 / 不设防瞬间
       连接到 characters.md 中的人物背景
       **不要**新加场景 —— **深化**已有场景

    d. 弱场景（3/4 同意）：
       写"戏剧化" brief → gen_revision.py
       改的是**怎么传达信息**，不是**传达什么**
       把"读文件"变成"调查 / 对峙"
       把"汇报"变成"带阻力的对峙"

    e. 一致性 / 时间线：
       搜矛盾（年代、年龄、事件顺序）
       修 canon.md + 所有源文件 + 章节引用
       会出现"10 年 / 12 年"这种差异。预先做好准备。

    f. 章节重编号：
       如果合并 / 删除了章节，**所有**内部标题都要更新
       用脚本，不要手动改

  每次结构性改动后：
    evaluate.py --chapter=N（受影响章节）
    分数提升 → 保留；下降 → 丢弃
    git commit，写明详细信息

  evaluate.py --full → 拿小说级分数
  git commit："循环 N：评审团结构性修订"
```

```
循环 4-5：定向改进（处理评估 callouts）

  evaluate.py --full 输出：
    - weakest_dimension（通常是 pacing_curve）
    - weakest_chapter
    - top_suggestion（具体修订建议）
    - 各维度分数与评语

  常见模式与修法：
    a. 节奏（pacing，永远的顽固分）：
       - 第二幕调查节奏重复 →
         压缩最弱的调查章，变化场景类型
       - 第三幕被压缩 → 扩展集结与高潮
       - 揭示太快 → 在揭示之间加"喘息节拍"
       警告：修一段会暴露下一段。pacing=7 可能是 LLM 评估小说的**结构上限**。

    b. 章节相对其结构重要性而言**太短**：
       写扩展 brief → gen_revision.py
       目标：+800-1500 字
       重点：身体堆积、恐惧、有持续时长的沉默
       brief 必须指明**扩展什么节拍**，而非"写更长"

    c. 跨章节重复短语：
       搜索短语在所有章节中的出现
       把除最有冲击力的实例外的所有改写
       常见 AI 重复：开篇描写、情感公式、"那种 X 的方式"、三件套

    d. 未回收线索：
       检查 outline.md 中的伏笔账本
       在已植入但未回收的位置加回收节拍
       外科补丁，非全章重写

  修后：
    evaluate.py --full → 检查分数提升
    weakest_chapter 变了 → 上一轮修对了
    连续 2 轮分数无变化 → 停，边际收益递减
```

```
循环 6：抛光（终轮）

  1. adversarial_edit.py all → 在重写章节上拿到新切口数据
  2. 应用循环 2-5 中重写过的章节的切口
  3. Slop pass：evaluate.py 单章扫描重写章节
  4. reader_panel.py → 终验
  5. 重建 founding 文档
```

```
PHASE 3b：OPUS 评审循环（深度散文级精修）

  自动循环之后，切到 Opus（或同档评审模型）做最后的质量推进。
  这是真正能捕捉到散文问题、结构性重复、人物浅薄、伦理空白的评估。

  工具：review.py
  模型：Claude Opus（文学分析当前最佳）
  Prompt：
    "阅读下面这部中文长篇小说《{title}》。先以**文学评论家**身份评论
     （报纸书评的风格），再以**文学教授**身份给出针对具体瑕疵的、
     **可执行**的修改建议。公允但诚实。你不一定要找瑕疵。"

  循环（最多 4 轮）：
    1. review.py --output reviews.md
       发整本到 Opus。拿双角色评审。
    2. review.py --parse
       抽取可执行项、严重度、类型。
       把项分类：major / moderate / minor，qualified / unqualified。
    3. **停止条件**：
       停 if：无重大未边际化项
       停 if：> 50% 项已被边际化（hedged）
       停 if：≤ 2 项
       这些信号意味着评审者已找不到真正的问题。
    4. 处理顶项：
       - gen_brief.py --auto → 选最弱章，生成 brief
       - gen_revision.py → 按 brief 重写章节
       - 机械修复（apply_cuts.py）处理模式问题
       - 外科补丁处理定向新增
    5. commit，重复。

  经验要点（来自原版项目的 6 轮评审）：
    - 同样的问题会**反复出现**直到被修。这是行动信号。
    - 当语言从"小说有问题"转向"这些是雄心的代价" → 停止修订。
    - 评审者**总会**找到些什么。停止条件是关于**严重度与边际化**，
      不是零瑕疵。
    - 持续出现 3+ 轮的项可能是**小说声音 / 路径的结构性产物**，不是 bug。
      学会接受它们。
    - 评审者的项严重度是指南：
      多个重大项 → 需要结构性工作
      少数重大、若干 moderate → 定向修订，再 2-3 轮
      全部 moderate / minor → 仅抛光，再 1-2 轮
      多为边际化 → 完成，发吧
```

### Phase 4：导出

```
1. 规范章节标题（所有 # 层级，统一格式）
2. typeset/build_tex.py → chapters_content.tex
3. 编辑 typeset/novel.tex：
   - 设标题、作者
   - 选题词（来自小说本身，不剧透）
   - 设末页文字
4. xelatex novel.tex → novel.pdf（中文需要 xelatex 而非 tectonic）
5. git commit："Export：[书名] —— [字数] 字"
```

---

## 关键经验

### 评估器奖赏什么

- **主题一致性**触顶（10）较早，如果种子有强中心问题。把思辨系统**做成**主题。
- **文风一致性**（9）保持，如果你**从不**违反 POV 且让叙事词汇本土化。
- **伏笔**（9）需要从基础到起草都维护账本。每根植入都要有兑现。

### 评估器扣什么

- **节奏**（7）是结构性顽固分。调查类章节（去-学-被堵）的节奏会被评估器抓到。
  修一段，它发现下一段。除非重构剧情，**接受 7 是上限**。
- **OVER-EXPLAIN** 是 #1 AI 写作模式（约 32% 的对抗式切口）。叙述者解释场景已展示的事。**砍**。
- **REDUNDANT** 是 #2（约 26%）。同一洞察重述 3-4 次。一次就够。
- **中文专属**：成语堆 / ABB 副词病 / 心眸唇眉四件套 / "X 道"对话标记滥用 / 翻译腔。
  详见 ANTI-SLOP.md。

### 评审团能捕捉到评估器抓不住的

- "勾选式同意" —— 盟友们没有摩擦地全部同意
- 关键人物之间缺失的情绪场景
- "更像机器而不像人"的人物
- 应当更乱、更人、更少编排的场景
- "工作"与"活着"之间的差别

### 危险模式

- **过度压缩**：把章节砍到 1800 字以下会让它成为新的最弱。甜点是 2200-3000 字。
- **扩展膨胀**：gen_revision.py 加的字数比 brief 多约 30%。目标 3200 字 → 实际 3800-4200 字。
- **追分**：循环 4 之后，修一个分数往往让另一个掉下来。
- 评估器**轮流**说"weakest chapter" —— 追它是打地鼠。轮 2 次后，停。

### 时间估计

| 阶段 | API 时间 |
|---|---|
| Phase 1（基础） | 2-4 小时，5-15 轮 |
| Phase 2（初稿） | 8-16 小时，23-30 章 |
| Phase 3（修订） | 4-8 小时，3-6 个循环 |
| Phase 4（导出） | 30 分钟 |
| **总计** | **~15-30 小时**（75k 字小说） |

---

## Orchestrator（run_pipeline.py 规范）

```python
# 完整自动化流水线伪代码

def run_pipeline(seed_path, tag="run1"):
    setup(tag, seed_path)

    # Phase 1
    while state.foundation_score < 7.5 or state.lore_score < 7.0:
        weakest = evaluate_foundation()
        improve_layer(weakest)
        score = evaluate_foundation()
        if score > state.foundation_score:
            commit(f"foundation: improve {weakest}")
            state.foundation_score = score
        else:
            reset()

    state.phase = "drafting"

    # Phase 2
    for ch in range(1, state.chapters_total + 1):
        for attempt in range(5):
            draft_chapter(ch)
            score = evaluate_chapter(ch)
            if score > 6.0:
                commit(f"drafting: ch {ch} score {score}")
                break
            else:
                reset()
        mechanical_slop_pass(ch)

    state.phase = "revision"

    # Phase 3
    prev_score = 0
    for cycle in range(1, 7):
        # 诊断
        cuts = adversarial_edit_all()
        apply_top_cuts(cuts, types=["OVER-EXPLAIN", "REDUNDANT"])
        panel = run_reader_panel()

        # 结构性修订
        for item in panel.consensus_items():
            brief = generate_brief(item, panel, cuts)
            revise_chapter(item.chapter, brief)
            if evaluate_chapter(item.chapter) > previous:
                commit(f"cycle {cycle}: {item.type}")
            else:
                reset()

        # 全本评估
        score = evaluate_full()
        if abs(score - prev_score) < 0.5 and cycle >= 3:
            break  # 平台期
        prev_score = score

        # 评估 callouts 的定向修订
        fix_eval_callouts(score.top_suggestion)
        slop_pass(rewritten_chapters)

        commit(f"循环 {cycle} 完成：分数 {score}")

    # Phase 4
    rebuild_docs()
    typeset()
    export()
```

---

*本流水线源自原版项目 60+ 次提交、5 个修订循环、2 次评审团、2 次对抗式编辑、约 20 小时 agent 时间产出 75,000 字奇幻长篇的实战经验，并针对中文小说写作做了完整的 prompt、slop 词表、文档与排版重新校准。*
