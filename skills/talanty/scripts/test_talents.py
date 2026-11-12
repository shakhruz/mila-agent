#!/usr/bin/env python3
"""talents.py — the queue of talents after birth: order; a pack not in the library is skipped and named in list; «later» is not
offered again; a standing talent is not offered; the measure of touches (no answer to the last card → nothing; a second card
within a day → nothing; night in the owner's zone → nothing); Shturman «connect» connects nothing; a pack's card is the
library's own; register 600; a foreign id or a path in talents.json is refused. The neighbours (library, mila-update, shturman)
are stand-ins in a temporary skills folder. python3 test_talents.py"""
import json, os, shutil, subprocess, sys, tempfile
H = os.path.dirname(os.path.abspath(__file__)); SK = os.path.dirname(os.path.dirname(H))
T = tempfile.mkdtemp(prefix="talanty-"); S = os.path.join(T, "skills"); W = os.path.join(T, "work"); os.makedirs(W)
ok = n = 0
def chk(m, c, x=""):
    global ok, n; n += 1; ok += bool(c); print(("✅ " if c else "❌ ") + m + ("" if c else "  ← " + str(x)[:300]))
def put(rel, text, mode=0o644):
    p = os.path.join(S, rel); os.makedirs(os.path.dirname(p), exist_ok=True); open(p, "w").write(text); os.chmod(p, mode)
shutil.copytree(os.path.join(SK, "talanty"), os.path.join(S, "talanty"), ignore=shutil.ignore_patterns("__pycache__", "test_*"))
shutil.copytree(os.path.join(SK, "raspisanie"), os.path.join(S, "raspisanie"), ignore=shutil.ignore_patterns("__pycache__"))
put("shturman/talent.json", open(os.path.join(SK, "shturman", "talent.json"), encoding="utf-8").read())
ST = os.path.join(T, "sht.json"); open(ST, "w").write('{"connected": false}')
put("shturman/scripts/shturman.py", "import sys; print(open(%r).read())\n" % ST)
LIB = os.path.join(T, "lib.json"); OFFERS = os.path.join(T, "offers.log")
open(LIB, "w").write(json.dumps({"catalog": {"znakomstvo": [{"id": "proforientatsiya"}], "obrazovanie": [{"id": "kurs-kniga-ii"}]}}))
put("library/library.py", "import sys, json\nif sys.argv[1] == 'list': print(open(%r).read())\nelse:\n    open(%r, 'a').write(sys.argv[2] + '\\n')\n"
    "    print(json.dumps({'pack': sys.argv[2], 'text': 'Пак ' + sys.argv[2] + '. Поставить?', 'buttons': [[{'label': '✅ Поставить', 'data': 'pack:yes'}]], 'mark': '#pack-x'}))\n" % (LIB, OFFERS))
INST = os.path.join(T, "inst.json"); open(INST, "w").write("[]")
put("mila-update/update.py", "import json\ndef installed_packs():\n    return {k: {} for k in json.load(open(%r))}\n" % INST)
open(os.path.join(W, "USER.md"), "w").write("Часовой пояс — Asia/Tashkent\n")
def run(*a):
    env = dict(os.environ, MILA_WORK=W)
    r = subprocess.run([sys.executable, "-B", os.path.join(S, "talanty", "scripts", "talents.py")] + list(a), capture_output=True, text=True, env=env, timeout=60)
    try: return r.returncode, json.loads(r.stdout)
    except ValueError: return r.returncode, {"raw": r.stdout, "err": r.stderr}
DAY1 = "2026-11-13T06:00:00+00:00"   # 11:00 в Ташкенте
try:
    rc, d = run("list"); rows = {x["id"]: x for x in d.get("talents", [])}
    chk("list: пять талантов по порядку; диагностики и бренда нет — «нет в библиотеке»", [x["id"] for x in d["talents"]] == ["shturman", "biznes-diagnostika", "proforientatsiya", "lichnyj-brend", "kurs-kniga-ii"]
        and rows["biznes-diagnostika"].get("note") == "нет в библиотеке" and rows["lichnyj-brend"].get("note") and "note" not in rows["proforientatsiya"], d)
    rc, d = run("next", "--now", "2026-11-12T18:30:00+00:00")
    chk("ночь у хозяина (23:30 по Ташкенту) — карточки нет", d.get("id") is None and "ночь" in d.get("why", ""), d)
    rc, d = run("next", "--now", DAY1)
    chk("первым — Штурман: реплика, что даёт, что нужно (полный доступ — честно), бесплатно; «Подключить» / «Позже»", d.get("id") == "shturman"
        and "полный доступ" in d["text"] and [b["choice"] for b in d["buttons"][0]] == ["talent:shturman:connect", "talent:shturman:later"], d)
    reg = os.path.join(W, "talents", "registry.json")
    chk("реестр 600, папка 700", oct(os.stat(reg).st_mode & 0o777) == "0o600" and oct(os.stat(os.path.dirname(reg)).st_mode & 0o777) == "0o700")
    rc, d = run("next", "--now", "2026-11-14T06:00:00+00:00")
    chk("на прошлую карточку ответа нет — следующей нет, даже через сутки", d.get("id") is None and "ответа" in d.get("why", ""), d)
    rc, d = run("answer", "shturman", "connect")
    chk("«Подключить» Штурмана — только путь в карточку навыка с рисками; ничего не подключено", "три строки риска" in d.get("next", "") and json.load(open(ST))["connected"] is False, d)
    rc, d = run("next", "--now", "2026-11-13T09:00:00+00:00")
    chk("ответ был, но сутки не прошли — второй карточки в тот же день нет", d.get("id") is None and "сутки" in d.get("why", ""), d)
    rc, d = run("next", "--now", "2026-11-15T06:00:00+00:00")
    chk("после «Подключить» Штурман больше не предлагается (решение — в карточке навыка) — дальше; диагностики нет в библиотеке — пропуск; карточка Профориентации — та, что дала библиотека", d.get("id") == "proforientatsiya"
        and d.get("text") == "Пак proforientatsiya. Поставить?" and d.get("mark") == "#pack-x" and open(OFFERS).read().split() == ["proforientatsiya"], d)
    rc, d = run("answer", "proforientatsiya", "connect"); open(INST, "w").write('["proforientatsiya"]')
    rc, d = run("next", "--now", "2026-11-16T06:00:00+00:00")
    chk("пак поставлен — дальше курс (бренда нет в библиотеке)", d.get("id") == "kurs-kniga-ii", d)
    rc, d = run("answer", "kurs-kniga-ii", "later"); rc, d = run("next", "--now", "2026-11-17T06:00:00+00:00")
    chk("всё стоит или отложено — предлагать нечего", d.get("id") is None and "нечего" in d.get("why", ""), d)
    open(ST, "w").write('{"connected": true}'); rc, d = run("list"); rows = {x["id"]: x for x in d["talents"]}
    chk("Штурман подключён хозяином — в list «active»", rows["shturman"]["state"] == "active", rows)
    rc, d = run("answer", "../etc", "later"); chk("id с путём — отказ", rc == 1 and d.get("ok") is False, d)
    rc, d = run("answer", "zrenie", "later"); chk("таланта нет в очереди ядра — отказ", rc == 1, d)
    q = os.path.join(S, "talanty", "talents.json"); keep = open(q).read()
    open(q, "w").write(json.dumps({"order": [{"id": "../../x", "kind": "pack"}]})); rc, d = run("list")
    chk("talents.json с путём в id — отказ до любого пути", rc == 1 and "неверном виде" in d.get("why", ""), d)
    open(q, "w").write(json.dumps({"order": [{"id": "safe-link", "kind": "skill"}]})); rc, d = run("list")
    chk("talents.json называет навыком не талант ядра — отказ", rc == 1, d)
    open(q, "w").write(keep)
    p = json.load(open(os.path.join(SK, "shturman", "talent.json"), encoding="utf-8"))
    chk("паспорт Штурмана: четыре языка — что даёт, что нужно, сколько стоит, реплика", all(set(p["passport"][k]) == {"ru", "en", "uz", "zh"} for k in ("gives", "needs", "costs")) and set(p["offer"]) == {"ru", "en", "uz", "zh"})
finally:
    shutil.rmtree(T, ignore_errors=True)
print("итог %d/%d" % (ok, n)); sys.exit(0 if ok == n else 1)
