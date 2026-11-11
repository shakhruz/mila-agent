#!/usr/bin/env python3
"""doctor: демон ЭТОГО дома — по <state>/receiver.pid, иначе по TELEGRAM_STATE_DIR в окружении процесса; соседняя Мила
под тем же пользователем — не моя («демон работает (pid чужой)» обманывал диагностику)."""
import importlib.util, os, sys, tempfile
H = os.path.dirname(os.path.abspath(__file__)); T = tempfile.mkdtemp(); ST = os.path.join(T, "mine"); os.makedirs(ST)
os.environ["TELEGRAM_STATE_DIR"] = ST
os.environ["MILA_LANG"] = "ru"   # тексты проверок сверяются по-русски; язык вывода doctor — MILA_LANG
spec = importlib.util.spec_from_file_location("doc", os.path.join(H, "doctor.py")); D = importlib.util.module_from_spec(spec); spec.loader.exec_module(D)
ok = n = 0
def chk(m, c, x=""):
    global ok, n; n += 1; ok += bool(c); print(("✅ " if c else "❌ ") + m + ("" if c else "  ← " + str(x)[:200]))
L = [("101", "bun /x/mila-telegram/receiver.ts"), ("202", "bun /y/mila-telegram/receiver.ts")]
envs = {"101": {"TELEGRAM_STATE_DIR": os.path.join(T, "neighbour")}, "202": {"TELEGRAM_STATE_DIR": ST}}
D._proc_env = lambda pid: envs.get(pid)
chk("без pid-файла: свой — по TELEGRAM_STATE_DIR в окружении, сосед отброшен", D.own_receivers(L) == [L[1]], D.own_receivers(L))
open(os.path.join(ST, "receiver.pid"), "w").write("101\n")
chk("pid-файл моего дома указывает на 101 — он и мой", D.own_receivers(L) == [L[0]], D.own_receivers(L))
os.remove(os.path.join(ST, "receiver.pid")); D._proc_env = lambda pid: None
chk("окружение не прочитать и pid-файла нет — чужой демон своим НЕ считаю (раньше считала: «демон работает» про соседнюю Милу)", D.own_receivers(L) == [], D.own_receivers(L))
open(os.path.join(ST, "receiver.pid"), "w").write("202\n")
chk("окружение не прочитать, но pid-файл моего дома называет 202 — он мой, сосед отброшен", D.own_receivers(L) == [L[1]], D.own_receivers(L))
os.remove(os.path.join(ST, "receiver.pid"))
D._proc_env = lambda pid: envs.get(pid); envs["202"] = {}
chk("у процесса нет TELEGRAM_STATE_DIR — состояние по умолчанию ~/.claude/channels/telegram ≠ моё → не мой", D.own_receivers(L) == [], D.own_receivers(L))
class R:
    def __init__(s): s.rows = []
    def add(s, *a): s.rows.append(a)
envs["202"] = {"TELEGRAM_STATE_DIR": ST}; D.running = lambda pat: list(L); r = R(); D.check_daemon(r)
chk("check_daemon: сосед + мой → «работает (pid 202)», не «запущено 2 копии»", r.rows and "pid 202" in str(r.rows[0]) and "копий" not in str(r.rows[0]), r.rows)
# канал в сессии: MCP-сервер соседнего дома (другой HOME) — не мой
me = os.path.realpath(os.path.expanduser("~"))
S = [("301", "bun /n/mila-telegram/server.ts"), ("302", "bun /m/mila-telegram/server.ts")]
homes = {"301": {"HOME": "/elsewhere/home"}, "302": {"HOME": me}}
D._proc_env = lambda pid: homes.get(pid)
D.running = lambda pat: [S[0]] if pat == "server.ts" else []
r = R(); D.check_flag(r)
chk("канал в сессии: только MCP соседнего HOME → не OK «запущен»", bool(r.rows) and r.rows[0][0] != D.OK, r.rows)
D.running = lambda pat: list(S) if pat == "server.ts" else []
r = R(); D.check_flag(r)
chk("канал в сессии: свой MCP есть → «MCP-сервер плагина запущен»", r.rows and r.rows[0][0] == D.OK, r.rows)
# чьи процессы — неизвестно (macOS, окружение не читается): не зелёное и не красное, а «определить нельзя»
D._proc_env = lambda pid: None
D.running = lambda pat: [S[0]] if pat == "server.ts" else []
r = R(); D.check_flag(r)
chk("канал в сессии: процесс есть, чей — не узнать → 🟡 «определить нельзя», не 🟢 и не 🔴", len(r.rows) == 1 and r.rows[0][0] == D.WARN and "определить нельзя" in str(r.rows[0]), r.rows)
D.running = lambda pat: [("401", "/usr/local/bin/claude --channels x")] if pat == "claude" else []
r = R(); D.check_flag(r)
chk("сессия claude есть, чья — не узнать → 🟡, а не 🔴 «сессия запущена, сервер канала — нет»", len(r.rows) == 1 and r.rows[0][0] == D.WARN and "определить нельзя" in str(r.rows[0]), r.rows)
D._proc_env = lambda pid: {"HOME": me}
r = R(); D.check_flag(r)
chk("своя сессия без сервера канала — по-прежнему 🔴", r.rows and r.rows[0][0] == D.BAD, r.rows)
D._proc_env = lambda pid: {"HOME": "/elsewhere/home"}
r = R(); D.check_flag(r)
chk("только чужая сессия — «сессия не найдена» (🟡), чужое не моё", r.rows and r.rows[0][0] == D.WARN and "не найдена" in str(r.rows[0]), r.rows)
# таймер учёта: служба с этим именем может смотреть в другой дом
import subprocess as _sp
CL = os.path.join(T, "claude"); os.environ["CLAUDE_CONFIG_DIR"] = CL; MINE = os.path.join(CL, "hooks", "turns_collect.py")
class P:
    def __init__(s, rc, out): s.returncode, s.stdout, s.stderr = rc, out, ""
def fake(out_by_cmd):
    def run(cmd, **kw):
        for key, val in out_by_cmd.items():
            if key in " ".join(cmd): return P(*val)
        return P(1, "")
    return run
real_run = D.subprocess.run; real_platform = D.sys.platform
try:
    D.sys.platform = "darwin"
    D.subprocess.run = fake({"launchctl list": (0, '{\n\t"Label" = "com.milagpt.turns-collect";\n\t"ProgramArguments" = (\n\t\t"/usr/bin/python3";\n\t\t"%s";\n\t);\n};' % MINE)})
    chk("Мак: служба загружена и смотрит в МОЙ дом → стоит, моя", D.timer_installed() == (True, "launchd com.milagpt.turns-collect", True), D.timer_installed())
    D.subprocess.run = fake({"launchctl list": (0, '{\n\t"ProgramArguments" = (\n\t\t"/usr/bin/python3";\n\t\t"/Users/drugaya/.claude/hooks/turns_collect.py";\n\t);\n};')})
    chk("Мак: служба загружена, но смотрит в ДРУГОЙ дом → не моя", D.timer_installed()[2] is False, D.timer_installed())
    r = R(); D.check_turns_timer(r)
    chk("…доктор говорит 🟡 «собирает другой дом», а не 🟢 «установлен»", r.rows and r.rows[0][0] == D.WARN and "другой дом" in str(r.rows[0]) and not any(x[0] == D.OK for x in r.rows), r.rows)
    D.subprocess.run = fake({"launchctl list": (0, "{ }")})
    chk("Мак: описание службы без пути — «стоит», чей — неизвестно (как раньше, зелёным)", D.timer_installed() == (True, "launchd com.milagpt.turns-collect", None), D.timer_installed())
    D.subprocess.run = fake({})
    chk("Мак: службы нет → не стоит", D.timer_installed()[0] is False, D.timer_installed())
    D.sys.platform = "linux"
    D.subprocess.run = fake({"is-enabled": (0, "enabled"), "systemctl --user cat": (0, "[Service]\nExecStart=/usr/bin/python3 /home/drugaya/.claude/hooks/turns_collect.py --days 1 --quiet\n")})
    chk("Linux: таймер включён, ExecStart смотрит в другой дом → не мой", D.timer_installed()[2] is False, D.timer_installed())
    D.subprocess.run = fake({"is-enabled": (0, "enabled"), "systemctl --user cat": (0, "[Service]\nExecStart=/usr/bin/python3 %s --days 1 --quiet\n" % MINE)})
    chk("Linux: ExecStart смотрит в мой дом → мой", D.timer_installed()[2] is True, D.timer_installed())
finally:
    D.subprocess.run = real_run; D.sys.platform = real_platform
import shutil; shutil.rmtree(T, ignore_errors=True)
print("итог %d/%d" % (ok, n)); sys.exit(0 if ok == n else 1)
