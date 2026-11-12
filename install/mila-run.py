#!/usr/bin/env python3
"""mila-run — Mila works in the background, without a terminal: the service a born Mila runs under (launchd on macOS,
systemd --user on Linux; `mila start | stop | status | logs`).

One process keeps these alive, the same way the container image does:
  1. the receiver  — the plugin's daemon that talks to Telegram and writes the inbound journal (skipped if one already runs);
  2. the feeder    — install/companion-feeder.py: journal → the session's standard input;
  0. the sign-in   — while this home has no Claude login, docker/claude_login.py runs INSTEAD of the receiver: the owner gets
                     Anthropic's own sign-in button in the chat with the new bot; the session starts after the sign-in;
  3. the session   — `claude -p --input-format stream-json` with the mila-telegram plugin, working folder = Mila's home
                     (~/work), never the folder a command was typed in. A session that ends is started again after a pause;
                     the conversation goes on (--continue), a continued session that dies at once starts fresh next time.
There is no window, so nothing is asked on a screen: Claude Code's «trust this folder» dialog does not exist in this mode.
Permissions are NOT switched off (a laptop is not a container). With nobody at a screen to ask, Claude Code refuses every tool
that is not allowed beforehand — so the session gets a short allow-list of its own (mila-run-settings.json, passed with
--settings; it does not touch the owner's other Claude Code sessions): her Telegram tools, reading and writing inside her
home folder ~/work (not its .git, .claude and .mcp.json), reading her skills and the files people send her, web search. Bash has
no rule at all: a hook (run-allow.py) allows only «python3|bash <a script of the kit>», the path resolved, nothing for a shell
to act on. The rest of the person's disk is not hers to read. Rules the owner has put into their own settings.json still
apply to her as well — the start says how many. Everything else is refused and she says so; the guard hooks and the
deny rules of settings.json apply as in a terminal session.

  mila-run.py run                 the service itself (foreground)
  mila-run.py status [--json]     what is alive, since when, how many turns the session has finished
  mila-run.py unborn [--all]      take her off this machine: everything that makes her «born» here — the bot's token and
                                  access list, the birth record, the Claude sign-in made from the chat, the owner's id in
                                  settings.json, her logs — is MOVED to ~/.mila-removed/<date-time>/ (nothing is deleted;
                                  it can be put back by hand). --all moves her home folder ~/work and her conversation
                                  too: the next birth starts from an empty page. The service must be stopped first.
  mila-run.py trust               mark Mila's home folder as trusted in Claude Code's own config (the installer made this
                                  folder, so `mila open` in a terminal is not met by «do you trust this folder?»)
State and logs: ~/.local/state/mila/run (700). Logs are size-capped and pass through a mask: bot tokens and provider keys are
replaced before a line is written. Only stdlib.
Env: MILA_WORK, CLAUDE_CONFIG_DIR, TELEGRAM_STATE_DIR, MILA_RUN_STATE, MILA_AUTH_DIR (default ~/.mila-auth: the login saved by a
sign-in from Telegram, 600), MILA_LOGIN_HELPER, MILA_PLUGIN_DIR, MILA_PLUGIN_REF, MILA_CLAUDE (the claude
binary), MILA_BUN, TELEGRAM_API_ROOT (passed through), MILA_RUN_PAUSE (seconds between session restarts, default 10)."""
import fcntl, json, os, re, signal, subprocess, sys, threading, time

HOME = os.path.expanduser("~")
CL = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(HOME, ".claude")
TG = os.environ.get("TELEGRAM_STATE_DIR") or os.path.join(HOME, ".claude", "channels", "telegram")   # the same rule as the plugin and onboard.py
TGS = TG.rstrip("/") + "-session"            # the session's own bridge folder: same token, EMPTY journal — the feeder delivers
WORK = os.path.expanduser(os.environ.get("MILA_WORK") or os.path.join(HOME, "work"))
ST = os.environ.get("MILA_RUN_STATE") or os.path.join(os.environ.get("XDG_STATE_HOME") or os.path.join(HOME, ".local", "state"), "mila", "run")
HOOKS = os.path.dirname(os.path.abspath(__file__))
AUTH = os.path.expanduser(os.environ.get("MILA_AUTH_DIR") or "~/.mila-auth")
FIFO = os.path.join(ST, "session.in")
RUN_SETTINGS = os.environ.get("MILA_RUN_SETTINGS") or os.path.join(HOOKS, "mila-run-settings.json")
STATE = os.path.join(ST, "state.json")
LOG_MAX = 8 * 1024 * 1024
MASKS = [(re.compile(r"\b\d{6,12}:[A-Za-z0-9_-]{30,50}\b"), "<bot-token>"),
         (re.compile(r"\b(?:sk|pk)[-_][A-Za-z0-9_-]{16,}"), "<key>"),
         (re.compile(r"\bgsk_[A-Za-z0-9]{20,}"), "<key>"),
         (re.compile(r"(?i)\b(authorization|x-api-key)(\"?\s*[:=]\s*\"?)(?:bearer |token )?[A-Za-z0-9._-]{16,}"), r"\1\2<key>")]
stopping = threading.Event()
children = {}          # name → Popen
state_lock = threading.Lock()
state = {"owner_allow": 0, "claude": None, "started": None, "session_pid": None, "session_started": None, "turns": 0, "last_turn": None, "restarts": 0, "receiver": None, "feeder": None, "note": ""}


def mask(s):
    for rx, to in MASKS: s = rx.sub(to, s)
    return s


def log_to(name, text):
    """Append to a capped log, masked. One rotation: <name>.1."""
    p = os.path.join(ST, name)
    try:
        if os.path.getsize(p) > LOG_MAX: os.replace(p, p + ".1")
    except OSError:
        pass
    fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_APPEND | getattr(os, "O_NOFOLLOW", 0), 0o600)
    with os.fdopen(fd, "a", encoding="utf-8", errors="replace") as f: f.write(mask(text))


def say(msg):
    log_to("run.log", "%s %s\n" % (time.strftime("%Y-%m-%dT%H:%M:%S%z"), msg))


def save_state(**kw):
    with state_lock:
        state.update(kw); tmp = STATE + ".tmp"
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f: json.dump(state, f, ensure_ascii=False)
        os.replace(tmp, STATE)


def alive(pid):
    try: os.kill(int(pid), 0); return True
    except (OSError, ValueError, TypeError): return False


def plugin_dir():
    """Where the INSTALLED mila-telegram plugin lies (the folder with receiver.ts) — the copy the session itself loads.
    MILA_PLUGIN_DIR; else the install path Claude Code recorded (plugins/installed_plugins.json); else a search under the
    plugins folder where the installed copy (…/cache/…) wins over a marketplace's own copy — that one can be newer or older
    than what is installed, and a receiver of one version beside a server of another is a quiet breakage."""
    d = os.environ.get("MILA_PLUGIN_DIR")
    if d: return d if os.path.isfile(os.path.join(d, "receiver.ts")) else None
    root = os.path.join(CL, "plugins"); ok = lambda p: isinstance(p, str) and os.path.isfile(os.path.join(p, "receiver.ts")) and os.path.isfile(os.path.join(p, "server.ts"))
    try:
        rec = json.load(open(os.path.join(root, "installed_plugins.json"), encoding="utf-8"))
        plugs = rec.get("plugins") if isinstance(rec, dict) else None
        for key, val in (plugs.items() if isinstance(plugs, dict) else []):
            if not str(key).startswith("mila-telegram@"): continue
            for e in (val if isinstance(val, list) else [val]):
                p = e.get("installPath") if isinstance(e, dict) else None
                if ok(p) and os.path.realpath(p).startswith(os.path.realpath(root) + os.sep): return p
    except (OSError, ValueError):
        pass
    best = None
    for cur, dirs, files in os.walk(root):
        if cur[len(root):].count(os.sep) > 6: dirs[:] = []; continue
        dirs[:] = [x for x in dirs if x != "node_modules"]
        if "mila-telegram" in cur and ok(cur):
            rank = (1 if (os.sep + "cache" + os.sep) in cur else 0, os.path.getmtime(os.path.join(cur, "receiver.ts")))
            if best is None or rank > best[0]: best = (rank, cur)
    return best[1] if best else None


def plugin_ref(pdir):
    """`plugin:mila-telegram@<marketplace>` — the marketplace name from the manifest above the plugin, else «mila»."""
    ref = os.environ.get("MILA_PLUGIN_REF")
    if ref: return ref
    d = pdir or ""
    for _ in range(4):
        d = os.path.dirname(d); mf = os.path.join(d, ".claude-plugin", "marketplace.json")
        try: return "plugin:mila-telegram@%s" % json.load(open(mf, encoding="utf-8"))["name"]
        except (OSError, ValueError, KeyError, TypeError): continue
    return "plugin:mila-telegram@mila"


def prepare():
    """Folders and the session's bridge folder. → problem text or ''."""
    for d in (ST, TGS, os.path.join(TGS, "inbound")):
        os.makedirs(d, mode=0o700, exist_ok=True); os.chmod(d, 0o700)
    env = os.path.join(TG, ".env")
    if not os.path.isfile(env): return "no bot token yet (%s) — Mila is not born: run  mila birth" % env
    if not os.path.isfile(os.path.join(TG, "access.json")): return "no owner yet (access.json) — Mila is not born: run  mila birth"
    if not os.path.isdir(WORK): return "Mila's home folder is missing: %s" % WORK
    data = open(env, "rb").read()                      # the same token for the session's bridge; never printed
    fd = os.open(os.path.join(TGS, ".env.tmp"), os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_NOFOLLOW", 0), 0o600)
    with os.fdopen(fd, "wb") as f: f.write(data)
    os.replace(os.path.join(TGS, ".env.tmp"), os.path.join(TGS, ".env"))
    for n in ("access.json", "receiver.pid", "cards.jsonl", "topics.json"):   # one file for the receiver and the session's tools
        link = os.path.join(TGS, n); target = os.path.join(TG, n)
        if n == "cards.jsonl" and os.path.isfile(link) and not os.path.islink(link):
            with open(target, "ab") as out: out.write(open(link, "rb").read())
            os.remove(link)
        if os.path.islink(link) and os.readlink(link) == target: continue
        try:
            if os.path.islink(link) or os.path.isfile(link): os.remove(link)
            os.symlink(target, link)
        except OSError as e:
            say("link %s: %s" % (n, e))
    return ""


def pump(stream, name, on_line=None):
    """A child's output → a masked, capped log; on_line sees every line (the session's stream-json)."""
    for raw in iter(stream.readline, b""):
        line = raw.decode("utf-8", "replace")
        if on_line:
            try: on_line(line)
            except Exception: pass
        log_to(name, line)
    stream.close()


def keep(name, argv, env, pause, logname, cwd=None):
    """Run a helper forever (receiver, feeder): restart after `pause` seconds; stops when the service stops."""
    while not stopping.is_set():
        try:
            p = subprocess.Popen(argv, env=env, cwd=cwd or WORK, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, start_new_session=True)
        except OSError as e:
            say("%s did not start: %s" % (name, e)); save_state(**{name: None}); stopping.wait(30); continue
        children[name] = p; save_state(**{name: p.pid})
        pump(p.stdout, logname); p.wait(); children.pop(name, None); save_state(**{name: None})
        if not stopping.is_set(): say("%s ended (code %s) — again in %s s" % (name, p.returncode, pause)); stopping.wait(pause)


def onboard_mod():
    sys.path.insert(0, HOOKS)
    if os.environ.get("TELEGRAM_API_ROOT") and not os.environ.get("MILA_TG_API"):
        os.environ["MILA_TG_API"] = os.environ["TELEGRAM_API_ROOT"]      # one Telegram address for the plugin and for her first words
    import onboard
    return onboard


def saved_login():
    """The long-lived Claude login a sign-in from Telegram left in this home (600). → the value or ''. Never printed."""
    try:
        p = os.path.join(AUTH, "oauth_token")
        if os.stat(p).st_mode & 0o077: say("the saved Claude login is open to others (%s) — not using it" % p); return ""
        return open(p, encoding="utf-8").readline().strip()
    except OSError:
        return ""


def claude_ready():
    if os.environ.get("CLAUDE_CODE_OAUTH_TOKEN") or os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"): return True
    if saved_login(): return True
    try: return bool(onboard_mod().claude_status().get("loggedIn"))
    except Exception: return False


def wait_for_claude():
    """No Claude login in this home → the sign-in helper talks to the owner in Telegram until they are signed in.
    → True when a login is there; False when the service is stopping."""
    while not stopping.is_set():
        if claude_ready(): save_state(claude="ready", note=""); return True
        helper = os.environ.get("MILA_LOGIN_HELPER") or next((c for c in (os.path.join(HOOKS, "claude_login.py"), os.path.join(HOOKS, "..", "docker", "claude_login.py")) if os.path.isfile(c)), "")
        try:
            ob = onboard_mod(); tok = ob.saved_token(); owners = ob.owner_ids()
        except Exception as e:
            tok, owners = "", []; say("cannot read the bot token or the owner: %s" % type(e).__name__)
        if not helper or not tok or not owners:
            why = "no Claude login and no way to ask for it in Telegram (%s) — sign in on this computer: claude auth login" % ("the sign-in helper is missing" if not helper else "no bot token or owner")
            save_state(claude="missing", note=why); say(why); stopping.wait(30); continue
        save_state(claude="waiting", note="waiting for the owner to sign in to Claude — the button is in the chat with the bot")
        say("no Claude login — the sign-in helper is talking to the owner in Telegram")
        env = dict(os.environ, TELEGRAM_BOT_TOKEN=tok, OWNER_ID=str(owners[0]), MILA_AUTH_DIR=AUTH, MILA_BORN="1", MILA_BORN_LANG=birth_lang(), MILA_STICKER_SET=sticker_set())
        if os.environ.get("TELEGRAM_API_ROOT"): env["TG_API"] = os.environ["TELEGRAM_API_ROOT"]
        try:
            p = subprocess.Popen([sys.executable, "-B", helper], env=env, cwd=WORK, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, start_new_session=True)
        except OSError as e:
            say("the sign-in helper did not start: %s" % e); stopping.wait(30); continue
        children["login"] = p; pump(p.stdout, "login.log"); p.wait(); children.pop("login", None)
        if p.returncode == 0: greet_and_note(by_helper=True)     # the helper has said «My mind is on … what's your name?»
        if p.returncode != 0 and not stopping.is_set(): say("the sign-in helper stopped (code %s) — again in 10 s" % p.returncode); stopping.wait(10)
    return False


def session_settings():
    """The allow-list of the background session, with her real home folder in it. → path of the rendered file or ''.
    In Claude Code's rules a path under the person's home is «~/…», any other absolute path is «//…»."""
    try: tpl = open(RUN_SETTINGS, encoding="utf-8").read()
    except OSError: return ""
    w = os.path.realpath(WORK); h = os.path.realpath(HOME)
    rule = "~/" + os.path.relpath(w, h) if w.startswith(h + os.sep) else "/" + w
    out = os.path.join(ST, "session-settings.json")
    try:
        text = tpl.replace("{work}", rule).replace("{hooks}", json.dumps(HOOKS)[1:-1])
        json.loads(text)
        fd = os.open(out, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_NOFOLLOW", 0), 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f: f.write(text)
    except (OSError, ValueError) as e:
        say("the session's allow-list is broken (%s) — starting without it: she will be refused every tool" % e); return ""
    return out


def birth_lang():
    """The language of the birth page (the birth record), else MILA_LANG, else English."""
    try: l = str(json.load(open(os.path.join(CL, "mila-birth.json"), encoding="utf-8")).get("lang") or "")
    except (OSError, ValueError, AttributeError): l = ""
    l = l or (os.environ.get("MILA_LANG") or "")[:2].lower()
    return l if l in ("en", "ru", "uz", "zh") else "en"


def sticker_set():
    """The name of her sticker set: MILA_STICKER_SET, else the one line of hooks/sticker-set.txt (shipped with the kit). '' — none."""
    v = os.environ.get("MILA_STICKER_SET")
    if v is not None: return v.strip()
    try: return open(os.path.join(HOOKS, "sticker-set.txt"), encoding="utf-8").readline().strip()
    except OSError: return ""


GREETED = os.path.join(ST, "greeted")


def greet_and_note(by_helper):
    """Once in a home's life. Her first words: said by the sign-in helper (by_helper) or, on a computer that was already
    signed in, said here — a sticker and «I'm born … what's your name?». Then one note into her inbound journal, so that the
    session knows what has already been said from her and does not greet a second time."""
    if os.path.exists(GREETED): return
    sys.path.insert(0, HOOKS); sys.path.insert(0, os.path.join(HOOKS, "..", "docker"))
    try:
        import claude_login as cl
        ob = onboard_mod(); tok = ob.saved_token(); owners = ob.owner_ids()
    except Exception as e:
        say("her first words were not sent: %s" % type(e).__name__); return
    if not tok or not owners: return
    lang = birth_lang(); owner = str(owners[0]); words = cl.BORN_T[lang]
    if by_helper:
        said = words["mind"]
    else:
        said = words["born_ready"]; sset = sticker_set()
        try:
            if sset:
                r = ob.tg(tok, "getStickerSet", {"name": sset}); st = (r.get("result") or {}).get("stickers") or [] if r.get("ok") else []
                if st:
                    pick = next((x for x in st if any(e in str(x.get("emoji") or "") for e in ("👋", "🎉", "✨", "🥳"))), st[0])
                    ob.tg(tok, "sendSticker", {"chat_id": owner, "sticker": pick.get("file_id")})
            if not ob.tg(tok, "sendMessage", {"chat_id": owner, "text": said}).get("ok"):
                say("her first words did not reach Telegram — will try at the next start"); return
        except Exception as e:
            say("her first words were not sent: %s" % type(e).__name__); return
    note = ("[birth] You were born a moment ago on your owner's computer. Your first words have ALREADY been sent to them from you, "
            "in their language (%s): «%s». Do not greet again and do not send anything now. Wait for their answer — it will be their "
            "name — and go on with the first conversation from there, one question at a time, in the same language." % (lang, said.replace("\n", " ")))
    ev = {"ts": int(time.time() * 1000), "method": "notifications/claude/channel",
          "params": {"content": note, "meta": {"chat_id": owner, "chat_type": "private", "message_id": "birth-%d" % int(time.time()), "user": "Birth", "user_id": owner,
                                               "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "ritual": "birth"}}}
    try:
        d = os.path.join(TG, "inbound"); os.makedirs(d, mode=0o700, exist_ok=True)
        fd = os.open(os.path.join(d, "events.jsonl"), os.O_WRONLY | os.O_CREAT | os.O_APPEND | getattr(os, "O_NOFOLLOW", 0), 0o600)
        os.write(fd, (json.dumps(ev, ensure_ascii=False) + "\n").encode()); os.close(fd)
    except OSError as e:
        say("the birth note for the session was not written: %s" % e)
    fd = os.open(GREETED, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600); os.write(fd, (time.strftime("%Y-%m-%dT%H:%M:%S%z") + "\n").encode()); os.close(fd)
    say("her first words are with the owner (%s)" % ("after the sign-in" if by_helper else "this computer was already signed in"))


def owner_allow():
    """How many allow rules the owner's own settings.json carries: they widen this session too (Claude Code merges them)."""
    try: a = json.load(open(os.path.join(CL, "settings.json"), encoding="utf-8")).get("permissions", {}).get("allow") or []
    except (OSError, ValueError, AttributeError): return 0
    return len(a) if isinstance(a, list) else 0


def has_conversation():
    d = os.path.join(CL, "projects", re.sub(r"[^A-Za-z0-9]", "-", os.path.realpath(WORK)))
    try: return any(n.endswith(".jsonl") for n in os.listdir(d))
    except OSError: return False


def on_session_line(line):
    """Count finished turns: the birth page waits for the first one before it says «she is waiting»."""
    if '"type":"result"' not in line.replace(" ", "")[:400]: return
    try: d = json.loads(line)
    except ValueError: return
    if d.get("type") == "result":
        save_state(turns=state["turns"] + 1, last_turn=time.strftime("%Y-%m-%dT%H:%M:%S%z"))


def session_loop(ref):
    claude = os.environ.get("MILA_CLAUDE") or "claude"
    pause0 = float(os.environ.get("MILA_RUN_PAUSE") or 10); pause = pause0; fresh = os.path.join(ST, "session.fresh")
    while not stopping.is_set():
        env = dict(os.environ, TELEGRAM_STATE_DIR=TGS, MILA_TG_STATE=TG)
        tok = saved_login()
        if tok and not (env.get("CLAUDE_CODE_OAUTH_TOKEN") or env.get("ANTHROPIC_API_KEY") or env.get("ANTHROPIC_AUTH_TOKEN")): env["CLAUDE_CODE_OAUTH_TOKEN"] = tok
        try: os.remove(FIFO)
        except OSError: pass
        os.mkfifo(FIFO, 0o600); fifo = os.open(FIFO, os.O_RDWR)        # both ends open here: the reader never sees «end of file»
        cont = has_conversation() and not os.path.exists(fresh)
        argv = [claude, "-p"] + (["--continue"] if cont else []) + ["--input-format", "stream-json", "--output-format", "stream-json", "--verbose",
                                                                  "--dangerously-load-development-channels", ref]
        rs = session_settings()
        if rs: argv += ["--settings", rs]   # what she may do with nobody at a screen to ask
        t0 = time.time()
        try:
            p = subprocess.Popen(argv, env=env, cwd=WORK, stdin=fifo, stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
        except OSError as e:
            os.close(fifo); say("the session did not start: %s" % e); save_state(note="claude did not start: %s" % e); stopping.wait(60); continue
        children["session"] = p
        with open(os.path.join(ST, "session.pid"), "w") as f: f.write(str(p.pid))
        save_state(session_pid=p.pid, session_started=time.strftime("%Y-%m-%dT%H:%M:%S%z"), note="")
        te = threading.Thread(target=pump, args=(p.stderr, "session.err"), daemon=True); te.start()
        pump(p.stdout, "session.jsonl", on_session_line); p.wait(); te.join(5); os.close(fifo); children.pop("session", None)
        try: os.remove(os.path.join(ST, "session.pid"))
        except OSError: pass
        lived = time.time() - t0
        if cont and lived < 30: open(fresh, "w").close()      # a continued conversation that breaks at once must not loop
        else:
            try: os.remove(fresh)
            except OSError: pass
        pause = pause0 if lived > 120 else min(pause * 2, 120)  # a session that keeps dying is restarted more and more slowly
        save_state(session_pid=None, restarts=state["restarts"] + 1)
        if not stopping.is_set(): say("the session ended after %d s (code %s) — again in %d s" % (lived, p.returncode, pause)); stopping.wait(pause)


def stop_all(*_):
    stopping.set()
    for name, p in list(children.items()):
        try: os.killpg(p.pid, signal.SIGTERM)
        except OSError: pass


def run():
    os.makedirs(ST, mode=0o700, exist_ok=True); os.chmod(ST, 0o700)
    lock = os.open(os.path.join(ST, "lock"), os.O_WRONLY | os.O_CREAT, 0o600)
    try: fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        sys.stderr.write("mila-run: already running for this home\n"); return 3
    signal.signal(signal.SIGTERM, stop_all); signal.signal(signal.SIGINT, stop_all)
    with open(os.path.join(ST, "run.pid"), "w") as f: f.write(str(os.getpid()))
    while True:
        why = prepare(); pdir = None if why else plugin_dir()
        if not why and not pdir:
            why = "the Telegram plugin is not installed (no receiver.ts under %s/plugins) — in Claude Code: /plugin install mila-telegram@mila" % CL
        if not why: break
        say(why); save_state(started=time.strftime("%Y-%m-%dT%H:%M:%S%z"), note=why); sys.stderr.write("mila-run: %s\n" % why)
        if os.environ.get("MILA_RUN_SERVICE") != "1": return 2     # typed by hand: say why and leave
        if stopping.wait(30): return 0                               # as a service: wait quietly, do not flap
    save_state(started=time.strftime("%Y-%m-%dT%H:%M:%S%z"), turns=0, restarts=0, note="")
    say("start: home %s, plugin %s" % (WORK, pdir))
    extra = owner_allow()
    if extra: say("note: %d allow rule(s) in %s apply to her as well — she may do what they permit" % (extra, os.path.join(CL, "settings.json")))
    save_state(owner_allow=extra)
    threads = []

    def life():
        if not wait_for_claude(): return      # the receiver starts only after it: the sign-in helper reads the bot's updates itself
        greet_and_note(by_helper=False)       # a computer that was signed in already: her first words are said here, once
        try: rp = open(os.path.join(TG, "receiver.pid")).read().strip()
        except OSError: rp = ""
        mine = []
        if alive(rp):
            say("a receiver is already running (pid %s) — not starting a second one" % rp); save_state(receiver=int(rp))
        else:
            env = dict(os.environ, RECEIVER_DAEMON="1", TELEGRAM_STATE_DIR=TG)
            tv = os.path.join(HOOKS, "transcribe-voice.sh")
            if os.path.isfile(tv): env.setdefault("TELEGRAM_VOICE_TRANSCRIBE_CMD", tv)
            mine.append(threading.Thread(target=keep, args=("receiver", [os.environ.get("MILA_BUN") or "bun", os.path.join(pdir, "receiver.ts")], env, 5, "receiver.log", pdir), daemon=True))
        fenv = dict(os.environ, TELEGRAM_STATE_DIR=TG, COMPANION_STATE=ST, COMPANION_FIFO=FIFO, COMPANION_SESSION_PID=os.path.join(ST, "session.pid"))
        mine.append(threading.Thread(target=keep, args=("feeder", [sys.executable, "-B", os.path.join(HOOKS, "companion-feeder.py")], fenv, 3, "feeder.err"), daemon=True))
        mine.append(threading.Thread(target=session_loop, args=(plugin_ref(pdir),), daemon=True))
        for t in mine: t.start()
        for t in mine: t.join()
    threads.append(threading.Thread(target=life, daemon=True))
    for t in threads: t.start()
    while not stopping.is_set(): stopping.wait(1)
    for t in threads: t.join(12)
    for name, p in list(children.items()):
        try: os.killpg(p.pid, signal.SIGKILL)
        except OSError: pass
    try: os.remove(os.path.join(ST, "run.pid"))
    except OSError: pass
    say("stop"); save_state(session_pid=None, receiver=None, feeder=None, note="stopped")
    return 0


def status(as_json=False):
    try: st = json.load(open(STATE, encoding="utf-8"))
    except (OSError, ValueError): st = {}
    lock_held = False
    try:
        fd = os.open(os.path.join(ST, "lock"), os.O_WRONLY)
        try: fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB); fcntl.flock(fd, fcntl.LOCK_UN)
        except OSError: lock_held = True
        os.close(fd)
    except OSError:
        pass
    try: rp = open(os.path.join(TG, "receiver.pid")).read().strip()
    except OSError: rp = ""
    out = {"running": lock_held, "claude": (st.get("claude") or "unknown") if lock_held else "unknown", "session": bool(lock_held and alive(st.get("session_pid"))), "receiver": alive(rp), "feeder": bool(lock_held and alive(st.get("feeder"))),
           "turns": int(st.get("turns") or 0) if lock_held else 0, "last_turn": st.get("last_turn"), "started": st.get("started") if lock_held else None,
           "restarts": int(st.get("restarts") or 0), "note": st.get("note") or "", "owner_allow": int(st.get("owner_allow") or 0), "home": WORK, "logs": ST}
    if as_json: print(json.dumps(out, ensure_ascii=False))
    else:
        mark = lambda b: "up  " if b else "DOWN"
        print("Mila in the background: %s" % ("running since %s" % out["started"] if out["running"] else "not running"))
        if out["claude"] != "ready" and out["running"]: print("  Claude    %s" % {"waiting": "waiting for the owner to sign in (the button is in the chat with the bot)", "missing": "no login"}.get(out["claude"], out["claude"]))
        print("  session   %s   turns finished: %d%s" % (mark(out["session"]), out["turns"], ("  last: %s" % out["last_turn"]) if out["last_turn"] else ""))
        print("  receiver  %s" % mark(out["receiver"])); print("  feeder    %s" % mark(out["feeder"]))
        if out["note"]: print("  note: %s" % out["note"])
        if out["owner_allow"]: print("  note: %d allow rule(s) of your own settings.json apply to her as well" % out["owner_allow"])
        print("  home: %s   logs: %s" % (WORK, ST))
    return 0 if out["running"] and out["session"] and out["receiver"] else 1


def trust():
    """projects[<home>].hasTrustDialogAccepted = true in Claude Code's config. The file is the owner's: only this one key is
    added, the rest is kept as it is; written atomically, mode kept (600 for a new file)."""
    done = []
    for p in dict.fromkeys([os.path.join(HOME, ".claude.json")] + ([os.path.join(CL, ".claude.json")] if os.environ.get("CLAUDE_CONFIG_DIR") else [])):
        try: d = json.load(open(p, encoding="utf-8"))
        except FileNotFoundError: d = {}
        except (OSError, ValueError):
            print("mila-run: %s is not readable JSON — left alone" % p); continue
        if not isinstance(d, dict): continue
        pr = d.setdefault("projects", {})
        if not isinstance(pr, dict): continue
        key = os.path.realpath(WORK); cur = pr.get(key) if isinstance(pr.get(key), dict) else {}
        if cur.get("hasTrustDialogAccepted") is True: done.append(p); continue
        cur["hasTrustDialogAccepted"] = True; pr[key] = cur
        try: mode = os.stat(p).st_mode & 0o777
        except OSError: mode = 0o600
        tmp = p + ".mila-tmp"; fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_NOFOLLOW", 0), mode)
        with os.fdopen(fd, "w", encoding="utf-8") as f: json.dump(d, f, ensure_ascii=False, indent=2)
        os.replace(tmp, p); done.append(p)
    print("trusted: %s" % os.path.realpath(WORK) if done else "nothing changed")
    return 0 if done else 1


def unborn(everything=False):
    """Move aside what makes her born on this machine. → 0 done, 1 nothing to move, 3 she is still running."""
    try:
        fd = os.open(os.path.join(ST, "lock"), os.O_WRONLY)
        try: fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB); fcntl.flock(fd, fcntl.LOCK_UN)
        except OSError:
            print("Mila is still running — stop her first:  mila stop"); os.close(fd); return 3
        os.close(fd)
    except OSError:
        pass
    dest = os.path.join(HOME, ".mila-removed", time.strftime("%Y%m%d-%H%M%S")); moved = []

    def move(path, name):
        if not (os.path.lexists(path)): return
        os.makedirs(dest, mode=0o700, exist_ok=True); os.chmod(os.path.dirname(dest), 0o700)
        target = os.path.join(dest, name); os.rename(path, target); moved.append(name)
    things = [(TG, "telegram"), (TGS, "telegram-session"), (os.path.join(CL, "mila-birth.json"), "mila-birth.json"), (AUTH, "mila-auth"), (ST, "run")]
    if everything:
        things += [(WORK, "work"), (os.path.join(CL, "projects", re.sub(r"[^A-Za-z0-9]", "-", os.path.realpath(WORK))), "conversation")]
    for path, name in things:
        try: move(path, name)
        except OSError as e: print("could not move %s: %s" % (path, e))
    # the owner's id in settings.json: the launcher reads «born» from it
    sp = os.path.join(CL, "settings.json")
    try:
        d = json.load(open(sp, encoding="utf-8"))
        if isinstance(d, dict) and isinstance(d.get("env"), dict) and "OWNER_ID" in d["env"]:
            os.makedirs(dest, mode=0o700, exist_ok=True)
            with open(os.path.join(dest, "owner-id.txt"), "w", encoding="utf-8") as f: f.write(str(d["env"].pop("OWNER_ID")) + "\n")
            mode = os.stat(sp).st_mode & 0o777; tmp = sp + ".mila-tmp"
            fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_NOFOLLOW", 0), mode)
            with os.fdopen(fd, "w", encoding="utf-8") as f: json.dump(d, f, ensure_ascii=False, indent=2)
            os.replace(tmp, sp); moved.append("owner id (settings.json)")
    except (OSError, ValueError):
        pass
    if not moved:
        print("Nothing to remove: Mila is not born on this machine."); return 1
    print("Mila is taken off this machine. Moved to %s (nothing was deleted): %s" % (dest, ", ".join(moved)))
    print("Her bot itself stays in Telegram — delete it in @BotFather if you do not need it. To be born again:  mila")
    if not everything and os.path.isdir(WORK): print("Her home folder %s is kept (her memory). An empty start:  mila uninstall --all" % WORK)
    return 0


def main(argv):
    cmd = argv[1] if len(argv) > 1 else "status"
    if cmd == "run": return run()
    if cmd == "status": return status("--json" in argv)
    if cmd == "trust": return trust()
    if cmd == "unborn": return unborn("--all" in argv)
    sys.stderr.write("usage: mila-run.py run | status [--json] | trust | unborn [--all]\n"); return 64


if __name__ == "__main__":
    sys.exit(main(sys.argv))
