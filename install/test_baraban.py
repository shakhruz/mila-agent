#!/usr/bin/env python3
"""baraban.py на временном доме с задачами, поставленными самим mila_cron: срок наступил — одно событие с meta (ritual cron, job,
message_id cron-<slug>-<id>-<срок>), повторный тик — тишина; простой 3 дня — ОДНО событие; catchup skip — пропущенное не догоняет;
тихие часы — срок ждёт утра и приходит один раз; quiet ignore — сразу; истёк срок — одно «продлить?» и тишина; дважды без done — строка
в watch.jsonl, с done между — нет; журнал-симлинк — не доставлено и состояние не сдвинуто; журнала нет — не создаётся.
Run: python3 test_baraban.py"""
import datetime as dt, json, os, shutil, subprocess, sys, tempfile, zoneinfo
H = os.path.dirname(os.path.abspath(__file__)); R = os.path.dirname(H); ok = n = 0
def check(name, c, x=""):
    global ok, n; n += 1; ok += bool(c); print(("✅ " if c else "❌ ") + name + ("" if c else "  ← " + str(x)[:300]))
os.umask(0o077)   # a strict umask: the modes the service sets must not depend on it
sys.path.insert(0, H); import baraban as B
TZ = zoneinfo.ZoneInfo("Asia/Tashkent"); T = tempfile.mkdtemp(prefix="baraban-")
HOME = os.path.join(T, "home"); W = os.path.join(HOME, "work"); EV = os.path.join(HOME, ".claude/channels/telegram/inbound/events.jsonl")
os.makedirs(os.path.dirname(EV)); os.makedirs(W); open(EV, "w").close()
OWN = "555" + "000111"   # glued: no long id literal
json.dump({"allowFrom": [OWN]}, open(os.path.join(HOME, ".claude/channels/telegram/access.json"), "w"))
open(os.path.join(W, "USER.md"), "w").write("Часовой пояс — Asia/Tashkent\nТихие часы — 22:00–08:00\n")
ST = os.path.join(T, "state"); base = dt.datetime.now(TZ).replace(hour=8, minute=0, second=0, microsecond=0) + dt.timedelta(days=1)
def at(days=0, h=8, m=0): return base + dt.timedelta(days=days, hours=h - 8, minutes=m)
def mc(*a, now):
    r = subprocess.run([sys.executable, os.path.join(R, "skills/raspisanie/mila_cron.py"), *a], capture_output=True, text=True,
                       env=dict(os.environ, MILA_WORK=W, MILA_CRON_NOW=now.isoformat(), MILA_EVENTS=EV))
    assert r.returncode == 0, r.stdout + r.stderr
def tick(now): return B.tick(HOME, "milav", "", ST, now)["fired"]
def events(): return [json.loads(l) for l in open(EV) if l.strip()]
mc("add", "utro", "0 9 * * *", "Утренний план", now=at())
mc("add", "noch", "30 23 * * *", "Ночная сводка", now=at())
mc("add", "noch-sejchas", "45 23 * * *", "Срочно ночью", "--quiet", "ignore", now=at())
mc("add", "chas", "15 * * * *", "Каждый час", "--catchup", "skip", now=at())
check("08:30 — до срока тишина", tick(at(0, 8, 30)) == [])
f = tick(at(0, 9, 1)); e = events()[-1]["params"]
check("09:01 — «utro» одним событием, meta как у ритуалов", f == ["utro"] and e["meta"]["ritual"] == "cron" and e["meta"]["job"] == "utro"
      and e["meta"]["chat_id"] == OWN and e["meta"]["message_id"].startswith("cron-milav-utro-") and e["content"].startswith("[⏰ расписание] utro"), (f, e))
check("в событии — полная команда done (mila-cron нет в PATH)", "python3 ~/.claude/skills/raspisanie/mila_cron.py done utro" in e["content"] and "итог: mila-cron" not in e["content"], e["content"])
check("09:02 — повтора нет", tick(at(0, 9, 2)) == [])
f = tick(at(3, 10, 0))
check("простой 3 дня → «utro» ОДНИМ событием, не пачкой", f.count("utro") == 1, f)
check("catchup skip: пропущенный час не догоняется", "chas" not in f, f)
check("…а следующий час приходит", "chas" in tick(at(3, 10, 16)))
f = tick(at(3, 23, 46))
check("тихие часы: «noch» 23:30 ждёт, «noch-sejchas» (quiet ignore) — сразу", "noch" not in f and "noch-sejchas" in f, f)
check("ночью дальше тишина", "noch" not in tick(at(4, 3, 0)))
check("08:01 — «noch» приходит один раз", tick(at(4, 8, 1)).count("noch") == 1 and "noch" not in tick(at(4, 8, 2)))
# watchdog: «utro» fired at day 3 and day 5 without done between → one line
w = os.path.join(ST, "watch.jsonl"); cnt = lambda j: sum(1 for l in open(w) if '"%s"' % j in l) if os.path.exists(w) else 0
n0 = cnt("noch")
open(os.path.join(W, "schedule/done.jsonl"), "a").write(json.dumps({"id": "noch", "at": at(4, 9).isoformat(), "result": "ok"}) + "\n")
tick(at(5, 9, 1))
check("дважды без done → строка в watch.jsonl («utro»)", os.path.exists(w) and any('"utro"' in l for l in open(w)))
check("с done между срабатываниями — новой строки для «noch» нет", cnt("noch") == n0, (n0, cnt("noch")))
# expiry
d = json.load(open(os.path.join(W, "schedule/jobs.json"))); exp = d["jobs"][0]["expires"]
far = dt.datetime.combine(dt.date.fromisoformat(exp) + dt.timedelta(days=1), dt.time(9, 1), TZ)
f = tick(far); last = [x for x in events() if x["params"]["meta"]["job"] == "utro"][-1]["params"]["content"]
check("срок вышел → одно «продлить?»", "utro" in f and "Продлить" in last, last)
check("в «продлить?» — полная команда extend", "python3 ~/.claude/skills/raspisanie/mila_cron.py extend utro" in last, last)
check("…дальше тишина", "utro" not in tick(far + dt.timedelta(days=1)))
# symlinked journal: not delivered, state unchanged (a fresh job — the first ones have expired by now)
F = far + dt.timedelta(days=2); mc("add", "posle", "20 * * * *", "После", now=F)
os.rename(EV, EV + ".real"); os.symlink(EV + ".real", EV)
f = tick(F + dt.timedelta(minutes=21))
check("журнал — симлинк: не доставлено, состояние не сдвинуто", f == [] and not json.load(open(os.path.join(ST, "milav.json")))["jobs"].get("posle", {}).get("last"))
os.remove(EV); os.rename(EV + ".real", EV)
check("…журнал починили — срок доставлен на следующем тике", "posle" in tick(F + dt.timedelta(minutes=22)))
# a folder on the way swapped for a link (to a copy outside the home) — refused, nothing delivered there
OUT = os.path.join(T, "outside"); shutil.copytree(os.path.dirname(EV), OUT)
inb = os.path.dirname(EV); os.rename(inb, inb + ".real"); os.symlink(OUT, inb)
c0 = open(os.path.join(OUT, "events.jsonl")).read().count("\n")
f = tick(F + dt.timedelta(minutes=41))
check("промежуточная папка заменена ссылкой наружу — не доставлено, снаружи ничего не дописано", f == [] and open(os.path.join(OUT, "events.jsonl")).read().count("\n") == c0, f)
os.remove(inb); os.rename(inb + ".real", inb)
os.remove(EV); f = tick(F + dt.timedelta(hours=1, minutes=21))
check("журнала нет — не создаётся, ничего не доставлено", f == [] and not os.path.exists(EV))
# ── the pass mark: every pass that has an owner leaves <state>/<slug>.beat; the guard and the doctor judge the Scheduler by it
sys.path.insert(0, os.path.join(R, "skills", "raspisanie")); import cronspec as C
H2 = os.path.join(T, "dom"); os.makedirs(os.path.join(H2, ".claude/channels/telegram/inbound")); os.makedirs(os.path.join(H2, "work"))
ST2 = os.path.join(T, "state2"); P = at(5, 9, 0); beat = os.path.join(ST2, "dom.beat")
r = B.tick(H2, "dom", "", ST2, P)
check("хозяин не известен — это не проход: отметки нет", r.get("why") in ("no owner", "no jobs.json") and not os.path.exists(beat), r)
json.dump({"allowFrom": [OWN]}, open(os.path.join(H2, ".claude/channels/telegram/access.json"), "w"))
r = B.tick(H2, "dom", "", ST2, P)
check("хозяин подключён, задач нет — проход есть: отметка со временем прохода", r.get("why") == "no jobs.json" and open(beat).read().strip() == P.isoformat(timespec="seconds"), r)
check("отметка в папке состояния закрыта, как само состояние: папка 700, файл 600", oct(os.stat(beat).st_mode & 0o777) == "0o600" and oct(os.stat(ST2).st_mode & 0o777) == "0o700", (oct(os.stat(beat).st_mode & 0o777), oct(os.stat(ST2).st_mode & 0o777)))
P2 = P + dt.timedelta(minutes=1); B.tick(H2, "dom", "", ST2, P2)
check("следующий проход переписывает отметку", open(beat).read().strip() == P2.isoformat(timespec="seconds") and not os.path.exists(beat + ".tmp"))
BD = os.path.join(T, "beats"); B.tick(H2, "dom", "", ST2, P2 + dt.timedelta(minutes=1), BD)
check("--beat-dir: отметка — в названной папке, открытой для чтения (папка 755, файл 644), состояние — в своей закрытой",
      oct(os.stat(BD).st_mode & 0o777) == "0o755" and oct(os.stat(os.path.join(BD, "dom.beat")).st_mode & 0o777) == "0o644"
      and open(beat).read().strip() == P2.isoformat(timespec="seconds") and oct(os.stat(ST2).st_mode & 0o777) == "0o700")
outside = os.path.join(T, "outside.txt"); open(outside, "w").write("чужое\n"); os.symlink(outside, os.path.join(BD, "dom.beat.tmp"))
r = B.tick(H2, "dom", "", ST2, P2 + dt.timedelta(minutes=2), BD)
check("на месте временного файла отметки — ссылка наружу: чужой файл цел, проход не упал", open(outside).read() == "чужое\n" and "fired" in r, r)
os.remove(os.path.join(BD, "dom.beat.tmp"))
rc = B.main(["tick", "--home", H2, "--state", ST2, "--beat-dir", BD, "--now", (P2 + dt.timedelta(minutes=9)).isoformat()])
check("командой, как её зовёт таймер ноутбука (без --owner и --slug): имя отметки — по папке дома, хозяин — подключённый", rc == 0 and open(os.path.join(BD, "dom.beat")).read().strip() == (P2 + dt.timedelta(minutes=9)).astimezone(TZ).isoformat(timespec="seconds"))
env = {"MILA_SCHEDULER_BEAT": BD}
check("cronspec.last_beat находит эту отметку по дому", C.last_beat(H2, env) == P2 + dt.timedelta(minutes=9), C.last_beat(H2, env))
check("служба и mila-cron берут пояс у одного правила", B.user_md(HOME)[0] == C.owner_tz(open(os.path.join(W, "USER.md")).read()) and str(B.user_md(H2)[0]) == C.DEFAULT_TZ == "Asia/Tashkent")
# v4: разовое дело на дату, сторож итога, бюджет срабатываний
H3 = os.path.join(T, "h3"); W3 = os.path.join(H3, "work"); EV3 = os.path.join(H3, ".claude/channels/telegram/inbound/events.jsonl")
os.makedirs(os.path.dirname(EV3)); os.makedirs(W3); open(EV3, "w").close()
json.dump({"allowFrom": [OWN]}, open(os.path.join(H3, ".claude/channels/telegram/access.json"), "w"))
open(os.path.join(W3, "USER.md"), "w").write("Часовой пояс — Asia/Tashkent\nТихие часы — 22:00–08:00\n")
ST3 = os.path.join(T, "state3")
def mc3(*a, now):
    r = subprocess.run([sys.executable, os.path.join(R, "skills/raspisanie/mila_cron.py"), *a], capture_output=True, text=True,
                       env=dict(os.environ, MILA_WORK=W3, MILA_CRON_NOW=now.isoformat(), MILA_EVENTS=EV3))
    assert r.returncode == 0, r.stdout + r.stderr
def t3(now): return B.tick(H3, "h3", "", ST3, now)["fired"]
mc3("add", "vstrecha", "--at", at(2, 12, 0).strftime("%Y-%m-%d %H:%M"), "Встреча с партнёром", now=at())
check("v4: разовое — до своего часа тишина", t3(at(2, 11, 59)) == [])
check("v4: разовое — в свой час одно событие", t3(at(2, 12, 1)) == ["vstrecha"])
check("v4: разовое — больше не приходит", t3(at(2, 12, 30)) == [] and t3(at(3, 12, 0)) == [])
w = [json.loads(l) for l in open(os.path.join(ST3, "watch.jsonl"))] if os.path.exists(os.path.join(ST3, "watch.jsonl")) else []
check("v4: разовое без итога за 2 ч — одна строка сторожа", sum(1 for x in w if x["job"] == "vstrecha" and "one-off" in x["why"]) == 1, w)
mc3("add", "noch-at", "--at", at(4, 23, 30).strftime("%Y-%m-%d %H:%M"), "Ночью", now=at())
r1, r2, r3 = t3(at(4, 23, 31)), t3(at(5, 8, 1)), t3(at(5, 8, 2))
check("v4: разовое в тихие часы ждёт утра и приходит один раз", r1 == [] and r2 == ["noch-at"] and r3 == [], (r1, r2, r3))
# v4: «удар» без модели — встроенная проверка перед срабатыванием (бывший Пульс)
dl = os.path.join(W3, "sroki.json")
json.dump([{"id": "pasport", "text": "Продлить паспорт", "due": at(8, 15, 0).strftime("%Y-%m-%d %H:%M")}], open(dl, "w"))
mc3("add", "sroki", "0 * * * *", "Сроки: что подходит", "--check", "deadlines:work/sroki.json:3", now=at(7))
check("v4: проверка — до срока далеко, Милу не будим", t3(at(8, 9, 1)) == [])
f = t3(at(8, 12, 1)); e = [json.loads(l) for l in open(EV3)][-1]["params"]["content"]
check("v4: проверка — срок через 3 ч, одно событие с найденным", f == ["sroki"] and "Продлить паспорт" in e and "Нашла проверка" in e, (f, e[:200]))
check("v4: проверка — та же находка второй раз не будит", t3(at(8, 13, 1)) == [])
json.dump([{"id": "pasport", "text": "Продлить паспорт", "due": "x", "done": True}], open(dl, "w"))
mc3("add", "smotri", "0 * * * *", "Файл поменялся — разбери", "--check", "changed:work/sroki.json", now=at(8, 13, 5))
check("v4: changed — первый раз будит, без правки тишина", t3(at(8, 14, 1)) == ["smotri"] and t3(at(8, 15, 1)) == [])
r = subprocess.run([sys.executable, os.path.join(R, "skills/raspisanie/mila_cron.py"), "add", "zlo", "0 9 * * *", "x", "--check", "deadlines:/etc/shadow"],
                   capture_output=True, text=True, env=dict(os.environ, MILA_WORK=W3, MILA_CRON_NOW=at(8).isoformat(), MILA_EVENTS=EV3))
check("v4: проверка вне дома — отказ", r.returncode == 1 and "--check" in r.stdout, r.stdout)
mc3("add", "dolgo", "--at", at(9, 10, 0).strftime("%Y-%m-%d %H:%M"), "Длинная задача", "--by", "owner", "--word", "-1001/2", now=at(8, 16, 0))
t3(at(9, 10, 1)); t3(at(9, 11, 0))
wl = lambda: [json.loads(l) for l in open(os.path.join(ST3, "watch.jsonl"))]
check("v4: в работе меньше срока — сторож молчит", not any(x["job"] == "dolgo" for x in wl()))
t3(at(9, 12, 5)); t3(at(9, 12, 30))
check("v4: нет итога за 120 мин — одна строка «no done»", sum(1 for x in wl() if x["job"] == "dolgo" and x["why"].startswith("no done")) == 1, wl()[-3:])
os.environ["MILA_FIRES_PER_DAY"] = "2"; import importlib; importlib.reload(B)
for i in range(4): mc3("add", "b%d" % i, "0 10 * * *", "x", now=at(5))
f = t3(at(6, 10, 1))
w = [json.loads(l) for l in open(os.path.join(ST3, "watch.jsonl"))]
check("v4: бюджет 2 в сутки — пришли 2 своих, строка сторожа одна", len(f) == 2 and sum(1 for x in w if "budget" in x["why"]) == 1, (f, w))
os.environ.pop("MILA_FIRES_PER_DAY"); importlib.reload(B)
# пометка «по просьбе хозяина» не обходит бюджет; жёсткая ссылка в проверке — отказ
H4 = os.path.join(T, "h4"); W4 = os.path.join(H4, "work"); EV4 = os.path.join(H4, ".claude/channels/telegram/inbound/events.jsonl")
os.makedirs(os.path.dirname(EV4)); os.makedirs(W4); open(EV4, "w").close()
json.dump({"allowFrom": [OWN]}, open(os.path.join(H4, ".claude/channels/telegram/access.json"), "w"))
open(os.path.join(W4, "USER.md"), "w").write("Часовой пояс — Asia/Tashkent\nТихие часы — 22:00–08:00\n")
ST4 = os.path.join(T, "state4")
def mc4(*a, now):
    return subprocess.run([sys.executable, os.path.join(R, "skills/raspisanie/mila_cron.py"), *a], capture_output=True, text=True,
                          env=dict(os.environ, MILA_WORK=W4, MILA_CRON_NOW=now.isoformat(), MILA_EVENTS=EV4))
for i in range(50):
    mc4("add", "o%d" % i, "*/5 * * * *", "x", "--by", "owner", "--word", "1/1", "--no-expire", now=at(10))
r51 = mc4("add", "o50", "*/5 * * * *", "x", "--by", "owner", "--word", "1/1", "--no-expire", now=at(10))
check("приёмка: 51-я задача без срока — отказ", r51.returncode == 1 and "без срока" in r51.stdout, r51.stdout)
os.environ["MILA_OWNER_FIRES_PER_DAY"] = "300"; importlib.reload(B)
tot = 0
for m in range(0, 60, 5):
    tot += len(B.tick(H4, "h4", "", ST4, at(11, 9, m))["fired"])
w4 = [json.loads(l) for l in open(os.path.join(ST4, "watch.jsonl"))]
check("приёмка: 50 задач */5 by=owner — за сутки не больше 300 срабатываний, одна строка сторожа", tot == 300 and sum(1 for x in w4 if "budget" in x["why"]) == 1, (tot, w4[-2:]))
os.environ.pop("MILA_OWNER_FIRES_PER_DAY"); importlib.reload(B)
mc4("add", "svoya", "30 10 * * *", "своя", now=at(11, 10, 0))
rest = []
for m in range(0, 11 * 60, 5): rest += B.tick(H4, "h4", "", ST4, at(11, 10, m + 1))["fired"]      # the rest of the day, 10:01 … 20:56
check("бюджет хозяйских задач исчерпан — до конца суток они молчат, а своя задача приходит (у неё свой бюджет)", rest == ["svoya"], rest[:5])
nxt = B.tick(H4, "h4", "", ST4, at(12, 8, 1))["fired"]
check("наутро бюджет новый: каждая задача по разу, не пачкой за вчера", len(nxt) == 50 and len(set(nxt)) == 50, len(nxt))
w4 = [json.loads(l) for l in open(os.path.join(ST4, "watch.jsonl"))]
check("строка сторожа о бюджете — по одной на сутки, не на каждый отказ", sum(1 for x in w4 if "budget" in x["why"]) == 1, [x["why"] for x in w4][-3:])
outside2 = os.path.join(H4, "chuzhoe.json"); json.dump([{"id": "x", "text": "секрет", "due": "2020-01-01 00:00"}], open(outside2, "w"))
os.link(outside2, os.path.join(W4, "link.json"))
check("приёмка: проверка по жёсткой ссылке — отказ (nlink≠1)", B.run_check(H4, "deadlines:work/link.json", at(11), TZ) == [])
open(os.path.join(W4, "odno.txt"), "w").write("свой файл\n")
B.append_in_home(H4, "work/odno.txt", "строка")
check("контроль: в обычный файл дома служба дописывает", open(os.path.join(W4, "odno.txt")).read() == "свой файл\nстрока\n")
os.link(os.path.join(W4, "odno.txt"), os.path.join(T, "vtoroe-imya.txt"))
try:
    B.append_in_home(H4, "work/odno.txt", "ещё"); _ap = "записано"
except OSError:
    _ap = "отказ"
check("файл со вторым именем (жёсткая ссылка) — служба в него не дописывает", _ap == "отказ" and open(os.path.join(W4, "odno.txt")).read() == "свой файл\nстрока\n", _ap)
# приёмка 15.11: битая запись не останавливает дом; бюджет — только за доставленное; 1000 задач читаются
H5 = os.path.join(T, "h5"); W5 = os.path.join(H5, "work"); EV5 = os.path.join(H5, ".claude/channels/telegram/inbound/events.jsonl")
os.makedirs(os.path.dirname(EV5)); os.makedirs(os.path.join(W5, "schedule")); open(EV5, "w").close()
json.dump({"allowFrom": [OWN]}, open(os.path.join(H5, ".claude/channels/telegram/access.json"), "w"))
open(os.path.join(W5, "USER.md"), "w").write("Часовой пояс — Asia/Tashkent\n")
ST5 = os.path.join(T, "state5"); J5 = os.path.join(W5, "schedule", "jobs.json"); c0 = at(20, 8, 0).isoformat()
good = {"id": "good", "cron": "0 9 * * *", "text": "x", "by": "mila", "created": c0, "expires": None, "enabled": True}
bad = [{"id": "b1", "cron": "0 9 * * *", "expires": "soon", "created": c0}, {"id": "b2", "cron": "0 9 * * *", "created": "x"},
       {"id": "b3", "at": 5, "created": c0}, {"id": "b4", "cron": "0 9 * * *", "expires": 5, "created": c0},
       {"id": "b5", "cron": "0 9 * * *", "created": c0, "check": "deadlines:work/d.json:nan"}, {"id": "b6", "cron": "0 9 * * *", "created": c0, "dlit": 1e999}, 5, "x"]
json.dump([{"id": "p", "text": "t", "due": "2020-01-01 00:00"}], open(os.path.join(W5, "d.json"), "w"))
json.dump({"jobs": bad + [good]}, open(J5, "w"))
open(os.path.join(W5, "schedule", "done.jsonl"), "w").write('5\n{"id":"good","at":"zzz"}\n"s"\n')
r = B.tick(H5, "h5", "", ST5, at(20, 9, 1))
check("приёмка: восемь битых записей и мусор в итогах — проход не падает, целая задача срабатывает", "good" in r["fired"], r)
for shape in ("[]", '{"jobs": 5}', "7"):
    open(J5, "w").write(shape)
    check("приёмка: jobs.json вида %s — проход без падения" % shape, B.tick(H5, "h5", "", ST5, at(20, 9, 2))["fired"] == [])
big = [{"id": "j%d" % i, "cron": "0 10 * * *", "text": "я" * 190, "by": "owner", "created": c0, "expires": None, "enabled": True} for i in range(1000)]
json.dump({"jobs": big}, open(J5, "w"), ensure_ascii=False)
r = B.tick(H5, "h5", "", ST5, at(20, 10, 1))
check("приёмка: 1000 задач (%d КБ) читаются, срабатывает ровно бюджет" % (os.path.getsize(J5) // 1024), len(r["fired"]) == B.OWNER_FIRES_PER_DAY, len(r["fired"]))
json.dump({"jobs": [dict(good, id="nd%d" % i, cron="0 11 * * *") for i in range(5)]}, open(J5, "w")); os.remove(EV5)
r = B.tick(H5, "h5", "", ST5, at(21, 11, 1)); d5 = json.load(open(os.path.join(ST5, "h5.json")))["day"]
check("приёмка: событие не доставлено — бюджет не тратится", r["fired"] == [] and d5.get("mila", 0) == 0, d5)
shutil.rmtree(T, ignore_errors=True); print("итог %d/%d" % (ok, n)); sys.exit(0 if ok == n else 1)
