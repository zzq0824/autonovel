# autonovel（中文版）

一个端到端、由 AI 自动完成的中文长篇小说**写作 → 修订 → 排版 → 配图 → 有声化**流水线。
从一个种子概念开始，输出可印刷的 PDF、ePub、有声书与落地页 —— 全部由 AI agent 生成。

灵感来源 [karpathy/autoresearch](https://github.com/karpathy/autoresearch)：
同一种"修改 — 评估 — 保留 / 丢弃"循环，应用于小说创作。

> 本仓库的 `master` 分支是**英文版**框架；当前分支（`claude/review-project-logic-T4SJZ`）是**纯中文版**改造，所有 prompt、slop 词表、文档、排版均针对中文小说重新校准。

---

## 快速开始

```bash
# 克隆并进入项目
git clone <repo-url> && cd autonovel
cp .env.example .env    # 填你的 API key

# 安装依赖
uv sync

# 生成种子概念（或自己写一份到 seed.txt）
uv run python seed.py

# 运行完整流水线
uv run python run_pipeline.py --from-scratch
```

---

## 流水线五阶段

### Phase 1：基础（Foundation）
从种子概念出发，构建**世界观 / 人物 / 大纲 / 文风 / canon（硬事实库）**。
循环到 `foundation_score > 7.5`。

### Phase 2：初稿（First Draft）
按章顺序写。每章评估。`score > 6.0` 留下，否则重试（最多 5 次）。**前进比完美重要**。

### Phase 3a：自动修订
对抗式编辑（让裁判砍 500 字）→ 应用切口 → 4 人读者评审团 → 自动生成修订 brief → 重写章节。
分数稳定即停（plateau detection）。

### Phase 3b：Opus 终评循环
把整稿送给 Claude Opus（或同档模型）做**双角色**评审（文学评论家 + 文学教授）。
解析可执行项 → 修最严重的 → 重复，直到评审者找不到重大问题为止。

### Phase 4：导出
重建 outline / arc summary → LaTeX 排版（xeCJK + 思源宋体）→ 生成封面与章节插图 →
有声书脚本 → ePub → 落地页。

详见 [PIPELINE.md](PIPELINE.md)。

---

## 工具一览（27 个 Python 脚本）

### 基础阶段
| 脚本 | 用途 |
|------|------|
| `seed.py` | 生成种子概念 |
| `gen_world.py` | 种子 → 世界观 |
| `gen_characters.py` | 种子 + 世界观 → 人物名册 |
| `gen_outline.py` | 大纲（含节拍 + 伏笔） |
| `gen_outline_part2.py` | 续写大纲 + 伏笔账本 |
| `gen_canon.py` | 硬事实交叉核查 |
| `voice_fingerprint.py` | 文风量化分析 |

### 起草
| 脚本 | 用途 |
|------|------|
| `draft_chapter.py` | 写单章（带反模式规则） |
| `run_drafts.py` | 批量按序写章 |

### 评估
| 脚本 | 用途 |
|------|------|
| `evaluate.py` | 机械 slop 扫描 + LLM 裁判 |
| `adversarial_edit.py` | "砍 500 字"分析 → 分类切口 |
| `compare_chapters.py` | 章节两两对决 + Elo 排序 |
| `reader_panel.py` | 4 人读者评审团（编辑 / 类型读者 / 作家 / 普通读者） |
| `review.py` | Opus 双角色评审 + 停止条件判定 |

### 修订
| 脚本 | 用途 |
|------|------|
| `gen_brief.py` | 从反馈自动生成修订 brief |
| `gen_revision.py` | 按 brief 重写章节 |
| `apply_cuts.py` | 批量应用对抗式切口 |

### 配图与封面
| 脚本 | 用途 |
|------|------|
| `gen_art.py` | 配图流水线（风格 → 选优 → 章饰 → 矢量化） |
| `gen_art_directions.py` | 生成多样化配图方向 |
| `gen_cover_composite.py` | 封面图叠书名 |
| `gen_cover_print.py` | 印刷级整封面（Lulu / KDP 规格） |

### 有声书
| 脚本 | 用途 |
|------|------|
| `gen_audiobook_script.py` | 把章节解析成"说话人 + 文本 + 音频标记"的脚本 |
| `gen_audiobook.py` | 通过 ElevenLabs 生成多人配音 |

### 编排
| 脚本 | 用途 |
|------|------|
| `run_pipeline.py` | 全流程编排器（种子 → 完整小说） |
| `build_arc_summary.py` | 从章节重建弧线摘要 |
| `build_outline.py` | 从章节重建大纲 |

---

## 文件结构

```
框架（可复用，在 master / 本分支）：
  llm_client.py          — 统一 LLM 客户端（Anthropic + OpenAI 兼容）
  program.md             — 各阶段的 agent 指令
  CRAFT.md               — 叙事手艺教育（情节、人物、世界观、散文）
  ANTI-SLOP.md           — 词级 AI 露馅检测
  ANTI-PATTERNS.md       — 结构性 AI 模式检测
  PIPELINE.md            — 完整自动化规范
  WORKFLOW.md            — 人工分步指南

模板（每部小说在分支上填写）：
  voice.md               — Part 1：底线（永久）；Part 2：本书声音（每书生成）
  world.md               — 世界观文档
  characters.md          — 人物名册
  outline.md             — 章节大纲
  canon.md               — 硬事实数据库
  MYSTERY.md             — 中心谜团（仅作者）
  state.json             — 流水线状态

排版：
  typeset/novel.tex      — LaTeX 模板（xeCJK + 思源宋体，简体中文）
  typeset/build_tex.py   — 章节 → LaTeX（含矢量章饰）
  typeset/epub_*         — ePub 元数据 / CSS / 前后护页

配图与封面：
  audiobook_voices.json  — 角色 → ElevenLabs voice ID 映射
  landing/index.html     — 响应式落地页模板

配置：
  .env.example           — API key 模板（Anthropic / OpenAI / fal.ai / ElevenLabs）
  pyproject.toml         — Python 依赖
```

---

## 工作原理

小说被建模为**五个互相演化的层**：

```
  Layer 5: voice.md          — 怎么写（HOW）
  Layer 4: world.md          — 有什么（WHAT EXISTS）
  Layer 3: characters.md     — 谁在做（WHO ACTS）
  Layer 2: outline.md        — 发生什么（WHAT HAPPENS）
  Layer 1: chapters/ch_NN.md — 实际散文
  贯穿层： canon.md           — 什么是真的（WHAT IS TRUE）
```

变更**双向传播**：上层改了要触发下层重写（设定改 → 大纲改 → 章节改），下层写出空缺也会回溯上层（写到才发现某个细节没设定）。流水线在 `state.json` 里追踪传播债务（debts）。

### 两套"免疫系统"

1. **机械检测**（`evaluate.py`，不调 LLM）：正则扫描中文 AI 禁词、网文成语堆、ABB 副词病、心眸唇眉四件套、"X 道"对话标记滥用、翻译腔、句长齐整。
2. **LLM 裁判**（`evaluate.py`，独立模型）：评散文质量、文风贴合度、人物辨识度、节拍覆盖。

### Opus 评审循环

在自动修订循环之后，整本稿子送给评审模型：

> "请阅读这部中文长篇小说《{title}》。先以**文学评论家**身份评论它（报纸书评的风格），再以**文学教授**身份给出针对具体瑕疵的、**可执行**的修改建议。公允但诚实。你不一定要找瑕疵。"

双角色评审能捕捉自动工具捕捉不到的东西：散文层面的重复、人物的浅薄、伦理空白、结构上的单调。循环持续到评审者剩下的多是"qualified hedge"（边际化的次要问题）而非真正的重大问题。

---

## API key

需要一个 LLM key + 两个可选服务 key：

| 服务 | key | 用途 |
|------|-----|------|
| LLM | `ANTHROPIC_API_KEY` 或 `OPENAI_API_KEY` 或 `AUTONOVEL_API_KEY` | 写作、评估、评审 |
| fal.ai | `FAL_KEY` | 封面与章节插图（Nano Banana 2） |
| ElevenLabs | `ELEVENLABS_API_KEY` | 多音色有声书 |

把 `.env.example` 复制成 `.env`，填进 key。**只有 LLM key 是必需的**；配图与有声书可选。

### LLM 服务商

`llm_client.py` 同时讲 **Anthropic Messages** 与 **OpenAI Chat Completions** 两种协议。靠 `AUTONOVEL_API_BASE_URL` 选服务商：

| 服务商 | Base URL |
|---|---|
| Anthropic（默认） | `https://api.anthropic.com` |
| OpenAI | `https://api.openai.com/v1` |
| DeepSeek | `https://api.deepseek.com` |
| Ollama（本地） | `http://localhost:11434/v1` |
| vLLM / LiteLLM（本地） | `http://localhost:8000/v1` |

服务商**自动从 base URL 检测**（URL 里有 `anthropic` → 走 Anthropic 原生协议；其他 → 走 OpenAI Chat Completions）。
需要时用 `AUTONOVEL_API_PROVIDER=anthropic|openai` 显式覆盖。
模型名通过 `AUTONOVEL_WRITER_MODEL` / `AUTONOVEL_JUDGE_MODEL` / `AUTONOVEL_REVIEW_MODEL` 设置。

1M 上下文 beta（`anthropic-beta: context-1m-2025-08-07`）只在 Anthropic 模式下发送 —— 切到 OpenAI 兼容端点时会被静默忽略。中文长稿（80k 字 ≈ 130k tokens）做全本评审时建议优先 Anthropic + Opus。

---

## 中文版的几个特殊事项

1. **机械 slop 词表已校准**：`evaluate.py` 中的禁词与正则**全部针对中文 AI 写作**重写，包括成语堆、ABB 副词病、心眸唇眉四件套、"X 道"对话标记滥用、翻译腔。
2. **西方叙事框架保留并译名**：救猫咪 / 故事圆环 / MICE / 桑德森魔法三定律等概念保留，因为 `evaluate.py` 的评分维度强耦合于这些命名节拍。`CRAFT.md` 同时新增了"起承转合 / 章回小说节拍 / 武侠三段式"作为补充词汇。
3. **JSON 输出契约**：所有 LLM 返回的 JSON **key 保持英文**（`magic_system`、`overall_score` 等），只翻译 prompt 文本和 value。`run_pipeline.py` 的解析逻辑依赖这些英文 key。
4. **排版字体**：`typeset/novel.tex` 使用 `xeCJK` + 思源宋体（Noto Serif CJK SC）。需要在 OS 层安装 `noto-cjk` 或等价中文字体；并安装 LaTeX 包 `xeCJK` 与 `zhnumber`（章节序号"第一章 / 第二章"渲染）。
5. **有声书语音**：ElevenLabs 中文 voice 选项有限。`audiobook_voices.json` 留的是 `REPLACE_WITH_VOICE_ID` 占位符，请到 ElevenLabs Voice Library 选 `language: zh` 的语音再填进去。

---

## 致谢

- [karpathy/autoresearch](https://github.com/karpathy/autoresearch) —— 自动化研究循环的思路源头
- Brandon Sanderson 的写作课程（魔法三定律、人物三杆）
- K.M. Weiland《Creating Character Arcs》
- Blake Snyder《救猫咪》（Save the Cat）
- Ursula K. Le Guin "From Elfland to Poughkeepsie"
- [slop-forensics](https://github.com/sam-paech/slop-forensics) 与 [EQ-Bench Slop Score](https://eqbench.com/slop-score.html)
- 中文叙事传统：《红楼梦》《聊斋志异》《镜花缘》、还珠楼主、金庸、莫言、阿来、刘慈欣、韩松等
