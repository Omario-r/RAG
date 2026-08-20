"""Конвертация сводного документа в fb2 для читалки.

Запускает pandoc и чинит за ним структуру: pandoc укладывает
подзаголовки во вложенные <section>, но текст, стоящий в разделе до
первого подзаголовка, оставляет тут же — рядом с вложенными секциями.
Схема FB2 такого не допускает: секция содержит **либо** поток (p, table,
empty-line...), **либо** подсекции. Строгая читалка на этом отказывается
открыть файл целиком, и именно по этой причине первая сборка 20.08.2026
не открылась.

Починка: каждый подряд идущий кусок потока заворачивается в безымянную
секцию на своём же месте — порядок текста сохраняется, схема
удовлетворена.

Заодно префикс пространства имён xlink приводится к общепринятому
`xlink:` (pandoc пишет `l:`, наивные разборщики его не узнают).

Ссылки снимаются целиком, текст остаётся: относительные пути к соседним
файлам волта после слияния указывают в никуда, а на читалке не нужны и
внешние — в тексте ссылки и так стоит опознавательный признак источника
(название, arXiv ID).

Запуск:  python3 tools/build-fb2.py
"""

import subprocess
import sys
import uuid
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path

VAULT = Path(__file__).resolve().parents[1]
SRC = VAULT / "knowledge-base-combined.md"
OUT = VAULT / "knowledge-base-combined.fb2"

FB2 = "http://www.gribuser.ru/xml/fictionbook/2.0"
XLINK = "http://www.w3.org/1999/xlink"
NS = f"{{{FB2}}}"

TITLE = "База знаний — сводный документ"
AUTHOR = "Роман"
GENRE = "comp_programming"

# Что по схеме FB2 считается потоком внутри секции.
FLOW = {"p", "image", "poem", "subtitle", "cite", "empty-line", "table"}
# Что стоит в начале секции и потоком не является.
HEAD = {"title", "epigraph", "image", "annotation"}


def run_pandoc(raw):
    cmd = [
        "pandoc", str(SRC), "-f", "markdown", "-t", "fb2",
        "-o", str(raw), "--standalone",
        "--metadata", f"title={TITLE}",
        "--metadata", f"author={AUTHOR}",
        "--metadata", "lang=ru",
        "--metadata", "genre=comp_programming",
        "--metadata", f"date={date.today().isoformat()}",
    ]
    subprocess.run(cmd, check=True)


def unmix(section):
    """Развести поток и подсекции внутри одной секции."""
    children = list(section)
    if not any(c.tag == NS + "section" for c in children):
        return 0

    fixed = 0
    rebuilt = []
    run = []

    def flush():
        nonlocal fixed
        if not run:
            return
        wrapper = ET.Element(NS + "section")
        wrapper.extend(run)
        rebuilt.append(wrapper)
        run.clear()
        fixed += 1

    for child in children:
        tag = child.tag.replace(NS, "")
        if tag in HEAD and not rebuilt and not run:
            rebuilt.append(child)          # заголовок остаётся заголовком
        elif tag in FLOW:
            run.append(child)
        else:
            flush()
            rebuilt.append(child)
    flush()

    for c in children:
        section.remove(c)
    section.extend(rebuilt)
    return fixed


def walk(node):
    total = 0
    for section in node.findall(NS + "section"):
        total += walk(section)
    total += unmix(node)
    return total


def cells(row):
    return [" ".join("".join(c.itertext()).split()) for c in row]


def flatten_tables(root):
    """Развернуть таблицы в абзацы.

    На шестидюймовом экране таблица в три-четыре колонки нечитаема, а
    старые прошивки её и вовсе не поддерживают. Строка заголовка не
    выбрасывается, а раздаётся по ячейкам: «Файл: 01-methods.md; О чём:
    полная карта» вместо колонок, которые некуда положить.
    """
    done = 0
    for parent in root.iter():
        for i in range(len(parent) - 1, -1, -1):
            table = parent[i]
            if table.tag != NS + "table":
                continue
            rows = table.findall(NS + "tr")
            head = []
            if rows and all(c.tag == NS + "th" for c in rows[0]):
                head = cells(rows[0])
                rows = rows[1:]

            lines = []
            for row in rows:
                values = cells(row)
                if head and len(head) == len(values):
                    pairs = [f"{h}: {v}" for h, v in zip(head, values) if v]
                    lines.append("; ".join(pairs))
                else:
                    lines.append(" | ".join(v for v in values if v))

            parent.remove(table)
            for offset, line in enumerate(lines):
                p = ET.Element(NS + "p")
                p.text = line
                parent.insert(i + offset, p)
            done += 1
    return done


def sub(parent, tag, text=None):
    e = ET.SubElement(parent, NS + tag)
    if text is not None:
        e.text = text
    return e


def author_into(parent):
    a = sub(parent, "author")
    sub(a, "first-name", "")
    sub(a, "last-name", AUTHOR)
    return a


def rebuild_description(root):
    """Собрать <description> заново.

    Схема FB2 требует в document-info author, date, id и version, а
    pandoc пишет туда один program-used. Строгая читалка отвергает файл
    целиком — по этой причине сборка не открылась во второй раз.
    Идентификатор берётся детерминированный: при пересборке книга
    остаётся той же, а не заводится в читалке заново.
    """
    old = root.find(NS + "description")
    new = ET.Element(NS + "description")

    ti = sub(new, "title-info")
    sub(ti, "genre", GENRE)
    author_into(ti)
    sub(ti, "book-title", TITLE)
    sub(ti, "lang", "ru")

    di = sub(new, "document-info")
    author_into(di)
    sub(di, "program-used", "pandoc + tools/build-fb2.py")
    sub(di, "date", date.today().isoformat())
    sub(di, "id", str(uuid.uuid5(uuid.NAMESPACE_URL, "rag-vault/" + TITLE)))
    sub(di, "version", "1.0")

    root.remove(old)
    root.insert(0, new)
    # После снятия ссылок xlink нигде не используется, и ElementTree
    # перестаёт его объявлять. Объявление возвращается вручную: часть
    # читалок ждёт его в корне безусловно.
    root.set("xmlns:xlink", XLINK)


def strip_ids(root):
    """Снять id: без ссылок они не нужны, а кириллица в них — лишний риск."""
    n = 0
    for e in root.iter():
        if e.get("id") is not None:
            del e.attrib["id"]
            n += 1
    return n


# Элементы, между детьми которых перенос строки безопасен: у них нет
# собственного текста, только вложенные блоки.
BLOCK = {
    "FictionBook", "description", "title-info", "document-info",
    "publish-info", "body", "section", "title", "epigraph", "annotation",
    "cite", "poem", "stanza", "table", "tr",
}


def break_blocks(elem):
    kids = list(elem)
    if elem.tag.replace(NS, "") not in BLOCK or not kids:
        return
    if not elem.text or not elem.text.strip():
        elem.text = "\n"
    for kid in kids:
        break_blocks(kid)
        if not kid.tail or not kid.tail.strip():
            kid.tail = "\n"


def write(tree, path):
    """Записать файл в форме, которую переваривает простой разборщик.

    Два отличия от вывода ElementTree, обнаруженные сравнением с книгой,
    которая на устройстве открывается:

      * перенос строк между блоками. ElementTree пишет всё в одну
        строку — у сводного документа она выходила 265 КБ при 658
        байтах у рабочей книги. Читалки со старой прошивкой разбирают
        файл построчно в буфер фиксированного размера и на такой строке
        отказывают;
      * объявление XML в двойных кавычках. ElementTree ставит
        одинарные; часть разборщиков сверяет строку объявления
        буквально.

    Переносы ставятся только между блочными элементами: внутрь абзаца
    разборщик не заглядывает, а лишний перенос там сместил бы разметку.
    """
    break_blocks(tree.getroot())
    xml = ET.tostring(tree.getroot(), encoding="unicode")
    path.write_text('<?xml version="1.0" encoding="UTF-8"?>\n' + xml + "\n",
                    encoding="utf-8")


def append_text(parent, index, text):
    """Дописать текст в то место потока, где стоял ребёнок с номером index."""
    if not text:
        return
    if index == 0:
        parent.text = (parent.text or "") + text
    else:
        prev = parent[index - 1]
        prev.tail = (prev.tail or "") + text


def unlink(parent):
    """Снять <a>, оставив содержимое на месте. Разметка внутри сохраняется."""
    removed = 0
    for index in range(len(parent) - 1, -1, -1):
        child = parent[index]
        removed += unlink(child)
        if child.tag != NS + "a":
            continue

        inner = list(child)
        parent.remove(child)
        append_text(parent, index, child.text)
        for offset, node in enumerate(inner):
            parent.insert(index + offset, node)
        if inner:
            last = inner[-1]
            last.tail = (last.tail or "") + (child.tail or "")
        else:
            append_text(parent, index, child.tail)
        removed += 1
    return removed


def main():
    if not SRC.exists():
        sys.exit(f"нет исходника: {SRC} — сперва tools/build-knowledge-base.py")

    plain = "--no-tables" in sys.argv
    out = OUT.with_stem(OUT.stem + "-no-tables") if plain else OUT

    # Промежуточный файл отдельно от результата: иначе прогон с одним
    # набором ключей затирает сырым выводом pandoc файл, собранный
    # прогоном с другим.
    raw = out.with_suffix(".raw.fb2")
    run_pandoc(raw)

    ET.register_namespace("", FB2)
    ET.register_namespace("xlink", XLINK)
    tree = ET.parse(raw)
    root = tree.getroot()

    fixed = sum(walk(body) for body in root.findall(NS + "body"))
    dropped = unlink(root)
    tables = flatten_tables(root) if plain else 0
    rebuild_description(root)
    ids = strip_ids(root)
    write(tree, out)
    raw.unlink()

    print(f"записано: {out.relative_to(VAULT)} "
          f"({out.stat().st_size // 1024} КБ, развёрнуто секций: {fixed}, "
          f"снято ссылок: {dropped}, снято id: {ids}"
          + (f", таблиц развёрнуто: {tables}" if plain else "") + ")")


if __name__ == "__main__":
    main()
