#!/usr/bin/env python3
"""crons-keeper.py — запись кронов сессии в ~/work/state/crons.json: CronCreate записывается с id, CronDelete вычёркивает, тот же
крон после рестарта не копится дублем, несозданный не запоминается; при старте — одна строка «подними недостающее», разовые с
прошедшим временем — отдельно. Ответ CronCreate — по форме живого события Claude Code (17.11.2026: объект {"id", "humanSchedule",
"recurring", "durable", "nextFireAt"}; значения выдуманы) и прежней строкой. Всё во временном доме (HOME).
Usage: python3 test_crons_keeper.py [папка с crons-keeper.py]"""
import json, os, shutil, subprocess, sys, tempfile, time
D = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.abspath(__file__)); K = os.path.join(D, "crons-keeper.py")
ok = n = 0
def chk(name, cond, x=""):
    global ok, n
    n += 1; ok += bool(cond); print(("✅ " if cond else "❌ ") + name + ("" if cond else "  ← " + str(x)[:400]))
H = tempfile.mkdtemp(prefix="crons-"); P = os.path.join(H, "work", "state", "crons.json")
def run(ev, raw=None):
    p = subprocess.run([sys.executable, K], input=raw if raw is not None else json.dumps(ev), env=dict(os.environ, HOME=H), capture_output=True, text=True, timeout=30)
    return p.returncode, p.stdout.strip(), p.stderr.strip()
def rows(): return json.load(open(P, encoding="utf-8")) if os.path.exists(P) else []
def create(cron, prompt, resp, **inp):
    return run({"hook_event_name": "PostToolUse", "session_id": "s", "tool_name": "CronCreate", "tool_input": dict({"cron": cron, "prompt": prompt}, **inp), "tool_response": resp})
LIVE = lambda jid, rec=True: {"id": jid, "humanSchedule": "17 10,12 * * *", "recurring": rec, "durable": False, "nextFireAt": 17948934e5}

code, out, err = create("17 10,12 * * *", "Второй взгляд", LIVE("6040bf50"), recurring=True)
r = rows()
chk("CronCreate с ответом-объектом (живая форма): крон записан с id из поля, cron, текстом, recurring, временем создания",
    code == 0 and out == "" and len(r) == 1 and r[0]["id"] == "6040bf50" and r[0]["cron"] == "17 10,12 * * *" and r[0]["prompt"] == "Второй взгляд"
    and r[0]["recurring"] is True and r[0]["durable"] is False and abs(r[0]["created"] - time.time()) < 60, r)
create("17 10,12 * * *", "Второй взгляд", LIVE("aa11bb22"), recurring=True)
chk("тот же крон с тем же текстом после рестарта — запись заменена новым id, дубля нет", [x["id"] for x in rows()] == ["aa11bb22"])
create("5 9 * * 1", "Неделя", "Scheduled recurring job cc33dd44 (5 9 * * 1). Next run: Nov 23 9:05am.")
chk("ответ строкой («job <id>») — тоже записан", [x["id"] for x in rows()] == ["aa11bb22", "cc33dd44"])
create("30 14 28 2 *", "Разовое", LIVE("ee55ff66", False), recurring=False)
chk("разовый (recurring: false во входе) записан как разовый", rows()[-1]["id"] == "ee55ff66" and rows()[-1]["recurring"] is False)
before = rows()
for resp in ({"error": "cron expression is not valid"}, "Error: invalid cron", None, {"id": 5}, {"id": "ab"}, {"id": "../../x y"}):
    create("1 1 * * *", "Не создан", resp)
chk("крон не создан (ошибка, пусто, id не строкой, слишком короткий, с чужими знаками) — ничего не запомнено", rows() == before, rows())
run({"hook_event_name": "PostToolUse", "tool_name": "CronDelete", "tool_input": {"id": "cc33dd44"}, "tool_response": {"id": "cc33dd44"}})
chk("CronDelete вычёркивает запись по id", [x["id"] for x in rows()] == ["aa11bb22", "ee55ff66"])
run({"hook_event_name": "PostToolUse", "tool_name": "Bash", "tool_input": {"command": "ls"}, "tool_response": {"stdout": "job 12345678"}})
chk("чужой инструмент файл не трогает", [x["id"] for x in rows()] == ["aa11bb22", "ee55ff66"])

code, out, err = run({"hook_event_name": "SessionStart"})
ctx = json.loads(out)["hookSpecificOutput"]["additionalContext"] if out else ""
chk("старт сессии: одна строка контекста — сначала CronList, поднять недостающее; у записи есть её id (не None)",
    code == 0 and "CronList" in ctx and "aa11bb22" in ctx and "None" not in ctx and "Второй взгляд" in ctx, ctx[:300])
old = rows(); old[0]["created"] = int(time.time()) - 7 * 86400; json.dump(old, open(P, "w"), ensure_ascii=False)
code, out, err = run({"hook_event_name": "SessionStart"})
chk("повтору старше 6 дней — пометка «пересоздать» (повтор истекает на 7-й день)", "пересоздать] aa11bb22" in out, out[:300])
past = time.localtime(time.time() - 2 * 86400)
json.dump(rows() + [{"id": "gg77hh88", "cron": "%d %d %d %d *" % (past.tm_min, past.tm_hour, past.tm_mday, past.tm_mon), "prompt": "Позавчерашнее", "recurring": False, "durable": False, "created": 1}], open(P, "w"), ensure_ascii=False)
code, out, err = run({"hook_event_name": "SessionStart"})
ok_past = past.tm_year == time.localtime().tm_year      # правило хука — «в этом году»: на стыке лет проверка не о том
chk("разовый с прошедшим временем: назван отдельно и убран из файла", (not ok_past) or ("Позавчерашнее" in out and "gg77hh88" not in [x.get("id") for x in rows()]), out[-300:])
for raw in ("", "{не json", "[1]", '{"hook_event_name": "PostToolUse", "tool_name": "CronCreate", "tool_input": "строка", "tool_response": 5}'):
    code, out, err = run(None, raw=raw)
    chk("мусор на входе (%s) — код 0, без следов ошибки" % (raw[:24] or "пусто"), code == 0 and "Traceback" not in err)
open(P, "w").write("{битый"); code, out, err = create("2 2 * * *", "После битого", LIVE("ii99jj00"))
chk("битый crons.json — не падение: файл начат заново с новой записи", code == 0 and [x["id"] for x in rows()] == ["ii99jj00"])
shutil.rmtree(H, ignore_errors=True)
print("итог %d/%d" % (ok, n)); sys.exit(0 if ok == n else 1)
