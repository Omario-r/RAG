"""Связность журнала прогонов с остальным волтом.

Проверяет то, что проверяется механически:

  * каждая ссылка `RUN-...` ведёт в существующий прогон `checks/runs.md`;
  * у каждого прогона есть раздел с конфигурацией и строка «Дал:»
    (что прогон дал) — прогон без вывода бесполезен;
  * каждый закрытый этап роадмапа назван прогоном или лабой;
  * прогон, на который никто не ссылается, — сирота: либо он не нужен,
    либо потерялась ссылка.

Чего он НЕ проверяет: что числа в прогоне верны, что конфигурация полна,
что аннотация осмысленна. Это ловится только чтением.

Запуск:  python3 tools/check-runs.py
"""

import re
import sys
from pathlib import Path

VAULT = Path(__file__).resolve().parents[1]
RUNS = VAULT / "checks" / "runs.md"
RUN_RE = re.compile(r"RUN-\d{8}-[A-Z]")

runs_text = RUNS.read_text(encoding="utf-8")

# заголовки прогонов: ### `RUN-20260809-C` — реранкер...
declared = {}
for m in re.finditer(r"^### `(RUN-\d{8}-[A-Z])`(.*)$", runs_text, re.M):
    declared[m.group(1)] = m.group(2).strip(" —")

problems = []
if not declared:
    problems.append("в journal нет ни одного прогона — проверять нечего")

# у каждого прогона должен быть вывод
for run_id in declared:
    i = runs_text.index(f"### `{run_id}`")
    nxt = re.search(r"^(### |## )", runs_text[i + 5:], re.M)
    body = runs_text[i: i + 5 + nxt.start()] if nxt else runs_text[i:]
    if "**Дал" not in body:
        problems.append(f"{run_id}: нет строки «**Дал:**» — непонятно, что прогон дал")
    if not any(k in body for k in ("**Конфигурация:**", "| Что | Значение |", "config:")):
        problems.append(f"{run_id}: нет конфигурации — прогон невоспроизводим")

# ссылки по волту
referenced = {}
for f in sorted(VAULT.glob("*.md")) + sorted((VAULT / "checks").glob("*.md")):
    if f == RUNS:
        continue
    for m in RUN_RE.finditer(f.read_text(encoding="utf-8")):
        run_id = m.group(0)
        referenced.setdefault(run_id, set()).add(f.name)
        if run_id not in declared:
            problems.append(f"{f.name}: ссылка на несуществующий прогон {run_id}")

for run_id in declared:
    if run_id not in referenced:
        problems.append(f"{run_id}: сирота — на прогон никто не ссылается")

# закрытые этапы роадмапа названы прогоном
roadmap = (VAULT / "06-roadmap.md").read_text(encoding="utf-8")
for line in roadmap.split("\n"):
    if not line.startswith("| ") or "✅" not in line:
        continue
    cells = [c.strip() for c in line.split("|")]
    if len(cells) < 6:
        continue
    stage, closed_by = cells[1], cells[4]
    if stage in {"—", "Этап"}:
        continue
    if not (RUN_RE.search(closed_by) or "лаб" in closed_by):
        problems.append(f"этап {stage}: помечен пройденным, но не назван прогоном или лабой")

print(f"прогонов в журнале: {len(declared)}")
for run_id in sorted(declared):
    where = ", ".join(sorted(referenced.get(run_id, ()))) or "—"
    print(f"  {run_id}  ссылаются: {where}")

print()
if problems:
    print(f"замечаний: {len(problems)}")
    for p in sorted(set(problems)):
        print("  -", p)
    sys.exit(1)
print("замечаний нет")
