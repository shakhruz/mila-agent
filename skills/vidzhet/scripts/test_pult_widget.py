#!/usr/bin/env python3
"""The day board as a widget: one message a day — what is in progress, ONE question that waits for the owner with «and N more»,
what is done; the question has one button «Answer» and the press only says «send the question as a usual card» — the widget takes
no answers (data change in place: a tap on an option could hit another question). Texts are text: a phone, a mail, a card in a
question are masked; the data never exceed 1024 bytes; a new day asks for a new board. A temp home; the day is DAY_BOARD_DATE.
Run: python3 test_pult_widget.py"""
import json, os, re, shutil, subprocess, sys, tempfile, zlib
sys.dont_write_bytecode = True; os.umask(0o022)
H = os.path.dirname(os.path.abspath(__file__)); SK = os.path.dirname(os.path.dirname(H))
T = tempfile.mkdtemp(prefix="vzpult-"); HOME = os.path.join(T, "home"); WORK = os.path.join(HOME, "work"); os.makedirs(os.path.join(WORK, "state"))
for k in ("OWNER_TZ", "MILA_LANG", "DAY_BOARD_NOW"): os.environ.pop(k, None)
DAY1, DAY2 = "2026-05-04", "2026-05-05"
os.environ.update(HOME=HOME, MILA_WORK=WORK, DAY_BOARD_DATE=DAY1, PYTHONDONTWRITEBYTECODE="1")
sys.path.insert(0, H)
import widget as W, pult as P
ok = n = 0
def chk(m, c, x=""):
    global ok, n
    n += 1; ok += bool(c); print(("✅ " if c else "❌ ") + m + ("" if c else "  ← " + str(x)[:400]))
def run(*a, **env):
    r = subprocess.run([sys.executable, *a], capture_output=True, text=True, env=dict(os.environ, **env), stdin=subprocess.DEVNULL, timeout=60)
    return r.returncode, (r.stdout + r.stderr).strip()
def R(*a, **env):
    rc, o = run("-I", os.path.join(H, "widget.py"), *a, **env)
    try: return rc, json.loads(o)
    except ValueError: return rc, {"raw": o[:300]}
DB = os.path.join(SK, "pult-dnya", "scripts", "day_board.py"); CARDS = os.path.join(SK, "cards", "cards.py")
def board(*a):
    rc, o = run(DB, *a); assert rc == 0, o
    return json.loads(o)
def ask(q, *more):
    rc, o = run(CARDS, "ask", "--q", q, "--why", "нужно ваше слово", "--opt", "a|Да|сделаю", "--opt", "b|Нет|не буду", "--rec", "a", *more); assert rc == 0, o
    return json.loads(o)["id"]
OWNER = "555" + "000111"; BOT = "m_test_bot"
PHONE = "+998 90 " + "123-45-67"; MAIL = "ivan" + "@" + "example.org"

try:
    # ── the template
    t = open(os.path.join(H, "..", "templates", "pult.html"), encoding="utf-8").read()
    html, size, packed = W.build_html("b" * 32, ["w_pult_ask"], "pult.html")
    chk("шаблон пульта: %d байт, %d после сжатия — в бюджете 3000 из 4096" % (size, packed), packed <= 3000 and packed == len(zlib.compress(html.encode(), 9)), (size, packed))
    MARKUP = r"innerHTML|outerHTML|insertAdjacentHTML|document\.write|\beval\b|\bFunction\s*\(|setAttribute|\.href|\.src\b|srcdoc|DOMParser|createContextualFragment|setTimeout\s*\(\s*['\"]"
    FORBIDDEN = [r"<\s*(input|select|textarea|form)\b", r"<\s*(iframe|video|audio|object|embed)\b", r"<\s*script\b[^>]*\bsrc\s*=", r"<\s*link\b", r"@font-face",
                 r"(?<![\w.$])fetch\s*\(|\b(XMLHttpRequest|WebSocket|EventSource|sendBeacon)\b", r"<\s*img\b", r"@import", r"url\s*\("]
    chk("в шаблоне пульта данные не становятся разметкой и нет того, что Telegram не даёт", not re.search(MARKUP, t) and not any(re.search(rx, t, re.I) for rx in FORBIDDEN) and "textContent" in t)
    chk("кнопка в пульте одна, её ссылка — в коде, не в данных; класс — только из кода", t.count("createElement('button'") + t.count("el('button'") == 1 and "L[0]" in t and "S.bot" not in t and "start=" not in t
        and not re.search(r"className\s*=\s*S\.", t))
    chk("в отправляемом коде — одна ссылка с меткой пульта", re.findall(r"[?&]start=(w_[A-Za-z0-9_-]{1,62})", html) == ["w_pult_ask"])

    # ── data: an empty day
    d = P.data("ru")
    chk("пустой день: заголовки, дата дня, «пусто», вопроса нет", d == {"t": "Пульт дня", "d": "04.05", "h": ["Сейчас", "Ждёт вас", "Сделано · 0"], "e": "пусто", "n": [], "dn": []}, d)
    chk("пульт только читает: файл дня не появился", not os.path.exists(os.path.join(WORK, "state", "day-%s.json" % DAY1)))
    d = P.data("en"); chk("по-английски", d["t"] == "Day board" and d["h"] == ["Now", "Waiting for you", "Done · 0"] and d["e"] == "empty", d)

    # ── the board fills
    board("add", "--text", "Свести отчёт за неделю", "--red"); board("add", "--text", "Написать план поста")
    board("add", "--text", "Позвонить в типографию " + PHONE)
    d = P.data("ru")
    chk("в работе — строка с номером; очередь в «сейчас» не идёт", d["n"] == ["№1 Свести отчёт за неделю"] and d["h"][0] == "Сейчас", d)
    board("done", "1", "--evidence", "file:otchet.pdf", "--result", "отчёт готов"); board("start", "2"); board("start", "3")
    d = P.data("ru")
    chk("сделано — счётчик в заголовке и строка; телефон в строке доски уже под маской", d["h"][2] == "Сделано · 1" and d["dn"] == ["№1 Свести отчёт за неделю"] and d["n"][1] == "№3 Позвонить в типографию ⟦тел⟧"
        and PHONE not in json.dumps(d, ensure_ascii=False), d)
    for i in range(4): board("add", "--text", "Срочное дело %d" % i, "--red")
    d = P.data("ru"); chk("в работе больше трёх — три строки и число в заголовке", len(d["n"]) == 3 and d["h"][0] == "Сейчас · 6", d)
    for no in (2, 3, 4, 5): board("done", str(no), "--evidence", "file:x.txt", "--result", "готово")
    d = P.data("ru"); chk("сделано больше трёх — три последних, новое сверху, счёт полный", d["h"][2] == "Сделано · 5" and d["dn"] == ["№5 Срочное дело 1", "№4 Срочное дело 0", "№3 Позвонить в типографию ⟦тел⟧"], d)

    # ── one question at a time
    chk("вопросов нет — блока вопроса и кнопки нет", "q" not in d and "a" not in d and "m" not in d)
    q1 = ask("Выпускаем обновление сегодня вечером"); d = P.data("ru")
    chk("один вопрос: его текст и кнопка «Ответить», без «и ещё»", d.get("q") == "Выпускаем обновление сегодня вечером" and d.get("a") == "Ответить" and "m" not in d, d)
    ask("Отвечаем клиенту на почту " + MAIL); ask("Оплачиваем хостинг сейчас", "--urgent"); d = P.data("ru")
    chk("три вопроса: показан один — срочный первым, остальные счётчиком «и ещё 2»", d["q"] == "Оплачиваем хостинг сейчас" and d["m"] == "и ещё 2", d)
    chk("вариантов ответа в данных пульта нет — только вопрос и одна подпись кнопки", "Да" not in json.dumps([d.get("q"), d.get("m")], ensure_ascii=False) and isinstance(d["a"], str) and set(d) == {"t", "d", "h", "e", "n", "dn", "q", "m", "a"})
    rc, o = run(CARDS, "answer", json.loads(run(CARDS, "next", "inbox")[1])["card"]["id"], "--pick", "a"); assert rc == 0, o
    d = P.data("ru"); chk("на срочный ответили — следующий по порядку, «и ещё 1»", d["q"] == "Выпускаем обновление сегодня вечером" and d["m"] == "и ещё 1", d)
    rc, o = run(CARDS, "answer", q1, "--pick", "b"); d = P.data("ru")
    chk("почта в тексте вопроса закрыта маской", d["q"] == "Отвечаем клиенту на почту ⟦почта⟧" and MAIL not in json.dumps(d, ensure_ascii=False) and "m" not in d, d)
    long_q = ask("Очень длинный вопрос про " + "договорпоставкиоборудования" * 6); rc, o = run(CARDS, "answer", json.loads(run(CARDS, "next", "inbox")[1])["card"]["id"], "--pick", "a")
    d = P.data("ru"); chk("длинный вопрос обрезан до 120 знаков с «…», в одну строку", len(d["q"]) == 120 and d["q"].endswith("…") and "\n" not in d["q"], (len(d["q"]), d["q"][-10:]))
    en = P.data("en"); chk("английский пульт: Answer, and N more нет при одном вопросе", en["a"] == "Answer" and "m" not in en, en)

    # ── never above 1024 bytes
    for i in range(3): board("add", "--text", "😀" * 90 + str(i), "--red")
    s = W.build_data("pult", P.MANIFEST, "ru"); back = json.loads(s)
    chk("данные с длинными строками сжаты до предела 1024 байт (%d), заголовки и счёт целы" % len(s.encode()), len(s.encode()) <= 1024 and back["h"][2] == "Сделано · 5" and back["t"] == "Пульт дня" and any(x.endswith("…") for x in back["n"]), len(s.encode()))

    fat = {"t": "Пульт дня", "d": "04.05", "h": ["Сейчас · 9", "Ждёт вас", "Сделано · 12"], "e": "пусто", "n": ["😀" * 80] * 3, "dn": ["я" * 80] * 3, "q": "😀" * 120, "m": "и ещё 4", "a": "Ответить"}
    raw = json.dumps(fat, ensure_ascii=False, separators=(",", ":")); s2 = W.pack_data(json.loads(raw)); back = json.loads(s2)
    chk("самый полный пульт (%d байт) сжат до 1024: %d; заголовки, счёт, «и ещё» и кнопка целы, длинное — с «…»" % (len(raw.encode()), len(s2.encode())), len(raw.encode()) > 1500 and 1000 <= len(s2.encode()) <= 1024
        and back["h"] == fat["h"] and back["m"] == "и ещё 4" and back["a"] == "Ответить" and back["q"].endswith("…") and all(x.endswith("…") for x in back["n"]), len(s2.encode()))
    # a day file somebody wrote by hand, past the board's own mask: the widget masks on reading too
    dayf = os.path.join(WORK, "state", "day-%s.json" % DAY1); keep = open(dayf, encoding="utf-8").read(); bj = json.loads(keep)
    bj["items"].append({"no": 99, "text": "Перезвонить " + PHONE + " и написать на " + MAIL, "state": "now", "prio": "red"}); bj["items"] = bj["items"][-1:] + bj["items"][:-1]
    json.dump(bj, open(dayf, "w", encoding="utf-8"), ensure_ascii=False); dd = P.data("ru")
    chk("строка, попавшая в файл дня мимо маски доски, в пульте всё равно под маской", dd["n"][0] == "№99 Перезвонить ⟦тел⟧ и написать на ⟦почта⟧" and PHONE not in json.dumps(dd, ensure_ascii=False) and MAIL not in json.dumps(dd, ensure_ascii=False), dd["n"])
    open(dayf, "w", encoding="utf-8").write(keep)

    # ── show / sent / refresh / press: one board a day
    rc, o = R("show", "pult", "--chat", "-100" + "5550001", "--bot", BOT); chk("пульт в группу — отказ", rc != 0 and "личку" in o.get("error", ""), o)
    rc, o = R("show", "pult", "--chat", OWNER, "--bot", BOT); a = o.get("args", {})
    chk("show pult: инструмент widget, шаблон пульта, данные, и сказано закрепить", rc == 0 and o.get("tool") == "widget" and "id=\"kq\"" in a.get("html", "") and json.loads(a["chat_data"])["t"] == "Пульт дня"
        and "pin" in o.get("pin", "") and "https://t.me/%s?start=w_pult_ask" % BOT in a["html"], o)
    rc, o = R("press", "w_pult_ask"); chk("до записи нажатие ещё не моё", o.get("known") is False, o)
    rc, o = R("sent", "pult", "--message", "900"); st = json.load(open(os.path.join(WORK, "state", "widgets.json")))["widgets"]["pult"]
    chk("sent: записаны сообщение и день пульта", rc == 0 and st["message_id"] == 900 and st["day"] == DAY1, st)
    rc, o = R("show", "pult", "--chat", OWNER, "--bot", BOT); chk("второй пульт в тот же день — отказ: обновлять прежний", rc != 0 and "refresh pult" in o.get("error", "") and "900" in o.get("error", ""), o)
    rc, o = R("show", "pult", "--chat", OWNER, "--bot", BOT, "--again"); chk("…а с --again — можно (сообщение удалили)", rc == 0 and o.get("tool") == "widget", o)
    R("sent", "pult", "--message", "901")
    rc, o = R("refresh", "pult"); chk("ничего не изменилось — без вызова", o.get("widgets") == [{"pack": "pult", "changed": False}], o)
    board("done", "6", "--evidence", "file:y.txt", "--result", "готово")
    rc, o = R("refresh", "--all"); w = (o.get("widgets") or [{}])[0]
    chk("дело закрыто — правка данных того же сообщения", w.get("tool") == "widget_data" and w["args"]["message_id"] == "901" and json.loads(w["args"]["chat_data"])["h"][2] == "Сделано · 6", o)
    R("sent", "pult")
    rc, o = R("press", "w_pult_ask")
    chk("нажатие «Ответить»: прислать вопрос обычной карточкой; сам пульт ответов не принимает; скрипт ничего не исполнил", o.get("known") is True and o.get("core") is True and "cards.py next inbox" in o.get("do", "")
        and "ответов не принимает" in o["do"] and o.get("lock") is False, o)
    before = run(CARDS, "list", "inbox")[1]
    for mk in ("w_pult_a", "w_pult_pick", "w_pult_yes", "w_pult_ask2"):
        rc, o = R("press", mk); chk("нажатие «%s» — такой кнопки у пульта нет: ничего" % mk, o.get("known") is False, o)
    chk("нажатия не изменили ни одного вопроса", run(CARDS, "list", "inbox")[1] == before)
    rc, o = R("refresh", "pult", DAY_BOARD_DATE=DAY2); chk("наступил новый день — старый пульт не обновляется, нужен новый", "stale" in o["widgets"][0] and "show pult" in o["widgets"][0]["stale"] and "tool" not in o["widgets"][0], o)
    rc, o = R("show", "pult", "--chat", OWNER, "--bot", BOT, DAY_BOARD_DATE=DAY2); d2 = json.loads(o.get("args", {}).get("chat_data", "{}"))
    chk("новый день: новый пульт без --again; незакрытое перенесено, сделанное вчера — нет", rc == 0 and d2.get("d") == "05.05" and d2["h"][2] == "Сделано · 0" and len(d2["n"]) == 3, o)

    # ── a pack cannot be the day board
    m = {"title": {"ru": "Подмена"}, "numbers": [{"label": {"ru": "штук"}, "file": "count.json", "key": "total"}]}
    chk("пак с id «pult» — без виджета", any("модуля ядра" in x for x in W.check_manifest(m, "pult")))
    os.makedirs(os.path.join(WORK, "pult")); open(os.path.join(WORK, "pult", W.DATA_MARK), "w").write("pult\n"); open(os.path.join(WORK, "pult", "count.json"), "w").write('{"total": 9}')
    chk("папка данных с именем «pult» не читается", W.read_value("pult", {"file": "count.json", "key": "total"}) is None)

    # ── a broken source
    open(os.path.join(WORK, "inbox.jsonl"), "a").write("{broken\n"); d = P.data("ru"); chk("битая строка во входящих не роняет пульт", d["t"] == "Пульт дня", d)
    open(os.path.join(WORK, "state", "day-%s.json" % DAY1), "w").write("{broken"); d = P.data("ru")
    chk("файл дня не читается — пустая доска, без падения", d["n"] == [] and d["h"][2] == "Сделано · 0", d)
finally:
    shutil.rmtree(T, ignore_errors=True)
print("итог %d/%d" % (ok, n)); sys.exit(0 if ok == n else 1)
