#!/usr/bin/env python3
"""Кормилец и очередь Claude Code: событие, принятое в очередь живой сессии (queue-operation enqueue), не подаётся повторно —
иначе при конце долгого вызова (рендер 8 мин) ход получает две-три копии. Перезапуск сессии, пока событие в очереди, —
подаём в новую сразу. Формы записей — снимок живого транскрипта (enqueue → attachment queued_command → remove).
Всё во временной папке: HOME, журнал, транскрипт, pid сессии подменены."""
import importlib.util, json, os, sys, tempfile, time
HERE = os.path.dirname(os.path.abspath(__file__)); ok = n = 0
def chk(name, cond):
    global ok, n
    n += 1; ok += bool(cond); print(("✅ " if cond else "❌ ") + name)
T = tempfile.mkdtemp(prefix="fq-"); os.environ["HOME"] = T
ST = os.path.join(T, ".claude", "channels", "telegram"); os.makedirs(os.path.join(ST, "inbound")); PROJ = os.path.join(T, ".claude", "projects", "w"); os.makedirs(PROJ)
CS = os.path.join(T, "state"); os.makedirs(CS)
os.environ.update(TELEGRAM_STATE_DIR=ST, COMPANION_STATE=CS, COMPANION_INSTALL_DIR=HERE, CLAUDE_CONFIG_DIR=os.path.join(T, ".claude"),
                  COMPANION_PROJECTS=os.path.join(T, ".claude", "projects"))
sys.path.insert(0, HERE)
spec = importlib.util.spec_from_file_location("feeder", os.path.join(HERE, "companion-feeder.py")); F = importlib.util.module_from_spec(spec); spec.loader.exec_module(F)
fed = []; F.feed = lambda text: fed.append(text); F._save_pending = lambda: None
TR = os.path.join(PROJ, "s.jsonl")
def iso(t): return time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime(t))
def env(mid): return '<channel source="telegram" chat_id="1" message_id="%s" user="Планировщик" ts="x">задание</channel>' % mid
def enq(mid, t): return {"type": "queue-operation", "operation": "enqueue", "timestamp": iso(t), "sessionId": "s1", "content": env(mid)}
def att(mid, t): return {"type": "attachment", "timestamp": iso(t), "attachment": {"type": "queued_command", "prompt": env(mid)}}
def user(mid, t): return {"type": "user", "timestamp": iso(t), "message": {"role": "user", "content": env(mid)}}
def bash_echo(mid, t):   # эхо входящего в выводе команды — не доставка
    return {"type": "user", "timestamp": iso(t), "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "x", "content": env(mid)}]}}
def journal(*rows):
    open(TR, "w").write("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
    os.utime(TR, (time.time(), time.time()))   # mtime транскрипта — по тем же часам, что «сейчас» кормильца (тест без часов)
def pid(v): open(F.SESSION_PID, "w").write(str(v))
def pend(mid, t0, p=100, **k):
    F._pending.clear(); fed.clear()
    F._pending["1:" + mid] = dict({"text": env(mid), "first_ts": t0, "last_ts": t0, "tries": 1, "backoff": F.DELIVERY_WAIT, "chat": "1", "mid": mid, "pid": p}, **k)
now = time.time(); MID = "cron-job-1"

pid(100); journal(enq(MID, now - 200)); pend(MID, now - 200); F.check_delivery()
chk("в очереди живой сессии 200 с — повторно не подаю, жду", not fed and ("1:" + MID) in F._pending)
pend(MID, now - 600, last_ts=now - 400, backoff=180); F.check_delivery()
chk("в очереди 10 мин (долгий рендер) — всё ещё не подаю, LOST не пишу", not fed and ("1:" + MID) in F._pending)
journal(enq(MID, now - 600), att(MID, now - 5)); F.check_delivery()
chk("ход взял (вложение queued_command) — ожидание закрыто, повторов было 0", not fed and not F._pending)
journal(enq(MID, now - 200), user(MID, now - 1)); pend(MID, now - 200); F.check_delivery()
chk("ход взял отдельной записью user — закрыто", not F._pending and not fed)
# перезапуск сессии, пока событие стояло в очереди
journal(enq(MID, now - 100)); pend(MID, now - 100, p=100, last_ts=now - 10); pid(200); F.check_delivery()
chk("сессию перезапустили (pid другой), событие было только в очереди — подаю в новую сразу", len(fed) == 1 and F._pending["1:" + MID]["pid"] == 200)
journal(enq(MID, now - 1200)); pend(MID, now - 1200, p=100, last_ts=now - 300, backoff=300); pid(300); F.check_delivery()
chk("в очереди 20 мин (дольше MAX_PENDING_AGE), потом рестарт — подаю в новую, не LOST", len(fed) == 1 and ("1:" + MID) in F._pending)
journal(enq(MID, now - 100)); pend(MID, now - 100, p=100, last_ts=now - 10); pid(200); F.check_delivery()
fed.clear(); F.check_delivery()
chk("после повторной подачи в новую — не повторяю до её ответа (новый enqueue той же сессии)", not fed)
journal(enq(MID, now - 100), enq(MID, now - 1)); F._pending["1:" + MID]["last_ts"] = now - 1000; F.check_delivery()
chk("enqueue в новой сессии — жду дальше, без дубля", not fed)
# старые правила не сломаны
pid(100); journal(); pend("m2", now - 100); F.check_delivery()
chk("не видно нигде 100 с — повторная подача, как прежде", len(fed) == 1)
journal(bash_echo("m3", now - 2)); pend("m3", now - 100); F.check_delivery()
chk("эхо в выводе команды (tool_result) — не доставка и не очередь: подаю повторно", len(fed) == 1)
journal(); pend("m4", now - F.MAX_PENDING_AGE - 1); F.check_delivery()
chk("не видно нигде дольше MAX_PENDING_AGE — LOST, как прежде", not F._pending and not fed)
journal(enq("m5", now - F.QUEUED_MAX_AGE - 5)); pend("m5", now - F.QUEUED_MAX_AGE - 5); F.check_delivery()
chk("в очереди дольше QUEUED_MAX_AGE — LOST строкой, без повторной подачи", not F._pending and not fed)
journal(enq(MID, now - 100)); F._pending.clear(); fed.clear()
F._pending["1:" + MID] = {"text": env(MID), "first_ts": now - 100, "last_ts": now - 100, "tries": 1, "backoff": 90, "chat": "1", "mid": MID}
F.check_delivery()
chk("запись прежнего кормильца без pid, событие в очереди — считаю той же сессией, без дубля", not fed)
chk("очередь другого события не считается этим", F._in_transcript("other-1", now - 300) is None)
journal({"type": "queue-operation", "operation": "remove", "timestamp": iso(now), "content": env(MID)})
chk("remove без enqueue — не «в очереди»", F._in_transcript(MID, now - 300) is None)
print("итог %d/%d" % (ok, n))
sys.exit(0 if ok == n else 1)
