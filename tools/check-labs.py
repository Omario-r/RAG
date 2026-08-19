"""Механическая проверка лаб по чек-листу lab-style.md.

Проверяет то, что проверяется механически, и только это:

  * длину шагов (порог правила 8 — около 80 строк);
  * положение первой команды в шаге (правило 3). Шаг без команды нарушением
    НЕ считается, если он несёт метку «Своей команды у шага нет» — это
    разрешённый правилом 11 шаг-разбор чужого вывода. Метка обязательна:
    без неё шаг без команды неотличим от забытой команды, а раньше скрипт
    ругался на все такие шаги подряд и приучал себя игнорировать;
  * наличие маркеров блоков вывода и вопроса-предсказания;
  * целость вики-ссылок: существует ли документ и есть ли в нём такой
    заголовок дословно;
  * отсутствие markdown-якорей `](#...)` — в Obsidian они не переходят;
  * отсутствие отсылок «см. шаг N» (правило 4).

Чего он НЕ проверяет и проверить не может: что вывод в блоке снят
выполнением команды, а не пересказан; что объяснение понятно; что
предсказание осмысленно. Это ловится только прохождением лабы.

Запуск:  python3 tools/check-labs.py [шаблон]
"""

import re
import sys
from pathlib import Path

VAULT = Path(__file__).resolve().parents[1]
LABS_DIR = VAULT / "Лабы"
PATTERN = sys.argv[1] if len(sys.argv) > 1 else "lab-0[3-7]*.md"
LABS = sorted(LABS_DIR.glob(PATTERN))

# --- заголовки всех документов волта, чтобы проверить вики-ссылки
headings = {}
sources = (list(VAULT.glob("*.md")) + list(LABS_DIR.glob("*.md"))
           + list((VAULT / "checks").glob("*.md")) + list((VAULT / "Рецепты").glob("*.md"))
           + list((VAULT / "Партнёр").glob("*.md")) + list((VAULT / "База знаний").rglob("*.md")))
for f in sources:
    hs = {
        m.group(1).strip() for m in re.finditer(r"^#{1,6}\s+(.+)$", f.read_text(encoding="utf-8"), re.M)
    }
    # ключи: и короткое имя, и путь от корня волта без расширения
    headings.setdefault(f.stem, set()).update(hs)
    headings.setdefault(str(f.relative_to(VAULT).with_suffix("")), set()).update(hs)

print(f"{'лаба':22s} {'строк':>6} {'шагов':>6} {'макс шаг':>9} {'>80':>5} {'до 1-й команды':>15}")
print("-" * 72)
problems = []
for lab in LABS:
    text = lab.read_text(encoding="utf-8")
    lines = text.split("\n")
    steps = [(i, l) for i, l in enumerate(lines) if re.match(r"^## Шаг \d+", l)]
    lengths, far = [], []
    for n, (i, title) in enumerate(steps):
        if n + 1 < len(steps):
            end = steps[n + 1][0]
        else:
            end = next((j for j, l in enumerate(lines) if l.startswith("# Разбор")), len(lines))
        body = lines[i:end]
        lengths.append((len(body), title))
        first_cmd = next((j for j, l in enumerate(body) if l.startswith("```bash")), None)
        # правило 11: шаг-разбор вывода предыдущего шага, объявленный меткой
        declared = any("Своей команды у шага нет" in l for l in body)
        if first_cmd is None and declared:
            pass
        elif first_cmd is None or first_cmd > 15:
            far.append((title, first_cmd))
    mx = max(lengths) if lengths else (0, "")
    over = [t for ln, t in lengths if ln > 80]
    print(f"{lab.name:22s} {len(lines):6d} {len(steps):6d} {mx[0]:9d} {len(over):5d} {len(far):15d}")
    for t in over:
        problems.append(f"{lab.name}: шаг длиннее 80 строк — {t}")
    for t, pos in far:
        problems.append(f"{lab.name}: команда не в первых 15 строках ({pos}) — {t}")

    # маркировка блоков вывода
    fences = re.findall(r"```(none|json|bash|python)?\n", text)
    marked = len(re.findall(r"\*\*(Вывод \(дословно\)|Выжимка|Схема формата|Было|Стало)", text))
    if marked == 0:
        problems.append(f"{lab.name}: нет маркеров блоков вывода")

    # предсказания
    if "Прежде чем выполнить" not in text:
        problems.append(f"{lab.name}: нет ни одного вопроса-предсказания")

    # отсылки «см. шаг N» запрещены
    for m in re.finditer(r"см\.\s*шаг", text, re.I):
        problems.append(f"{lab.name}: отсылка «см. шаг» — {text[m.start()-40:m.start()+20]!r}")

    # вики-ссылки
    for m in re.finditer(r"\[\[([^\]|#]+)#([^\]|]+)(?:\|[^\]]*)?\]\]", text):
        doc, head = m.group(1).strip(), m.group(2).strip().rstrip("\\")
        if doc not in headings:
            problems.append(f"{lab.name}: вики-ссылка на несуществующий документ {doc}")
        elif head not in headings[doc]:
            problems.append(f"{lab.name}: заголовок не найден — [[{doc}#{head}]]")

    # markdown-якоря запрещены
    for m in re.finditer(r"\]\(#", text):
        problems.append(f"{lab.name}: markdown-якорь вместо вики-ссылки")

    # ссылки на файлы волта — из папки лаб, поэтому относительно неё
    for m in re.finditer(r"\]\((?!http)((?:\.\./)?[\w\-. ]+\.md)\)", text):
        if not (lab.parent / m.group(1)).exists():
            problems.append(f"{lab.name}: ссылка на несуществующий файл {m.group(1)}")

print()
if problems:
    print(f"замечаний: {len(problems)}")
    for p in sorted(set(problems)):
        print("  -", p)
else:
    print("замечаний нет")
