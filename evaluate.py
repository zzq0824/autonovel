#!/usr/bin/env python3
"""
evaluate.py -- Novel evaluation harness.

Usage:
  python evaluate.py --phase=foundation    # Score planning docs only
  python evaluate.py --chapter=5           # Score a single chapter
  python evaluate.py --full                # Score the entire novel

Output: structured scores to stdout + eval_logs/<timestamp>.json

This file is READ-ONLY during autonomous runs. The human edits it
to tune what "good" means. The agent treats it as a black box.
"""

import argparse
import json
import os
import sys
import glob
import re
from datetime import datetime
from pathlib import Path

# --- Configuration ---
BASE_DIR = Path(__file__).parent

# Load .env file if present
from dotenv import load_dotenv
load_dotenv(BASE_DIR / ".env")

# Judge uses Opus 4.6 (harsh, critical). Writer uses Sonnet 4.6 (fast, long context).
# Intentionally different to avoid self-congratulation.
JUDGE_MODEL = os.environ.get("AUTONOVEL_JUDGE_MODEL", "claude-opus-4-6")
CHAPTERS_DIR = BASE_DIR / "chapters"
EVAL_LOG_DIR = BASE_DIR / "eval_logs"
EVAL_LOG_DIR.mkdir(exist_ok=True)


# ---- 机械 slop 检测（不调 LLM）----
# 中文版：识别中文 AI 写作的统计性露馅信号。

TIER1_BANNED = [
    # AI 写中式奇幻最爱用的"成语堆"
    "璀璨", "斑斓", "波光粼粼", "金光闪闪", "炯炯有神", "深邃",
    "绝美", "惊鸿", "举世无双", "举足轻重", "不容忽视",
    "淋漓尽致", "栩栩如生", "跃然纸上", "鳞次栉比",
    "川流不息", "络绎不绝", "一应俱全", "五光十色",
    "美轮美奂", "登峰造极", "巧夺天工", "叹为观止",
    "气势磅礴", "蔚为壮观",
]

TIER2_SUSPICIOUS = [
    # ABB 副词病 / 网文填料 —— 单用没问题，同段三个以上要重写
    "缓缓", "悠悠", "淡淡", "微微", "轻轻", "深深", "紧紧",
    "渐渐", "默默", "静静", "幽幽", "袅袅", "淙淙",
    "潺潺", "凛冽", "清冷", "肃穆", "庄严", "凝重",
    "复杂", "微妙", "意味深长",
]

TIER3_FILLER = [
    # AI 议论文式套话 —— 见即删
    r"值得(?:一提|注意)的是",
    r"不容忽视(?:的是)?",
    r"举足轻重",
    r"归根结底",
    r"综上所述",
    r"毋庸置疑",
    r"由此可见",
    r"众所周知",
    r"显而易见",
    r"不言而喻",
    r"从某种(?:意义|程度)上(?:讲|说|来说)",
    r"总(?:的|而言之)",
    r"换(?:言|而言)之",
    r"在(?:某种|一定)程度上",
    r"不仅(?:仅)?\s*\S+\s*[,，]?\s*而且",
    r"一方面\s*\S+\s*[,，]?\s*另一方面",
]

TRANSITION_OPENERS = [
    "然而", "此外", "另外", "再者", "因此", "于是",
    "可是", "不过", "进而", "更何况",
]

# 中文小说 AI tells —— 「心眸唇眉」四件套是重灾区
FICTION_AI_TELLS = [
    r"眼眶(?:湿润|泛红|发红)",
    r"心如刀绞",
    r"肝肠寸断",
    r"脸色(?:苍白|煞白|惨白|铁青)",
    r"面色凝重",
    r"眉头紧(?:锁|蹙|皱)",
    r"倒吸(?:了)?一口(?:冷|凉)气",
    r"心(?:头|中|里)一(?:颤|紧|沉|凛|跳)",
    r"嘴角(?:微微|轻轻)?(?:上扬|勾起|扬起)",
    r"眸(?:光|中)(?:流转|闪动|微闪|一闪)",
    r"(?:深|长|轻)(?:吸|呼)了一口气",
    r"目光(?:如炬|灼灼|凌厉|深邃)",
    r"嘴唇(?:微微|轻轻)?(?:颤抖|发白)",
    r"心(?:跳|脏)(?:加速|漏跳了一拍|猛地一沉)",
    r"(?:乌黑|墨色|金色)的?长?发(?:如|似)瀑(?:布)?般(?:垂落|散开)",
    r"(?:他|她)的?身(?:子|体|形)(?:微微|不由)?一(?:震|颤|僵)",
    r"(?:寒|凉)意(?:从|自).{0,4}(?:升起|涌上|蔓延)",
]

# 中文版"我不是 X，我是 Y"修辞癖
STRUCTURAL_AI_TICS = [
    r"不是\s*\S{2,20}\s*[,，。]\s*而是",          # 不是X，而是Y
    r"与其(?:说(?:是)?)?\s*\S{2,20}\s*[,，]?\s*不如(?:说)?",
    r"看似\s*\S{2,20}\s*[,，]?\s*(?:实则|实际上)",
    r"表面上\s*\S{2,20}\s*[,，]?\s*(?:背后|实质)",
    r"既\s*\S{2,15}\s*又\s*\S{2,15}\s*更\s*\S{2,15}",  # 三联排比
]

# 直陈情绪 + ABB 副词病 + 三连"的"
TELLING_PATTERNS = [
    # 他/她/我/某Name + (感到|觉得|心想|不禁|忽然) + 情绪词
    (r"(?:他|她|我|你|[一-鿿]{1,3})"
     r"(?:感到|觉得|心想|心中|心里|不禁|忽然|有些)"
     r"(?:愤怒|生气|悲伤|难过|开心|喜悦|害怕|恐惧|紧张|兴奋|嫉妒|愧疚|"
     r"焦虑|孤独|绝望|失望|愤恨|羞愧|骄傲|苦涩|挫败|得意|惊讶|震惊|无奈)"),
    # ABB 副词 + 动词
    (r"(?:深深|紧紧|缓缓|悠悠|淡淡|微微|轻轻|渐渐|默默|静静|幽幽)地?\s*"
     r"(?:看|望|凝视|叹|笑|说|想|握|抱|靠|站|坐|走|跑|拥|抚摸|触碰)"),
    # 三连"的"
    r"\S+的\S+的\S+的\S+",
]

# 对话标记滥用：现代中文小说传统极少用 "X道"
SAID_TAGS = [
    r"(?:说|道|问|答|喝|叹|吼|嘟囔|嘀咕|嗤笑|冷笑|苦笑|低声|轻声)道"
]


def slop_score(text):
    """
    机械 slop 检测（中文）。返回字典：
      - tier1_hits: list of (word, count)
      - tier2_hits: list of (word, count)
      - tier3_hits: list of (pattern, count)
      - em_dash_density: 双破折号 per 1000 字
      - sentence_length_cv: 句长变异系数（越高越像活人）
      - transition_opener_ratio: 段首过渡词比例
      - said_tag_density: "X道"对话标记 per 1000 字（应稀少）
      - slop_penalty: 0-10 总分（0 = 干净，10 = 灾难）
    """
    char_count = len(re.findall(r'[一-鿿]', text)) or 1

    # Tier 1：子串包含计数（中文不能 token-equality）
    tier1_hits = []
    for w in TIER1_BANNED:
        c = text.count(w)
        if c > 0:
            tier1_hits.append((w, c))

    # Tier 2：段落级聚类
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    tier2_hits = []
    tier2_cluster_count = 0
    for w in TIER2_SUSPICIOUS:
        c = text.count(w)
        if c > 0:
            tier2_hits.append((w, c))
    for para in paragraphs:
        hits_in_para = sum(1 for w in TIER2_SUSPICIOUS if w in para)
        if hits_in_para >= 3:
            tier2_cluster_count += 1

    # Tier 3
    tier3_hits = []
    for pattern in TIER3_FILLER:
        matches = re.findall(pattern, text, re.MULTILINE)
        if matches:
            tier3_hits.append((pattern, len(matches)))

    # 双破折号密度（中文用 "——"，比英文稀；阈值降低）
    pair_dashes = text.count("——")
    leftover_em = max(text.count("—") - 2 * pair_dashes, 0)
    em_dashes = pair_dashes + leftover_em * 0.5
    em_dash_density = (em_dashes / char_count) * 1000

    # 句长变异（按中英标点切分；只计中文字符长度）
    sentences = re.split(r'[.!?。！？]+', text)
    sentences = [s.strip() for s in sentences
                 if len(re.findall(r'[一-鿿]', s.strip())) > 4]
    if len(sentences) > 2:
        lengths = [len(re.findall(r'[一-鿿]', s)) for s in sentences]
        mean_len = sum(lengths) / len(lengths)
        variance = sum((l - mean_len) ** 2 for l in lengths) / len(lengths)
        std_len = variance ** 0.5
        sentence_length_cv = std_len / mean_len if mean_len > 0 else 0
    else:
        sentence_length_cv = 0.5

    # 段首过渡词比例（前 1-3 字）
    transition_starts = 0
    for para in paragraphs:
        opener = para[:3]
        if any(opener.startswith(t) for t in TRANSITION_OPENERS):
            transition_starts += 1
    transition_ratio = transition_starts / len(paragraphs) if paragraphs else 0

    # 中文 AI tells
    fiction_tells = []
    for pattern in FICTION_AI_TELLS:
        matches = re.findall(pattern, text)
        if matches:
            fiction_tells.append((pattern[:40], len(matches)))
    fiction_tell_count = sum(c for _, c in fiction_tells)

    # 直陈情绪 / 副词病
    telling_count = 0
    for pattern in TELLING_PATTERNS:
        telling_count += len(re.findall(pattern, text))

    # 修辞癖
    structural_tics = []
    for pattern in STRUCTURAL_AI_TICS:
        matches = re.findall(pattern, text)
        if matches:
            structural_tics.append((pattern[:40], len(matches)))
    structural_tic_count = sum(c for _, c in structural_tics)

    # "X道"密度
    said_tag_count = 0
    for pattern in SAID_TAGS:
        said_tag_count += len(re.findall(pattern, text))
    said_tag_density = (said_tag_count / char_count) * 1000

    # 综合扣分
    penalty = 0.0
    penalty += min(len(tier1_hits) * 1.5, 4.0)
    penalty += min(tier2_cluster_count * 1.0, 2.0)
    penalty += min(sum(c for _, c in tier3_hits) * 0.3, 2.0)
    if em_dash_density > 5:  # 中文阈值更低
        penalty += min((em_dash_density - 5) * 0.3, 1.0)
    if sentence_length_cv < 0.3:
        penalty += 1.0
    if transition_ratio > 0.3:
        penalty += min(transition_ratio * 2, 1.0)
    penalty += min(fiction_tell_count * 0.3, 2.0)
    penalty += min(telling_count * 0.2, 1.5)
    penalty += min(structural_tic_count * 0.5, 2.0)
    if said_tag_density > 5:  # "X道" 滥用
        penalty += min((said_tag_density - 5) * 0.2, 1.0)

    penalty = min(penalty, 10.0)

    return {
        "tier1_hits": tier1_hits,
        "tier2_hits": tier2_hits,
        "tier2_clusters": tier2_cluster_count,
        "tier3_hits": tier3_hits,
        "fiction_ai_tells": fiction_tells,
        "structural_ai_tics": structural_tics,
        "telling_violations": telling_count,
        "said_tag_density": round(said_tag_density, 2),
        "em_dash_density": round(em_dash_density, 2),
        "sentence_length_cv": round(sentence_length_cv, 3),
        "transition_opener_ratio": round(transition_ratio, 3),
        "slop_penalty": round(penalty, 2),
    }


def load_file(path):
    """Load a text file, return empty string if missing."""
    try:
        return Path(path).read_text()
    except FileNotFoundError:
        return ""


def load_layer_files():
    """Load all planning layer files."""
    return {
        "voice": load_file(BASE_DIR / "voice.md"),
        "world": load_file(BASE_DIR / "world.md"),
        "characters": load_file(BASE_DIR / "characters.md"),
        "outline": load_file(BASE_DIR / "outline.md"),
        "canon": load_file(BASE_DIR / "canon.md"),
    }


def load_chapter(n):
    """Load a single chapter file."""
    return load_file(CHAPTERS_DIR / f"ch_{n:02d}.md")


def load_all_chapters():
    """Load all chapter files in order."""
    chapters = {}
    for f in sorted(glob.glob(str(CHAPTERS_DIR / "ch_*.md"))):
        num = int(re.search(r'ch_(\d+)', f).group(1))
        chapters[num] = Path(f).read_text()
    return chapters


def call_judge(prompt, max_tokens=2000):
    """Call the configured judge LLM and return its response text."""
    import llm_client
    return llm_client.call(
        prompt,
        model=JUDGE_MODEL,
        max_tokens=max_tokens,
        temperature=0.3,
        system="你是一位文学评论家与小说编辑。"
               "你以精准的眼光评估小说。回复必须是合法 JSON。"
               "不要 markdown 代码块，不要开场白 —— 只输出那个 JSON 对象。"
               "JSON 的 key 必须保持英文（原样照抄），只在 value 字段里写中文。",
        timeout=180,
        extra_beta=True,
    )


# 防御性 fallback：模型偶尔会把英文 key "贴心地"翻译成中文。归一化映射回英文。
JSON_KEY_NORMALIZE = {
    "魔法系统": "magic_system",
    "世界历史": "world_history",
    "地理与文化": "geography_and_culture",
    "设定互联": "lore_interconnection",
    "冰山深度": "iceberg_depth",
    "人物深度": "character_depth",
    "人物辨识度": "character_distinctiveness",
    "人物秘密": "character_secrets",
    "大纲完整度": "outline_completeness",
    "伏笔平衡": "foreshadowing_balance",
    "内部一致性": "internal_consistency",
    "文风清晰度": "voice_clarity",
    "canon覆盖": "canon_coverage",
    "整体评分": "overall_score",
    "总分": "overall_score",
    "设定分": "lore_score",
    "最弱维度": "weakest_dimension",
    "前三改进": "top_3_improvements",
    "前三修订": "top_3_revisions",
    "策划文档slop": "slop_in_planning_docs",
    "矛盾": "contradictions_found",
    "弱点引用": "weakest_moment",
    "最弱句": "weakest_sentence",
    "最强句": "strongest_sentence",
    "三句最弱": "three_weakest_sentences",
    "三句最强": "three_strongest_sentences",
    "AI模式": "ai_patterns_detected",
    "新canon条目": "new_canon_entries",
    "弧线完成": "arc_completion",
    "节奏曲线": "pacing_curve",
    "主题一致": "theme_coherence",
    "伏笔回收": "foreshadowing_resolution",
    "世界观一致": "world_consistency",
    "文风一致": "voice_consistency",
    "整体投入度": "overall_engagement",
    "小说总分": "novel_score",
    "最弱章节": "weakest_chapter",
    "首要建议": "top_suggestion",
    "文风贴合": "voice_adherence",
    "节拍覆盖": "beat_coverage",
    "人物声音": "character_voice",
    "伏笔植入": "plants_seeded",
    "散文质量": "prose_quality",
    "连续性": "continuity",
    "canon符合": "canon_compliance",
    "设定融入": "lore_integration",
    "投入度": "engagement",
    "评分": "score",
    "差距": "gap",
    "弱点": "gap",
    "改进": "fix",
    "备注": "note",
    "违规": "violations",
    "发现": "found",
}


def _normalize_keys(obj):
    """递归把任何被翻译成中文的 JSON key 映回英文。"""
    if isinstance(obj, dict):
        return {JSON_KEY_NORMALIZE.get(k, k): _normalize_keys(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_normalize_keys(x) for x in obj]
    return obj


def parse_json_response(text):
    """Extract JSON from a response that might have markdown fences or trailing text."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r'^```\w*\n?', '', text)
        text = re.sub(r'\n?```$', '', text)
    # Find the outermost JSON object
    start = text.find('{')
    if start == -1:
        raise ValueError("No JSON object found in response")
    # Walk forward to find the matching closing brace
    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(text)):
        c = text[i]
        if escape:
            escape = False
            continue
        if c == '\\' and in_string:
            escape = True
            continue
        if c == '"' and not escape:
            in_string = not in_string
            continue
        if in_string:
            continue
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                return _normalize_keys(json.loads(text[start:i+1], strict=False))
    # Fallback: try loading as-is, with strict=False to handle control chars
    try:
        return _normalize_keys(json.loads(text, strict=False))
    except json.JSONDecodeError:
        # Last resort: fix common issues (literal newlines in strings)
        fixed = re.sub(r'(?<!\\)\n', '\\n', text)
        return _normalize_keys(json.loads(fixed, strict=False))


# --- Foundation Evaluation ---

FOUNDATION_PROMPT = """评估这部奇幻小说的策划文档。

评分校准（开始打分前请通读这一段）：

  9-10：一个月专注编辑也无法再提升 —— 出版级品质，你能指出它在书架上能与哪本已出版的中文长篇并列。为真正让你"惊艳"的作品保留 10 分。
  7-8： 扎实。一位有功底的作者能从这份文档直接动笔，无需再发明结构。瑕疵存在但有限可数。
  5-6： 可用但单薄。作者在写作过程中需要现场发明大量素材。重大空白或泛化选择。
  3-4： 草稿水平。问题多于答案。开始动笔前需大量补充。
  1-2： 占位 / 空壳。无法用于动笔。
  0：   空白或缺失。

  打 8 分以上要求**零**重大空白。打 9 分以上要求你**真正绞尽脑汁**才能找到瑕疵。倾向于打低分。

强制要求：每个维度在打分**之前**，你必须明确指出：
  (a) 该领域**唯一最大的**空白或弱点
  (b) 一个具体、可执行的改进，能把分数往上拉
  如果你确信不存在空白，写明你为什么这样判断。

VOICE DEFINITION（文风定义）：
{voice}

WORLD BIBLE（世界观）：
{world}

CHARACTER REGISTRY（人物名册）：
{characters}

OUTLINE（大纲）：
{outline}

CANON（已确立的硬事实）：
{canon}

交叉核查（评分前请逐项执行）：
1. 把所有示例对话句子拿来对照 ANTI-SLOP 模式：
   - 找跨人物重复出现的结构公式（"不是 X，而是 Y" / "看似 X，实则 Y" / "既 X 又 Y 更 Z"）
   - 找伪装成人物声音的 AI 修辞癖
   - 如多个人物共享同一种句法骨架，从 character_distinctiveness 扣分
2. 找**消失的负空间** —— 缺了什么？
   - 魔法系统是否存在会卡住某场具体剧情的空白？（例：高潮该如何用既有规则解决？POV 视角人物的能力边界在哪？）
   - 剧情需要某类人物却没出现？
   - 大纲索取的某些场景，世界观无法支撑？
3. 区分**便利的空白**与**刻意的悬念**：
   - 便利的：在该具体的地方写"细节不详"
   - 刻意的：作者**知道**答案，只是对**读者**保密。如果策划文档回避一个作者动笔时必须回答的问题，那是空白，不是冰山。
4. 在 canon 里**积极搜寻内部矛盾**：
   - 交叉核对日期、年龄、时间线
   - 检查人物能力是否符合魔法系统规则
   - 找文档间的事实冲突

按以下维度打分（每项必须给出 gap 与 fix）：

LORE & WORLDBUILDING（设定与世界观）：
- magic_system：硬规则 + 代价 + 限制（按桑德森第二定律 / Sanderson's Second Law）。作者能否**只用已确立的规则**解决高潮冲突？代价是否驱动剧情而非装饰？是否有至少 3 项被具体探讨过的社会影响？系统**可被测试**吗 —— 你能否在不发明新规则的前提下写出一场法庭辩论、一桩契约谈判、一次魔法对决？
- world_history：能造成**当下**张力的事件时间线。每一段历史都该映射到当前某个派系冲突或人物动机。装饰性历史（酷但与剧情无关）扣分而非加分。
- geography_and_culture：地点须有独特的感官签名。文化须有能**生成冲突**的具体习俗。经济结构须制造阶级张力。检查：基于这份文档，两个不同地点的两场戏能否因"地点本身"而读来截然不同？
- lore_interconnection：动一个元素，是否会逼迫至少另外两个元素发生改变？心算移除魔法系统 —— 政治结构会崩塌吗？阶级体系会变吗？如果元素是模块化、可拆解的，得低分。
- iceberg_depth：暗示的深度 vs 已言明的深度。但要核查：作者是真的知道这些秘密的答案，还是在打太极？如果策划文档说"这个谜团稍后揭晓"却不写明**揭的是什么**，那是穿着冰山外衣的空白。

CHARACTER（人物）：
- character_depth：创伤 / 欲望 / 需要 / 谎言（Wound·Want·Need·Lie）链条要有**因果关联**，而非仅主题相关。"谎言"必须从"创伤"逻辑推出。"欲望"必须是"谎言"的错误解。"需要"必须直接对立"欲望"。检查每条链有无逻辑断点。也要检查：是否有人物**应该**有这条链却没建？
- character_distinctiveness：把示例台词的对话标记全去掉。能仅凭句法识出说话人吗？检查跨人物**重复的结构公式**（如多个角色都用"不是 X，而是 Y"或对仗骈句）。检查比喻领域是否互相重叠。检查言语模式是否反映人物背景（14 岁的少年不该听起来像 60 岁的商人）。
- character_secrets：每个主要角色的秘密一旦被揭，应改变剧情走向。模糊的秘密（"他知道得比说的多"）得分低于具体的秘密（"他知道某条规则意味着 X，而 X 会推翻 Y"）。

STRUCTURE（结构）：
- outline_completeness：每章都有节拍 / POV / 情感弧 / 试-错循环类型。Save the Cat（救猫咪）节拍出现在正确的百分比位置。空白则 0 分。仅在三幕结构存在时才给 5 分以上。
- foreshadowing_balance：每根植入的伏笔线都有规划好的回收。如果伏笔账本（foreshadowing ledger）是空的，本项 0 分 —— 不论其他文档里有多少隐含线索 —— 伏笔必须**被追踪记录**才算数。

CRAFT（手艺）：
- internal_consistency：主动搜寻矛盾。交叉核对日期、年龄、人物数量、地名。任何文档间冲突都要标记。一处重大矛盾即把本项封顶在 6 分。三处或以上封顶 4 分。
- voice_clarity：文风定义必须**具体且可执行**。范文段落必须**演示**该文风。反范文段落必须**划出**界限。检查范文对话本身是否带 AI slop（成语堆砌 / ABB 副词病 / 心眸唇眉四件套 / "X道"滥用 / 翻译腔）。一份美但**自身范文里就含 slop** 的 voice doc 已被自我削弱 —— 扣分。
- canon_coverage：事实是否被记录、追溯、足以捕捉矛盾？检查：如果作者在第五章引入了一项**新事实**，能否在 canon 中验证？canon 的颗粒度够细吗？其他文档里已知的事实，是否**有遗漏没进 canon** 的？

请用 JSON 回复（**JSON 的 key 必须保持英文，原样照抄；只在 value 字段里写中文**）：
{{
  "magic_system": {{"score": N, "gap": "最大弱点", "fix": "具体改进", "note": "..."}},
  "world_history": {{"score": N, "gap": "...", "fix": "...", "note": "..."}},
  "geography_and_culture": {{"score": N, "gap": "...", "fix": "...", "note": "..."}},
  "lore_interconnection": {{"score": N, "gap": "...", "fix": "...", "note": "..."}},
  "iceberg_depth": {{"score": N, "gap": "...", "fix": "...", "note": "..."}},
  "character_depth": {{"score": N, "gap": "...", "fix": "...", "note": "..."}},
  "character_distinctiveness": {{"score": N, "gap": "...", "fix": "...", "note": "..."}},
  "character_secrets": {{"score": N, "gap": "...", "fix": "...", "note": "..."}},
  "outline_completeness": {{"score": N, "gap": "...", "fix": "...", "note": "..."}},
  "foreshadowing_balance": {{"score": N, "gap": "...", "fix": "...", "note": "..."}},
  "internal_consistency": {{"score": N, "gap": "...", "fix": "...", "note": "..."}},
  "voice_clarity": {{"score": N, "gap": "...", "fix": "...", "note": "..."}},
  "canon_coverage": {{"score": N, "gap": "...", "fix": "...", "note": "..."}},
  "slop_in_planning_docs": {{"found": ["列出范文对话 / 文风范例 / 人物描述里发现的任何 AI slop 模式"], "note": "..."}},
  "contradictions_found": ["列出文档间的事实矛盾"],
  "overall_score": N,
  "lore_score": N,
  "weakest_dimension": "...",
  "top_3_improvements": ["按杠杆作用排序的 3 项最重要改进"]
}}

权重：lore/worldbuilding 40%，character 30%，structure 20%，craft 10%。
一部"世界观薄但大纲完整"的小说**比**"世界观深但大纲不完整"的更糟。

最终核查：如果你打了 7 分以上，重读你的 gap 列表。如果其中任何 gap 描述的问题会迫使作者在动笔时停下来发明东西，你的分数就太高了。往下调。
"""


def evaluate_foundation():
    layers = load_layer_files()
    prompt = FOUNDATION_PROMPT.format(**layers)
    raw = call_judge(prompt, max_tokens=16000)
    return parse_json_response(raw)


# --- Chapter Evaluation ---

CHAPTER_PROMPT = """对照策划文档，评估这一章奇幻小说。

评分校准：
  9-10：你读过的已出版中文奇幻里最好的章节之一。能指出它在书架上能与哪部出版小说的某一章并列；指不出，就别给 9+。
  7-8： 扎实，经过编辑润色后可出版。具体瑕疵存在，但不破坏阅读体验。
  5-6： 可用但平淡。一份合格但需大修的草稿。该具体的地方在泛化，该冒险的地方在保守。
  3-4： 重大问题。文风断裂，节拍未中，散文泛泛。
  1-2： 无法用。从头重写。

  AI 生成章节的**中位**分应当是 6。
  7 = 它做到了一份普通 AI 草稿做不到的事。
  8 = 编辑会留下它，只批注少量小问题。
  大多数维度应当落在 6-7。8 分以上留给真正的卓越。

强制要求：每个维度都必须给出：
  (a) 唯一最弱的瞬间 —— **直接引用**那句具体的话或那段段落
  (b) 怎么改 —— 具体的改写建议，不是含糊的批注
  如果你觉得"每句话都完美"，那是你没读细。

VOICE DEFINITION（文风定义）：
{voice}

WORLD BIBLE（世界观摘要）：
{world}

CHARACTER REGISTRY（人物名册）：
{characters}

CANON（已确立的硬事实 —— 违反就是 bug）：
{canon}

CHAPTER OUTLINE ENTRY（本章大纲条目）：
{chapter_outline}

PREVIOUS CHAPTER（上一章末尾约 1500 字）：
{prev_chapter_tail}

THE CHAPTER TO EVALUATE（待评章节）：
{chapter_text}

交叉核查（评分前请逐项执行）：
1. 引用测试：找出 3 句最强、3 句最弱。如果找不到 3 句弱的，是你标准定低了 —— 每章都有薄弱处。要找：本可具体却写得泛化、任何段落里的节奏单一、不来自人物经验的比喻、用陈述代替展示的情感时刻、用概述代替戏剧化的过渡。
2. 对话真实度：把所有对话**默念出来**。听起来像活人说话还是像写出来的散文？人物会说一个 14 岁少年 / 60 岁老者 / 等具体身份**真会**说的话吗？
3. 场景 vs 概述：本章多少在场景里（一刻一刻，有对话有动作）vs 多少是概述（叙述者压缩时间）？散文质量再好，概述偏多的章节在 engagement 上得低分。
4. AI 模式核查：搜以下常见 AI 写作模式：
   - 每段长度齐整
   - 观察总以三件套出现（X、Y、Z）
   - 情感节拍按表准时到达，而非令人意外
   - 人物从不说错话或相互错过
   - 描写是清单式（罗列 5 项感官细节，而不挑出 2 项最锐利的）
   - 内心独白解释场景已经展示过的事
   - "心 / 眸 / 唇 / 眉"四件套堆砌
   - 对话标记滥用（"X 道"过密）
   - ABB 副词病（深深地 / 紧紧地 / 缓缓地 + 动词）
5. 挣得 vs 给定：张力是经由场景挣来的，还是叙述者直接告诉读者？悬念是真正的隐瞒，还是人物**便利地**不去想自己本会想的事？

按以下维度打分：

- voice_adherence：散文是否贴合 voice.md Part 2？检查：句长节奏变化、词汇井（vocabulary wells）、身体先于情绪原则、被定义的具体调性。引用最强的 voice 时刻**和**最弱的 voice 时刻。是否有**任何段落**听起来像"放在任何小说里都成立"的泛化奇幻散文？是的话，封顶 7 分。

- beat_coverage：是否打中了大纲里的每一个节拍？节拍是被戏剧化还是被一句带过？被概述带过的节拍只算"半中"。分数反映节拍执行**质量**，不只是是否存在。

- character_voice：把对话标记心算去掉，能否分辨说话人？人物之间是否听起来一模一样？对话读起来像说话还是像散文？POV 视角人物听起来是"那一个具体的 X 岁少年/中年商人/老学者"，还是"年轻主角""中年配角"这种类型化的标签？有没有人说出**真实的**而非**正确的**话？从不结巴、不犹豫、不偶尔说错的人物 = AI 模式人物。

- plants_seeded：伏笔是否自然植入？太显眼的伏笔比看不见的更糟。按"融合得多好"打分，不只是"是否在场"。

- prose_quality：句式多样（量度：3 句以上连续以同样方式开头吗？）；具体性（具体名词 > 抽象名词）；比喻应来自人物经验而非辞典；情感峰值处展示而非陈述。**直接引用**最弱句并解释为什么弱。也要检查：重复短语、被倚赖的固定结构、可以删除而无损的段落。

- continuity：是否从上一章合乎逻辑地接续？情感连续性 + 剧情连续性。人物心境的轨迹对得上吗？

- canon_compliance：把**所有**事实对照 canon 核查。列出违规项。一处重大违规即把本项封顶 6 分。检查：人物名、地点、魔法系统规则、时间线、已确立事件、外貌描述。

- lore_integration：世界观在本章是**做工**还是**布景**？某场景如果把专有名词替换掉就能放进任何奇幻城市 = 封顶 5 分。

- engagement：读者愿意翻页吗？张力来自哪里 —— 剧情、人物、悬念、散文？有让人**意外**的瞬间吗？可预测的优秀仍是可预测。8 分以上仅当本章做了某件出乎意料之事。

请用 JSON 回复（**JSON 的 key 必须保持英文，原样照抄；只在 value 字段里写中文**）：
{{
  "voice_adherence": {{"score": N, "weakest_moment": "直接引用具体段落", "fix": "如何改", "note": "..."}},
  "beat_coverage": {{"score": N, "weakest_moment": "...", "fix": "...", "note": "..."}},
  "character_voice": {{"score": N, "weakest_moment": "...", "fix": "...", "note": "..."}},
  "plants_seeded": {{"score": N, "weakest_moment": "...", "fix": "...", "note": "..."}},
  "prose_quality": {{"score": N, "weakest_sentence": "引用", "fix": "改写建议", "strongest_sentence": "引用", "note": "..."}},
  "continuity": {{"score": N, "note": "..."}},
  "canon_compliance": {{"score": N, "violations": ["列出发现的违规项"], "note": "..."}},
  "lore_integration": {{"score": N, "weakest_moment": "...", "fix": "...", "note": "..."}},
  "engagement": {{"score": N, "weakest_moment": "...", "fix": "...", "note": "..."}},
  "three_weakest_sentences": ["引用 1", "引用 2", "引用 3"],
  "three_strongest_sentences": ["引用 1", "引用 2", "引用 3"],
  "ai_patterns_detected": ["列出发现的 AI 写作模式"],
  "overall_score": N,
  "weakest_dimension": "...",
  "top_3_revisions": ["具体可执行的修订 1", "修订 2", "修订 3"],
  "new_canon_entries": ["本章确立的新事实"]
}}

最终核查：如果你打了 7 分以上，重读你的 weakest_moment 引用。如果其中任何一处会被编辑画红线，你的分数就太高。AI 章节的中位是 6，8 分是出色，9 分罕见，10 分对一份初稿不存在。
"""


def evaluate_chapter(chapter_num):
    layers = load_layer_files()
    chapter_text = load_chapter(chapter_num)
    if not chapter_text.strip():
        return {"error": f"Chapter {chapter_num} is empty or missing",
                "overall_score": 0.0}

    # Extract this chapter's outline entry (rough heuristic)
    outline = layers["outline"]
    # 兼容中英文章节锚：### Ch 1: 标题 / ### 第 1 章: 标题
    ch_pattern = (rf'###\s*(?:Ch|第)\s*{chapter_num}\s*(?:章)?\b.*?'
                  rf'(?=###\s*(?:Ch|第)\s*\d|## Act|## 幕|## Foreshadowing|## 伏笔|$)')
    ch_match = re.search(ch_pattern, outline, re.DOTALL)
    chapter_outline = ch_match.group(0) if ch_match else "(outline entry not found)"

    # Load previous chapter tail
    prev_text = load_chapter(chapter_num - 1) if chapter_num > 1 else "(first chapter)"
    prev_tail = prev_text[-3000:] if len(prev_text) > 3000 else prev_text

    prompt = CHAPTER_PROMPT.format(
        voice=layers["voice"],
        world=layers["world"][:4000],  # truncate world bible
        characters=layers["characters"],
        canon=layers["canon"],
        chapter_outline=chapter_outline,
        prev_chapter_tail=prev_tail,
        chapter_text=chapter_text,
    )
    raw = call_judge(prompt, max_tokens=8000)
    result = parse_json_response(raw)

    # Mechanical slop check -- adjusts score independently of judge
    slop = slop_score(chapter_text)
    result["slop"] = slop
    if "overall_score" in result:
        adjusted = max(0, result["overall_score"] - slop["slop_penalty"])
        result["raw_judge_score"] = result["overall_score"]
        result["overall_score"] = round(adjusted, 2)

    return result


# --- Full Novel Evaluation ---

FULL_NOVEL_PROMPT = """整体评估这部完成的奇幻小说。
你有策划文档与**所有**章节摘要及它们各自的分数。

VOICE DEFINITION（文风定义）：
{voice}

WORLD BIBLE（世界观）：
{world_summary}

CHARACTER REGISTRY（人物名册）：
{characters}

OUTLINE + FORESHADOWING LEDGER（大纲与伏笔账本）：
{outline}

CHAPTER SUMMARIES AND SCORES（章节摘要与分数）：
{chapter_summaries}

按以下小说级维度打 0-10 分：
- arc_completion：人物弧线是否有令人满意的收束？
- pacing_curve：张力是否在全书范围内合理累积？
- theme_coherence：主题是否被一贯地探讨？
- foreshadowing_resolution：植入的伏笔线是否全部回收？
- world_consistency：跨章节是否有设定矛盾？
- voice_consistency：文风是否始终如一？
- overall_engagement：整本书从头到尾是否好读？

请用 JSON 回复（**JSON 的 key 必须保持英文，原样照抄；只在 value 字段里写中文**）：
{{
  "arc_completion": {{"score": N, "note": "..."}},
  "pacing_curve": {{"score": N, "note": "..."}},
  "theme_coherence": {{"score": N, "note": "..."}},
  "foreshadowing_resolution": {{"score": N, "note": "..."}},
  "world_consistency": {{"score": N, "note": "..."}},
  "voice_consistency": {{"score": N, "note": "..."}},
  "overall_engagement": {{"score": N, "note": "..."}},
  "novel_score": N,
  "weakest_dimension": "...",
  "weakest_chapter": N,
  "top_suggestion": "..."
}}
"""


def evaluate_full():
    layers = load_layer_files()
    chapters = load_all_chapters()

    if not chapters:
        return {"error": "No chapters found", "novel_score": 0.0}

    # Build chapter summaries (first/last 500 chars of each)
    summaries = []
    for num in sorted(chapters.keys()):
        text = chapters[num]
        word_count = len(text.split())
        head = text[:500]
        tail = text[-500:] if len(text) > 500 else ""
        summaries.append(
            f"Chapter {num} ({word_count} words):\n"
            f"  Opening: {head}...\n"
            f"  Closing: ...{tail}\n"
        )

    prompt = FULL_NOVEL_PROMPT.format(
        voice=layers["voice"],
        world_summary=layers["world"][:3000],
        characters=layers["characters"],
        outline=layers["outline"],
        chapter_summaries="\n".join(summaries),
    )
    raw = call_judge(prompt)
    return parse_json_response(raw)


# --- Main ---

def main():
    parser = argparse.ArgumentParser(description="Evaluate the novel")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--phase", choices=["foundation"],
                       help="Evaluate planning documents")
    group.add_argument("--chapter", type=int,
                       help="Evaluate a specific chapter number")
    group.add_argument("--full", action="store_true",
                       help="Evaluate the entire novel")
    args = parser.parse_args()

    if args.phase == "foundation":
        result = evaluate_foundation()
        score_key = "overall_score"
    elif args.chapter is not None:
        result = evaluate_chapter(args.chapter)
        score_key = "overall_score"
    elif args.full:
        result = evaluate_full()
        score_key = "novel_score"

    # Print structured output
    print("---")
    if score_key in result:
        print(f"{score_key}: {result[score_key]}")
    for key, val in result.items():
        if key == score_key:
            continue
        if isinstance(val, dict):
            print(f"{key}: {val.get('score', 'N/A')} -- {val.get('note', '')}")
        else:
            print(f"{key}: {val}")

    # Save full eval log
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    mode = args.phase or (f"ch{args.chapter:02d}" if args.chapter else "full")
    log_path = EVAL_LOG_DIR / f"{timestamp}_{mode}.json"
    with open(log_path, "w") as f:
        json.dump(result, f, indent=2)
    print(f"\neval_log: {log_path}")


if __name__ == "__main__":
    main()
