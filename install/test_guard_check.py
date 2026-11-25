#!/usr/bin/env python3
"""guard_check.py: сломанный обязательный сторож находится (компиляция и положительный контроль) и заменяется релизной копией;
состояние пишется в файл. Песочница: свой CLAUDE_CONFIG_DIR, настоящие сторожа из репозитория, без сети."""
import hashlib, json, os, shutil, stat, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(HERE)
ok = n = 0


def chk(name, cond):
    global ok, n
    n += 1; ok += bool(cond); print(("✅ " if cond else "❌ ") + name)


REL = json.load(open(os.path.join(REPO, "release.json"), encoding="utf-8"))
SRC = {"hooks/send-guard.py": os.path.join(REPO, "templates/home/.claude/hooks/send-guard.py"),
       "hooks/secret-guard.py": os.path.join(REPO, "templates/home/.claude/hooks/secret-guard.py"),
       "hooks/pd-mask.py": os.path.join(REPO, "install/pd-mask.py")}
CONTROLS = {g["key"]: g["control"] for g in REL["guards"] if "control" in g}


def home():
    """Дом после обновления: три обязательных сторожа на месте, их релизные копии и хеши — как пишет mila-update."""
    t = tempfile.mkdtemp(prefix="gchk-"); c = os.path.join(t, ".claude")
    os.makedirs(os.path.join(c, "hooks")); os.makedirs(os.path.join(c, "mila-update", "guards"), mode=0o700)
    copies = {}
    for key, src in SRC.items():
        shutil.copy(src, os.path.join(c, key)); os.chmod(os.path.join(c, key), 0o755)
        dst = os.path.join(c, "mila-update", "guards", os.path.basename(key)); shutil.copy(src, dst); os.chmod(dst, 0o600)
        copies[key] = hashlib.sha256(open(src, "rb").read()).hexdigest()
    json.dump({"tag": "v0", "guards_required": sorted(SRC), "guard_copies": copies, "guard_controls": CONTROLS}, open(os.path.join(c, "mila-update", "version.json"), "w"))
    return t, c


def run(c, *args):
    env = dict(os.environ, CLAUDE_CONFIG_DIR=c, HOME=os.path.dirname(c))
    r = subprocess.run([sys.executable, os.path.join(HERE, "guard_check.py"), *args], capture_output=True, text=True, timeout=120, env=env)
    try: st = json.load(open(os.path.join(c, "mila-update", "guards-state.json"), encoding="utf-8"))
    except (OSError, ValueError): st = {}
    return r, st


chk("в релизе у обязательных сторожей отправки и тайны есть положительный контроль (вход «откажи» и вход «пропусти»)",
    set(CONTROLS) >= {"hooks/send-guard.py", "hooks/secret-guard.py"} and all(set(v) == {"deny", "allow"} for v in CONTROLS.values()))

# 1. контроль: всё цело
t, c = home(); r, st = run(c)
chk("контроль: целые сторожа — код 0, состояние ok, проверены три, вывод пуст", r.returncode == 0 and st.get("guards") == "ok" and sorted(st.get("checked", [])) == ["pd-mask.py", "secret-guard.py", "send-guard.py"] and r.stdout.strip() == "")
chk("файл состояния 600", stat.S_IMODE(os.stat(os.path.join(c, "mila-update", "guards-state.json")).st_mode) == 0o600)
chk("проверка не оставляет следов в доме: журнала отказов сторожа тайны нет", not os.path.exists(os.path.join(c, "mila-guard")))

# 2. сторож не компилируется → заменён копией
t, c = home(); g = os.path.join(c, "hooks", "secret-guard.py"); open(g, "a").write("\ndef сломан(:\n")
r, st = run(c)
chk("не компилируется: заменён релизной копией, код 0, состояние replaced", r.returncode == 0 and st.get("guards") == "replaced" and [x["name"] for x in st["replaced"]] == ["secret-guard.py"]
    and open(g, "rb").read() == open(SRC["hooks/secret-guard.py"], "rb").read())
chk("сломанный файл лежит рядом (.broken-<время>), права сторожа те же (755)", any(f.startswith("secret-guard.py.broken-") for f in os.listdir(os.path.join(c, "hooks"))) and stat.S_IMODE(os.stat(g).st_mode) == 0o755)
chk("строка для человека: какой сторож, что заменён, кому сказать", "secret-guard.py" in r.stdout and "заменён релизной копией" in r.stdout and "хозяину" in r.stdout)
r2, st2 = run(c)
chk("следующая проверка: снова ok", r2.returncode == 0 and st2.get("guards") == "ok")

# 3. компилируется, но не отказывает (положительный контроль) → тоже сломан
t, c = home(); g = os.path.join(c, "hooks", "secret-guard.py"); open(g, "w").write("import sys\nsys.exit(0)\n")
r, st = run(c, "--no-fix")
chk("компилируется, но пропускает всё: без починки — код 1, состояние broken, причина «не отказал»", r.returncode == 1 and st.get("guards") == "broken" and "не отказал" in st["broken"][0]["why"])
r, st = run(c)
chk("…с починкой — заменён копией", r.returncode == 0 and st.get("guards") == "replaced")
t, c = home(); g = os.path.join(c, "hooks", "send-guard.py"); open(g, "w").write("import sys\nraise SystemExit(0)\n")
r, st = run(c)
chk("сторож отправки, который пропускает всё, — найден и заменён", st.get("guards") == "replaced" and st["replaced"][0]["name"] == "send-guard.py")
t, c = home(); g = os.path.join(c, "hooks", "secret-guard.py")
open(g, "w").write('import json\nprint(json.dumps({"hookSpecificOutput": {"permissionDecision": "deny"}}))\n')
r, st = run(c, "--no-fix")
chk("сторож, который отказывает всем подряд, — тоже сломан («отказал там, где должен пропустить»)", st.get("guards") == "broken" and "должен пропустить" in st["broken"][0]["why"])
t, c = home(); os.remove(os.path.join(c, "hooks", "send-guard.py"))
r, st = run(c)
chk("файла сторожа нет — возвращён из копии", st.get("guards") == "replaced" and os.path.isfile(os.path.join(c, "hooks", "send-guard.py")))

# 4. замена невозможна → broken, код 1, сломанный файл не тронут
t, c = home(); g = os.path.join(c, "hooks", "secret-guard.py"); open(g, "w").write("def (:\n"); os.remove(os.path.join(c, "mila-update", "guards", "secret-guard.py"))
r, st = run(c)
chk("копии нет: код 1, состояние broken, строка «сломан и не защищает»", r.returncode == 1 and st.get("guards") == "broken" and "релизной копии нет" in st["broken"][0]["why"] and "не защищает" in r.stdout)
t, c = home(); g = os.path.join(c, "hooks", "secret-guard.py"); open(g, "w").write("def (:\n")
open(os.path.join(c, "mila-update", "guards", "secret-guard.py"), "a").write("\n# подменено\n")
r, st = run(c)
chk("копия изменена (хеш не тот): не ставлю её, broken", r.returncode == 1 and "хеш копии не совпал" in st["broken"][0]["why"] and open(g).read() == "def (:\n")
t, c = home(); g = os.path.join(c, "hooks", "secret-guard.py"); open(g, "w").write("def (:\n")
cp = os.path.join(c, "mila-update", "guards", "secret-guard.py"); open(cp, "w").write("import sys\nsys.exit(0)\n")
v = json.load(open(os.path.join(c, "mila-update", "version.json"))); v["guard_copies"]["hooks/secret-guard.py"] = hashlib.sha256(open(cp, "rb").read()).hexdigest()
json.dump(v, open(os.path.join(c, "mila-update", "version.json"), "w"))
r, st = run(c)
chk("копия с верным хешем, но сама пропускает всё: не ставлю, broken", r.returncode == 1 and "копия сама не проходит" in st["broken"][0]["why"])
t, c = home(); g = os.path.join(c, "hooks", "secret-guard.py"); os.remove(g); victim = os.path.join(t, "victim.py"); open(victim, "w").write("def (:\n"); os.symlink(victim, g)
r, st = run(c)
chk("на месте сторожа ссылка: не иду по ней, цель цела, broken", r.returncode == 1 and open(victim).read() == "def (:\n" and os.path.islink(g))

# 5. сторож без положительного контроля (pd-mask) — проверяется компиляцией
t, c = home(); g = os.path.join(c, "hooks", "pd-mask.py"); open(g, "a").write("\ndef (:\n")
r, st = run(c)
chk("сторож личных данных не компилируется — заменён копией", st.get("guards") == "replaced" and st["replaced"][0]["name"] == "pd-mask.py")

# 6. дом без записи об обязательных (старое обновление) — не падает
t = tempfile.mkdtemp(prefix="gchk-"); c = os.path.join(t, ".claude"); os.makedirs(c)
r, st = run(c)
chk("version.json нет: код 0, состояние ok, проверять нечего", r.returncode == 0 and st.get("guards") == "ok" and st.get("checked") == [])
r, st = run(c, "--json")
chk("--json печатает состояние", json.loads(r.stdout).get("guards") == "ok")

print("итог %d/%d" % (ok, n)); sys.exit(0 if ok == n else 1)
