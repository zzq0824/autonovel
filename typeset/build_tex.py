#!/usr/bin/env python3
"""从章节文件构建 LaTeX 源（中文版）。

用法：python build_tex.py
输出：typeset/chapters_content.tex（被 typeset/novel.tex 通过 \\input 引入）
"""
import re
import os
from pathlib import Path

# 路径相对于本文件，不再硬编码用户名
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
CHAPTERS_DIR = PROJECT_ROOT / "chapters"
OUT_DIR = SCRIPT_DIR


def latex_escape(t):
    """转义 LaTeX 特殊字符。注意：中文字符不需要特殊转义，直接通过 xeCJK 处理。"""
    t = t.replace('&', '\\&')
    t = t.replace('%', '\\%')
    t = t.replace('$', '\\$')
    t = t.replace('#', '\\#')
    t = t.replace('_', '\\_')
    return t


def md_to_latex(body):
    """Markdown → LaTeX。中文版使用「」直角引号取代英文 ``''。"""
    result = []
    for line in body.split('\n'):
        s = line.strip()
        if s == '---':
            result.append('\n\\scenebreak\n')
        elif s == '':
            result.append('')
        else:
            # *斜体* → \textit{...}（中文小说较少用斜体，但保留以兼容）
            s = re.sub(r'(?<!\*)\*([^*]+)\*(?!\*)', r'\\textit{\1}', s)
            s = latex_escape(s)
            # Unicode 标点直接保留（中文标点 xeCJK 直接渲染）
            s = s.replace('—', '——')          # — → 中文双破折号
            s = s.replace('–', '——')          # – → 也用双破折号
            s = s.replace('…', '……')          # … → 中文省略号
            # 把英文双引号 " " (U+201C/U+201D) 转中文直角引号「」
            s = s.replace('“', '「')
            s = s.replace('”', '」')
            s = s.replace('‘', '『')
            s = s.replace('’', '』')
            # ASCII 直引号也转直角引号 —— 用启 / 闭推断
            # 启："...的开头 / 标点之后 / 行首
            s = re.sub(r'(?<=\s)"(?=[一-鿿\w])', '「', s)
            s = re.sub(r'^"(?=[一-鿿\w])', '「', s)
            s = re.sub(r'(?<=[一-鿿\w,，。.?？!！])"', '」', s)
            s = re.sub(r'(?<=\s)"', '「', s)
            s = re.sub(r'"(?=\s)', '」', s)
            s = re.sub(r'^"', '「', s)
            result.append(s)
    return '\n'.join(result)


def make_drop_cap(latex_body):
    """中文 drop-cap 直接禁用（lettrine 对 CJK 字符的 bbox 不工作）。
    这里返回原文本，章首加粗效果由 novel.tex 的 \\chapterleadparagraph 提供。"""
    return latex_body


def _all_chapter_paths():
    """从 chapters/ 扫出所有 ch_*.md，按编号排序。"""
    if not CHAPTERS_DIR.exists():
        return []
    paths = []
    for p in CHAPTERS_DIR.glob("ch_*.md"):
        m = re.match(r"ch_(\d+)\.md", p.name)
        if m:
            paths.append((int(m.group(1)), p))
    paths.sort()
    return paths


def main():
    chapters_tex = []
    chapter_paths = _all_chapter_paths()
    if not chapter_paths:
        raise SystemExit(f"错误：{CHAPTERS_DIR} 下没有 ch_*.md 文件")

    for n, path in chapter_paths:
        text = path.read_text()

        lines = text.strip().split('\n')
        title_line = lines[0].lstrip('# ').strip()
        body = '\n'.join(lines[1:]).strip()

        # 章名：兼容 "Ch 1: 标题" / "第一章: 标题" / "标题"
        # LaTeX 章节内部用纯标题（不含编号），编号由 \chapter 自动生成
        if ': ' in title_line:
            label, subtitle = title_line.split(': ', 1)
        elif '：' in title_line:
            label, subtitle = title_line.split('：', 1)
        else:
            label, subtitle = title_line, ""

        chapter_name = subtitle if subtitle else label
        # 移除可能残留的编号前缀（"Ch 1"、"第一章" 等）
        chapter_name = re.sub(r'^(?:Ch(?:apter)?|第)\s*[\d一二三四五六七八九十百零]+\s*章?\s*', '',
                              chapter_name, flags=re.I).strip()
        if not chapter_name:
            chapter_name = label

        latex_body = md_to_latex(body)
        latex_body = make_drop_cap(latex_body)

        # 章饰（优先用 PDF 矢量图，回退 PNG）
        pdf_path = PROJECT_ROOT / "art" / "pdf" / f"ornament_ch{n:02d}.pdf"
        png_path = PROJECT_ROOT / "art" / f"ornament_ch{n:02d}.png"
        ornament_tex = ""
        ornament_file = None
        if pdf_path.exists():
            ornament_file = str(pdf_path)
        elif png_path.exists():
            ornament_file = str(png_path)
        if ornament_file:
            ornament_tex = (
                f"\\begin{{center}}\n"
                f"\\includegraphics[width=0.8in]{{{ornament_file}}}\n"
                f"\\end{{center}}\n"
                f"\\vspace{{0.15in}}\n"
            )

        chapters_tex.append(
            f"\\chapter{{{latex_escape(chapter_name)}}}\n\n{ornament_tex}{latex_body}\n"
        )
        print(f"  {n:2d}. {title_line}")

    content = '\n\\clearpage\n\n'.join(chapters_tex)
    out_path = OUT_DIR / "chapters_content.tex"
    out_path.write_text(content)

    print(f"\n已写入 {len(chapters_tex)} 章到 {out_path}")


if __name__ == "__main__":
    main()
