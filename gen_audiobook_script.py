#!/usr/bin/env python3
"""
把小说章节切分成"说话人 + 文本"的有声书脚本。

对每一章，用 LLM：
  - 识别每一句对话及其说话人
  - 把叙述部分标记为 NARRATOR
  - 根据语境为每段加 [audio tag]（情绪 / 语气）

用法：
  python gen_audiobook_script.py           # 全部章节
  python gen_audiobook_script.py 1         # 单章
  python gen_audiobook_script.py 1 5       # 章节范围

注意：本脚本依赖 audiobook_voices.json 中的角色列表 + 描述。请在运行前编辑该文件，
把你的小说人物（来自 characters.md）添加进去。说话人 key 用 ASCII（如 CASS、EDDAN），
因为它们会被用作 JSON key 与文件名片段。description 可以用中文。
"""
import os
import sys
import json
import re
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env", override=True)

WRITER_MODEL = os.environ.get("AUTONOVEL_WRITER_MODEL", "claude-sonnet-4-6")

CHAPTERS_DIR = BASE_DIR / "chapters"
AUDIO_DIR = BASE_DIR / "audiobook"
SCRIPTS_DIR = AUDIO_DIR / "scripts"

# 角色列表从 audiobook_voices.json 加载（不再硬编码原 Bells 角色）
# 文件格式：{"CASS": {"description": "...", "voice_id": "..."}, ...}
def _load_characters():
    voices_path = BASE_DIR / "audiobook_voices.json"
    if not voices_path.exists():
        return {"NARRATOR": "叙述者声音 —— 温暖、平稳、精准。以本书世界的节奏读散文。"}
    try:
        data = json.loads(voices_path.read_text())
        chars = {}
        for key, info in data.items():
            if isinstance(info, dict):
                chars[key] = info.get("description", "")
            else:
                chars[key] = str(info)
        if "NARRATOR" not in chars:
            chars["NARRATOR"] = "叙述者声音 —— 温暖、平稳、精准。以本书世界的节奏读散文。"
        return chars
    except Exception as e:
        print(f"警告：无法读取 audiobook_voices.json：{e}", file=sys.stderr)
        return {"NARRATOR": "叙述者声音 —— 温暖、平稳、精准。"}


CHARACTERS = _load_characters()

AUDIO_TAG_GUIDE = """
可用的 ElevenLabs v3 音频标记（**节省使用** —— 仅在情绪明确时打）：

情绪类（英文标记，由 ElevenLabs 模型解析）：[happy] [sad] [angry] [excited] [nervous] [calm] [worried] [frustrated] [hopeful] [tense]
表达类：[whisper] [softly] [firmly] [hesitantly] [sarcastically] [matter-of-factly] [gently]
反应类：[gasp] [sigh] [laughs] [clears throat]
音量类：[quietly] [loudly]
节奏类：[slowly] [quickly] [pause]

规则：
- 叙述：标记**极少使用**。绝大多数直接读。柔和瞬间用 [softly]，揭示用 [slowly]，悬念用 [tense]。
- 对话：根据说话人在该语境中的情绪状态选择标记。担忧的父亲与愤怒的少年听起来应当不同。
- 不要过度打标。**每段一个标记通常够了**。中性段落可不打。
- 在揭示之前 / 毁灭性台词之后用 [pause]。
- 秘密、密室戏、深夜场景用 [whisper]。

注意：标记本身保持英文（ElevenLabs API token），但被标记的文本可以是中文。
"""


def call_claude(prompt, max_tokens=8000):
    import llm_client
    return llm_client.call(
        prompt,
        model=WRITER_MODEL,
        max_tokens=max_tokens,
        temperature=0.1,
        timeout=300,
        extra_beta=True,
    )


def parse_chapter(ch_num):
    """Parse a chapter into speaker-attributed segments."""
    ch_path = CHAPTERS_DIR / f"ch_{ch_num:02d}.md"
    if not ch_path.exists():
        print(f"  Chapter {ch_num} not found", file=sys.stderr)
        return None

    text = ch_path.read_text()
    title = text.split("\n")[0].lstrip("# ").strip()
    # 字数：中文按字符计
    wc = len(re.findall(r"[一-鿿]", text)) or len(text.split())

    prompt = f"""你正在把一章中文小说切分成有声书脚本。把文本切成若干段，每段标注说话人，并可选地加上音频标记。

CHARACTERS IN THIS NOVEL（本书人物 —— 仅用此清单中出现的 key 作为说话人）：
{json.dumps(CHARACTERS, indent=2, ensure_ascii=False)}

AUDIO TAG GUIDE（音频标记指南）：
{AUDIO_TAG_GUIDE}

规则：
1. 每一段文本必须有说话人。叙述 = "NARRATOR"。
2. 每句对话必须归属到说出它的角色。
3. **去掉**对话中的引号 —— 由配音演员演绎。
4. 叙述段落保持合理长度（每段 2-4 句）。把长段落切开。
5. "X 说" / "X 道" 这种对话标记应作为**对话之后**的 NARRATOR 段，不属于角色的台词。
6. 分节符号（---）变成 {{"speaker": "NARRATOR", "text": "[pause]"}}
7. 章节标题作为首段：{{"speaker": "NARRATOR", "text": "[slowly] 第一章：标题"}}
8. 根据情感语境加音频标记。要克制 —— 大多数台词不需要标记。
9. *斜体*的内心独白由对应角色读出，标记为 [softly] 或 [whisper]。
10. 标记本身保持英文（[softly]、[pause] 等是 ElevenLabs API token），文本用中文。

输出格式：JSON 数组，每个对象含：
  "speaker"：角色 key（来自上面的清单）
  "text"：要朗读的文本（可在开头带 [audio tag]）

CHAPTER {ch_num}：「{title}」（约 {wc} 字）

{text}

只输出 JSON 数组，不要其他文字。"""

    print(f"  Ch {ch_num}: parsing '{title}' ({wc}w)...", end="", flush=True)
    result = call_claude(prompt)

    # Extract JSON from response
    result = result.strip()
    if result.startswith("```"):
        result = re.sub(r'^```\w*\n?', '', result)
        result = re.sub(r'\n?```$', '', result)

    try:
        segments = json.loads(result)
    except json.JSONDecodeError:
        # Try to fix common JSON issues from LLM output
        # 1. Remove trailing commas before ] or }
        cleaned = re.sub(r',\s*([}\]])', r'\1', result)
        # 2. Fix unescaped newlines in strings
        cleaned = cleaned.replace('\n', '\\n')
        # 3. Re-add structural newlines (between array elements)
        cleaned = cleaned.replace('\\n{', '\n{').replace('\\n]', '\n]')
        try:
            segments = json.loads(cleaned)
        except json.JSONDecodeError:
            # Last resort: extract individual objects
            print(f" (fixing JSON...)", end="", flush=True)
            segments = []
            for m in re.finditer(r'\{\s*"speaker"\s*:\s*"([^"]+)"\s*,\s*"text"\s*:\s*"((?:[^"\\]|\\.)*)"\s*\}', result):
                segments.append({
                    "speaker": m.group(1),
                    "text": m.group(2).replace('\\n', '\n').replace('\\"', '"'),
                })
            if not segments:
                print(f" PARSE ERROR", file=sys.stderr)
                (SCRIPTS_DIR / f"ch{ch_num:02d}_raw.txt").write_text(result)
                return None

    print(f" → {len(segments)} segments")
    return {
        "chapter": ch_num,
        "title": title,
        "segments": segments,
        "total_segments": len(segments),
        "speakers": list(set(s["speaker"] for s in segments)),
        "total_chars": sum(len(s["text"]) for s in segments),
    }


def main():
    SCRIPTS_DIR.mkdir(parents=True, exist_ok=True)

    # Parse args for chapter range
    chapters = sorted(CHAPTERS_DIR.glob("ch_*.md"))
    total = len(chapters)

    if len(sys.argv) == 2:
        start = end = int(sys.argv[1])
    elif len(sys.argv) == 3:
        start, end = int(sys.argv[1]), int(sys.argv[2])
    else:
        start, end = 1, total

    print(f"正在切分第 {start}-{end} 章为有声书脚本...")

    all_scripts = []
    for ch_num in range(start, end + 1):
        script = parse_chapter(ch_num)
        if script:
            # Save individual chapter script
            out_path = SCRIPTS_DIR / f"ch{ch_num:02d}_script.json"
            out_path.write_text(json.dumps(script, indent=2))
            all_scripts.append(script)

    # Summary
    print(f"\n{'='*50}")
    print(f"AUDIOBOOK SCRIPT SUMMARY")
    print(f"  Chapters: {len(all_scripts)}")
    total_segs = sum(s["total_segments"] for s in all_scripts)
    total_chars = sum(s["total_chars"] for s in all_scripts)
    all_speakers = set()
    for s in all_scripts:
        all_speakers.update(s["speakers"])
    print(f"  Total segments: {total_segs}")
    print(f"  Total characters: {total_chars:,}")
    print(f"  Speakers found: {sorted(all_speakers)}")
    print(f"  Scripts saved to: {SCRIPTS_DIR}/")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()
