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
ZONES = {g["key"]: g["matcher"] for g in REL["guards"] if g["key"] in REL["guards_required"] and g.get("matcher")}


def home():
    """Дом после обновления: три обязательных сторожа на месте, их релизные копии и хеши — как пишет mila-update."""
    t = tempfile.mkdtemp(prefix="gchk-"); c = os.path.join(t, ".claude")
    os.makedirs(os.path.join(c, "hooks")); os.makedirs(os.path.join(c, "mila-update", "guards"), mode=0o700)
    copies = {}
    for key, src in SRC.items():
        shutil.copy(src, os.path.join(c, key)); os.chmod(os.path.join(c, key), 0o755)
        dst = os.path.join(c, "mila-update", "guards", os.path.basename(key)); shutil.copy(src, dst); os.chmod(dst, 0o600)
        copies[key] = hashlib.sha256(open(src, "rb").read()).hexdigest()
    json.dump({"tag": "v0", "guards_required": sorted(SRC), "guard_copies": copies, "guard_controls": CONTROLS, "guard_zones": ZONES}, open(os.path.join(c, "mila-update", "version.json"), "w"))
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
chk("копии нет: код 1, состояние blocked, строка «инструменты его зоны остановлены»", r.returncode == 1 and st.get("guards") == "blocked" and "релизной копии нет" in st["blocked"][0]["why"] and "остановлены" in r.stdout)
t, c = home(); g = os.path.join(c, "hooks", "secret-guard.py"); open(g, "w").write("def (:\n")
open(os.path.join(c, "mila-update", "guards", "secret-guard.py"), "a").write("\n# подменено\n")
r, st = run(c)
chk("копия изменена (хеш не тот): не ставлю её; на месте сторожа — заглушка, сломанный файл рядом", r.returncode == 1 and "хеш копии не совпал" in st["blocked"][0]["why"]
    and open(g).read().splitlines()[1].startswith("# mila-guard-stub") and any(open(os.path.join(c, "hooks", f)).read() == "def (:\n" for f in os.listdir(os.path.join(c, "hooks")) if ".broken-" in f))
t, c = home(); g = os.path.join(c, "hooks", "secret-guard.py"); open(g, "w").write("def (:\n")
cp = os.path.join(c, "mila-update", "guards", "secret-guard.py"); open(cp, "w").write("import sys\nsys.exit(0)\n")
v = json.load(open(os.path.join(c, "mila-update", "version.json"))); v["guard_copies"]["hooks/secret-guard.py"] = hashlib.sha256(open(cp, "rb").read()).hexdigest()
json.dump(v, open(os.path.join(c, "mila-update", "version.json"), "w"))
r, st = run(c)
chk("копия с верным хешем, но сама пропускает всё: не ставлю, blocked", r.returncode == 1 and "копия сама не проходит" in st["blocked"][0]["why"])
t, c = home(); g = os.path.join(c, "hooks", "secret-guard.py"); os.remove(g); victim = os.path.join(t, "victim.py"); open(victim, "w").write("def (:\n"); os.symlink(victim, g)
r, st = run(c)
chk("на месте сторожа ссылка: не иду по ней, цель цела, broken", r.returncode == 1 and open(victim).read() == "def (:\n" and os.path.islink(g))

# 4а. заглушка: отказывает всему в зоне сторожа (и входу «можно»), чужому инструменту не мешает; состояние blocked держится; починка снимает
def call(path, payload, c):
    r = subprocess.run([sys.executable, path], input=json.dumps(payload), capture_output=True, text=True, timeout=20, env=dict(os.environ, CLAUDE_CONFIG_DIR=c, HOME=os.path.dirname(c)))
    try: deny = json.loads(r.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"
    except Exception: deny = False
    return deny, r.returncode, r.stdout


for key, other in (("hooks/secret-guard.py", {"tool_name": "mcp__plugin_mila-telegram_telegram__reply", "tool_input": {"chat_id": "1", "text": "x"}}),
                   ("hooks/send-guard.py", {"tool_name": "Bash", "tool_input": {"command": "ls"}})):
    t, c = home(); g = os.path.join(c, key); name = os.path.basename(key)
    open(g, "w").write("import sys\nsys.exit(0)\n"); os.remove(os.path.join(c, "mila-update", "guards", name))
    r, st = run(c)
    allow_in = json.loads(json.dumps(CONTROLS[key]["allow"]).replace("{home}", t)); deny_in = json.loads(json.dumps(CONTROLS[key]["deny"]).replace("{home}", t))
    if key == "hooks/send-guard.py": allow_in = {"tool_name": "mcp__plugin_telegram_telegram__edit_message", "tool_input": {"chat_id": "1", "text": "Готово."}}
    d1, c1, o1 = call(g, deny_in, c); d2, c2, o2 = call(g, allow_in, c); d3, c3, o3 = call(g, other, c)
    chk("%s сломан, копии нет → заглушка отказывает и запретному входу, и входу «можно» из своей зоны (код 2, причина и путь починки)" % name,
        st.get("guards") == "blocked" and d1 and d2 and c1 == 2 and c2 == 2 and name in o2 and "mila update" in o2)
    chk("…права заглушки %s те же, что были у сторожа (755)" % name, stat.S_IMODE(os.stat(g).st_mode) == 0o755)
    chk("…а чужому инструменту заглушка %s не мешает" % name, not d3 and c3 == 0)
    d4, c4, o4 = call(g, None, c)
    chk("…вход не читается — заглушка %s отказывает" % name, d4 and c4 == 2)
    hooks_before = sorted(os.listdir(os.path.join(c, "hooks"))); body = open(g).read()
    r2, st2 = run(c)
    chk("повторная проверка: заглушку %s узнаю — состояние blocked держится, её не «чиню» и .broken из неё не делаю" % name,
        r2.returncode == 1 and st2.get("guards") == "blocked" and st2["blocked"][0]["name"] == name and sorted(os.listdir(os.path.join(c, "hooks"))) == hooks_before and open(g).read() == body)
    shutil.copy(SRC[key], os.path.join(c, "mila-update", "guards", name))            # копия вернулась (например, обновлением)
    r3, st3 = run(c)
    chk("копия появилась: заглушка %s заменена настоящим сторожем, состояние replaced, запись о заглушке снята" % name,
        r3.returncode == 0 and st3.get("guards") == "replaced" and st3.get("stubs") == {} and open(g, "rb").read() == open(SRC[key], "rb").read()
        and sorted(f for f in os.listdir(os.path.join(c, "hooks")) if ".broken-" in f) == sorted(f for f in hooks_before if ".broken-" in f))

t, c = home(); g = os.path.join(c, "hooks", "secret-guard.py"); open(g, "w").write("def (:\n"); os.remove(os.path.join(c, "mila-update", "guards", "secret-guard.py"))
run(c); open(g, "a").write("\n# правка хозяина поверх заглушки\n")
r, st = run(c, "--no-fix")
chk("правка хозяина поверх заглушки — уже не «наша заглушка»: проверяется как обычный файл", st.get("stubs") == {} and st.get("guards") in ("ok", "broken", "blocked") and "правка хозяина" in open(g).read())

# 4б. строка администратору: один раз на перемену, не на каждый старт
t, c = home(); inbox = os.path.join(t, "work", "inbox"); os.makedirs(inbox); adm = os.path.join(inbox, "to-admin.jsonl")
g = os.path.join(c, "hooks", "secret-guard.py"); open(g, "w").write("def (:\n"); os.remove(os.path.join(c, "mila-update", "guards", "secret-guard.py"))
env = dict(os.environ, CLAUDE_CONFIG_DIR=c, HOME=t, MILA_SENIOR_INBOX=adm)
for _ in range(3): subprocess.run([sys.executable, os.path.join(HERE, "guard_check.py"), "--start"], capture_output=True, text=True, timeout=120, env=env)
rows = [json.loads(l) for l in open(adm, encoding="utf-8")] if os.path.exists(adm) else []
chk("--start: сломанный сторож — одна строка администратору за три старта (kind alert, имя сторожа)", len(rows) == 1 and rows[0]["kind"] == "alert" and "secret-guard.py" in rows[0]["text"])
t, c = home(); adm = os.path.join(t, "work", "inbox", "to-admin.jsonl"); os.makedirs(os.path.dirname(adm))
subprocess.run([sys.executable, os.path.join(HERE, "guard_check.py"), "--start"], capture_output=True, text=True, timeout=120, env=dict(os.environ, CLAUDE_CONFIG_DIR=c, HOME=t, MILA_SENIOR_INBOX=adm))
chk("контроль: всё цело — администратору ничего не пишется", not os.path.exists(adm))
t, c = home(); g = os.path.join(c, "hooks", "secret-guard.py"); open(g, "w").write("def (:\n")
r = subprocess.run([sys.executable, os.path.join(HERE, "guard_check.py"), "--start"], capture_output=True, text=True, timeout=120, env=dict(os.environ, CLAUDE_CONFIG_DIR=c, HOME=t, MILA_SENIOR_INBOX=os.path.join(t, "нет", "to-admin.jsonl")))
chk("папки канала администратора нет — не создаю её и не падаю", r.returncode == 0 and not os.path.exists(os.path.join(t, "нет")))

# 4в. правка сторожа посреди сессии (PostToolUse) проверяется сразу
def hook(c, t, path):
    r = subprocess.run([sys.executable, os.path.join(HERE, "guard_check.py"), "--hook"], input=json.dumps({"tool_name": "Edit", "tool_input": {"file_path": path}}), capture_output=True, text=True, timeout=120,
                       env=dict(os.environ, CLAUDE_CONFIG_DIR=c, HOME=t))
    return r


t, c = home(); g = os.path.join(c, "hooks", "secret-guard.py"); open(g, "w").write("import sys\nsys.exit(0)\n")
r = hook(c, t, os.path.join(t, "work", "notes.md"))
chk("правка обычного файла: проверка сторожей не запускается (сломанный пока стоит), вывода нет", r.stdout.strip() == "" and open(g).read() == "import sys\nsys.exit(0)\n")
r = hook(c, t, g)
chk("правка файла в hooks/: сторож проверен сразу и заменён копией, строка в контекст", open(g, "rb").read() == open(SRC["hooks/secret-guard.py"], "rb").read()
    and "заменён релизной копией" in json.loads(r.stdout)["hookSpecificOutput"]["additionalContext"] and r.returncode == 0)
r = hook(c, t, g)
chk("контроль: правка в hooks/ при целых сторожах — тихо", r.stdout.strip() == "" and r.returncode == 0)

# 4г. старт сессии: session-start.py зовёт проверку, строка о стороже — первой в контексте
def start(c, t):
    for f, src in (("session-start.py", os.path.join(REPO, "templates/home/.claude/hooks/session-start.py")), ("guard_check.py", os.path.join(HERE, "guard_check.py"))):
        shutil.copy(src, os.path.join(c, "hooks", f))
    env = {k: v for k, v in os.environ.items() if k != "CLAUDE_CONFIG_DIR"}; env["HOME"] = t
    return subprocess.run([sys.executable, os.path.join(c, "hooks", "session-start.py")], input="{}", capture_output=True, text=True, timeout=120, env=env)


t, c = home(); g = os.path.join(c, "hooks", "secret-guard.py"); open(g, "w").write("import sys\nsys.exit(0)\n")
r = start(c, t)
ctx = json.loads(r.stdout)["hookSpecificOutput"]["additionalContext"] if r.stdout.strip() else ""
chk("старт сессии: сломанный сторож заменён, и об этом первая строка контекста", r.returncode == 0 and open(g, "rb").read() == open(SRC["hooks/secret-guard.py"], "rb").read()
    and ctx.startswith("Старт сессии Компаньона: Сторож secret-guard.py был сломан"))
r = start(c, t)
chk("контроль: старт при целых сторожах — о сторожах ни слова", "Сторож" not in r.stdout and r.returncode == 0)
t, c = home(); shutil.copy(os.path.join(REPO, "templates/home/.claude/hooks/session-start.py"), os.path.join(c, "hooks", "session-start.py"))
env = {k: v for k, v in os.environ.items() if k != "CLAUDE_CONFIG_DIR"}; env["HOME"] = t
r = subprocess.run([sys.executable, os.path.join(c, "hooks", "session-start.py")], input="{}", capture_output=True, text=True, timeout=60, env=env)
chk("старый дом без guard_check.py: старт сессии не падает", r.returncode == 0 and "Traceback" not in r.stderr)

# 5. сторож без положительного контроля (pd-mask) — проверяется компиляцией
t, c = home(); g = os.path.join(c, "hooks", "pd-mask.py"); open(g, "a").write("\ndef (:\n")
r, st = run(c)
chk("сторож личных данных не компилируется — заменён копией", st.get("guards") == "replaced" and st["replaced"][0]["name"] == "pd-mask.py")
t, c = home(); g = os.path.join(c, "hooks", "pd-mask.py"); open(g, "w").write("def (:\n"); os.remove(os.path.join(c, "mila-update", "guards", "pd-mask.py"))
r, st = run(c); r2, st2 = run(c)
chk("сторож личных данных сломан, копии нет: заглушки нет (он не отказывает, а правит файл) — состояние broken держится от старта к старту",
    st.get("guards") == "broken" and st2.get("guards") == "broken" and st2["broken"][0]["name"] == "pd-mask.py" and open(g).read() == "def (:\n" and r2.returncode == 1)

# 6. дом без записи об обязательных (старое обновление) — не падает
t = tempfile.mkdtemp(prefix="gchk-"); c = os.path.join(t, ".claude"); os.makedirs(c)
r, st = run(c)
chk("version.json нет: код 0, состояние ok, проверять нечего", r.returncode == 0 and st.get("guards") == "ok" and st.get("checked") == [])
r, st = run(c, "--json")
chk("--json печатает состояние", json.loads(r.stdout).get("guards") == "ok")

print("итог %d/%d" % (ok, n)); sys.exit(0 if ok == n else 1)
