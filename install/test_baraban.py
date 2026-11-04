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
shutil.rmtree(T, ignore_errors=True); print("итог %d/%d" % (ok, n)); sys.exit(0 if ok == n else 1)
