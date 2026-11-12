#!/usr/bin/env python3
"""run-allow.py — the only Bash the background session may run is her own script from the kit: «python3 <script>» or
«bash <script>» where the script, with links resolved, lies in ~/.claude/skills or ~/.claude/hooks. A path with «..», a script
she could have written herself, a link out of the kit, anything a shell would act on — no decision (Claude Code refuses).
Run: python3 install/test_run_allow.py"""
import json, os, shutil, subprocess, sys, tempfile

H = os.path.dirname(os.path.abspath(__file__)); T = os.path.realpath(tempfile.mkdtemp(prefix="runallow-")); ok = n = 0
HOME = os.path.join(T, "home"); SK = os.path.join(HOME, ".claude", "skills", "demo"); HK = os.path.join(HOME, ".claude", "hooks"); WORK = os.path.join(HOME, "work")
for d in (SK, HK, WORK): os.makedirs(d)
for p in (os.path.join(SK, "tool.py"), os.path.join(SK, "run.sh"), os.path.join(HK, "doctor.py"), os.path.join(WORK, "x.py"), os.path.join(T, "outside.py")):
    open(p, "w").write("print('x')\n")
os.symlink(os.path.join(WORK, "x.py"), os.path.join(SK, "link-out.py"))            # a link from the kit to a file she can write
os.symlink(os.path.join(SK, "tool.py"), os.path.join(WORK, "link-in.py"))          # a link from her home into the kit — the target is the kit's


def chk(m, c, x=""):
    global ok, n
    n += 1; ok += bool(c); print(("✅ " if c else "❌ ") + m + ("" if c else "  ← " + str(x)[:300]))


def ask(cmd, tool="Bash", raw=None):
    inp = raw if raw is not None else json.dumps({"tool_name": tool, "tool_input": {"command": cmd}})
    r = subprocess.run([sys.executable, "-B", os.path.join(H, "run-allow.py")], input=inp, capture_output=True, text=True, env=dict(os.environ, HOME=HOME), timeout=20)
    try: dec = json.loads(r.stdout)["hookSpecificOutput"]["permissionDecision"] if r.stdout.strip() else ""
    except Exception: dec = "?"
    return r.returncode, dec


def yes(cmd): rc, d = ask(cmd); return rc == 0 and d == "allow"
def no(cmd): rc, d = ask(cmd); return rc == 0 and d == ""


try:
    chk("её скрипт из навыков: python3 ~/.claude/skills/demo/tool.py list — разрешено", yes("python3 ~/.claude/skills/demo/tool.py list --lang ru"))
    chk("…с -B, с полным путём, с кавычками в аргументе — разрешено", yes("python3 -B %s add proba \"0 9 * * 1\" 'текст с пробелами'" % os.path.join(SK, "tool.py")))
    chk("bash ~/.claude/skills/demo/run.sh и python3 ~/.claude/hooks/doctor.py — разрешено", yes("bash ~/.claude/skills/demo/run.sh a") and yes("python3 ~/.claude/hooks/doctor.py"))
    chk("ссылка из её дома на скрипт набора — разрешено (исполняется файл набора)", yes("python3 %s" % os.path.join(WORK, "link-in.py")))
    chk("путь с «..» из папки навыков в её дом (находка Качества) — нет решения", no("python3 ~/.claude/skills/../../work/x.py"))
    chk("…и «..» даже когда путь остаётся внутри набора — нет решения", no("python3 ~/.claude/skills/demo/../demo/tool.py"))
    chk("скрипт из её дома, который она могла написать сама, — нет решения", no("python3 ~/work/x.py") and no("python3 %s" % os.path.join(WORK, "x.py")))
    chk("ссылка из набора наружу, на файл её дома, — нет решения (смотрю, куда ссылка ведёт)", no("python3 ~/.claude/skills/demo/link-out.py"))
    chk("скрипт вне дома и относительный путь — нет решения", no("python3 %s" % os.path.join(T, "outside.py")) and no("python3 tool.py") and no("python3 .claude/skills/demo/tool.py"))
    chk("файла нет или это папка — нет решения", no("python3 ~/.claude/skills/demo/absent.py") and no("python3 ~/.claude/skills/demo"))
    for bad, why in (("python3 ~/.claude/skills/demo/tool.py; rm -rf ~", "точка с запятой"), ("python3 ~/.claude/skills/demo/tool.py && id", "&&"),
                     ("python3 ~/.claude/skills/demo/tool.py | sh", "труба"), ("python3 ~/.claude/skills/demo/tool.py > ~/.bashrc", "перенаправление"),
                     ("python3 ~/.claude/skills/demo/tool.py $(id)", "подстановка"), ("python3 ~/.claude/skills/demo/tool.py `id`", "обратные кавычки"),
                     ("python3 ~/.claude/skills/demo/tool.py\nid", "перевод строки"), ("X=1 python3 ~/.claude/skills/demo/tool.py", "переменная впереди"),
                     ("python3 $HOME/.claude/skills/demo/tool.py", "переменная в пути")):
        chk("после её скрипта или перед ним — то, что исполнит оболочка (%s) — нет решения" % why, no(bad), bad)
    chk("python3 -c, python3 -m, другие ключи и другие программы — нет решения", no("python3 -c 'print(1)'") and no("python3 -m http.server") and no("python3 -u ~/.claude/skills/demo/tool.py")
        and no("sh ~/.claude/skills/demo/run.sh") and no("env python3 ~/.claude/skills/demo/tool.py") and no("ls") and no("cat ~/.claude/skills/demo/tool.py"))
    chk("не Bash — хук молчит", ask("x", tool="Read") == (0, ""))
    chk("вход не читается, пустая команда, команда не строка — нет решения и нет падения", ask("", raw="не json") == (0, "") and no("") and no("   ")
        and ask("", raw=json.dumps({"tool_name": "Bash", "tool_input": {"command": ["python3"]}})) == (0, "") and ask("", raw=json.dumps({"tool_name": "Bash"})) == (0, ""))
    chk("незакрытая кавычка — нет решения", no("python3 ~/.claude/skills/demo/tool.py 'abc"))
    chk("очень длинная команда — нет решения", no("python3 ~/.claude/skills/demo/tool.py " + "a" * 5000))
finally:
    shutil.rmtree(T, ignore_errors=True)
print("итог %d/%d" % (ok, n)); sys.exit(0 if ok == n else 1)
