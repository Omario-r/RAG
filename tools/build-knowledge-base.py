"""Сборка «База знаний/» в один документ с оглавлением.

Раздел = папка верхнего уровня (или корневой файл), подраздел = файл
внутри папки. README.md папки идёт как вводный текст раздела, а не как
отдельный подраздел — его материал и так виден в оглавлении через
названия подразделов.

Все заголовки внутри файлов смещаются вниз по уровню, чтобы влиться в
иерархию сводного документа: у корневых файлов на 1 уровень (## -> ###),
у файлов внутри папки — на 2 (## -> ####), сама папка при этом на
уровне ##, а файл внутри неё — на уровне ###.

Документ идёт на конвертацию в fb2 для читалки, поэтому оглавление —
простой текст без ссылок: навигацию даёт панель «Содержание» самой
читалки, собранная из вложенности заголовков. Одинаковые заголовки
(например, несколько файлов «Словарь раздела») всё равно разрешаются
добавлением имени папки — чтобы в этой панели не было неразличимых
пунктов.

Запуск:  python3 tools/build-knowledge-base.py
"""

import re
from datetime import date
from pathlib import Path

VAULT = Path(__file__).resolve().parents[1]
KB = VAULT / "База знаний"
OUT = VAULT / "knowledge-base-combined.md"

ROOT_FILES = ["README.md"]

FENCE_RE = re.compile(r"^\s*(```|~~~)")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*$")
LINK_RE = re.compile(r"\[([^\]]+)\]\([^)]*\)")
CODE_RE = re.compile(r"`([^`]*)`")
BOLD_RE = re.compile(r"(\*\*|__)(.*?)\1")
ITALIC_RE = re.compile(r"(\*|_)(.*?)\1")


def strip_md(text):
    text = LINK_RE.sub(r"\1", text)
    text = CODE_RE.sub(r"\1", text)
    text = BOLD_RE.sub(r"\2", text)
    text = ITALIC_RE.sub(r"\2", text)
    return text.strip()


def split_h1(path):
    lines = path.read_text(encoding="utf-8").splitlines()
    i = 0
    while i < len(lines) and not lines[i].strip():
        i += 1
    m = HEADING_RE.match(lines[i]) if i < len(lines) else None
    title = strip_md(m.group(2)) if m else path.stem
    body = "\n".join(lines[i + 1:] if m else lines).strip("\n")
    return title, body


def dedup(text, context, seen):
    if text not in seen:
        seen[text] = 1
        return text
    seen[text] += 1
    candidate = f"{text} — {context}"
    if candidate not in seen:
        seen[candidate] = 1
        return candidate
    candidate = f"{candidate} ({seen[text]})"
    seen[candidate] = 1
    return candidate


def shift_body(body, shift, context, seen):
    out = []
    in_fence = False
    for line in body.split("\n"):
        if FENCE_RE.match(line):
            in_fence = not in_fence
            out.append(line)
            continue
        m = HEADING_RE.match(line) if not in_fence else None
        if m:
            level = min(len(m.group(1)) + shift, 6)
            text = dedup(m.group(2).strip(), context, seen)
            out.append(f"{'#' * level} {text}")
        else:
            out.append(line)
    return "\n".join(out)


def main():
    seen = {}
    toc = []
    body_parts = []

    for name in ROOT_FILES:
        path = KB / name
        title, body = split_h1(path)
        title = dedup(title, path.stem, seen)
        toc.append((2, title))
        body_parts.append(f"## {title}\n\n" + shift_body(body, 1, path.stem, seen))

    folders = sorted(p for p in KB.iterdir() if p.is_dir())
    for folder in folders:
        readme = folder / "README.md"
        if readme.exists():
            title, intro = split_h1(readme)
        else:
            title, intro = folder.name, ""
        title = dedup(title, folder.name, seen)
        toc.append((2, title))

        section = [f"## {title}"]
        if intro.strip():
            section.append(shift_body(intro, 1, folder.name, seen))

        files = sorted(
            p for p in folder.glob("*.md") if p.name != "README.md"
        )
        for path in files:
            sub_title, sub_body = split_h1(path)
            sub_title = dedup(sub_title, folder.name, seen)
            toc.append((3, sub_title))
            section.append(f"### {sub_title}\n\n" + shift_body(sub_body, 2, folder.name, seen))

        body_parts.append("\n\n".join(section))

    toc_lines = []
    for level, title in toc:
        indent = "  " * (level - 2)
        toc_lines.append(f"{indent}- {title}")

    doc = "\n".join([
        "# База знаний — сводный документ",
        "",
        f"Собрано скриптом tools/build-knowledge-base.py из «База знаний/» — {date.today().isoformat()}.",
        "",
        "## Оглавление",
        "",
        "\n".join(toc_lines),
        "",
        "---",
        "",
        "\n\n---\n\n".join(body_parts),
        "",
    ])

    OUT.write_text(doc, encoding="utf-8")
    print(f"записано: {OUT.relative_to(VAULT)} ({len(toc)} пунктов оглавления, {len(doc)} символов)")


if __name__ == "__main__":
    main()
