#!/usr/bin/env python3
"""mila-run.py — Mila in the background: the session lives in her home folder, comes back after it ends, never runs with
permissions switched off, logs carry no keys, two services over one home do not start, a home that is not born says so.
Claude Code and bun are replaced by small scripts; nothing leaves the temp folder. Run: python3 install/test_mila_run.py"""
import http.server, json, os, shutil, signal, stat, subprocess, sys, tempfile, threading, time, urllib.parse
os.umask(0o022)   # a CI runner's umask: her files must come out 600 by themselves, not by the caller's 077

H = os.path.dirname(os.path.abspath(__file__)); RUN = os.path.join(H, "mila-run.py")
T = os.path.realpath(tempfile.mkdtemp(prefix="milarun-")); ok = n = 0


def chk(m, c, x=""):
    global ok, n
    n += 1; ok += bool(c); print(("✅ " if c else "❌ ") + m + ("" if c else "  ← " + str(x)[:400]))


def wait(cond, sec=20):
    t = time.time()
    while time.time() - t < sec:
        try:
            if cond(): return True
        except Exception:
            pass
        time.sleep(0.2)
    return False


CL = os.path.join(T, "home", ".claude"); TG = os.path.join(CL, "channels", "telegram"); WORK = os.path.join(T, "home", "work"); ST = os.path.join(T, "state")
PLUG = os.path.join(CL, "plugins", "cache", "mila", "mila-telegram", "1.0.0"); BIN = os.path.join(T, "bin"); ELSE = os.path.join(T, "elsewhere")
for d in (TG, WORK, PLUG, BIN, ELSE, os.path.join(CL, "plugins", "cache", "mila", ".claude-plugin")): os.makedirs(d)
open(os.path.join(PLUG, "receiver.ts"), "w").write("// fake"); open(os.path.join(PLUG, "server.ts"), "w").write("// fake")
json.dump({"name": "mila-test-market"}, open(os.path.join(CL, "plugins", "cache", "mila", ".claude-plugin", "marketplace.json"), "w"))
KEY = "55500" + "0111:" + "K" * 35                      # a made-up bot token, glued
FAKE_CLAUDE = os.path.join(BIN, "claude"); FAKE_BUN = os.path.join(BIN, "bun")
open(FAKE_CLAUDE, "w").write('''#!/bin/bash
# a stand-in for Claude Code: notes how it was started, answers every input line with a finished turn, «die» ends it
if [ "$1" = auth ]; then if [ -e "$FAKE_LOG.signed" ]; then echo '{"loggedIn": true}'; else echo '{"loggedIn": false}'; fi; exit 0; fi
printf '%s\\n' "$*" >> "$FAKE_LOG.argv"; pwd >> "$FAKE_LOG.cwd"; printf '%s\\n' "${CLAUDE_CODE_OAUTH_TOKEN:+saved-login-in-env}" >> "$FAKE_LOG.auth"; printf '%s\\n' "$TELEGRAM_STATE_DIR" >> "$FAKE_LOG.tgs"
echo "token in stderr: $FAKE_KEY" >&2
while IFS= read -r line; do
  case "$line" in *die*) exit 7;; esac
  echo "{\\"type\\":\\"assistant\\",\\"text\\":\\"saw $FAKE_KEY\\"}"
  echo '{"type":"result","subtype":"success"}'
done
''')
open(FAKE_BUN, "w").write('''#!/bin/bash
echo $$ > "$TELEGRAM_STATE_DIR/receiver.pid"; printf '%s|%s|%s\\n' "$RECEIVER_DAEMON" "$TELEGRAM_STATE_DIR" "$*" >> "$FAKE_LOG.bun"; exec sleep 600
''')
HELPER = os.path.join(BIN, "login_helper.py")
open(HELPER, "w").write("""import os, sys, time
# a stand-in for the sign-in helper: notes who it was started for, waits for the «owner», then leaves a saved login (600)
open(os.environ["FAKE_LOG"] + ".helper-env", "a").write("%s|%s|%s\\n" % (os.environ.get("MILA_BORN"), os.environ.get("MILA_BORN_LANG"), os.environ.get("MILA_STICKER_SET")))
open(os.environ["FAKE_LOG"] + ".login", "a").write("%s|%s|%s\\n" % (os.environ.get("OWNER_ID"), bool(os.environ.get("TELEGRAM_BOT_TOKEN")), os.path.exists(os.path.join(os.environ["TG_DIR"], "receiver.pid"))))
while not os.path.exists(os.environ["FAKE_LOG"] + ".owner-signed"): time.sleep(0.2)
os.makedirs(os.environ["MILA_AUTH_DIR"], mode=0o700, exist_ok=True)
fd = os.open(os.path.join(os.environ["MILA_AUTH_DIR"], "oauth_token"), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
os.write(fd, b"saved-login-value\\n"); os.close(fd)
""")
os.chmod(FAKE_CLAUDE, 0o755); os.chmod(FAKE_BUN, 0o755)
ENV = dict(os.environ, HOME=os.path.join(T, "home"), CLAUDE_CONFIG_DIR=CL, MILA_WORK=WORK, MILA_RUN_STATE=ST, MILA_CLAUDE=FAKE_CLAUDE, MILA_BUN=FAKE_BUN,
           MILA_RUN_PAUSE="0.5", FAKE_LOG=os.path.join(T, "fake"), FAKE_KEY=KEY, MILA_AUTH_DIR=os.path.join(T, "auth"), MILA_LOGIN_HELPER=HELPER, TG_DIR=TG)
for k in ("TELEGRAM_STATE_DIR", "MILA_PLUGIN_DIR", "MILA_PLUGIN_REF", "XDG_STATE_HOME", "CLAUDE_CODE_" + "OAUTH_TOKEN", "ANTHROPIC_" + "API_KEY", "ANTHROPIC_" + "AUTH_TOKEN", "TELEGRAM_" + "BOT_TOKEN", "OWNER_ID"): ENV.pop(k, None)


class TGFake(http.server.BaseHTTPRequestHandler):   # a stand-in Telegram for her first words
    calls = []
    def log_message(self, *a): pass
    def do_POST(self):
        raw = self.rfile.read(int(self.headers.get("Content-Length") or 0)); m = self.path.rsplit("/", 1)[-1]
        body = {k: v[0] for k, v in urllib.parse.parse_qs(raw.decode("utf-8", "replace")).items()}
        TGFake.calls.append((m, body))
        res = {"stickers": [{"file_id": "ST-HELLO", "emoji": "👋"}]} if m == "getStickerSet" else {"message_id": 1}
        b = json.dumps({"ok": True, "result": res}).encode(); self.send_response(200); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
    do_GET = do_POST
tgsrv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), TGFake); threading.Thread(target=tgsrv.serve_forever, daemon=True).start()
ENV["MILA_TG_API"] = "http://127.0.0.1:%d" % tgsrv.server_port; ENV["MILA_STICKER_SET"] = "super_set"; ENV["MILA_LANG"] = "en"
json.dump({"bot_username": "ivan_mila_bot", "lang": "uz"}, open(os.path.join(CL, "mila-birth.json"), "w"))   # the page was in Uzbek


def journal(): return read(os.path.join(TG, "inbound", "events.jsonl"))
def pid_alive(pid):
    try: os.kill(int(pid), 0); return True
    except (OSError, ValueError): return False
def start(): return subprocess.Popen([sys.executable, "-B", RUN, "run"], env=ENV, cwd=ELSE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
def status():
    r = subprocess.run([sys.executable, "-B", RUN, "status", "--json"], env=ENV, cwd=ELSE, capture_output=True, text=True)
    return r.returncode, json.loads(r.stdout)
def read(p):
    try: return open(p, encoding="utf-8", errors="replace").read()
    except OSError: return ""
def feed(text):
    """into the service's pipe only: never create session.in here (a file made by the test under umask 022 would be 644 — the
    flake of «журналы 600» when the service had not made its pipe yet)."""
    p = os.path.join(ST, "session.in")
    if not wait(lambda: stat.S_ISFIFO(os.stat(p).st_mode) if os.path.exists(p) else False): raise SystemExit("the service made no pipe " + p)
    fd = os.open(p, os.O_WRONLY)
    with os.fdopen(fd, "w") as f: f.write(text + "\n")


procs = []
try:
    # not born: no token, no owner
    p = start(); out, err = p.communicate(timeout=20)
    chk("дом не рождён (нет ключа бота) — служба не стартует, говорит «run mila birth», код 2", p.returncode == 2 and "mila birth" in err, (p.returncode, err))
    rc, st = status(); chk("…status: не работает, причина названа", rc == 1 and st["running"] is False and "birth" in st["note"], st)
    open(os.path.join(TG, ".env"), "w").write("TELEGRAM_BOT_TOKEN=%s\n" % KEY); os.chmod(os.path.join(TG, ".env"), 0o600)
    json.dump({"dmPolicy": "allowlist", "allowFrom": ["555000"]}, open(os.path.join(TG, "access.json"), "w"))

    # born, but no Claude login yet: the sign-in helper runs INSTEAD of the receiver, the session waits
    p = start(); procs.append(p)
    chk("входа в Claude нет — служба запускает помощника входа для хозяина из access.json, с ключом бота в его окружении", wait(lambda: read(ENV["FAKE_LOG"] + ".login").strip() == "555000|True|False"), read(ENV["FAKE_LOG"] + ".login"))
    rc, st = status()
    chk("…пока хозяин не вошёл: сеанса и приёмника нет, status говорит «жду входа»", st["running"] and st["claude"] == "waiting" and not st["session"] and not os.path.exists(os.path.join(TG, "receiver.pid")) and not os.path.exists(ENV["FAKE_LOG"] + ".argv"), st)
    open(ENV["FAKE_LOG"] + ".owner-signed", "w").close()
    chk("хозяин вошёл — служба поднимает сеанс, приёмник и feeder", wait(lambda: status()[1]["session"] and status()[1]["receiver"] and status()[1]["feeder"]), status()[1])
    argv = read(ENV["FAKE_LOG"] + ".argv").strip().splitlines()
    chk("сеанс — без окна (claude -p, вход потоком), с плагином по имени маркетплейса из манифеста", argv and "-p" in argv[0].split() and "--input-format stream-json" in argv[0] and "plugin:mila-telegram@mila-test-market" in argv[0], argv)
    hl = read(ENV["FAKE_LOG"] + ".helper-env").strip()
    chk("помощник входа запущен как у рождённой: язык страницы рождения (из записи о рождении, не из MILA_LANG) и имя набора стикеров", hl == "1|uz|super_set", hl)
    chk("после входа: отметка «первые слова сказаны» и одна записка сеансу — что уже сказано от её имени, «не здоровайся заново»",
        os.path.isfile(os.path.join(ST, "greeted")) and journal().count('"ritual": "birth"') == 1 and "Aql menda" in journal() and "Do not greet again" in journal(), journal()[-400:])
    chk("…сама служба в этом случае хозяину ничего не шлёт (слова сказал помощник входа)", not TGFake.calls, TGFake.calls)
    chk("сохранённый вход передан сеансу в окружении (и только ему: в журналах его нет)", read(ENV["FAKE_LOG"] + ".auth").strip().splitlines()[0] == "saved-login-in-env" and "saved-login-value" not in "".join(read(os.path.join(ST, f)) for f in os.listdir(ST) if not f.endswith(".in")), read(ENV["FAKE_LOG"] + ".auth"))
    chk("разрешения НЕ отключены: ни --dangerously-skip-permissions, ни режима обхода", "skip-permissions" not in argv[0] and "bypass" not in argv[0], argv)
    rs = os.path.join(ST, "session-settings.json"); allow = json.load(open(rs))["permissions"]["allow"] if os.path.exists(rs) else []
    chk("сеансу передан свой короткий список разрешённого (--settings): инструменты Telegram, запись только в доме Милы, её навыки", "--settings " + rs in argv[0] and "mcp__plugin_mila-telegram_telegram" in allow
        and "Edit(~/work/**)" in allow and "Write(~/work/**)" in allow and oct(os.stat(rs).st_mode & 0o777) == "0o600", (argv, allow))
    rsj = json.load(open(rs)) if os.path.exists(rs) else {}
    chk("…для Bash в списке НЕТ ни одного правила: её скрипты разрешает хук run-allow.py (путь к нему — настоящий, из папки хуков службы)",
        not any(a.startswith("Bash") for a in allow) and rsj.get("hooks", {}).get("PreToolUse", [{}])[0].get("matcher") == "Bash"
        and rsj["hooks"]["PreToolUse"][0]["hooks"][0]["command"] == "python3 -B %s/run-allow.py" % H and os.path.isfile(os.path.join(H, "run-allow.py")), rsj.get("hooks"))
    deny = rsj.get("permissions", {}).get("deny", [])
    chk("…в её доме закрыты на запись .mcp.json, .git и .claude (ими можно подменить её собственные правила)", all(x in deny for x in ("Edit(~/work/.mcp.json)", "Write(~/work/.git/**)", "Edit(~/work/.claude/**)", "Write(~/work/.claude/**)")), deny)
    chk("…читать ей разрешено её дом, её навыки и папку канала (вложения) — НЕ весь диск человека: общего Read, Glob, Grep в списке нет",
        "Read(~/work/**)" in allow and "Read(~/.claude/skills/**)" in allow and "Read(~/.claude/channels/**/inbox/**)" in allow and "Read(~/.claude/channels/**)" not in allow and not any(a in ("Read", "Glob", "Grep", "Read(*)", "Read(**)", "Read(~/**)") for a in allow), allow)
    chk("…в списке нет ни Bash целиком, ни записи куда угодно, ни режима обхода", not any(a in ("Bash", "Bash(*)", "Edit", "Write", "*") for a in allow) and "bypassPermissions" not in open(rs).read() and "defaultMode" not in open(rs).read(), allow)
    json.dump({"permissions": {"allow": ["Bash(git status:*)", "WebFetch"]}}, open(os.path.join(CL, "settings.json"), "w"))
    chk("первый запуск в доме без разговоров — без --continue", "--continue" not in argv[0], argv)
    chk("рабочая папка сеанса — дом Милы, не папка, где набрали команду", read(ENV["FAKE_LOG"] + ".cwd").strip().splitlines()[0] == WORK, read(ENV["FAKE_LOG"] + ".cwd"))
    tgs = read(ENV["FAKE_LOG"] + ".tgs").strip().splitlines()[0]
    chk("у сеанса своя папка моста (…-session) с тем же ключом 600 и ссылками на доступ и карточки приёмника", tgs == TG + "-session" and read(os.path.join(tgs, ".env")) == read(os.path.join(TG, ".env"))
        and oct(os.stat(os.path.join(tgs, ".env")).st_mode & 0o777) == "0o600" and os.readlink(os.path.join(tgs, "access.json")) == os.path.join(TG, "access.json")
        and os.readlink(os.path.join(tgs, "cards.jsonl")) == os.path.join(TG, "cards.jsonl"), (tgs, os.listdir(tgs)))
    bun = read(ENV["FAKE_LOG"] + ".bun").strip()
    chk("приёмник — демоном над настоящей папкой Telegram", bun.startswith("1|%s|" % TG) and bun.endswith("receiver.ts"), bun)
    chk("папка состояния и труба закрыты (700 / 600)", oct(os.stat(ST).st_mode & 0o777) == "0o700" and oct(os.stat(os.path.join(ST, "session.in")).st_mode & 0o777) == "0o600")

    chk("записка о рождении дошла до сеанса через feeder (первый ход)", wait(lambda: status()[1]["turns"] == 1), status()[1])
    feed('{"type":"user","message":{"role":"user","content":"hello"}}')
    chk("строка на вход → законченный ход посчитан (ходов стало 2)", wait(lambda: status()[1]["turns"] == 2), status()[1])
    logs = "".join(read(os.path.join(ST, f)) for f in os.listdir(ST) if f.endswith((".jsonl", ".err", ".log")))
    chk("в журналах ключа бота нет — стоит маска", KEY not in logs and "<bot-token>" in logs and "saw" in logs, logs[-300:])
    def modes():   # a file replaced between listdir and stat is skipped, not a crash
        res = []
        for f in os.listdir(ST):
            try: st = os.lstat(os.path.join(ST, f))
            except FileNotFoundError: continue
            res.append((f, oct(st.st_mode & 0o777), "fifo" if stat.S_ISFIFO(st.st_mode) else "file" if stat.S_ISREG(st.st_mode) else "other"))
        return res
    m_ = modes()
    chk("журналы, pid и очередь 600 — даже при umask 022", all(m == "0o600" for f, m, k in m_ if k in ("file", "fifo")), m_)

    p2 = start(); out2, err2 = p2.communicate(timeout=20)
    chk("вторая служба над тем же домом не стартует (код 3)", p2.returncode == 3 and "already running" in err2, (p2.returncode, err2))

    # the session ends → comes back; a conversation exists now → --continue
    os.makedirs(os.path.join(CL, "projects", "".join(c if c.isalnum() else "-" for c in WORK))); open(os.path.join(CL, "projects", "".join(c if c.isalnum() else "-" for c in WORK), "s.jsonl"), "w").write("{}")
    pid1 = status()[1]; feed("die")
    chk("сеанс завершился — служба подняла его снова", wait(lambda: len(read(ENV["FAKE_LOG"] + ".argv").strip().splitlines()) >= 2 and status()[1]["session"]), status()[1])
    argv = read(ENV["FAKE_LOG"] + ".argv").strip().splitlines()
    chk("…разговор продолжается (--continue), рабочая папка та же", "--continue" in argv[1] and read(ENV["FAKE_LOG"] + ".cwd").strip().splitlines()[1] == WORK, argv)
    chk("…перезапуск посчитан", status()[1]["restarts"] >= 1, status()[1])
    feed("die")   # the continued session died at once → the next start is fresh
    chk("продолженный сеанс умер сразу — следующий запуск без --continue (сломанный разговор не зацикливается)",
        wait(lambda: len(read(ENV["FAKE_LOG"] + ".argv").strip().splitlines()) >= 3) and "--continue" not in read(ENV["FAKE_LOG"] + ".argv").strip().splitlines()[2], read(ENV["FAKE_LOG"] + ".argv"))

    # a receiver that someone else already runs is not doubled
    spid = status()[1]
    p.send_signal(signal.SIGTERM); p.wait(timeout=25)
    rcv = read(os.path.join(TG, "receiver.pid")).strip()
    chk("остановка службы (SIGTERM): сеанс, приёмник и feeder остановлены", p.returncode == 0 and wait(lambda: not pid_alive(rcv), 10) and not status()[1]["running"], (p.returncode, status()[1]))
    other = subprocess.Popen(["sleep", "300"]); procs.append(other); open(os.path.join(TG, "receiver.pid"), "w").write(str(other.pid)); bun_before = read(ENV["FAKE_LOG"] + ".bun").count("\n")
    p = start(); procs.append(p)
    chk("приёмник уже работает у другого хозяина процесса — второй не запускаю", wait(lambda: status()[1]["session"]) and read(ENV["FAKE_LOG"] + ".bun").count("\n") == bun_before and "already running" in read(os.path.join(ST, "run.log")), read(os.path.join(ST, "run.log"))[-300:])
    p.send_signal(signal.SIGTERM); p.wait(timeout=25)

    # signed in on this computer (claude auth status) and no saved login: the helper is not needed
    shutil.rmtree(ENV["MILA_AUTH_DIR"]); open(ENV["FAKE_LOG"] + ".signed", "w").close(); n_login = read(ENV["FAKE_LOG"] + ".login").count("\n"); os.remove(os.path.join(TG, "receiver.pid"))
    p = start(); procs.append(p)
    chk("в настройках человека есть свои разрешающие правила — служба говорит об этом в status и в журнале (они действуют и на неё)",
        wait(lambda: status()[1]["owner_allow"] == 2) and "2 allow rule(s)" in read(os.path.join(ST, "run.log")), status()[1])
    chk("…и второй раз она не здоровается: отметка есть — ни слов, ни второй записки", wait(lambda: status()[1]["session"]) and not TGFake.calls and journal().count('"ritual": "birth"') == 1, (TGFake.calls, journal().count("birth")))
    p.send_signal(signal.SIGTERM); p.wait(timeout=25)
    # a fresh home on a computer that is already signed in: her first words are said by the service itself
    os.remove(os.path.join(ST, "greeted")); os.remove(os.path.join(TG, "inbound", "events.jsonl")); os.remove(os.path.join(TG, "receiver.pid")) if os.path.exists(os.path.join(TG, "receiver.pid")) else None
    p = start(); procs.append(p)
    chk("компьютер уже со входом в Claude: служба сама говорит первые слова — стикер, затем «Я родилась … как вас зовут?» на языке страницы, хозяину",
        wait(lambda: len(TGFake.calls) >= 3) and [m for m, _ in TGFake.calls[:3]] == ["getStickerSet", "sendSticker", "sendMessage"] and TGFake.calls[1][1].get("sticker") == "ST-HELLO"
        and TGFake.calls[2][1].get("chat_id") == "555000" and TGFake.calls[2][1].get("text", "").startswith("Men tug‘ildim! ✨") and "Ismingiz nima?" in TGFake.calls[2][1]["text"], TGFake.calls)
    chk("…в её первых словах нет технических слов", not any(w in TGFake.calls[2][1].get("text", "") for w in ("Paired", "Claude", "token", "session", "terminal")) if len(TGFake.calls) >= 3 else False)
    chk("…отметка и записка сеансу оставлены", wait(lambda: os.path.isfile(os.path.join(ST, "greeted")) and journal().count('"ritual": "birth"') == 1), journal()[-200:])
    chk("вход сделан на этом компьютере (claude auth status) — помощник входа не запускается, сеанс стартует", wait(lambda: status()[1]["session"] and status()[1]["claude"] == "ready") and read(ENV["FAKE_LOG"] + ".login").count("\n") == n_login, status()[1])
    p.send_signal(signal.SIGTERM); p.wait(timeout=25)

    # two copies of the plugin on the machine: the marketplace's own copy (newer by time) and the installed one — the installed wins
    MKT = os.path.join(CL, "plugins", "mila-marketplace", "mila-telegram"); os.makedirs(MKT)
    for d in (MKT,): open(os.path.join(d, "receiver.ts"), "w").write("// market copy"); open(os.path.join(d, "server.ts"), "w").write("// market copy")
    future = time.time() + 3600; os.utime(os.path.join(MKT, "receiver.ts"), (future, future))
    os.remove(os.path.join(TG, "receiver.pid")) if os.path.exists(os.path.join(TG, "receiver.pid")) else None
    p = start(); procs.append(p); wait(lambda: status()[1]["session"])
    chk("две копии плагина (каталог магазина новее по времени и установленная в cache): служба берёт установленную", "plugin %s" % PLUG in read(os.path.join(ST, "run.log")).strip().splitlines()[-1] or any(("plugin %s" % PLUG) in l for l in read(os.path.join(ST, "run.log")).splitlines()[-4:]), read(os.path.join(ST, "run.log"))[-300:])
    p.send_signal(signal.SIGTERM); p.wait(timeout=25)
    OTHER = os.path.join(CL, "plugins", "cache", "mila", "mila-telegram", "0.9.0"); os.makedirs(OTHER)
    open(os.path.join(OTHER, "receiver.ts"), "w").write("// old"); open(os.path.join(OTHER, "server.ts"), "w").write("// old")
    json.dump({"version": 2, "plugins": {"mila-telegram@mila": [{"scope": "user", "installPath": OTHER, "version": "0.9.0"}], "other@x": [{"installPath": MKT}]}}, open(os.path.join(CL, "plugins", "installed_plugins.json"), "w"))
    os.remove(os.path.join(TG, "receiver.pid")) if os.path.exists(os.path.join(TG, "receiver.pid")) else None
    p = start(); procs.append(p); wait(lambda: status()[1]["session"])
    chk("есть запись Claude Code об установке (installed_plugins.json) — берётся путь из неё, даже если рядом есть копии новее", any(("plugin %s" % OTHER) in l for l in read(os.path.join(ST, "run.log")).splitlines()[-4:]), read(os.path.join(ST, "run.log"))[-300:])
    p.send_signal(signal.SIGTERM); p.wait(timeout=25)

    # her sticker set: the default every Mila is born with, a file to use another one, an empty variable to have none
    def _set(extra, hooks_file=None):
        d = tempfile.mkdtemp(dir=T); shutil.copy(RUN, os.path.join(d, "mila-run.py"))
        if hooks_file is not None: open(os.path.join(d, "sticker-set.txt"), "w").write(hooks_file)
        e = dict(ENV); e.pop("MILA_STICKER_SET", None); e.update(extra)
        code = "import importlib.util as u, sys; s = u.spec_from_file_location('m', sys.argv[1]); m = u.module_from_spec(s); s.loader.exec_module(m); print(m.sticker_set())"
        return subprocess.run([sys.executable, "-B", "-c", code, os.path.join(d, "mila-run.py")], env=e, capture_output=True, text=True).stdout.strip()
    chk("набор стикеров: без настроек — набор, с которым рождается каждая Мила", _set({}) == "super_mila" + "_by_milamini_ashot_bot", _set({}))
    chk("…файл sticker-set.txt в папке хуков заменяет набор; строка не вида имени набора — не берётся", _set({}, "my_own_set\n") == "my_own_set" and _set({}, "плохое имя; rm\n").startswith("super_mila"), (_set({}, "my_own_set\n"), _set({}, "плохое имя; rm\n")))
    chk("…пустая переменная MILA_STICKER_SET — без стикера; непустая — она", _set({"MILA_STICKER_SET": ""}) == "" and _set({"MILA_STICKER_SET": "x_set"}) == "x_set")

    # no plugin
    shutil.rmtree(os.path.join(CL, "plugins")); p = start(); out, err = p.communicate(timeout=20)
    chk("плагина Telegram нет — служба говорит, как поставить, код 2", p.returncode == 2 and "/plugin install" in err, (p.returncode, err))
finally:
    for q in procs:
        try: q.kill()
        except Exception: pass
    subprocess.run(["pkill", "-f", "^/bin/bash %s" % FAKE_BUN], capture_output=True); subprocess.run(["pkill", "-f", "^/bin/bash %s" % FAKE_CLAUDE], capture_output=True)
    shutil.rmtree(T, ignore_errors=True)
print("итог %d/%d" % (ok, n)); sys.exit(0 if ok == n else 1)
