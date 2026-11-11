#!/usr/bin/env python3
"""pult.py — данные «пульта дня» виджетом: одно сообщение на день в личке хозяина — что сейчас в работе, один вопрос, который
ждёт его, и что сделано. Источник один: доска дня (skills/pult-dnya — файл дня) и вопросы хозяину (skills/cards — входящие).

У вопроса в пульте одна кнопка — «Ответить»: по ней Мила присылает этот вопрос обычной карточкой с вариантами под сообщением.
Сам пульт ответов не принимает: данные виджета меняются на месте, и нажатие по варианту могло бы попасть не в тот вопрос.
Всё, что идёт в данные, — текст: строки доски уже прошли её маску (карта, телефон, почта), вопрос проходит её здесь."""
import importlib.util
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SKILLS = os.path.normpath(os.path.join(HERE, "..", ".."))
ID = "pult"
L = lambda ru, en: {"ru": ru, "en": en}
MANIFEST = {"title": L("Пульт дня", "Day board"), "actions": [{"label": L("Ответить", "Answer"), "mark": "ask"}]}
DO = ("показать хозяину следующий вопрос обычной карточкой: python3 ~/.claude/skills/cards/cards.py next inbox — варианты под сообщением, "
      "правила Согласования как всегда; пульт сам ответов не принимает")
WORDS = {"ru": {"now": "Сейчас", "wait": "Ждёт вас", "done": "Сделано", "empty": "пусто", "more": "и ещё %d"},
         "en": {"now": "Now", "wait": "Waiting for you", "done": "Done", "empty": "empty", "more": "and %d more"}}
MAX_LINES, LINE_MAX, QUESTION_MAX = 3, 80, 120


def _mod(name, path):
    spec = importlib.util.spec_from_file_location("_vz_" + name, path)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m


def clip(s, cap):
    s = " ".join(str(s or "").split())
    return s if len(s) <= cap else s[:cap - 1].rstrip() + "…"


def day():
    """The date of the day board's «today» — the board's own rule (the owner's zone, DAY_BOARD_DATE in tests)."""
    return _mod("day_board", os.path.join(SKILLS, "pult-dnya", "scripts", "day_board.py")).today()


def data(lang):
    """→ dict for chat_data. Nothing is written: the board is read as it is, a day without a file is an empty board."""
    db = _mod("day_board", os.path.join(SKILLS, "pult-dnya", "scripts", "day_board.py"))
    cards = _mod("cards", os.path.join(SKILLS, "cards", "cards.py"))
    w = WORDS.get(lang) or WORDS["en"]
    b = db.load(); items = [i for i in b.get("items", []) if isinstance(i, dict)]
    line = lambda i: clip("№%s %s" % (i.get("no"), db.mask(i.get("text"))), LINE_MAX)
    now = [line(i) for i in items if i.get("state") == "now"]
    done = [i for i in items if i.get("state") == "done"]
    inbox = cards.deck("inbox")
    d = {"t": MANIFEST["title"].get(lang) or MANIFEST["title"]["en"], "d": ".".join(reversed(str(b.get("date", ""))[5:].split("-"))),
         "h": [w["now"], w["wait"], "%s · %d" % (w["done"], len(done))], "e": w["empty"],
         "n": now[:MAX_LINES], "dn": [line(i) for i in done[-MAX_LINES:]][::-1]}
    if len(now) > MAX_LINES: d["h"][0] = "%s · %d" % (w["now"], len(now))
    if inbox:
        d["q"] = clip(db.mask(inbox[0].get("q")), QUESTION_MAX)
        if len(inbox) > 1: d["m"] = w["more"] % (len(inbox) - 1)
        d["a"] = MANIFEST["actions"][0]["label"].get(lang) or MANIFEST["actions"][0]["label"]["en"]
    return d
