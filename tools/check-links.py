"""Целость ссылок и разметки во всех слоях волта.

Проверяет:

  * markdown-ссылки на файлы: существует ли цель (ссылки за пределы волта
    пропускаются — их проверить нечем);
  * вики-ссылки с якорем: существует ли документ и есть ли в нём такой
    заголовок дословно;
  * вики-ссылки без якоря: существует ли документ;
  * баланс ограждений ```: нечётное число означает оборванный блок кода.
    Ровно этот дефект возник 20.08.2026 при разрезании документа: комментарий
    `# ...` внутри блока кода был принят за заголовок, и половина раздела
    осталась в старом файле.

Запуск:  python3 tools/check-links.py
"""

import os
import re
import sys
from pathlib import Path

VAULT = Path(__file__).resolve().parents[1]
LAYERS = ["*.md", "Лабы/*.md", "checks/*.md", "Партнёр/*.md", "Рецепты/*.md", "Коллега/*.md"]
ALL = LAYERS + ["База знаний/**/*.md"]


def files(patterns):
    out = []
    for pat in patterns:
        out += sorted(VAULT.glob(pat))
    return out


headings = {}
for f in files(ALL):
    text = f.read_text(encoding="utf-8")
    hs = {re.sub(r"\s+", " ", m.group(1).strip())
          for m in re.finditer(r"^#{1,6}\s+(.+)$", text, re.M)}
    for key in (f.stem, str(f.relative_to(VAULT).with_suffix(""))):
        headings.setdefault(key, set()).update(hs)

problems = []
for f in files(LAYERS):
    text = f.read_text(encoding="utf-8")
    name = f.relative_to(VAULT)

    if sum(1 for l in text.split("\n") if l.lstrip().startswith("```")) % 2:
        problems.append(f"{name}: нечётное число ``` — оборванный блок кода")

    for m in re.finditer(r"\]\((?!http|#)([^)]+\.md)\)", text):
        target = os.path.normpath(os.path.join(f.parent, m.group(1)))
        if not str(Path(target)).startswith(str(VAULT)):
            continue  # ссылка наружу волта
        if not os.path.exists(target):
            problems.append(f"{name}: ссылка на несуществующий файл {m.group(1)}")

    for m in re.finditer(r"\[\[([^\]|#]+)#([^\]|]+?)\\?(?:\|[^\]]*)?\]\]", text):
        doc = m.group(1).strip()
        head = re.sub(r"\s+", " ", m.group(2).strip().rstrip("\\"))
        if doc not in headings:
            problems.append(f"{name}: вики-ссылка на несуществующий документ {doc}")
        elif head not in headings[doc]:
            problems.append(f"{name}: заголовок не найден — [[{doc}#{head}]]")

    for m in re.finditer(r"\[\[([^\]|#]+?)\\?\|", text):
        doc = m.group(1).strip()
        if doc not in headings:
            problems.append(f"{name}: вики-ссылка на несуществующий документ {doc}")

print(f"файлов проверено: {len(files(LAYERS))}")
if problems:
    print(f"замечаний: {len(problems)}")
    for p in sorted(set(problems)):
        print("  -", p)
    sys.exit(1)
print("замечаний нет")
