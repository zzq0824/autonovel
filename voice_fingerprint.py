#!/usr/bin/env python3
"""
文风指纹：跨章节的散文定量分析。
voice.md 说"应当"成立的事，这里检查它们**是否**真的成立。

输出：edit_logs/voice_fingerprint.json，附每章指标。

注：以下三个"词汇井"是**通用中文感官 well**。如果你的小说有特定的题材
词汇井（武侠 = 兵器 / 经穴；硬科幻 = 物理 / 数学；乡土 = 农耕 / 节气），
直接编辑此文件中的 WELL_* 集合，让它们对齐你的 voice.md Part 2。
"""
import re
import json
import statistics
from pathlib import Path
from collections import Counter

BASE_DIR = Path(__file__).parent
CHAPTERS_DIR = BASE_DIR / "chapters"

# ---- 通用中文词汇井 ----
# 这些是大多数严肃文学小说会用到的"具体感官词"。
# 任何一部小说都可以用作基准。如需要题材特化，编辑下面三个集合。

WELL_BODY = {
    # 身体部位与体感
    "眼", "眼睛", "眼睑", "瞳", "目", "脸", "面", "颊", "嘴", "唇", "舌",
    "牙", "齿", "下颌", "下巴", "颈", "脖", "肩", "臂", "肘", "腕", "手",
    "指", "拳", "掌", "胸", "腹", "腰", "背", "脊", "膝", "腿", "脚", "足",
    "趾", "骨", "皮", "肉", "血", "汗", "泪", "鼻", "耳", "发", "毛",
    # 体感动词与状态
    "呼吸", "气息", "脉", "心跳", "颤", "抖", "紧", "松", "酸", "麻", "痛",
    "疼", "胀", "热", "凉", "冷", "暖", "重", "轻", "稳",
}

WELL_MATERIAL = {
    # 物质与器物
    "木", "石", "铁", "铜", "金", "银", "锡", "铅", "瓷", "陶", "玻璃",
    "丝", "麻", "棉", "皮", "革", "毛", "纸", "墨", "竹", "藤", "草",
    "土", "泥", "沙", "灰", "盐", "油", "蜡", "酒", "茶", "米", "面",
    # 工具与物件
    "刀", "斧", "锤", "锯", "钳", "钉", "针", "线", "勺", "碗", "盘",
    "锅", "瓮", "坛", "瓶", "缸", "篮", "筐", "袋", "绳", "灯", "烛",
    "钥匙", "锁", "门", "窗", "梁", "柱", "墙", "瓦", "砖", "桥", "船",
}

WELL_NATURE = {
    # 光、声、气
    "光", "影", "亮", "暗", "明", "黑", "白", "红", "黄", "蓝", "绿", "灰",
    "金", "银", "霜", "烟", "雾", "云", "尘", "雨", "雪", "风", "雷", "电",
    "声", "响", "音", "鸣", "叫", "啼", "吼", "喊", "笑", "哭", "叹",
    "嗅", "闻", "气", "味", "香", "臭", "腥", "甜", "酸", "苦", "辣",
    # 自然与时空
    "山", "川", "河", "湖", "海", "江", "溪", "井", "塘", "田", "坡", "崖",
    "石头", "树", "林", "叶", "枝", "花", "草", "藤", "果", "鸟", "兽", "鱼",
    "晨", "晚", "暮", "夜", "晓", "昏", "霞", "月", "星", "日",
}

# 抽象 / 议论文标记词（这些越多 = 越像散文论说，不像小说）
ABSTRACT_INDICATORS = {
    "感觉", "感受", "意识", "认识", "概念", "本质", "性质", "属性",
    "层面", "方面", "因素", "存在", "缺席", "意义", "含义", "可能性",
    "确定性", "不确定", "觉察", "理解", "认知", "想法", "念头", "现实",
    "状态", "情境", "情况", "局面", "事实", "原则",
}


def analyze_chapter(path):
    text = path.read_text()
    char_count = len(re.findall(r"[一-鿿]", text)) or 1
    raw_chars = list(re.findall(r"[一-鿿]", text))

    # 句子分析（中英标点都切）
    sentences = re.split(r'[.!?。！？]+', text)
    sentences = [s.strip() for s in sentences
                 if len(re.findall(r"[一-鿿]", s.strip())) > 4]
    sent_lengths = [len(re.findall(r"[一-鿿]", s)) for s in sentences]

    # 段落分析
    paragraphs = [p.strip() for p in text.split('\n\n')
                  if p.strip()
                  and not p.strip().startswith('#')
                  and p.strip() != '---']
    para_lengths = [len(re.findall(r"[一-鿿]", p)) for p in paragraphs]

    # 词汇井命中（用子串包含）
    body_count = sum(text.count(w) for w in WELL_BODY)
    material_count = sum(text.count(w) for w in WELL_MATERIAL)
    nature_count = sum(text.count(w) for w in WELL_NATURE)
    total_well = body_count + material_count + nature_count or 1

    # 抽象词
    abstract_count = sum(text.count(w) for w in ABSTRACT_INDICATORS)

    # 对话比例（中文常见的 ""「」『』）
    dialogue_matches = re.findall(
        r'(?:[""]([^""\n]*)[""])'
        r'|(?:「([^」\n]*)」)'
        r'|(?:『([^』\n]*)』)',
        text
    )
    dialogue_chars = sum(len(re.findall(r"[一-鿿]", "".join(g for g in m if g)))
                         for m in dialogue_matches)
    dialogue_ratio = dialogue_chars / char_count if char_count > 0 else 0

    # 双破折号密度（中文用 ——）
    em_dashes = text.count('——')
    em_per_1k = (em_dashes / char_count) * 1000

    # 分节符号
    section_breaks = text.count('\n---\n') + text.count('\n\n---\n\n')

    # 句首字符（统计开头的"他 / 她"等代词；不是 He/She）
    pronoun_starts = 0
    for s in sentences:
        s_strip = s.strip()
        if s_strip and s_strip[0] in "他她它":
            pronoun_starts += 1
    pronoun_start_pct = pronoun_starts / len(sentences) * 100 if sentences else 0

    # 副词病："X 地 Y" 计数（深深地、紧紧地等）
    adverb_de = len(re.findall(
        r'(?:深深|紧紧|缓缓|悠悠|淡淡|微微|轻轻|渐渐|默默|静静|幽幽)地',
        text
    ))

    # "X 道" 对话标记滥用
    said_dao = len(re.findall(
        r'(?:说|道|问|答|喝|叹|吼|嘟囔|嘀咕|嗤笑|冷笑|苦笑|低声|轻声)道',
        text
    ))

    # 短句 / 长句比例
    fragments = sum(1 for l in sent_lengths if l < 6)
    long_sents = sum(1 for l in sent_lengths if l > 30)

    # 比喻密度（"如 / 像 / 似 / 仿佛 / 犹如" 计数）
    simile_count = len(re.findall(r'(?:如|像|似|仿佛|犹如|宛如|好比)(?:一|个|是|的)', text))

    return {
        "char_count": char_count,
        "sentence_count": len(sentences),
        "paragraph_count": len(paragraphs),
        "avg_sentence_length": round(statistics.mean(sent_lengths), 1) if sent_lengths else 0,
        "sentence_length_std": round(statistics.stdev(sent_lengths), 1) if len(sent_lengths) > 1 else 0,
        "sentence_length_cv": round(
            statistics.stdev(sent_lengths) / statistics.mean(sent_lengths), 3
        ) if sent_lengths and statistics.mean(sent_lengths) > 0 else 0,
        "min_sentence": min(sent_lengths) if sent_lengths else 0,
        "max_sentence": max(sent_lengths) if sent_lengths else 0,
        "fragments_pct": round(fragments / len(sentences) * 100, 1) if sentences else 0,
        "long_sentences_pct": round(long_sents / len(sentences) * 100, 1) if sentences else 0,
        "avg_paragraph_length": round(statistics.mean(para_lengths), 1) if para_lengths else 0,
        "paragraph_length_std": round(statistics.stdev(para_lengths), 1) if len(para_lengths) > 1 else 0,
        "well_body_pct": round(body_count / total_well * 100, 1),
        "well_material_pct": round(material_count / total_well * 100, 1),
        "well_nature_pct": round(nature_count / total_well * 100, 1),
        "well_total_per_1k": round(total_well / char_count * 1000, 1),
        "abstract_per_1k": round(abstract_count / char_count * 1000, 1),
        "dialogue_ratio": round(dialogue_ratio, 3),
        "em_dash_per_1k": round(em_per_1k, 1),
        "section_breaks": section_breaks,
        "pronoun_start_pct": round(pronoun_start_pct, 1),
        "adverb_de_count": adverb_de,
        "said_dao_count": said_dao,
        "simile_density": round(simile_count / (char_count / 1000), 1),
    }


def _all_chapter_numbers():
    nums = []
    for p in sorted(CHAPTERS_DIR.glob("ch_*.md")):
        m = re.match(r"ch_(\d+)\.md", p.name)
        if m:
            nums.append(int(m.group(1)))
    return nums


def main():
    results = {}
    chapters = _all_chapter_numbers()
    if not chapters:
        print("错误：chapters/ 目录下没有 ch_*.md 文件")
        return

    for ch in chapters:
        path = CHAPTERS_DIR / f"ch_{ch:02d}.md"
        results[f"ch_{ch:02d}"] = analyze_chapter(path)

    # 全本平均
    all_vals = list(results.values())
    avg = {}
    for key in all_vals[0]:
        vals = [r[key] for r in all_vals]
        avg[key] = round(statistics.mean(vals), 2)
    results["novel_average"] = avg

    # 离群（>1.5σ）
    outliers = {}
    for key in all_vals[0]:
        vals = [r[key] for r in all_vals]
        if len(vals) > 2:
            m = statistics.mean(vals)
            s = statistics.stdev(vals)
            if s > 0:
                for ch_key, r in results.items():
                    if ch_key == "novel_average":
                        continue
                    z = (r[key] - m) / s
                    if abs(z) > 1.5:
                        if ch_key not in outliers:
                            outliers[ch_key] = []
                        direction = "HIGH" if z > 0 else "LOW"
                        outliers[ch_key].append(f"{key}: {r[key]}（{direction}, z={z:.1f}）")

    # 摘要
    print("文风指纹（VOICE FINGERPRINT）")
    print("=" * 80)
    print(f"{'章':<6} {'字数':<7} {'平均句长':<9} {'CV':<6} {'短句%':<7} {'长句%':<7} {'对话%':<7} "
          f"{'身%':<5} {'物%':<5} {'然%':<5} {'抽象/千':<8} {'X道/章':<7} {'地副/章':<7}")
    for ch in chapters:
        key = f"ch_{ch:02d}"
        r = results[key]
        print(f"  {ch:<4} {r['char_count']:<7} {r['avg_sentence_length']:<9} "
              f"{r['sentence_length_cv']:<6} {r['fragments_pct']:<7} {r['long_sentences_pct']:<7} "
              f"{r['dialogue_ratio']:<7} {r['well_body_pct']:<5} {r['well_material_pct']:<5} "
              f"{r['well_nature_pct']:<5} {r['abstract_per_1k']:<8} {r['said_dao_count']:<7} "
              f"{r['adverb_de_count']:<7}")

    r = results["novel_average"]
    print(f"  {'平均':<4} {r['char_count']:<7} {r['avg_sentence_length']:<9} "
          f"{r['sentence_length_cv']:<6} {r['fragments_pct']:<7} {r['long_sentences_pct']:<7} "
          f"{r['dialogue_ratio']:<7} {r['well_body_pct']:<5} {r['well_material_pct']:<5} "
          f"{r['well_nature_pct']:<5} {r['abstract_per_1k']:<8} {r['said_dao_count']:<7} "
          f"{r['adverb_de_count']:<7}")

    print(f"\n\n离群点（>1.5σ）：")
    for ch_key in sorted(outliers.keys()):
        print(f"  {ch_key}：")
        for o in outliers[ch_key]:
            print(f"    {o}")

    # 保存结果
    out_path = BASE_DIR / "edit_logs" / "voice_fingerprint.json"
    out_path.parent.mkdir(exist_ok=True)
    with open(out_path, "w") as f:
        json.dump({"chapters": results, "outliers": outliers}, f, indent=2, ensure_ascii=False)
    print(f"\n已保存到 {out_path}")


if __name__ == "__main__":
    main()
