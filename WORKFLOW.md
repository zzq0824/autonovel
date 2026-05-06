# WORKFLOW

运行 autonovel 的人工分步指南。

完整技术规范见 [PIPELINE.md](PIPELINE.md)。

---

## 快速开始

```bash
# 1. 准备
cd ~/autonovel
cp .env.example .env   # 填你的 LLM API key

# 2. 生成种子概念（或自己写一份到 seed.txt）
uv run python seed.py

# 3. 为本部小说建一个分支
git checkout -b autonovel/my-novel

# 4. 运行完整流水线
uv run python run_pipeline.py --from-scratch
```

流水线会：
1. 构建世界观 / 人物 / 大纲 / 文风（Phase 1）
2. 按章顺序起草所有章节（Phase 2）
3. 通过自动修订循环 + Opus 评审进行修订（Phase 3）
4. 导出为定稿 / PDF / ePub（Phase 4）

---

## 分阶段运行

```bash
# 仅基础阶段
uv run python run_pipeline.py --phase foundation

# 仅起草
uv run python run_pipeline.py --phase drafting

# 仅修订（限制循环次数）
uv run python run_pipeline.py --phase revision --max-cycles 5

# 仅导出
uv run python run_pipeline.py --phase export
```

---

## 手动工具

### 评估
```bash
uv run python evaluate.py --phase=foundation   # 给策划文档打分
uv run python evaluate.py --chapter=5           # 单章打分
uv run python evaluate.py --full                # 全本打分
```

### 修订
```bash
uv run python adversarial_edit.py all           # 找出所有章节的可砍内容
uv run python apply_cuts.py all --types OVER-EXPLAIN REDUNDANT
uv run python reader_panel.py                   # 4 人读者评审团
uv run python review.py                         # Opus 双角色评审
uv run python gen_brief.py --auto               # 自动生成修订 brief
uv run python gen_revision.py 5 briefs/ch05.md  # 按 brief 重写某章
```

### 配图（需要 FAL_KEY）
```bash
uv run python gen_art.py style                  # 推导视觉风格
uv run python gen_art.py curate cover --n=6     # 生成 6 个封面变体
uv run python gen_art.py pick cover 3           # 选定第 3 个变体
uv run python gen_art.py ornaments-all          # 生成所有章饰
uv run python gen_art.py vectorize              # 矢量化（SVG → PDF）
uv run python gen_cover_print.py art/cover.png --canvas-width 11.889 --canvas-height 8.75 --spine-width 0.639
```

### 有声书（需要 ELEVENLABS_API_KEY）
```bash
# 先在 audiobook_voices.json 里把人物的 voice_id 占位符替换为
# ElevenLabs Voice Library 中 language: zh 的实际 ID
uv run python gen_audiobook_script.py           # 解析所有章节为脚本
uv run python gen_audiobook.py --list-voices    # 浏览可用语音
uv run python gen_audiobook.py --test 1         # 测试第 1 章
uv run python gen_audiobook.py                  # 生成全部
uv run python gen_audiobook.py --assemble       # 拼接
```

### 导出（PDF / ePub）
```bash
uv run python build_outline.py                  # 重建大纲
uv run python build_arc_summary.py              # 重建弧线摘要
python3 typeset/build_tex.py && cd typeset && xelatex novel.tex  # PDF（中文需要 xelatex 而非 tectonic）
```

> 排版前置条件：操作系统已安装 `noto-cjk` 或 `source-han-serif` 中文字体；已安装 LaTeX 包 `xeCJK`、`zhnumber`。

---

## 三个循环

```
内循环（agent，可整夜跑）：
  生成 → 评估 → 保留 / 丢弃 → 重复

外循环（你，定期检查时）：
  读结果 → 调整 program.md / evaluate.py / 层级文件
  → 让 agent 再跑一轮

评审循环（自动修订之后）：
  送 Opus → 解析评审 → 修复顶项 → 重复
  → 直到没有重大且未被边际化的问题为止
```

你**不是**在写小说。你在**编程一个会写小说的系统**。
