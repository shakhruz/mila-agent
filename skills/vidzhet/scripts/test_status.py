#!/usr/bin/env python3
"""status.py: the five core modules' widgets — the Scheduler, Tasks, the Library, the Safe, Telegram — count with the modules'
own code on a temp home; only numbers, times and a status word come out — never a job's text, a question, a key's value or
name; a broken source is «no data»; a pack cannot take a core module's id; show / press / refresh work for a core module the
same way as for a pack. The Scheduler's clock is one moment handed to every process (MILA_CRON_NOW), so the result does not
depend on which clock the test's process and its children see. Run: python3 test_status.py"""
import datetime as dt, hashlib, json, os, shutil, subprocess, sys, tempfile, time
sys.dont_write_bytecode = True; os.umask(0o022)
H = os.path.dirname(os.path.abspath(__file__)); SK = os.path.dirname(os.path.dirname(H))
T = tempfile.mkdtemp(prefix="vzstatus-"); HOME = os.path.join(T, "home"); WORK = os.path.join(HOME, "work"); CL = os.path.join(HOME, ".claude")
TG = os.path.join(CL, "channels", "telegram"); EV = os.path.join(TG, "inbound", "events.jsonl")
os.makedirs(os.path.join(WORK, "state")); os.makedirs(CL)
for k in ("MILA_SCHEDULER_BEAT", "BARABAN_STATE", "XDG_STATE_HOME", "OWNER_TZ", "OPENROUTER_API_KEY", "GROQ_API_KEY", "SAFE_DIR", "OWNER_JSON", "MILA_LANG"): os.environ.pop(k, None)
os.environ.update(HOME=HOME, MILA_WORK=WORK, CLAUDE_CONFIG_DIR=CL, TELEGRAM_STATE_DIR=TG, MILA_EVENTS=EV, PYTHONDONTWRITEBYTECODE="1")
sys.path.insert(0, H)
import status as S, widget as W
ok = n = 0
def chk(m, c, x=""):
    global ok, n
    n += 1; ok += bool(c); print(("✅ " if c else "❌ ") + m + ("" if c else "  ← " + str(x)[:400]))
def run(*a):
    r = subprocess.run([sys.executable, *a], capture_output=True, text=True, env=dict(os.environ), stdin=subprocess.DEVNULL, timeout=60)
    return r.returncode, (r.stdout + r.stderr).strip()
def R(*a):
    rc, o = run("-I", os.path.join(H, "widget.py"), *a)
    try: return rc, json.loads(o)
    except ValueError: return rc, {"raw": o[:300]}
nums = lambda r: [v for v, _ in r["numbers"]]
MC = os.path.join(SK, "raspisanie", "mila_cron.py"); CARDS = os.path.join(SK, "cards", "cards.py")
SECRET_TEXT = "тайный текст задачи про договор"; QUESTION = "Выпускаем обновление сегодня вечером"
now = dt.datetime.now().astimezone().replace(microsecond=0)
os.environ["MILA_CRON_NOW"] = now.isoformat()      # one clock for the Scheduler's part: mila-cron here, mila-cron as a child and the status all read this moment

try:
    # ── an empty home: every module answers, nothing falls
    e = {k: S.status(k) for k in S.FUNCS}
    chk("пустой дом: Планировщик — 0 задач, ближайшей нет, «работает»", e["planirovshchik"] == {"state": "ok", "numbers": [["0", S.L("задач", "jobs")], ["—", S.L("ближайшая", "next")], ["0", S.L("без итога", "no result")]]}, e["planirovshchik"])
    chk("пустой дом: Задачи — три нуля", nums(e["zadachi"]) == ["0", "0", "0"] and e["zadachi"]["state"] == "ok", e["zadachi"])
    chk("пустой дом: Библиотека — каталога нет: «нет данных», прочерки", e["biblioteka"]["state"] is None and nums(e["biblioteka"]) == ["0", "—", "—"], e["biblioteka"])
    chk("пустой дом: Сейф — 0 и 0", nums(e["sejf"]) == ["0", "0"] and e["sejf"]["state"] == "ok", e["sejf"])
    chk("пустой дом: Telegram — журнала нет: «внимание», входящих не было", e["telegram"]["state"] == "attention" and nums(e["telegram"])[0] == "—", e["telegram"])

    # ── the Scheduler
    rc, o = run(MC, "add", "utro", "0 9 * * *", SECRET_TEXT); assert rc == 0, o
    rc, o = run(MC, "add", "vecher", "30 19 * * *", "вечерняя проверка"); assert rc == 0, o
    rc, o = run(MC, "add", "pauza", "0 12 * * *", "на паузе"); run(MC, "pause", "pauza")
    r = S.status("planirovshchik")
    chk("задачи есть, а отметки прохода службы нет — «стоит»: ничего не сработает", r["state"] == "down" and nums(r)[0] == "2", r)
    BEAT = os.path.join(HOME, "state", "baraban", "home.beat"); os.makedirs(os.path.dirname(BEAT))
    def beat(ago_s): open(BEAT, "w", encoding="utf-8").write((now - dt.timedelta(seconds=ago_s)).isoformat())
    beat(301); r = S.status("planirovshchik"); chk("отметка старше пяти минут — «стоит»", r["state"] == "down", r)
    beat(300); r = S.status("planirovshchik"); chk("отметке ровно пять минут — служба жива", r["state"] == "ok", r)
    open(BEAT, "w").write("вчера"); r = S.status("planirovshchik"); chk("в отметке не время — «стоит», без падения", r["state"] == "down" and nums(r)[0] == "2", r)
    beat(20)
    r = S.status("planirovshchik")
    chk("две включённые задачи, одна на паузе — в счёте две; ближайшая — время", nums(r)[0] == "2" and len(nums(r)[1]) in (5, 11) and ":" in nums(r)[1] and nums(r)[2] == "0" and r["state"] == "ok", r)
    import importlib.util
    spec = importlib.util.spec_from_file_location("mc_for_test", MC); mcm = importlib.util.module_from_spec(spec); spec.loader.exec_module(mcm)
    want = min(dt.datetime.fromisoformat(x["next"]) for x in mcm.listing() if x.get("enabled") and x.get("next"))
    chk("ближайшая — самый ранний срок из включённых задач, как его считает сам mila-cron", nums(r)[1] == S._when(want, mcm.now()), (nums(r)[1], want))
    os.makedirs(os.path.dirname(EV)); os.chmod(TG, 0o700); os.chmod(os.path.dirname(EV), 0o700)
    def fire(job, ago_s):
        t = now - dt.timedelta(seconds=ago_s)
        open(EV, "a", encoding="utf-8").write(json.dumps({"ts": int(t.timestamp() * 1000), "params": {"content": "[⏰ расписание] " + job, "meta": {"message_id": "cron-x-%s-1" % job, "ts": t.isoformat(), "ritual": "cron", "job": job}}}) + "\n")
    fire("utro", 3600); os.chmod(EV, 0o600)
    r = S.status("planirovshchik"); chk("задача сработала, итога нет — «без итога» 1, «внимание»", nums(r)[2] == "1" and r["state"] == "attention", r)
    beat(900); r = S.status("planirovshchik"); chk("есть «без итога», и служба стоит — «стоит» сильнее «внимания»", r["state"] == "down" and nums(r)[2] == "1", r); beat(20)
    run(MC, "done", "utro", "сделано"); r = S.status("planirovshchik"); chk("итог записан — 0, «работает»", nums(r)[2] == "0" and r["state"] == "ok", r)
    fire("utro", -600); r = S.status("planirovshchik"); chk("сработала снова, позже итога — снова «без итога»", nums(r)[2] == "1", r)
    again = (now + dt.timedelta(seconds=600)).replace(second=0, microsecond=0)
    open(os.path.join(WORK, "schedule", "done.jsonl"), "a", encoding="utf-8").write(json.dumps({"id": "utro", "at": again.isoformat(timespec="minutes"), "result": "ещё раз"}) + "\n")
    r = S.status("planirovshchik"); chk("итог в ту же минуту, что запуск (итог пишется до минуты) — засчитан", nums(r)[2] == "0", r)
    jf = os.path.join(WORK, "schedule", "jobs.json"); d = json.load(open(jf, encoding="utf-8"))
    for j in d["jobs"]:
        if j["id"] == "vecher": j["expires"] = (now.date() - dt.timedelta(days=1)).isoformat()
    json.dump(d, open(jf, "w", encoding="utf-8"), ensure_ascii=False)
    r = S.status("planirovshchik"); chk("у задачи вышел срок — она не в счёте, «внимание»", nums(r)[0] == "1" and r["state"] == "attention", r)
    chk("текст задачи в статус не попадает", SECRET_TEXT not in json.dumps(r, ensure_ascii=False) and "utro" not in json.dumps(r, ensure_ascii=False))
    keep = open(jf, encoding="utf-8").read(); open(jf, "w").write("{broken")
    r = S.status("planirovshchik"); chk("файл задач не читается — «нет данных», без цифр, без падения", r == {"state": None, "numbers": []}, r)
    open(jf, "w", encoding="utf-8").write(keep)

    # ── Tasks
    rc, o = run(CARDS, "ask", "--q", QUESTION, "--why", "окно для выкладки до вечера", "--opt", "a|Да, выпускаем|уйдёт сегодня", "--opt", "b|Подождать|уйдёт завтра", "--rec", "a"); assert rc == 0, o
    r = S.status("zadachi"); chk("один открытый вопрос — «ждёт вас» 1, «работает»", nums(r)[0] == "1" and r["state"] == "ok", r)
    rc, o = run(CARDS, "ask", "--q", "Продлеваем домен на год", "--why", "срок был вчера", "--opt", "a|Да|продлим", "--opt", "b|Нет|отпустим", "--rec", "a", "--due", (now - dt.timedelta(days=1)).isoformat(timespec="minutes")); assert rc == 0, o
    r = S.status("zadachi"); chk("несрочный вопрос с вышедшим сроком — «внимание», в счёте два", nums(r)[0] == "2" and r["state"] == "attention", r)
    rc, o2 = run(CARDS, "answer", json.loads(o)["id"], "--close", "домен продлили сами"); assert rc == 0, o2
    r = S.status("zadachi"); chk("просроченный вопрос закрыт — снова один, «работает»", nums(r)[0] == "1" and r["state"] == "ok", r)
    rc, o = run(CARDS, "ask", "--q", "Оплачиваем хостинг сейчас", "--why", "срок истекает", "--opt", "a|Да|оплата", "--opt", "b|Нет|ждём", "--rec", "a", "--urgent"); assert rc == 0, o
    r = S.status("zadachi"); chk("срочный вопрос (срок не вышел) — «внимание», в счёте два", nums(r)[0] == "2" and r["state"] == "attention", r)
    chk("текст вопроса в статус не попадает", QUESTION not in json.dumps(r, ensure_ascii=False))
    rc, o = run(CARDS, "task", "--task", "Собрать отчёт за неделю", "--why", "хозяин просил к пятнице", "--to", "mila"); assert rc == 0, o
    r = S.status("zadachi"); chk("предложенная задача — «предложено» 1, вопросов по-прежнему два", nums(r)[:2] == ["2", "1"], r)
    today = now.date().isoformat(); yday = (now.date() - dt.timedelta(days=1)).isoformat()
    with open(os.path.join(WORK, "dela.jsonl"), "w", encoding="utf-8") as f:
        for date, st in ((today, "сделала"), (today, "сделала"), (today, "приняли"), (yday, "сделала")):
            f.write(json.dumps({"дата": date, "дело": "дело " + st, "ступень": st}, ensure_ascii=False) + "\n")
        f.write("not json\n")
    r = S.status("zadachi"); chk("сделано сегодня — только сегодняшние строки «сделала»; битая строка не мешает", nums(r)[2] == "2", r)

    # ── the Library
    for pid in ("pack-one", "pack-two"):
        os.makedirs(os.path.join(WORK, "packs", pid)); json.dump({"id": pid, "keys": ["OPENROUTER_API_KEY", {"name": "GROQ_API_KEY"}, "DEMO_API_KEY"] if pid == "pack-one" else []}, open(os.path.join(WORK, "packs", pid, "pack.json"), "w"))
    os.makedirs(os.path.join(WORK, "packs", "not-a-pack"))
    r = S.status("biblioteka"); chk("паков стоит — по pack.json в доме (2), папка без него не в счёте; каталога нет — «нет данных»", nums(r) == ["2", "—", "—"] and r["state"] is None, r)
    cache = os.path.join(CL, "mila-library"); os.makedirs(cache)
    ix = {"v": 1, "packs": [{"id": pid, "category": "razminka", "free": True, "requires_core": "1.0.0", "sha256": hashlib.sha256(pid.encode()).hexdigest(), "title": {"ru": pid}, "for_whom": {"ru": "для пробы"}, "version": "0.1.0"} for pid in ("pack-one", "lib-a", "lib-b")]}
    body = json.dumps(ix).encode(); open(os.path.join(cache, "library.json"), "wb").write(body)
    r = S.status("biblioteka"); chk("каталог в кэше не тот, чью сумму несёт ядро, — «стоит», цифр каталога нет", r["state"] == "down" and nums(r) == ["2", "—", "—"], r)
    lock = os.path.join(T, "library.lock"); json.dump({"index_sha256": hashlib.sha256(body).hexdigest()}, open(lock, "w"))
    real_mod = S._mod
    def patched(name, *paths):
        m = real_mod(name, *paths)
        if name == "library": m.LOCK = lock
        return m
    S._mod = patched
    r = S.status("biblioteka"); chk("каталог проверен: в каталоге 3, новых 2 (один уже стоит), «работает»", nums(r) == ["2", "3", "2"] and r["state"] == "ok", r)
    old = time.time() - 8 * 86400; os.utime(os.path.join(cache, "library.json"), (old, old))
    r = S.status("biblioteka"); chk("каталог не обновлялся 8 дней — «внимание»", r["state"] == "attention", r)
    fresh = time.time() - 6 * 86400; os.utime(os.path.join(cache, "library.json"), (fresh, fresh))
    chk("шесть дней — ещё «работает»", S.status("biblioteka")["state"] == "ok")
    S._mod = real_mod

    # ── the Safe: have / missing by names the packs gave; never a value, never a name
    r = S.status("sejf"); chk("паки назвали два ключа, которые ядро умеет проверить, — нет ни одного: 0 и 2, «внимание»; третий (чужой) не в счёте", nums(r) == ["0", "2"] and r["state"] == "attention", r)
    VALUE = "sk-" + "or-" + "v" * 12
    os.environ["OPENROUTER_API_KEY"] = VALUE
    r = S.status("sejf"); chk("один ключ появился — 1 и 1", nums(r) == ["1", "1"] and r["state"] == "attention", r)
    os.makedirs(os.path.join(WORK, "secrets"), mode=0o700); open(os.open(os.path.join(WORK, "secrets", "groq.env"), os.O_WRONLY | os.O_CREAT, 0o600), "w").write("GROQ_API_KEY=" + "gsk" + "_" + "w" * 12 + "\n")
    r = S.status("sejf"); chk("второй — в сейфе: 2 и 0, «работает»", nums(r) == ["2", "0"] and r["state"] == "ok", r)
    dump = json.dumps(r, ensure_ascii=False); chk("ни значения, ни имени ключа в статусе нет", VALUE not in dump and "w" * 12 not in dump and "API_KEY" not in dump and "groq" not in dump.lower(), dump)
    os.chmod(os.path.join(WORK, "secrets", "groq.env"), 0o644)
    r = S.status("sejf"); chk("сейф открыт для других (права не 600) — «нет данных», а не цифры", r == {"state": None, "numbers": []}, r)
    os.chmod(os.path.join(WORK, "secrets", "groq.env"), 0o600); os.environ.pop("OPENROUTER_API_KEY")

    # ── Telegram: the doctor's local checks
    r = S.status("telegram"); stamp = dt.datetime.fromtimestamp(os.path.getmtime(EV)).astimezone().strftime("%H:%M")
    chk("журнал входящих есть, приёмник не запущен — «внимание»; последнее входящее — время журнала", r["state"] == "attention" and nums(r)[0] == stamp and int(nums(r)[1]) >= 1, r)
    os.chmod(EV, 0o644); r = S.status("telegram"); chk("журнал открыт для чужих — по доктору красное: «стоит»", r["state"] == "down", r); os.chmod(EV, 0o600)
    old = time.time() - 3 * 86400; os.utime(EV, (old, old)); r = S.status("telegram")
    chk("последнее входящее не сегодня — с датой", len(nums(r)[0]) == 11 and nums(r)[0][2] == ".", r)

    # ── status(): the closed list, the shape, the failure
    S.FUNCS["boom"] = lambda: 1 / 0; chk("сбой внутри модуля — «нет данных», виджет не падает", S.status("boom") == {"state": None, "numbers": []})
    S.FUNCS["odd"] = lambda: {"state": "great", "numbers": [["x" * 40, S.L("а", "a")]] * 5}
    r = S.status("odd"); chk("слово статуса не из списка — «нет данных»; значение режется до 24, цифр не больше трёх", r["state"] is None and len(r["numbers"]) == 3 and len(r["numbers"][0][0]) == 24, r)
    del S.FUNCS["boom"], S.FUNCS["odd"]
    chk("список модулей ядра закрытый и один: у каждого название, кнопка, расчёт и действие", set(S.CORE) == set(S.FUNCS) == {"planirovshchik", "zadachi", "biblioteka", "sejf", "telegram"}
        and all((k, a["mark"]) in S.DO for k, v in S.CORE.items() for a in v["actions"]) and len(S.DO) == sum(len(v["actions"]) for v in S.CORE.values()))

    # ── a pack cannot take a core module's id
    m = {"title": {"ru": "Подмена"}, "numbers": [{"label": {"ru": "штук"}, "file": "count.json", "key": "total"}]}
    for cid in S.CORE:
        chk("пак с id «%s» — без виджета: это модуль ядра" % cid, any("модуля ядра" in x for x in W.check_manifest(m, cid)))
    os.makedirs(os.path.join(WORK, "sejf")); open(os.path.join(WORK, "sejf", W.DATA_MARK), "w").write("sejf\n"); open(os.path.join(WORK, "sejf", "count.json"), "w").write('{"total": 999}')
    chk("папка данных с именем модуля ядра не читается, даже помеченная", W.read_value("sejf", {"file": "count.json", "key": "total"}) is None)
    os.makedirs(os.path.join(WORK, "packs", "zadachi")); json.dump(m, open(os.path.join(WORK, "packs", "zadachi", "widget.json"), "w"), ensure_ascii=False)
    d = json.loads(W.build_data("zadachi", W.load_manifest("zadachi")[0], "ru"))
    chk("widget.json, подложенный в packs/<модуль ядра>, не читается: виджет модуля рисует ядро", d["t"] == "Задачи" and d["a"] == ["Вопросы"] and [x[1] for x in d["n"]] == ["ждёт вас", "предложено", "сделано сегодня"], d)

    # ── show / sent / refresh / press for a core module
    OWNER = "555" + "000111"; BOT = "m_test_bot"
    rc, o = R("show", "planirovshchik", "--chat", OWNER, "--bot", BOT); a = o.get("args", {}); d = json.loads(a.get("chat_data", "{}"))
    chk("show модуля ядра: название, статус, три цифры, кнопка; ссылка с меткой модуля", rc == 0 and o.get("tool") == "widget" and d["t"] == "Планировщик" and d["sl"] in ("работает", "внимание") and len(d["n"]) == 3 and d["a"] == ["Список"]
        and "https://t.me/%s?start=w_planirovshchik_list" % BOT in a.get("html", ""), o)
    rc, o = R("show", "planirovshchik", "--chat", OWNER, "--bot", BOT, "--lang", "en"); d = json.loads(o["args"]["chat_data"])
    chk("show по-английски: Scheduler, jobs / next / no result, List", d["t"] == "Scheduler" and [x[1] for x in d["n"]] == ["jobs", "next", "no result"] and d["a"] == ["List"], d)
    R("show", "planirovshchik", "--chat", OWNER, "--bot", BOT); rc, o = R("sent", "planirovshchik", "--message", "77"); chk("sent: виджет модуля записан", rc == 0 and o.get("message_id") == 77, o)
    rc, o = R("refresh", "planirovshchik"); chk("refresh: ничего не изменилось — без вызова", o.get("widgets") == [{"pack": "planirovshchik", "changed": False}], o)
    run(MC, "add", "novaya", "0 7 * * *", "новая задача")
    rc, o = R("refresh", "--all"); w = (o.get("widgets") or [{}])[0]
    chk("refresh: задач стало больше — правка данных того же сообщения", w.get("tool") == "widget_data" and w["args"]["message_id"] == "77" and json.loads(w["args"]["chat_data"])["n"][0][0] == "2", o)
    rc, o = R("press", "w_planirovshchik_list"); chk("нажатие: шаг модуля ядра, названа команда ядра, скрипт ничего не исполнил", o.get("known") is True and o.get("core") is True and "mila_cron.py list" in o.get("do", "") and o.get("lock") is False, o)
    rc, o = R("press", "w_planirovshchik_delete"); chk("нажатие: кнопки, которой у модуля нет, — ничего", o.get("known") is False, o)
    rc, o = R("press", "w_sejf_add"); chk("нажатие на виджет модуля, который не отправляли, — ничего", o.get("known") is False, o)
    rc, o = R("show", "no-such-module", "--chat", OWNER, "--bot", BOT); chk("show неизвестного — отказ со списком модулей ядра и пультом", rc != 0 and o.get("core") == sorted(S.CORE) + ["pult"], o)
finally:
    shutil.rmtree(T, ignore_errors=True)
print("итог %d/%d" % (ok, n)); sys.exit(0 if ok == n else 1)
