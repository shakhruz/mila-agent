#!/usr/bin/env python3
"""doctor: the Scheduler row — no jobs: green; jobs set and a fresh pass mark: green with the time of the pass; jobs set and no
mark, or a stale one: yellow with what to do (the jobs will not fire); paused jobs do not count. A temp home; the mark is
written the way the service leaves it, stamped by the machine's clock as a child process sees it (the doctor runs as a
child), so the result does not depend on the clock of the test's own process. Run: python3 test_doctor_scheduler.py"""
import datetime as dt, json, os, shutil, subprocess, sys, tempfile
H = os.path.dirname(os.path.abspath(__file__)); T = tempfile.mkdtemp(prefix="doctor-sched-"); ok = n = 0
def check(name, c, x=""):
    global ok, n; n += 1; ok += bool(c); print(("✅ " if c else "❌ ") + name + ("" if c else "  ← " + str(x)[:300]))
HOME = os.path.join(T, "ivan"); WORK = os.path.join(HOME, "work"); os.makedirs(os.path.join(WORK, "schedule")); os.makedirs(os.path.join(T, "state"))
ENV = {k: v for k, v in os.environ.items() if k not in ("MILA_LANG", "LANG", "LC_ALL", "OWNER_JSON", "MILA_SCHEDULER_BEAT", "BARABAN_STATE", "XDG_STATE_HOME")}
ENV.update(HOME=HOME, MILA_WORK=WORK, TELEGRAM_STATE_DIR=os.path.join(T, "state"), OWNER_JSON=os.path.join(T, "owner.json"), MILA_LANG="en", PYTHONDONTWRITEBYTECODE="1")
def row(**env):
    r = subprocess.run([sys.executable, os.path.join(H, "doctor.py"), "--json"], capture_output=True, text=True, env=dict(ENV, **env), timeout=60)
    rows = [x for x in json.loads(r.stdout)["rows"] if x["name"] in ("Scheduler", "Планировщик")]
    return rows[0] if len(rows) == 1 else {"level": "?", "detail": str(rows), "fix": ""}
def machine_now():
    """The machine's clock as a child process sees it: doctor.py runs as a child and measures the age of the pass mark by ITS clock."""
    return float(subprocess.run([sys.executable, "-I", "-c", "import time; print(time.time())"], capture_output=True, text=True, timeout=30).stdout)
def stamp(age_s=0): return (dt.datetime.fromtimestamp(machine_now(), dt.timezone.utc) - dt.timedelta(seconds=age_s)).isoformat(timespec="seconds") + "\n"
def jobs(*js): json.dump({"jobs": list(js)}, open(os.path.join(WORK, "schedule", "jobs.json"), "w"))
def beat(age_s=None, folder=os.path.join(HOME, ".local", "state", "mila", "baraban")):
    shutil.rmtree(os.path.join(HOME, ".local"), ignore_errors=True); shutil.rmtree(os.path.join(HOME, "state"), ignore_errors=True)
    if age_s is None: return
    os.makedirs(folder, exist_ok=True)
    open(os.path.join(folder, "ivan.beat"), "w").write(stamp(age_s))
J = {"id": "utro", "cron": "0 9 * * *", "text": "x", "enabled": True}
try:
    r = row(); check("расписания нет — зелёная строка «задач нет»", r["level"] == "ok" and r["detail"] == "no jobs set", r)
    jobs(dict(J, enabled=False)); beat(None); r = row(); check("все задачи на паузе — зелёная: срабатывать нечему", r["level"] == "ok" and r["detail"] == "no jobs set", r)
    jobs(J, dict(J, id="vecher")); r = row()
    check("задачи стоят, отметки прохода нет — жёлтая: «не проходит», «ни разу», и что делать", r["level"] == "warn" and "jobs set: 2" in r["detail"] and "never" in r["detail"]
          and "will not fire" in r["fix"] and "install/install.sh" in r["fix"] and "OWNER_ID" in r["fix"], r)
    beat(30); r = row(); check("свежая отметка — зелёная, со временем прохода", r["level"] == "ok" and r["detail"].startswith("passing — last pass at ") and r["fix"] == "", r)
    beat(290); check("290 секунд — ещё зелёная", row()["level"] == "ok")
    beat(400); r = row(); check("400 секунд — жёлтая, с датой последнего прохода", r["level"] == "warn" and "never" not in r["detail"] and "last pass: " in r["detail"], r)
    beat(30, os.path.join(HOME, "state", "baraban")); check("отметка в папке контейнера (~/state/baraban) — зелёная", row()["level"] == "ok")
    beat(None); far = os.path.join(T, "far"); os.makedirs(far); open(os.path.join(far, "ivan.beat"), "w").write(stamp())
    check("отметка в папке, о которой доктор не знает, — жёлтая; названная серверу — зелёная", row()["level"] == "warn" and row(MILA_SCHEDULER_BEAT=far)["level"] == "ok")
    r = row(MILA_LANG="ru"); check("по-русски — та же строка, жёлтая", r["level"] == "warn" and r["name"] == "Планировщик" and "ни разу" in r["detail"] and "не сработают" in r["fix"], r)
    open(os.path.join(WORK, "schedule", "jobs.json"), "w").write("{broken"); r = row(); check("расписание не читается — зелёная «задач нет», без падения", r["level"] == "ok", r)
finally:
    shutil.rmtree(T, ignore_errors=True)
print("итог %d/%d" % (ok, n)); sys.exit(0 if ok == n else 1)
