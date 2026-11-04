#!/usr/bin/env python3
"""fleet_plan: таблица по трём домам — свежий, уже обновлённый, недоступный; ни одного файла в домах не появилось и не изменилось
(план без --offer — только чтение). Дома и Милы выдуманные. python3 test_fleet_plan.py"""
import hashlib, json, os, shutil, subprocess, sys, tempfile
H = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.abspath(os.path.join(H, "..", ".."))
T = tempfile.mkdtemp(); ok = n = 0
def check(name, c, x=""):
    global ok, n; n += 1; ok += bool(c); print(("✅ " if c else "❌ ") + name + ("" if c else "  " + str(x)[:300]))
rel = os.path.join(T, "rel"); shutil.copytree(REPO, rel, ignore=shutil.ignore_patterns(".git", "__pycache__"))
def home(name):
    h = os.path.join(T, "srv", name, "home"); os.makedirs(os.path.join(h, "work")); open(os.path.join(h, "work", "USER.md"), "w").write("знакомство: пройдено"); return h
fresh, done = home("alpha"), home("beta")
env = dict(os.environ, MILA_HOME=done); [env.pop(k, None) for k in ("CLAUDE_CONFIG_DIR", "MILA_WORK")]
subprocess.run([sys.executable, os.path.join(H, "update.py"), "apply", "--src", rel, "--yes", "тест"], env=env, capture_output=True, text=True)
def snap(*roots):
    s = {}
    for r in roots:
        for d, _, fs in os.walk(r):
            for f in fs:
                p = os.path.join(d, f); s[p] = hashlib.sha256(open(p, "rb").read()).hexdigest()
    return s
before = snap(fresh, done)
hf = os.path.join(T, "homes.txt")
open(hf, "w").write("# Милы\nalpha  %s\nbeta %s\ngamma %s\nbroken relative/path\n" % (fresh, done, os.path.join(T, "srv", "nope", "home")))
r = subprocess.run([sys.executable, os.path.join(H, "fleet_plan.py"), "--homes-file", hf, "--src", rel, "--json"], capture_output=True, text=True)
try: rows = {x["name"]: x for x in json.loads(r.stdout)}
except Exception: rows = {}
check("четыре строки, порядок файла", list(rows) == ["alpha", "beta", "gamma", "broken"], r.stdout[-300:] + r.stderr[-300:])
check("свежий дом: стоит «—», станет версия выпуска, риск назван", rows.get("alpha", {}).get("from") == "—" and rows["alpha"].get("to") not in (None, "—") and rows["alpha"].get("risk") not in (None, "—"), rows.get("alpha"))
check("обновлённый дом: стоит = станет, риск «нет»", rows.get("beta", {}).get("from") == rows.get("beta", {}).get("to") and rows["beta"].get("risk") == "нет", rows.get("beta"))
check("недоступный дом — «нет плана», остальные посчитаны", "error" in rows.get("gamma", {}) and "error" not in rows.get("alpha", {}), rows.get("gamma"))
check("относительный путь — отказ строкой, не чтение", "абсолютный" in rows.get("broken", {}).get("error", ""), rows.get("broken"))
check("только чтение: в домах ни одного нового или изменённого файла", snap(fresh, done) == before)
t = subprocess.run([sys.executable, os.path.join(H, "fleet_plan.py"), "--homes-file", hf, "--src", rel], capture_output=True, text=True).stdout
check("таблица текстом: шапка и строка «нет плана»", t.splitlines()[0].startswith("Мила") and "нет плана" in t, t[:300])
check("--src без release.json — отказ", subprocess.run([sys.executable, os.path.join(H, "fleet_plan.py"), "--homes-file", hf, "--src", T], capture_output=True, text=True).returncode != 0)
sys.path.insert(0, H); import fleet_plan as FP
st = os.stat(fresh)
check("от root — план правами хозяина дома (uid/gid папки дома), не root", FP.as_owner(fresh, euid=0) == (st.st_uid, st.st_gid) and FP.as_owner(fresh, euid=1000) is None)
orig = os.stat
class S: st_uid = 0; st_gid = 0
FP.os.stat = lambda p: S
try: FP.as_owner(fresh, euid=0); refused = False
except PermissionError: refused = True
FP.os.stat = orig
check("дом root-а — отказ, план от root не запускается", refused)
shutil.rmtree(T, ignore_errors=True); print("итог %d/%d" % (ok, n)); sys.exit(0 if ok == n else 1)
