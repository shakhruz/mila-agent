#!/usr/bin/env python3
"""widget.py: one template for every pack, data drawn as text only; a pack gives widget.json — data and pointers, never code;
values are read only from the pack's own data folder, made and marked by the install; a link, a second name of another file,
a folder that was in the home before the pack, a key-like name — «no data»; chat_data never above 1024 bytes; the same data —
no call; a ceiling of edits per hour; a press — whose step it is, nothing is run; a pack's code is never run (beacon file).
The home of the test is a temp folder; «now» is one moment taken at the start and handed to the script with --now, so the
result does not depend on the clock the test or the script sees. Run: python3 test_widget.py"""
import datetime as dt, json, os, re, shutil, subprocess, sys, tempfile, time, zlib
sys.dont_write_bytecode = True; os.umask(0o022)
H = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(os.path.dirname(os.path.dirname(H)))
T = tempfile.mkdtemp(prefix="widget-"); HOME = os.path.join(T, "home"); WORK = os.path.join(HOME, "work"); CL = os.path.join(HOME, ".claude")
os.makedirs(os.path.join(WORK, "packs")); os.makedirs(os.path.join(WORK, "state"))
os.environ["MILA_WORK"] = WORK
sys.path.insert(0, H)
import widget as W
ENV = dict(os.environ, HOME=HOME, MILA_WORK=WORK, PYTHONDONTWRITEBYTECODE="1")
ok = n = 0
def chk(m, c, x=""):
    global ok, n
    n += 1; ok += bool(c); print(("✅ " if c else "❌ ") + m + ("" if c else "  ← " + str(x)[:400]))
BASE = dt.datetime.now().astimezone(); NOW = [BASE]      # the test's own clock: moved by hand, never read from the machine again
def tick(seconds): NOW[0] += dt.timedelta(seconds=seconds)
def machine_iso():
    """The machine's clock as a child process sees it, already as the card's text. update.py runs as a child and checks that the
    pressed card is fresh by ITS clock; the stamp is made wholly in a child, so nothing of the test's own time functions touches it."""
    return subprocess.run([sys.executable, "-I", "-c", "import time; print(time.strftime('%Y-%m-%dT%H:%M:%S.000Z', time.gmtime()))"], capture_output=True, text=True, timeout=30).stdout.strip()
def R(*a):
    if a and a[0] in ("sent", "refresh") and "--now" not in a: a = (*a, "--now", NOW[0].isoformat())
    r = subprocess.run([sys.executable, "-I", os.path.join(H, "widget.py"), *a], capture_output=True, text=True, env=ENV, stdin=subprocess.DEVNULL, timeout=30)
    try: d = json.loads(r.stdout or "{}")
    except ValueError: d = {"raw": (r.stdout + r.stderr)[:300]}
    return r.returncode, d
OWNER = "555" + "000111"; BOT = "m_test_bot"; PID = "demo-audit"
BEACON = os.path.join(T, "beacon")
def manifest(**over):
    m = {"title": {"ru": "Аудит внимания", "en": "Attention audit"},
         "numbers": [{"label": {"ru": "разборов", "en": "reviews"}, "file": "count.json", "key": "total"},
                     {"label": {"ru": "за неделю"}, "file": "count.json", "key": "week"}],
         "state": {"file": "count.json", "key": "state"},
         "actions": [{"label": {"ru": "Новый разбор", "en": "New review"}, "mark": "new"}, {"label": {"ru": "Оплатить"}, "mark": "pay", "lock": True}]}
    m.update(over); return m
def install(pid=PID, m=None, data=None, mark=True):
    """What the pack install leaves in the home: the checked widget.json and a marked data folder."""
    os.makedirs(os.path.join(WORK, "packs", pid), exist_ok=True); os.makedirs(os.path.join(WORK, pid), exist_ok=True)
    json.dump(m or manifest(), open(os.path.join(WORK, "packs", pid, "widget.json"), "w", encoding="utf-8"), ensure_ascii=False)
    if mark: open(os.path.join(WORK, pid, W.DATA_MARK), "w").write(pid + "\n")
    if data is not None: put(pid, "count.json", data)
def put(pid, name, o):
    p = os.path.join(WORK, pid, name)
    if os.path.lexists(p): os.remove(p)
    open(p, "w", encoding="utf-8").write(o if isinstance(o, str) else json.dumps(o, ensure_ascii=False))
def state(): return json.load(open(os.path.join(WORK, "state", "widgets.json"), encoding="utf-8"))

try:
    # ── the template
    t = open(os.path.join(H, "..", "templates", "module.html"), encoding="utf-8").read()
    longest = ["w_%s_%s" % ("p" * 41, "a" * 19 + str(i)) for i in range(3)]
    html, size, packed = W.build_html("b" * 32, longest)
    chk("шаблон с тремя самыми длинными ссылками: %d байт, %d после сжатия — в бюджете 3000 из 4096" % (size, packed), size <= 32768 and packed <= 3000 and packed == len(zlib.compress(html.encode(), 9)), (size, packed))
    FORBIDDEN = [r"<\s*(input|select|textarea|form)\b", r"<\s*(iframe|video|audio|object|embed)\b", r"<\s*script\b[^>]*\bsrc\s*=", r"<\s*link\b", r"@font-face",
                 r"(?<![\w.$])fetch\s*\(|\b(XMLHttpRequest|WebSocket|EventSource|sendBeacon)\b", r"<\s*img\b", r"@import", r"url\s*\("]
    chk("в шаблоне нет того, что Telegram в виджете не даёт (поля ввода, сеть, внешние файлы)", not any(re.search(rx, t, re.I) for rx in FORBIDDEN))
    MARKUP = r"innerHTML|outerHTML|insertAdjacentHTML|document\.write|\beval\b|\bFunction\s*\(|setAttribute|\.href|\.src\b|srcdoc|DOMParser|createContextualFragment|setTimeout\s*\(\s*['\"]"
    chk("данные в шаблоне не становятся разметкой: ни одной вставки строкой", not re.search(MARKUP, t), re.findall(MARKUP, t))
    chk("текст кладётся как текст, класс статуса — только из закрытого списка", "textContent" in t and "hasOwnProperty.call(C,S.s)" in t and "className=" in t and t.count("className") == 1)
    chk("ссылки кнопок — в коде виджета, не в данных: в шаблоне одно место для них", t.count("/*LINKS*/") == 1 and "S.bot" not in t and "start=" not in t)
    found = re.findall(r"[?&]start=(w_[A-Za-z0-9_-]{1,62})(?![A-Za-z0-9_-])", html)
    chk("метки кнопок в отправляемом коде видит реестр плагина", found == longest, found)
    import hashlib; noise = "".join(hashlib.sha256(str(i).encode()).hexdigest() for i in range(120))
    try: W.build_html(BOT, ["w_x_" + noise]); chk("виджет больше пределов Telegram — отказ", False)
    except ValueError as e: chk("виджет больше пределов Telegram — отказ", "пределы" in str(e))

    # ── widget.json: data only
    chk("описание по образцу годится", W.check_manifest(manifest(), PID) == [], W.check_manifest(manifest(), PID))
    def bad(name, has, pid=PID, **over):
        why = W.check_manifest(manifest(**over), pid); chk(name + " — отказ", any(has in x for x in why), why)
    num = lambda **kw: dict({"label": {"ru": "штук"}, "file": "count.json", "key": "total"}, **kw)
    act = lambda **kw: dict({"label": {"ru": "Шаг"}, "mark": "go"}, **kw)
    bad("четыре цифры", "не больше 3", numbers=[num()] * 4)
    bad("четыре кнопки", "не больше 3", actions=[act(mark="a%d" % i) for i in range(4)])
    bad("поле с командой в описании", "лишние поля command", command="python3 run.py")
    bad("поле с путём к скрипту у кнопки", "лишние поля script", actions=[act(script="scripts/run.py")])
    bad("поле с командой у цифры", "лишние поля cmd", numbers=[num(cmd="cat /etc/passwd")])
    bad("поле с командой у статуса", "лишние поля exec", state={"file": "count.json", "key": "state", "exec": "x"})
    for f, what in (("../memory/x.json", "«..»"), ("sub/count.json", "папка в имени"), ("/etc/x.json", "полный путь"), ("count.txt", "не .json"), ("..json", "точки"), ("a\\..\\b.json", "обратная черта")):
        bad("файл: " + what, "без папок", numbers=[num(file=f)])
    for f in ("token.json", "my-secrets.json", "session.json", "x.env.json", "passwords.json"):
        bad("файл с именем ключей «%s»" % f, "файл ключей", numbers=[num(file=f)])
    bad("ключ не простым именем", "простое имя", numbers=[num(key="a.b")])
    bad("ключ списком", "простое имя", numbers=[num(key=["a"])])
    for mk in ("New", "a_b", "a-b", "", "x" * 21, 5):
        bad("метка не по форме %r" % (mk,), "строчные латинские", actions=[act(mark=mk)])
    bad("метка повторяется", "повторяется", actions=[act(), act()])
    bad("название длиннее 40 знаков", "до 40", title={"ru": "я" * 41})
    bad("название в две строки", "одна строка", title={"ru": "а\nб"})
    bad("название не по языкам", "по языкам", title="Аудит")
    bad("язык не двумя буквами", "две буквы", title={"russian": "Аудит"})
    bad("подпись кнопки длиннее 24", "до 24", actions=[act(label={"ru": "я" * 25})])
    bad("lock не да/нет", "true или false", actions=[act(lock="yes")])
    bad("своё слово статуса", "слово статуса даёт ядро", state={"file": "count.json", "key": "state", "label": {"ru": "всё отлично"}})
    bad("цифры не списком", "нужен список", numbers={"a": 1})
    for pid in ("state", "memory", "packs", "keys", "secrets"):
        chk("пак с id «%s» (папка самого дома) — без виджета" % pid, any("папка самого дома" in x for x in W.check_manifest(manifest(), pid)))
    chk("id пака не по форме — отказ", W.check_manifest(manifest(), "../x") == ["id пака не по форме"])
    chk("описание не объектом — отказ", W.check_manifest([1], PID) == ["widget.json: нужен объект"])
    chk("самая длинная метка — 64 знака, предел Telegram для ссылки", W.check_manifest(manifest(actions=[act(mark="a" * 20)]), "p" * 41) == [] and len(W.marks_of("p" * 41, {"actions": [act(mark="a" * 20)]})[0]) == 64)

    # ── values: only from the pack's own marked data folder
    install(data={"total": 12, "week": 3.5, "state": "ok", "name": "Иван", "flag": True, "long": "x" * 25, "deep": {"a": 1}, "nul": None, "big": 10 ** 30, "inf": 1e400})
    P = lambda k, f="count.json": {"file": f, "key": k}
    chk("число, дробь и короткая строка читаются", [W.read_value(PID, P(k)) for k in ("total", "week", "name")] == ["12", "3.5", "Иван"])
    chk("да/нет, длинная строка, вложенное, пустое, огромное число, бесконечность — «нет данных»", [W.read_value(PID, P(k)) for k in ("flag", "long", "deep", "nul", "big", "inf", "absent")] == [None] * 7)
    chk("нет файла — «нет данных»", W.read_value(PID, P("total", "none.json")) is None)
    put(PID, "broken.json", "{total: 12"); chk("битый JSON — «нет данных»", W.read_value(PID, P("total", "broken.json")) is None)
    put(PID, "list.json", "[1,2]"); chk("JSON не объектом — «нет данных»", W.read_value(PID, P("total", "list.json")) is None)
    put(PID, "huge.json", json.dumps({"total": 1, "pad": "x" * 70000})); chk("файл больше 64 КБ — «нет данных»", W.read_value(PID, P("total", "huge.json")) is None)
    outside = os.path.join(HOME, "outside.json"); open(outside, "w").write(json.dumps({"total": 777, "state": "ok"}))
    os.symlink(outside, os.path.join(WORK, PID, "link.json")); chk("ссылка на файл вне папки пака — «нет данных»", W.read_value(PID, P("total", "link.json")) is None)
    os.link(outside, os.path.join(WORK, PID, "hard.json")); chk("второе имя чужого файла (жёсткая ссылка) — «нет данных»", W.read_value(PID, P("total", "hard.json")) is None)
    os.mkfifo(os.path.join(WORK, PID, "pipe.json")); t0 = time.time()
    chk("канал вместо файла — «нет данных», без зависания", W.read_value(PID, P("total", "pipe.json")) is None and time.time() - t0 < 5)
    lone = os.path.join(WORK, "lone.json"); open(lone, "w").write('{"total": 778}')
    chk("указатель с «..» мимо проверки описания — всё равно «нет данных»", W.read_value(PID, P("total", "../lone.json")) is None)
    chk("указатель полным путём мимо проверки описания — всё равно «нет данных»", W.read_value(PID, P("total", lone)) is None)
    os.makedirs(os.path.join(WORK, "old-folder")); open(os.path.join(WORK, "old-folder", "count.json"), "w").write('{"total": 5}')
    chk("папка, что была в доме до пака (без пометки установки), — «нет данных»", W.read_value("old-folder", P("total")) is None)
    os.symlink(os.path.join(WORK, PID), os.path.join(WORK, "linked-pack"))
    chk("папка данных ссылкой на чужую — «нет данных»", W.read_value("linked-pack", P("total")) is None)
    os.makedirs(os.path.join(WORK, "memory"), exist_ok=True); open(os.path.join(WORK, "memory", W.DATA_MARK), "w").write("x"); open(os.path.join(WORK, "memory", "count.json"), "w").write('{"total": 5}')
    chk("папка самого дома — «нет данных», даже с пометкой", W.read_value("memory", P("total")) is None)

    # ── chat_data
    d = json.loads(W.build_data(PID, manifest(), "ru"))
    chk("данные виджета: название, статус словом ядра, цифры, подписи кнопок", d == {"t": "Аудит внимания", "s": "ok", "sl": "работает", "n": [["12", "разборов"], ["3.5", "за неделю"]], "a": ["Новый разбор", "Оплатить"]}, d)
    d = json.loads(W.build_data(PID, manifest(), "en"))
    chk("язык: английский, где он есть; где нет — что есть", d["t"] == "Attention audit" and d["sl"] == "working" and d["n"][1][1] == "за неделю" and d["a"] == ["New review", "Оплатить"], d)
    put(PID, "count.json", {"total": 12, "state": "great"}); d = json.loads(W.build_data(PID, manifest(), "ru"))
    chk("статус не из трёх слов и цифра без значения — «нет данных» и прочерк, а не старое", d["s"] == "nodata" and d["sl"] == "нет данных" and d["n"][1][0] == "—", d)
    d = json.loads(W.build_data(PID, {k: v for k, v in manifest().items() if k != "state"}, "ru")); chk("описание без статуса — виджет без слова статуса", "s" not in d and "sl" not in d)
    put(PID, "count.json", {"total": "<b>жирно</b>", "state": "ok", "week": "<img src=x>"})
    d = json.loads(W.build_data(PID, manifest(title={"ru": "<script>x</script>"}), "ru"))
    chk("текст с разметкой остаётся тем же текстом", d["t"] == "<script>x</script>" and d["n"][0][0] == "<b>жирно</b>" and d["n"][1][0] == "<img src=x>", d)
    fat = {"t": "😀" * 60, "s": "ok", "sl": "работает", "n": [["😀" * 24, "😀" * 16] for _ in range(3)], "a": ["😀" * 24] * 3}
    raw = json.dumps(fat, ensure_ascii=False, separators=(",", ":")); s = W.pack_data(json.loads(raw)); back = json.loads(s)
    chk("данные больше 1024 байт (%d) сжаты до предела: %d" % (len(raw.encode()), len(s.encode())), len(raw.encode()) > 1024 and 1000 <= len(s.encode()) <= 1024, len(s.encode()))
    chk("обрезка — с пометкой «…», короткое не тронуто", back["t"].endswith("…") and back["sl"] == "работает" and all(len(x) <= 24 for x in back["a"]), back)
    exact = {"t": "", "n": [], "a": []}; exact["t"] = "я" * ((1024 - len(json.dumps(exact, separators=(",", ":")))) // 2)
    chk("ровно 1024 байта — без обрезки", len(json.dumps(exact, ensure_ascii=False, separators=(",", ":")).encode()) == 1024 and json.loads(W.pack_data(dict(exact)))["t"] == exact["t"])
    more = dict(exact, t=exact["t"] + "я"); got = json.loads(W.pack_data(more))["t"]
    chk("на знак больше — обрезка", got.endswith("…") and len(W.pack_data(dict(exact, t=exact["t"] + "я")).encode()) <= 1024, len(got))

    # ── show → sent
    put(PID, "count.json", {"total": 12, "week": 3, "state": "ok"})
    open(os.path.join(WORK, "packs", PID, "run.py"), "w").write("open(%r, 'w').write('ran')\n" % BEACON)
    rc, o = R("show", PID, "--chat", "-100" + "5550001", "--bot", BOT); chk("виджет в группу — отказ", rc != 0 and "личку" in o.get("error", ""), o)
    rc, o = R("show", PID, "--chat", "@kanal", "--bot", BOT); chk("виджет в канал — отказ", rc != 0 and "личку" in o.get("error", ""), o)
    rc, o = R("show", PID, "--chat", OWNER, "--bot", "t.me/x?start=1"); chk("имя бота не по форме — отказ", rc != 0 and "--bot" in o.get("error", ""), o)
    rc, o = R("show", "no-such", "--chat", OWNER, "--bot", BOT); chk("пак без виджета — отказ", rc != 0 and "нет виджета" in o.get("error", ""), o)
    install("bad-pack", manifest(command="python3 run.py"), data={"total": 1})
    rc, o = R("show", "bad-pack", "--chat", OWNER, "--bot", BOT); chk("описание с командой, попавшее в дом мимо установки, — show отказывает с причиной", rc != 0 and any("command" in x for x in o.get("why", [])), o)
    rc, o = R("sent", PID, "--message", "5"); chk("записать неотправленное — отказ", rc != 0 and "сначала show" in o.get("error", ""), o)
    rc, o = R("show", PID, "--chat", OWNER, "--bot", BOT)
    a = o.get("args", {})
    chk("show: что отправить инструментом widget — чат, код, данные", rc == 0 and o.get("tool") == "widget" and set(a) == {"chat_id", "html", "chat_data"} and a["chat_id"] == OWNER
        and json.loads(a["chat_data"])["n"][0] == ["12", "разборов"] and len(a["chat_data"].encode()) <= 1024, o)
    chk("в коде — ссылки с метками этого пака и этого бота", re.findall(r"https://t\.me/[^\"?]+\?start=[\w-]+", a.get("html", "")) == ["https://t.me/%s?start=w_%s_new" % (BOT, PID), "https://t.me/%s?start=w_%s_pay" % (BOT, PID)])
    chk("пока не записано — нажатие ещё не моё", R("press", "w_%s_new" % PID)[1].get("known") is False)
    rc, o = R("sent", PID); chk("sent без id сообщения — отказ", rc != 0 and "--message" in o.get("error", ""), o)
    rc, o = R("sent", PID, "--message", "321"); r = state()["widgets"][PID]
    chk("время записи — то, что передано, а не часы машины", r["ts"] == int(NOW[0].timestamp()), r["ts"])
    chk("sent: записаны чат, сообщение, метки, данные; файл 600", rc == 0 and r["message_id"] == 321 and r["chat_id"] == OWNER and r["marks"] == ["w_%s_new" % PID, "w_%s_pay" % PID]
        and "pending" not in r and oct(os.stat(os.path.join(WORK, "state", "widgets.json")).st_mode & 0o777) == "0o600", r)

    # ── refresh
    rc, o = R("refresh", PID); chk("без изменений — без вызова", rc == 0 and o["widgets"] == [{"pack": PID, "changed": False}], o)
    chk("без изменений — правка в счёт часа не идёт", state()["edits"] == [])
    put(PID, "count.json", {"total": 13, "week": 3, "state": "attention"})
    rc, o = R("refresh", "--all"); w = (o.get("widgets") or [{}])[0]
    chk("изменилось — что отправить инструментом widget_data: то же сообщение, новые данные", w.get("tool") == "widget_data" and w["args"]["chat_id"] == OWNER and w["args"]["message_id"] == "321"
        and json.loads(w["args"]["chat_data"])["n"][0][0] == "13" and json.loads(w["args"]["chat_data"])["sl"] == "внимание" and set(w["args"]) == {"chat_id", "message_id", "chat_data"}, o)
    chk("предложенная правка идёт в счёт часа", len(state()["edits"]) == 1, state()["edits"])
    rc, o = R("refresh", PID); chk("пока не записано — то же предложение ещё раз", o["widgets"][0].get("tool") == "widget_data", o)
    rc, o = R("sent", PID); chk("sent после обновления: id прежний", rc == 0 and o["message_id"] == 321, o)
    rc, o = R("refresh", PID); chk("записано — снова без вызова", o["widgets"] == [{"pack": PID, "changed": False}], o)
    rc, o = R("refresh"); chk("refresh без пака и без --all — отказ", rc != 0, o)
    rc, o = R("refresh", "no-such"); chk("refresh неотправленного — отказ", rc != 0 and "show" in o.get("error", ""), o)
    s = state(); now = NOW[0].timestamp(); s["edits"] = [now - 4000] * 5 + [now - 10 * i for i in range(W.EDITS_PER_HOUR)]
    json.dump(s, open(os.path.join(WORK, "state", "widgets.json"), "w"))
    put(PID, "count.json", {"total": 14, "week": 3, "state": "ok"})
    rc, o = R("refresh", PID); w = o["widgets"][0]
    chk("потолок правок в час: изменилось, но придержано — без вызова", w.get("changed") is True and "потолок" in w.get("held", "") and "tool" not in w, o)
    chk("правки старше часа из счёта ушли, придержанная в счёт не пошла", len(state()["edits"]) == W.EDITS_PER_HOUR)
    tick(3309); rc, o = R("refresh", PID)      # the oldest of the thirty is now 3309 + 290 s old: one second short of an hour
    chk("за секунду до часа самая старая правка ещё в счёте — придержано", "held" in o["widgets"][0], o)
    tick(2); rc, o = R("refresh", PID); chk("час прошёл — самая старая ушла из счёта, правка проходит", o["widgets"][0].get("tool") == "widget_data", o); R("sent", PID)
    rc, o = R("refresh", PID, "--now", "вчера"); chk("--now не по форме — отказ", rc != 0 and "ISO" in o.get("error", ""), o)

    # ── press: whose step it is; nothing is run
    rc, o = R("press", "w_%s_new" % PID)
    chk("своя метка: чей шаг и что делать", rc == 0 and o.get("known") is True and o["pack"] == PID and o["action"] == "new" and o["label"] == "Новый разбор" and o["lock"] is False and "навыку пака" in o["do"], o)
    rc, o = R("press", "w_%s_pay" % PID); chk("действие под замком — сначала Согласование", o.get("lock") is True and "Согласование" in o["do"], o)
    for mk, what in (("w_%s_delete" % PID, "метка, которой у пака нет"), ("w_other-pack_new", "метка чужого пака"), ("w_oplatit", "метка не по форме"), ("W_%s_new" % PID, "другой регистр"),
                     ("w_%s_new; rm -rf ~" % PID, "метка с хвостом"), ("", "пустая")):
        rc, o = R("press", mk); chk("нажатие: %s — ничего" % what, o.get("known") is False and o.get("ok") is False and "ничего не делаю" in o.get("line", ""), o)
    m2 = manifest(); m2["actions"] = m2["actions"][:1]; install(m=m2)
    rc, o = R("press", "w_%s_pay" % PID); chk("кнопку убрали из описания — её нажатие уже не моё", o.get("known") is False, o)
    rc, o = R("refresh", PID); chk("кнопки пака изменились — обновление просит отправить виджет заново, данных не шлёт", "stale" in o["widgets"][0] and "tool" not in o["widgets"][0], o)
    m3 = manifest(); m3["actions"] = m3["actions"] + [{"label": {"ru": "Ещё"}, "mark": "extra"}]; install(m=m3)
    rc, o = R("press", "w_%s_extra" % PID); chk("кнопка есть в описании, но не в отправленном виджете — нажатие не моё", o.get("known") is False, o)
    install()

    # ── the pack is removed: «removed» once, then silence
    shutil.rmtree(os.path.join(WORK, "packs", PID))
    s = state(); s["edits"] = []; json.dump(s, open(os.path.join(WORK, "state", "widgets.json"), "w"))
    rc, o = R("refresh", "--all"); w = o["widgets"][0]; d = json.loads(w["args"]["chat_data"]) if "args" in w else {}
    chk("пак снят: последнее обновление — «снят», без цифр и кнопок", d == {"t": "Аудит внимания", "s": "removed", "sl": "снят", "n": [], "a": []}, o)
    chk("нажатие на виджет снятого пака — ничего", R("press", "w_%s_new" % PID)[1].get("known") is False)
    rc, o = R("sent", PID); chk("записано: виджет закрыт", o.get("retired") is True, o)
    rc, o = R("refresh", "--all"); chk("закрытый виджет больше не обновляется", o["widgets"] == [], o)
    install(); chk("пак поставили снова, а виджет закрыт: нажатие на старый — ничего, пока не отправлен новый", R("press", "w_%s_new" % PID)[1].get("known") is False)
    rc, o = R("refresh", "--all"); chk("и старый виджет не оживает", o["widgets"] == [], o)
    chk("код пака не запускался ни разу: файла-маячка нет", not os.path.exists(BEACON))

    # ── check, as the pack install calls it
    f = os.path.join(T, "w.json"); json.dump(manifest(), open(f, "w"))
    rc, o = R("check", f, "--pack", PID); chk("check: годится, метки названы", rc == 0 and o.get("ok") is True and o["marks"] == ["w_%s_new" % PID, "w_%s_pay" % PID], o)
    json.dump(manifest(command="python3 run.py"), open(f, "w")); rc, o = R("check", f, "--pack", PID)
    chk("check: поле с командой — код 1 и причина", rc == 1 and "ok" not in o and any("command" in x for x in o.get("why", [])), o)
    open(f, "w").write("{"); rc, o = R("check", f, "--pack", PID); chk("check: битый файл — код 1", rc == 1 and "JSON" in o.get("error", ""), o)

    # ── the pack install: update.py install-pack end to end
    UP = os.path.join(REPO, "skills", "mila-update", "update.py")
    TG = os.path.join(CL, "channels", "telegram"); os.makedirs(os.path.join(TG, "inbound")); os.makedirs(os.path.join(CL, "skills"))
    json.dump({"allowFrom": [OWNER]}, open(os.path.join(TG, "access.json"), "w"))
    KIT = os.path.join(T, "kit"); EV = os.path.join(TG, "inbound", "events.jsonl"); CARDS = os.path.join(TG, "cards.jsonl")
    UENV = dict(ENV, CLAUDE_CONFIG_DIR=CL, MILA_PACKS=KIT, TELEGRAM_STATE_DIR=TG, CLAUDECODE="1")
    for k in ("MILA_OUTBOX", "MILA_OWNER_CHAT", "MILA_KIT"): UENV.pop(k, None)
    def U(*a):
        r = subprocess.run([sys.executable, UP, *a], env=UENV, capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=60)
        try: return r.returncode, json.loads(r.stdout or r.stderr or "{}")
        except ValueError: return r.returncode, {"raw": (r.stdout + r.stderr)[:300]}
    def kit(pid, wj):
        d = os.path.join(KIT, pid); os.makedirs(os.path.join(d, pid + "-skill", "scripts"))
        json.dump({"id": pid, "version": "0.1.0", "title": {"ru": "Демо " + pid}}, open(os.path.join(d, "pack.json"), "w"), ensure_ascii=False)
        open(os.path.join(d, "ROLE.md"), "w").write("# Роль\n")
        open(os.path.join(d, pid + "-skill", "SKILL.md"), "w").write("---\nname: %s-skill\ndescription: demo\n---\nDemo.\n" % pid)
        open(os.path.join(d, pid + "-skill", "scripts", "run.py"), "w").write("open(%r, 'w').write('ran')\n" % BEACON)
        if wj is not None: open(os.path.join(d, "widget.json"), "w", encoding="utf-8").write(wj if isinstance(wj, str) else json.dumps(wj, ensure_ascii=False))
    cid = [0]
    def put_pack(pid):
        rc, plan = U("pack-plan", pid)
        if "text" not in plan: return rc, plan
        cid[0] += 1; c = "c%d" % cid[0]; ts = machine_iso()
        open(CARDS, "a").write(json.dumps({"card_id": c, "chat_id": OWNER, "text": plan["text"], "ts": ts, "buttons": plan["buttons"]}, ensure_ascii=False) + "\n")
        open(CARDS, "a").write(json.dumps({"card_id": c, "used_ts": ts, "used_by": OWNER}) + "\n")
        open(EV, "a").write(json.dumps({"params": {"meta": {"type": "callback", "card_id": c, "user_id": OWNER, "callback_data": "pack:yes"}}}) + "\n")
        return U("install-pack", pid, "--card", c)
    kit("vid-good", manifest()); kit("vid-cmd", manifest(command="python3 run.py")); kit("vid-none", None); kit("vid-taken", manifest()); kit("vid-broken", "{")
    os.makedirs(os.path.join(WORK, "vid-taken")); open(os.path.join(WORK, "vid-taken", "count.json"), "w").write('{"total": 99, "state": "ok"}')
    rc, o = put_pack("vid-good"); g = os.path.join(WORK, "vid-good")
    chk("установка пака с виджетом: описание в доме, папка данных создана и помечена, подсказка show", rc == 0 and o.get("ok") and "widget.py show vid-good" in o.get("widget", "")
        and os.path.isfile(os.path.join(WORK, "packs", "vid-good", "widget.json")) and os.path.isfile(os.path.join(g, W.DATA_MARK)) and oct(os.stat(g).st_mode & 0o777) == "0o700", o)
    put("vid-good", "count.json", {"total": 2, "state": "ok"})
    rc, o = R("show", "vid-good", "--chat", OWNER, "--bot", BOT); chk("после установки show читает данные пака", rc == 0 and json.loads(o["args"]["chat_data"])["n"][0][0] == "2", o)
    rc, o = put_pack("vid-good"); chk("повторная установка: папка данных та же, виджет ставится", rc == 0 and "widget" in o and "widget_refused" not in o and os.path.isfile(os.path.join(g, "count.json")), o)
    rc, o = put_pack("vid-cmd")
    chk("пак с командой в widget.json: пак стоит, виджета нет, причина названа, папки данных нет", rc == 0 and o.get("ok") and "widget" not in o and any("command" in x for x in o.get("widget_refused", []))
        and not os.path.exists(os.path.join(WORK, "packs", "vid-cmd", "widget.json")) and not os.path.exists(os.path.join(WORK, "vid-cmd")), o)
    rc, o = R("show", "vid-cmd", "--chat", OWNER, "--bot", BOT); chk("и show по нему — отказ", rc != 0, o)
    rc, o = put_pack("vid-broken"); chk("битый widget.json: пак стоит, виджета нет", rc == 0 and o.get("ok") and "widget" not in o and o.get("widget_refused"), o)
    rc, o = put_pack("vid-none"); chk("пак без widget.json: как раньше, ни слова о виджете", rc == 0 and o.get("ok") and "widget" not in o and "widget_refused" not in o and not os.path.exists(os.path.join(WORK, "vid-none")), o)
    rc, o = put_pack("vid-taken")
    chk("в доме уже есть папка с именем пака: виджета нет, папка не тронута и не помечена", rc == 0 and o.get("ok") and "widget" not in o and any("создана не этим паком" in x for x in o.get("widget_refused", []))
        and not os.path.exists(os.path.join(WORK, "vid-taken", W.DATA_MARK)) and not os.path.exists(os.path.join(WORK, "packs", "vid-taken", "widget.json")), o)
    # ── the pack is removed: an empty marked data folder goes with it, a folder with data stays
    def drop_pack(pid):
        rc, plan = U("remove-pack", pid)
        if "text" not in plan: return rc, plan
        cid[0] += 1; c = "c%d" % cid[0]; ts = machine_iso()
        open(CARDS, "a").write(json.dumps({"card_id": c, "chat_id": OWNER, "text": plan["text"], "ts": ts, "buttons": plan["buttons"]}, ensure_ascii=False) + "\n")
        open(CARDS, "a").write(json.dumps({"card_id": c, "used_ts": ts, "used_by": OWNER}) + "\n")
        open(EV, "a").write(json.dumps({"params": {"meta": {"type": "callback", "card_id": c, "user_id": OWNER, "callback_data": "pack:yes"}}}) + "\n")
        return U("remove-pack", pid, "--card", c)
    kit("vid-empty", manifest()); rc, o = put_pack("vid-empty"); e = os.path.join(WORK, "vid-empty")
    chk("пак с виджетом поставлен, данных ещё нет — в папке только пометка", rc == 0 and os.listdir(e) == [W.DATA_MARK], o)
    rc, o = drop_pack("vid-empty"); chk("пак снят: пустая помеченная папка данных ушла с ним", rc == 0 and o.get("widget_data_removed") is True and not os.path.exists(e), o)
    rc, o = drop_pack("vid-good"); chk("пак снят, а в папке есть данные — папка остаётся (данные хозяина), об уборке ни слова", rc == 0 and "widget_data_removed" not in o and os.path.isfile(os.path.join(g, "count.json")) and os.path.isfile(os.path.join(g, W.DATA_MARK)), o)
    rc, o = drop_pack("vid-taken"); chk("пак снят: папка, что была в доме до него (без пометки), не тронута", rc == 0 and "widget_data_removed" not in o and os.path.isfile(os.path.join(WORK, "vid-taken", "count.json")), o)
    kit("vid-link", manifest()); rc, o = put_pack("vid-link"); lk = os.path.join(WORK, "vid-link"); os.remove(os.path.join(lk, W.DATA_MARK)); os.symlink(outside, os.path.join(lk, W.DATA_MARK))
    rc, o = drop_pack("vid-link"); chk("пометка подменена ссылкой — папку не убираю, чужой файл цел", rc == 0 and "widget_data_removed" not in o and os.path.islink(os.path.join(lk, W.DATA_MARK)) and os.path.isfile(outside), o)
    chk("установка, снятие и виджеты не запустили код ни одного пака: файла-маячка нет", not os.path.exists(BEACON))
finally:
    shutil.rmtree(T, ignore_errors=True)
print("итог %d/%d" % (ok, n)); sys.exit(0 if ok == n else 1)
