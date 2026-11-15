#!/usr/bin/env python3
"""mila-cron (Планировщик): задачи расписания в доме Милы — что принимаю, что отказываю, импорт кронов из снимка, list по журналу плагина.
Всё во временной папке (MILA_WORK, MILA_EVENTS), время подменено (MILA_CRON_NOW). Usage: python3 test_mila_cron.py [папка с mila_cron.py]"""
import json, os, subprocess, sys, tempfile, threading
D = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.abspath(__file__)); K = os.path.join(D, "mila_cron.py")
ok = n = 0
def chk(name, cond):
    global ok, n
    n += 1; ok += bool(cond); print(("✅ " if cond else "❌ ") + name)
W = tempfile.mkdtemp(prefix="cron-"); EV = os.path.join(W, "events.jsonl")
open(os.path.join(W, "USER.md"), "w", encoding="utf-8").write("Часовой пояс — Asia/Tashkent\n")   # пояс владельца из USER.md; без него — пояс машины
env = dict(os.environ, MILA_WORK=W, MILA_EVENTS=EV, MILA_CRON_NOW="2026-10-26T10:00:00+05:00")
def k(*a):
    p = subprocess.run([sys.executable, K, *a], env=env, capture_output=True, text=True, timeout=30); return p.returncode, p.stdout
def jobs(): return json.load(open(os.path.join(W, "schedule", "jobs.json")))["jobs"]
code, out = k("add", "vtoroy-vzglyad", "17 10,12,14,16,18,20 * * *", "Второй взгляд: запусти vtoroy_vzglyad.py")
chk("add: задача записана, живёт 30 дней, ближайший срок 26.10 10:17", code == 0 and "до 2026-11-25" in out and "26.10 10:17" in out and jobs()[0]["by"] == "mila")
chk("файл расписания — только владельцу (600)", oct(os.stat(os.path.join(W, "schedule", "jobs.json")).st_mode)[-3:] == "600")
for args, why in ((["add", "Bad_ID", "0 9 * * *", "x"], "id"), (["add", "a", "* * * * *", "x"], "раза в 5"), (["add", "b", "*/3 * * * *", "x"], "раза в 5"),
                  (["add", "c", "61 9 * * *", "x"], "cron"), (["add", "d", "0 9 * * *", ""], "текст"), (["add", "e", "0 9 * * *", "я" * 2001], "текст"),
                  (["add", "f", "0 9 * * *", "x", "--by", "owner"], "--word"), (["add", "g", "0 9 * * *", "x", "--no-expire"], "без срока — только"),
                  (["add", "h", "0 9 * * *", "x", "--expires", "2027-03-01"], "срок жизни"), (["add", "vtoroy-vzglyad", "0 9 * * *", "x"], "уже есть")):
    code, out = k(*args)
    chk("отказ: %s → «%s»" % (" ".join(args[1:3]), why), code == 1 and why in out)
code, out = k("add", "vecher", "30 19 * * *", "Вечерняя проверка", "--by", "owner", "--word", "-100" + "1/2189", "--no-expire")
chk("v4: по просьбе хозяина — без срока можно (--by owner --word --no-expire)", code == 0 and [j for j in jobs() if j["id"] == "vecher"][0]["expires"] is None)
k("rm", "vecher")
code, out = k("add", "vecher", "30 19 * * *", "Вечерняя проверка", "--by", "owner", "--word", "-100" + "1/2189", "--expires", "2027-01-20")
chk("с согласия владельца — с word, срок до 400 дней (2027-01-20)", code == 0 and [j for j in jobs() if j["id"] == "vecher"][0]["expires"] == "2027-01-20")
chk("v4: своя задача — по-прежнему до 90 дней", k("add", "svoya", "0 9 * * *", "x", "--expires", "2027-03-01")[0] == 1)
code, out = k("add", "vstrecha", "--at", "2026-11-25 12:00", "Speed Dating, Humo Arena")
chk("v4: разовое дело на дату — записано, живёт до 27.11, следующий срок 25.11 12:00", code == 0 and "разово 2026-11-25 12:00" in out and [j for j in jobs() if j["id"] == "vstrecha"][0]["expires"] == "2026-11-27")
chk("v4: разовое в прошлом — отказ", k("add", "proshloe", "--at", "2026-10-01 09:00", "x")[0] == 1)
chk("v4: разовое дальше 400 дней — отказ", k("add", "daleko", "--at", "2028-01-01 09:00", "x")[0] == 1)
chk("v4: list показывает разовое как «разово ДАТА»", "vstrecha · разово 2026-11-25 12:00" in k("list")[1])
k("rm", "vstrecha")
chk("pause / resume / extend", k("pause", "vecher")[0] == 0 and not [j for j in jobs() if j["id"] == "vecher"][0]["enabled"]
    and k("resume", "vecher")[0] == 0 and k("extend", "vtoroy-vzglyad", "2026-12-20")[0] == 0 and [j for j in jobs() if j["id"] == "vtoroy-vzglyad"][0]["expires"] == "2026-12-20")
code, out = k("next", "0 9 * * 1", "3")
chk("next: три ближайших понедельника 09:00", code == 0 and out.count("09:00") == 3 and "Mon 02.11" in out)
open(EV, "w").write(json.dumps({"method": "notifications/claude/channel", "params": {"content": "[⏰ расписание] …", "meta": {"ritual": "cron", "job": "vtoroy-vzglyad",
                                 "message_id": "cron-razrabotka-vtoroy-vzglyad-" + "20261026" + "1017", "ts": "2026-10-26T10:17:00+05:00"}}}) + "\n")
k("done", "vtoroy-vzglyad", "пропусков нет")
code, out = k("list")
chk("list: следующий срок, последний запуск по журналу плагина, итог", code == 0 and "vtoroy-vzglyad" in out and "следующий 2026-10-26T10:17" in out and "последний 2026-10-26T10:17" in out and "итог: пропусков нет" in out)
k("start", "vtoroy-vzglyad", "взялась")
k("fail", "vtoroy-vzglyad", "нет доступа, звонить +998 90 123 45 67")
dl = [json.loads(l) for l in open(os.path.join(W, "dela.jsonl"))]
dn = [json.loads(l) for l in open(os.path.join(W, "schedule", "done.jsonl"))]
chk("v4: start/fail — статусы в done.jsonl; итог и срыв — в журнал дел, start — нет", [d.get("status") for d in dn][-2:] == ["start", "fail"]
    and [d["ступень"] for d in dl] == ["сделала", "сорвано"] and dl[0]["тип"] == "расписание" and dl[1]["улика"] == "journal:schedule/done.jsonl:%d" % len(dn))
chk("v4: личные данные в итоге в журнал дел не переходят", dl[1]["результат"] == "" and "+998" not in open(os.path.join(W, "dela.jsonl")).read())
code, out = k("event", "speed-dating", "2026-11-25 12:00", "Speed Dating, Humo Arena", "--by", "owner", "--word", "-1001/77")
ev = {j["id"]: j for j in jobs() if j["id"].startswith("speed-dating")}
chk("v4: событие + «будь готова» за день и за 2 ч", code == 0 and set(ev) == {"speed-dating", "speed-dating-p1d", "speed-dating-p2h"}
    and ev["speed-dating-p1d"]["at"].startswith("2026-11-24T12:00") and ev["speed-dating-p2h"]["at"].startswith("2026-11-25T10:00") and "Будь готова" in ev["speed-dating-p2h"]["text"])
code, out = k("agenda", "--hours", "1000")
chk("v4: повестка — событие 📅 и подготовка 🎒 по времени", code == 0 and out.index("🎒") < out.index("📅") and "Speed Dating" in out)
chk("v4: --prep с ошибкой — отказ", k("event", "x2", "2026-11-25 12:00", "x", "--prep", "вчера")[0] == 1)
for x in list(ev): k("rm", x)
chk("rm и задачи «нет такой»", k("rm", "vecher")[0] == 0 and k("rm", "vecher")[0] == 1)
snap = os.path.join(W, "crons.md")
open(snap, "w").write("# Снимок\n## Кроны сессии\n- 5223c3ed · «Второй взгляд» · 17 10,12,14,16,18,20 * * * · durable, истекает 01.11\n- 77aa · «Сломанный» · 99 9 * * * · x\n## Обещания\n- 1 · «не крон» · 0 9 * * * · x\n")
code, out = k("import", snap)
chk("import из снимка: «Кроны сессии» → задача c-5223c3ed; битая — пропуск с причиной; чужой раздел не трогаю", code == 0 and "перенесено 1" in out and "c-77aa" in out
    and any(j["id"] == "c-5223c3ed" for j in jobs()) and not any(j["id"] == "c-1" for j in jobs()))
open(os.path.join(W, "schedule", "jobs.json"), "w").write("{не json")
chk("испорченный jobs.json — отказ, не перезаписываю", k("add", "z", "0 9 * * *", "x")[0] == 1 and open(os.path.join(W, "schedule", "jobs.json")).read() == "{не json")
os.remove(os.path.join(W, "schedule", "jobs.json"))
th = [threading.Thread(target=k, args=("add", "p%d" % i, "0 9 * * *", "x")) for i in range(12)]
[t.start() for t in th]; [t.join() for t in th]
chk("12 одновременных add — все 12 записаны (замок, без потерь)", len(jobs()) == 12)
for i in range(12, 45): k("add", "p%d" % i, "0 9 * * *", "x")
chk("v4: 45 задач — без потолка в 30 (планировщик помощника, а не кроны)", len(jobs()) == 45)
# the zone without the USER.md line is the one the service fires by (Asia/Tashkent), not the machine's
W2 = tempfile.mkdtemp(prefix="cron-tz-")
p = subprocess.run([sys.executable, K, "next", "0 9 * * *", "1"], env=dict(os.environ, MILA_WORK=W2, MILA_EVENTS=EV, TZ="America/New_York", MILA_CRON_NOW="2026-10-26T10:00:00+05:00"), capture_output=True, text=True, timeout=30)
chk("без строки пояса в USER.md — сроки в Asia/Tashkent, хоть машина в другом поясе (правило службы)", p.returncode == 0 and "27.10 09:00" in p.stdout)      # 10:00 in Tashkent: today's 09:00 has passed; by New York's clock (01:00) it would be «26.10»
open(os.path.join(W2, "USER.md"), "w", encoding="utf-8").write("Часовой пояс — Europe/Berlin\n")
p = subprocess.run([sys.executable, K, "next", "0 9 * * *", "1"], env=dict(os.environ, MILA_WORK=W2, MILA_EVENTS=EV, TZ="America/New_York", MILA_CRON_NOW="2026-10-26T10:00:00+05:00"), capture_output=True, text=True, timeout=30)
chk("со строкой — пояс хозяина (в Берлине 06:00 — срок сегодня)", p.returncode == 0 and "26.10 09:00" in p.stdout)
print("итог %d/%d" % (ok, n)); sys.exit(0 if ok == n else 1)
