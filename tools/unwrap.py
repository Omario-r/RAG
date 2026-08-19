"""Снять жёсткие переносы в абзацах: абзац = одна строка.

Зачем: переносы стояли под колонку 75 символов, а читаем мы теперь в 1050 px —
в рендере markdown строки всё равно склеиваются, то есть перенос влиял только
на счётчик строк и на правку. Из-за него документы выглядели вдвое толще,
чем они есть, и потолок «делить длинное» мерился по ложной величине.

Трогает ТОЛЬКО обычные абзацы. Не трогает: блоки кода, таблицы, списки,
цитаты и callout-блоки, заголовки, front matter — всё, где перенос значим.

Запуск:  python3 tools/unwrap.py [--apply] [шаблон ...]
Без --apply только считает.
"""

import re
import sys
from pathlib import Path

VAULT = Path(__file__).resolve().parents[1]
SKIP_DIRS = {".git", ".obsidian", "tools"}

args = [a for a in sys.argv[1:] if not a.startswith("--")]
APPLY = "--apply" in sys.argv
PATTERNS = args or ["*.md", "Лабы/*.md", "checks/*.md", "Партнёр/*.md", "База знаний/**/*.md"]

# строка, которую нельзя склеивать с предыдущей
SPECIAL = re.compile(r"^\s*(#{1,6}\s|>|\||[-*+]\s|\d+[.)]\s|```|~~~|---\s*$|\[\^|\s{4,}\S)")


def unwrap(text: str) -> str:
    out, buf, in_fence = [], [], False
    def flush():
        if buf:
            out.append(" ".join(s.strip() for s in buf))
            buf.clear()

    for line in text.split("\n"):
        fence = line.lstrip().startswith("```") or line.lstrip().startswith("~~~")
        if fence:
            flush()
            in_fence = not in_fence
            out.append(line)
            continue
        if in_fence:
            out.append(line)
            continue
        if not line.strip():
            flush()
            out.append(line)
            continue
        if SPECIAL.match(line):
            flush()
            out.append(line)
            continue
        buf.append(line)
    flush()
    return "\n".join(out)


total_before = total_after = 0
changed = []
for pat in PATTERNS:
    for f in sorted(VAULT.glob(pat)):
        if any(p in SKIP_DIRS for p in f.parts):
            continue
        src = f.read_text(encoding="utf-8")
        dst = unwrap(src)
        b, a = len(src.split("\n")), len(dst.split("\n"))
        total_before += b
        total_after += a
        if src != dst:
            changed.append((f.relative_to(VAULT), b, a))
            if APPLY:
                f.write_text(dst, encoding="utf-8")

for name, b, a in changed:
    print(f"{b:6d} → {a:6d}   {name}")
print()
print(f"файлов затронуто: {len(changed)}; строк {total_before} → {total_after}")
print("режим:", "ПРИМЕНЕНО" if APPLY else "только подсчёт (добавь --apply)")
