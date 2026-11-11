#!/usr/bin/env python3
"""Connectors: the register of the home, the card, «later», the three steps with the safe record, the key check against a stand-in
service, the trial, switching off and on. The key never appears in any output; the key goes only to the address of the closed
list; an unknown connector or a passport that names a foreign service is refused. The first built-in connector is hearing («слух»).
The network and the safe are replaced inside the process. Run: python3 test_connectors.py"""
import contextlib, io, json, os, shutil, sys, tempfile
sys.dont_write_bytecode = True; os.umask(0o022)
H = os.path.dirname(os.path.abspath(__file__)); SK = os.path.dirname(os.path.dirname(H))
T = tempfile.mkdtemp(prefix="konn-"); WORK = os.path.join(T, "work"); SAFE = os.path.join(WORK, "secrets"); os.makedirs(SAFE, mode=0o700)
os.environ.update(MILA_WORK=WORK, SAFE_DIR=SAFE)
sys.path.insert(0, H)
import connectors as C
ok = n = 0
def chk(m, c, x=""):
    global ok, n
    n += 1; ok += bool(c); print(("✅ " if c else "❌ ") + m + ("" if c else "  ← " + str(x)[:400]))
KEY = "dg" + "test" + "0" * 28                          # выдуманный ключ, склейкой
FIELD = "DEEPGRAM_" + "API_KEY"; SAFE_FILE = os.path.join(SAFE, "deepgram" + ".env")
calls = []
def service(code):
    def http_status(url, headers, timeout=20):
        calls.append((url, dict(headers))); return code
    return http_status
def run(*argv):
    out = io.StringIO(); code = 0
    with contextlib.redirect_stdout(out):
        try: C.main(list(argv))
        except SystemExit as e: code = e.code or 0
    raw = out.getvalue()
    try: return code, json.loads(raw), raw
    except ValueError: return code, {}, raw
def put_key(value=KEY, mode=0o600):
    open(SAFE_FILE, "w").write("%s=%s\n" % (FIELD, value)); os.chmod(SAFE_FILE, mode)
everything = []
def R(*argv):
    code, d, raw = run(*argv); everything.append(raw); return code, d, raw
try:
    # ── реестр и карточка
    code, d, raw = R("list")
    chk("реестр: один встроенный коннектор — слух, состояние «предложен», строка «что даёт»", [x["id"] for x in d["connectors"]] == ["sluh"] and d["connectors"][0]["state"] == "offered" and d["connectors"][0]["sense"] == "слух" and "голосовые" in d["connectors"][0]["gives"], d)
    code, d, raw = R("next")
    b = d.get("buttons", [[{}]])[0]
    chk("при рождении первым предлагается слух: реплика, что нужно, сколько стоит и две кнопки — «Активировать слух» / «Позже»", d.get("id") == "sluh" and d["text"].startswith("Давайте активируем мне слух") and "Deepgram" in d["text"] and "пробный кредит" in d["text"]
        and [x["label"] for x in b] == ["Активировать слух", "Позже"] and [x["choice"] for x in b] == ["connector:sluh:activate", "connector:sluh:later"], d)
    code, d, raw = R("offer", "sluh", "--lang", "en"); chk("карточка по-английски: «Activate hearing» / «Later»", [x["label"] for x in d["buttons"][0]] == ["Activate hearing", "Later"] and "activate my hearing" in d["text"], d)
    code, d, raw = R("offer", "sluh", "--lang", "de"); chk("язык, которого нет, — английский", [x["label"] for x in d["buttons"][0]] == ["Activate hearing", "Later"], d)
    for lang in ("uz", "zh"):
        code, d, raw = R("offer", "sluh", "--lang", lang); chk("карточка на %s: свой текст, не английский" % lang, d.get("text") and "activate my hearing" not in d["text"] and d["buttons"][0][1]["label"] != "Later", d)
    # ── три шага и сейф
    code, d, raw = R("steps", "sluh")
    chk("три шага; ключ — через сейф: названы запись и поле, сам ключ не просится в чат", len(d["steps"]) == 3 and d["safe"] == {"name": "deepgram", "fields": [FIELD]} and "в чат" in d["steps"][2] and "сейф" in d["how"], d)
    # ── проверка ключа
    C.http_status = service(200); calls.clear()
    code, d, raw = R("check", "sluh"); chk("ключа в сейфе нет — не активирован, причина названа, в сеть не ходила", code == 1 and d["ok"] is False and d["state"] == "offered" and not calls, (d, calls))
    code, d, raw = R("trial", "sluh"); chk("пробы без активации нет", code == 1 and d["ok"] is False, d)
    put_key(mode=0o644); code, d, raw = R("check", "sluh"); chk("сейф открыт для других — ключ не читаю, не активирован, в сеть не ходила", code == 1 and not calls and "600" in d["why"], d)
    put_key(); C.http_status = service(401); code, d, raw = R("check", "sluh")
    chk("сервис не принял ключ — не активирован, сказано «нужен новый ключ»", code == 1 and d["state"] == "offered" and "новый ключ" in d["why"], d)
    C.http_status = service(0); code, d, raw = R("check", "sluh"); chk("сервис не ответил — не активирован, «проверю позже»", code == 1 and "позже" in d["why"] and d["state"] == "offered", d)
    C.http_status = service(500); code, d, raw = R("check", "sluh"); chk("сервис ответил 500 — не активирован", code == 1 and d["state"] == "offered", d)
    C.http_status = service(200); calls.clear(); code, d, raw = R("check", "sluh")
    chk("ключ в сейфе, сервис принял — активирован", code == 0 and d == {"id": "sluh", "ok": True, "state": "active"}, d)
    chk("ключ ушёл на адрес из закрытого списка ядра и только туда, заголовком", len(calls) == 1 and calls[0][0] == "https://api.deepgram.com/v1/projects" and calls[0][1] == {"Authorization": "Token " + KEY}, calls)
    reg = json.load(open(os.path.join(WORK, "connectors", "registry.json")))
    chk("реестр дома: слух — active, с отметкой времени; файл 600; ключа в нём нет", reg["sluh"]["state"] == "active" and reg["sluh"].get("ts") and (os.stat(os.path.join(WORK, "connectors", "registry.json")).st_mode & 0o777) == 0o600 and KEY not in json.dumps(reg), reg)
    # ── проба и состояние после активации
    code, d, raw = R("trial", "sluh"); chk("проба: «пришлите голосовое — отвечу текстом», бесплатная", code == 0 and "голосовое" in d["text"] and d["paid"] is False, d)
    code, d, raw = R("next"); chk("после активации предлагать нечего", d.get("id") is None, d)
    code, d, raw = R("offer", "sluh"); chk("карточка уже активированного — «уже активирован», кнопок нет", d.get("state") == "active" and "buttons" not in d, d)
    code, d, raw = R("later", "sluh"); chk("«позже» по активированному не пишется", d.get("state") == "active" and json.load(open(os.path.join(WORK, "connectors", "registry.json")))["sluh"]["state"] == "active", d)
    # ── снятие и возврат
    flag = os.path.join(WORK, "connectors", "sluh.off")
    code, d, raw = R("off", "sluh")
    chk("выключить: состояние off, флаг для расшифровщика лежит, строка о ключе в сейфе; ключ не тронут", d["state"] == "off" and os.path.exists(flag) and "Ключ остаётся в сейфе" in d["text"] and open(SAFE_FILE).read().strip() == "%s=%s" % (FIELD, KEY), d)
    code, d, raw = R("next"); chk("выключенный сам не предлагается", d.get("id") is None, d)
    C.http_status = service(401); code, d, raw = R("on", "sluh"); chk("включить обратно с негодным ключом — отказ, остаётся выключенным", code == 1 and os.path.exists(flag) and d["state"] == "off", d)
    C.http_status = service(200); code, d, raw = R("on", "sluh"); chk("включить обратно — ключ проверен заново, флаг убран", code == 0 and d["state"] == "active" and not os.path.exists(flag), d)
    # ── расшифровщик уважает выключатель: при флаге не идёт ни к одному сервису
    import subprocess
    TV = os.path.join(SK, "..", "install", "transcribe-voice.sh"); ogg = os.path.join(T, "g.ogg"); open(ogg, "wb").write(b"OggS" + b"0" * 64)
    fb = os.path.join(T, "fb"); os.makedirs(fb); open(os.path.join(fb, "curl"), "w").write("#!/bin/sh\necho curl >> %s/curl.calls\nexit 7\n" % T); os.chmod(os.path.join(fb, "curl"), 0o755)
    env = {k: v for k, v in os.environ.items() if not k.endswith("_API_KEY") and k != "MILA_KEYD"}; env.update(PATH=fb + ":" + env["PATH"], HOME=T, MILA_WORK=WORK, SAFE_DIR=SAFE)
    open(flag, "w").close()
    r = subprocess.run(["bash", TV, ogg], capture_output=True, text=True, env=env, timeout=60)
    chk("слух выключен: расшифровщик отказывает сразу и ни к какому сервису не идёт, хотя ключ в сейфе есть", r.returncode == 1 and "слух выключен" in r.stderr and not os.path.exists(os.path.join(T, "curl.calls")) and KEY not in r.stdout + r.stderr, r.stderr[:200])
    os.remove(flag)
    r = subprocess.run(["bash", TV, ogg], capture_output=True, text=True, env=env, timeout=60)
    chk("флага нет — расшифровщик идёт к сервису, как раньше (подставной curl вызван), ключа в выводе нет", os.path.exists(os.path.join(T, "curl.calls")) and "слух выключен" not in r.stderr and KEY not in r.stdout + r.stderr, r.stderr[:200])
    # ── «позже»
    shutil.rmtree(os.path.join(WORK, "connectors"))
    code, d, raw = R("later", "sluh"); chk("«позже»: состояние later", d["state"] == "later", d)
    code, d, raw = R("next"); chk("отложенный сам больше не предлагается", d.get("id") is None, d)
    code, d, raw = R("offer", "sluh"); chk("хозяин попросил сам — карточка отложенного показывается", bool(d.get("buttons")), d)
    # ── чего быть не должно
    code, d, raw = R("offer", "zrenie"); chk("коннектора, которого нет в ядре, нет: отказ", code == 1 and d["ok"] is False, d)
    code, d, raw = R("offer", "../sluh"); chk("id с путём — отказ", code == 1, d)
    real = os.path.join(SK, "sluh", "connector.json"); keep = open(real, encoding="utf-8").read()
    try:
        bad = json.loads(keep); bad["service"] = "example"; bad["check_url"] = "https://example.com/collect"
        C.SKILLS = os.path.join(T, "skills"); os.makedirs(os.path.join(C.SKILLS, "sluh")); json.dump(bad, open(os.path.join(C.SKILLS, "sluh", "connector.json"), "w"))
        calls.clear(); code, d, raw = R("check", "sluh")
        chk("паспорт называет сервис не из списка ядра и свой адрес — отказ, ключ никуда не ушёл", code == 1 and not calls, (d, calls))
        ch = json.loads(keep); ch["id"] = "chuzhoj"; os.makedirs(os.path.join(C.SKILLS, "chuzhoj")); json.dump(ch, open(os.path.join(C.SKILLS, "chuzhoj", "connector.json"), "w"))
        calls.clear(); code, d, raw = R("check", "chuzhoj")
        chk("папка навыка с исправным паспортом, но не из списка встроенных (пришла с паком) — коннектором не считается, ключ не читается", code == 1 and not calls and "встроенного" in d.get("why", ""), (d, calls))
        code, d, raw = R("offer", "chuzhoj"); chk("…и карточку по ней не показываю", code == 1 and "buttons" not in d, d)
        bad = json.loads(keep); bad["safe"] = {"name": "../../etc/passwd", "field": FIELD}; json.dump(bad, open(os.path.join(C.SKILLS, "sluh", "connector.json"), "w"))
        code, d, raw = R("steps", "sluh"); chk("паспорт называет запись сейфа с путём — отказ", code == 1, d)
    finally:
        C.SKILLS = SK
    chk("ни в одном выводе за весь прогон ключа нет", not any(KEY in x for x in everything))
    src = open(os.path.join(H, "connectors.py"), encoding="utf-8").read()
    chk("адрес сервиса не берётся ни из паспорта, ни из окружения", "check_url" not in src and src.count("environ") == 1 and 'd["service"]' in src)
    d = json.load(open(real, encoding="utf-8"))
    chk("паспорт слуха: пять частей на четырёх языках — что даёт, что нужно, сколько стоит; реплика; три шага; проба; снятие", all(set(d["passport"][k]) == set(C.LANGS) for k in ("gives", "needs", "costs"))
        and all(set(d[k]) == set(C.LANGS) for k in ("sense", "offer", "steps", "trial", "removal")) and all(len(v) == 3 for v in d["steps"].values()))
finally:
    shutil.rmtree(T, ignore_errors=True)
print("итог %d/%d" % (ok, n)); sys.exit(0 if ok == n else 1)
