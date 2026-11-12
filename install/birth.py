#!/usr/bin/env python3
"""mila birth — the same three steps as `mila onboard`, on a local web page instead of the terminal.

  1. A voice  — the BotFather token is pasted on the page, checked with getMe, saved exactly as onboard saves it (600 / 700).
  2. You      — a 6-character code is shown; the person who sends it to the bot becomes the owner (access.json, OWNER_ID).
  Then a small birth record (no secrets) is written once and Mila is started in the background (`mila start`). She writes to
  her owner first; her mind — the Claude sign-in — is connected from the chat with one button, not on this page (a computer
  that is already signed in to Claude needs nothing). The page says «she is waiting» only after her first words have left;
  then it shows the certificate and the server stops: the page is used once.
  (The sign-in step of the page, `claude auth login`, is still served for a page that asks for it.)

The server listens on 127.0.0.1 only, on a free port, and serves the page only under a one-time random path:
http://mila.localhost:<port>/<token>/   (`.localhost` is loopback in browsers; 127.0.0.1 and localhost work too).
The Host header must be one of those names with the right port, and a POST must carry a matching Origin — otherwise 403.
Every step reuses onboard.py (token check and save, claude status, code, owner), nothing is copied from it.

  mila birth                  start the page and open the browser
  mila birth --no-page [--lang en|ru|uz|zh]
                              a machine with no browser (a server over ssh): the same birth in the terminal, with two links
                              to open on a phone. The first leads to the parent bot — the person creates Mila's bot there,
                              and its key comes here by itself (the page's secret, no code to copy). The second opens the
                              new bot — whoever opens it is the owner. Then she is started in the background and writes
                              first; her mind is connected from the chat, as on a laptop.
Env: MILA_BIRTH_NO_OPEN=1 (do not open the browser), plus everything onboard.py reads
     (TELEGRAM_STATE_DIR, CLAUDE_CONFIG_DIR, MILA_TG_API, MILA_CLAUDE).
"""
import base64
import hmac
import json
import os
import re
import secrets
import subprocess
import sys
import threading
import webbrowser
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import onboard  # noqa: E402
import birth_relay  # noqa: E402

ASSETS = os.path.join(HERE, "birth-assets")
NAMES = ("mila.localhost", "127.0.0.1", "localhost")
MAX_BODY = 4096


def record_path():
    return os.path.join(onboard.CLAUDE_DIR, "mila-birth.json")


def read_record():
    try:
        r = json.load(open(record_path(), encoding="utf-8"))
        return r if isinstance(r, dict) else None
    except (OSError, ValueError):
        return None


def write_record_once(username, first_name, lang=""):
    """The birth record: date and time with the local offset, bot @username, owner's first name when known, the language of
    the birth page (she speaks it from her first word). No secrets. Created with O_EXCL — an existing record is never overwritten."""
    rec = {"born_at": datetime.now().astimezone().isoformat(timespec="seconds"), "bot_username": username}
    if lang in ("en", "ru", "uz", "zh"):
        rec["lang"] = lang
    if first_name:
        rec["owner_first_name"] = first_name
    os.makedirs(onboard.CLAUDE_DIR, exist_ok=True)
    try:
        fd = os.open(record_path(), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        return read_record() or rec
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(rec, f, ensure_ascii=False, indent=2)
        f.write("\n")
    return rec


def parent_bot():
    p = os.environ.get("MILA_BIRTH_PARENT", "").strip().lstrip("@")
    return p if re.fullmatch(r"[A-Za-z0-9_]{3,64}", p) else "mila_gpt_bot"


def page_html():
    html = open(os.path.join(ASSETS, "page.html"), encoding="utf-8").read().replace("__PARENT__", parent_bot()).replace("__BIND__", birth_relay.bind_of(S.secret))
    img = base64.b64encode(open(os.path.join(ASSETS, "portrait.jpg"), "rb").read()).decode()
    return html.replace("__PORTRAIT__", "data:image/jpeg;base64," + img)


# ── state of the three steps (quiet versions of onboard's checks) ──────────
def token_state():
    tok = onboard.saved_token()
    if tok:
        me = onboard.tg(tok, "getMe")
        if me.get("ok"):
            r = me["result"]
            return {"done": True, "username": r.get("username", ""), "name": r.get("first_name", "")}
    return {"done": False}


def claude_state():
    st = onboard.claude_status()
    if st.get("loggedIn"):
        return {"done": True}
    err = str(st.get("error", ""))
    return {"done": False, "error": "claude_missing" if "not found" in err else ("claude_not" if not err else "claude_error")}


def pair_state():
    return {"done": bool(onboard.owner_ids()) and onboard.load_access().get("dmPolicy") == "allowlist"}


def all_done():
    """Born = a bot and an owner. The mind is connected from the chat."""
    return token_state()["done"] and pair_state()["done"]


LANGS = ("en", "ru", "uz", "zh")


def run_state_dir():
    return os.environ.get("MILA_RUN_STATE") or os.path.join(os.environ.get("XDG_STATE_HOME") or os.path.join(os.path.expanduser("~"), ".local", "state"), "mila", "run")


def launcher():
    for c in (os.path.join(os.path.expanduser("~"), ".local", "bin", "mila"), os.path.join(HERE, "mila")):
        if os.path.isfile(c):
            return c
    return ""


def start_background():
    """`mila start`, once, not waiting for it: the page asks /api/awake how she is."""
    with S.lock:
        if S.started:
            return
        S.started = True
    m = launcher()
    if not m:
        return
    try:
        subprocess.Popen(["bash", m, "start"], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    except OSError:
        pass


def api_awake():
    """Has she said her first words? The page promises «she is waiting» only after this is true."""
    d = run_state_dir()
    try:
        st = json.load(open(os.path.join(d, "state.json"), encoding="utf-8"))
    except (OSError, ValueError):
        st = {}
    return 200, {"ok": True, "greeted": os.path.isfile(os.path.join(d, "greeted")), "claude": str(st.get("claude") or ""), "note": str(st.get("note") or "")[:200]}


class Birth:
    """What the server remembers between requests (never the bot token: that is read from onboard's own storage)."""

    def __init__(self):
        self.lock = threading.Lock()
        self.code = None
        self.first_name = ""
        self.login = None
        self.finished = threading.Event()
        self.started = False   # `mila start` was asked for
        # The page's secret: made here, kept in this process only, never sent to the page. Its public fingerprint rides in the
        # link to the parent bot; the bot token issued for that fingerprint is handed out only to whoever shows the secret.
        self.secret = birth_relay.new_secret()
        self.stop = None   # set by main(): shuts the server down


S = Birth()


def api_token(body):
    tok = str(body.get("token", "")).strip()
    if not onboard.TOKEN_RE.match(tok):
        return 400, {"ok": False, "error": "format"}
    me = onboard.tg(tok, "getMe")
    if not me.get("ok"):
        return 200, {"ok": False, "error": "telegram" if me.get("error_code") else "network"}
    onboard.save_token(tok)
    r = me["result"]
    return 200, {"ok": True, "username": r.get("username", ""), "name": r.get("first_name", "")}


CODE_ERRORS = {"format": "code_format", "refused": "code_refused", "no_token": "relay_no_token"}


def api_code(body):
    """The one-tap path: birth code → relay → bot token (+ owner id). The token goes straight to onboard's storage and
    is never returned or printed. Without an owner id from the relay the normal pairing step stays required."""
    r = birth_relay.claim(str(body.get("code", "")))
    if not r["ok"]:
        return 200, {"ok": False, "error": CODE_ERRORS.get(r["error"], "relay")}
    tok = r["bot_token"]
    me = onboard.tg(tok, "getMe")
    if not me.get("ok"):
        return 200, {"ok": False, "error": "telegram" if me.get("error_code") else "network"}
    onboard.save_token(tok)
    paired = False
    if r["owner_id"]:
        onboard.finish_pair(tok, r["owner_id"], greet=False)   # the page's path: her first words come from Mila herself
        paired = True
    res = me["result"]
    return 200, {"ok": True, "username": res.get("username", ""), "name": res.get("first_name", ""), "paired": paired}


def api_collect():
    """No code to copy: the person created the bot through the parent bot, and its token comes by the page's own secret.
    Polled by the page; «wait» — not there yet. The token goes straight to onboard's storage and is never returned or printed.
    The OWNER does not come this way: whoever saw the link first could have created the bot, so «who created it» is not «whose
    Mila this is». The owner is the person who opens the new bot from THIS page — the pairing step, one tap, as before."""
    if token_state()["done"]:
        return 200, {"ok": True, "username": token_state()["username"], "paired": pair_state()["done"]}
    r = birth_relay.collect(S.secret)
    if not r["ok"]:
        return 200, {"ok": False, "error": "wait" if r["error"] == "refused" else "relay"}
    tok = r["bot_token"]
    me = onboard.tg(tok, "getMe")
    if not me.get("ok"):
        return 200, {"ok": False, "error": "telegram" if me.get("error_code") else "network"}
    onboard.save_token(tok)
    res = me["result"]
    return 200, {"ok": True, "username": res.get("username", ""), "name": res.get("first_name", ""), "paired": False}


def api_claude_login():
    with S.lock:
        if S.login is not None and S.login.poll() is None:
            return 200, {"ok": True}
        try:
            S.login = subprocess.Popen([onboard.CLAUDE, "auth", "login"], stdin=subprocess.DEVNULL)
        except FileNotFoundError:
            return 200, {"ok": False, "error": "claude_missing"}
        except OSError:
            return 200, {"ok": False, "error": "srv"}
    return 200, {"ok": True}


def api_pair_start():
    ts = token_state()
    if not ts["done"]:
        return 200, {"ok": False, "error": "telegram"}
    if pair_state()["done"]:
        return 200, {"ok": True, "done": True, "username": ts["username"]}
    with S.lock:
        if not S.code:
            S.code = onboard.new_code()
        return 200, {"ok": True, "code": S.code, "username": ts["username"]}


def api_pair_poll():
    if pair_state()["done"]:
        return 200, {"paired": True}
    tok = onboard.saved_token()
    with S.lock:
        code = S.code
    if not tok or not code:
        return 200, {"paired": False, "error": "no_code"}
    r = onboard.tg(tok, "getUpdates", {"timeout": 0, "allowed_updates": json.dumps(["message"])}, timeout=20)
    if not r.get("ok"):
        desc = str(r.get("description", ""))
        if "webhook" in desc.lower():
            return 200, {"paired": False, "error": "webhook"}
        if r.get("error_code") == 409 or "terminated by other getUpdates" in desc:
            return 200, {"paired": False, "error": "conflict"}
        return 200, {"paired": False, "error": "network"}
    f = onboard.code_from(r.get("result", []), code)
    if not f:
        return 200, {"paired": False, "error": "no_code"}
    onboard.finish_pair(tok, str(f["id"]), greet=False)   # her first words come from Mila herself, not from this page
    with S.lock:
        S.first_name = str(f.get("first_name", ""))[:64]
    return 200, {"paired": True}


def api_born(body=None):
    ts = token_state()
    if not (ts["done"] and pair_state()["done"]):
        return 200, {"ok": False, "error": "srv"}
    lang = str((body or {}).get("lang") or "")
    rec = read_record() or write_record_once(ts["username"], S.first_name, lang if lang in LANGS else "")
    start_background()
    return 200, {"ok": True, "record": rec}


def api_done():
    if not read_record():
        return 200, {"ok": False, "error": "srv"}
    S.finished.set()   # the server stops after this answer has been written (do_POST), not while it is being written
    return 200, {"ok": True}


class Handler(BaseHTTPRequestHandler):
    server_version = "MilaBirth"
    sys_version = ""
    path_token = ""
    port = 0

    def log_message(self, *a):   # no access log: nothing about the request goes to the terminal
        pass

    def _send(self, code, body, ctype):
        data = body if isinstance(body, bytes) else body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        if ctype.startswith("text/html"):
            self.send_header("Content-Security-Policy", "default-src 'none'; img-src data:; style-src 'unsafe-inline'; "
                             "script-src 'unsafe-inline'; connect-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(data)

    def _json(self, code, obj):
        self._send(code, json.dumps(obj, ensure_ascii=False), "application/json; charset=utf-8")

    def _host_ok(self):
        host = self.headers.get("Host", "")
        return host in ["%s:%d" % (n, self.port) for n in NAMES]

    def _route(self):
        """The part of the path after /<token>/, or None."""
        p = self.path.split("?", 1)[0]
        pre = "/" + self.path_token + "/"
        if len(p) >= len(pre) and hmac.compare_digest(p[:len(pre)].encode(), pre.encode()):
            return p[len(pre):]
        return None

    def do_GET(self):
        if not self._host_ok():
            return self._send(403, "forbidden", "text/plain")
        r = self._route()
        if r is None:
            return self._send(404, "not found", "text/plain")
        if r == "":
            return self._send(200, page_html(), "text/html; charset=utf-8")
        if r == "api/status":
            return self._json(200, {"token": token_state(), "claude": claude_state(), "pair": pair_state(), "born": bool(read_record())})
        if r == "api/claude":
            return self._json(200, claude_state())
        if r == "api/pair/poll":
            return self._json(*api_pair_poll())
        if r == "api/awake":
            return self._json(*api_awake())
        return self._send(404, "not found", "text/plain")

    do_HEAD = do_GET

    def do_POST(self):
        if not self._host_ok():
            return self._send(403, "forbidden", "text/plain")
        if self.headers.get("Origin", "") != "http://" + self.headers.get("Host", ""):
            return self._send(403, "forbidden", "text/plain")
        r = self._route()
        if r is None:
            return self._send(404, "not found", "text/plain")
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            n = -1
        if n < 0 or n > MAX_BODY:
            return self._json(413, {"ok": False, "error": "srv"})
        try:
            body = json.loads(self.rfile.read(n).decode("utf-8")) if n else {}
        except ValueError:
            body = None
        if not isinstance(body, dict):
            return self._json(400, {"ok": False, "error": "srv"})
        routes = {"api/token": lambda: api_token(body), "api/code": lambda: api_code(body), "api/claude/login": api_claude_login, "api/pair/start": api_pair_start,
                  "api/born": lambda: api_born(body), "api/done": api_done, "api/collect": api_collect}
        if r not in routes:
            return self._send(404, "not found", "text/plain")
        self._json(*routes[r]())
        if r == "api/done" and S.finished.is_set() and S.stop:
            try:
                self.wfile.flush()
            except OSError:
                pass
            threading.Thread(target=S.stop, daemon=True).start()


NP = {"en": {"one": "1. Open this link on your phone and create a bot for your Mila — two taps:", "wait1": "   Waiting for the bot… (its key comes here by itself; nothing to copy)",
             "got": "   Her voice is ready: @%s", "two": "2. Now open her bot — whoever opens this link becomes her owner:", "wait2": "   Waiting for you in the chat…",
             "paired": "   You are her owner.", "start": "3. Starting her in the background…", "born": "Mila is born ✨ She is writing to you in Telegram: https://t.me/%s",
             "late": "She has not written yet. Check:  mila status   ·   start by hand:  mila start", "linger": "   To keep her running after you log out of this machine:  loginctl enable-linger %s",
             "timeout": "No bot came in 30 minutes. Start again:  mila birth --no-page", "relay": "The birth service did not answer. Try again in a minute:  mila birth --no-page",
             "tg": "Telegram did not accept the new bot's key. Start again:  mila birth --no-page"},
      "ru": {"one": "1. Откройте эту ссылку на телефоне и создайте бота для вашей Милы — два касания:", "wait1": "   Жду бота… (его ключ придёт сюда сам; копировать ничего не нужно)",
             "got": "   Её голос готов: @%s", "two": "2. Теперь откройте её бота — кто откроет эту ссылку, тот и станет её хозяином:", "wait2": "   Жду вас в чате…",
             "paired": "   Вы её хозяин.", "start": "3. Запускаю её в фоне…", "born": "Мила родилась ✨ Она пишет вам в Telegram: https://t.me/%s",
             "late": "Она пока не написала. Проверить:  mila status   ·   запустить руками:  mila start", "linger": "   Чтобы она работала после вашего выхода с этой машины:  loginctl enable-linger %s",
             "timeout": "Бот не пришёл за 30 минут. Начните заново:  mila birth --no-page", "relay": "Служба рождения не ответила. Попробуйте через минуту:  mila birth --no-page",
             "tg": "Telegram не принял ключ нового бота. Начните заново:  mila birth --no-page"}}


def _say(line):
    print(line, flush=True)   # a terminal over ssh, or a pipe: every line at once


def no_page(lang, out=_say, sleep=None, deadline=1800):
    """Birth in the terminal, for a machine with no browser. The same steps and the same storage as the page. → exit code."""
    import time as _t
    sleep = sleep or _t.sleep
    t = NP["ru" if lang == "ru" else "en"]
    if all_done():
        out("Mila is already born: her bot and her owner are set. She lives in the background:  mila status  ·  mila start"); return 0
    t0 = _t.time()
    if not token_state()["done"]:
        out(t["one"]); out("   https://t.me/%s?start=birth_%s_%s" % (parent_bot(), lang, birth_relay.bind_of(S.secret))); out(t["wait1"])
        while True:
            code, r = api_collect()
            if r.get("ok"): break
            if r.get("error") == "telegram": out(t["tg"]); return 1
            if _t.time() - t0 > deadline: out(t["timeout"] if r.get("error") == "wait" else t["relay"]); return 1
            sleep(2 if _t.time() - t0 < 20 else 5)
    out(t["got"] % token_state()["username"])
    if not pair_state()["done"]:
        code, r = api_pair_start()
        out(t["two"]); out("   https://t.me/%s?start=%s" % (r.get("username") or token_state()["username"], r.get("code", ""))); out(t["wait2"])
        while not pair_state()["done"]:
            api_pair_poll()
            if pair_state()["done"]: break
            if _t.time() - t0 > deadline: out(t["timeout"]); return 1
            sleep(2)
    out(t["paired"]); out(t["start"])
    code, r = api_born({"lang": lang})
    if not r.get("ok"): out(t["late"]); return 1
    for _ in range(45):
        if api_awake()[1].get("greeted"): break
        sleep(2)
    greeted = api_awake()[1].get("greeted")
    out((t["born"] % r["record"].get("bot_username", "")) if greeted else t["late"])
    if sys.platform.startswith("linux"):
        try:
            import getpass
            user = getpass.getuser()
            lg = subprocess.run(["loginctl", "show-user", user, "-p", "Linger", "--value"], capture_output=True, text=True, timeout=10).stdout.strip()
            if lg != "yes" and subprocess.run(["loginctl", "enable-linger", user], capture_output=True, timeout=10).returncode != 0:
                out(t["linger"] % user)
        except (OSError, subprocess.SubprocessError):
            pass
    return 0 if greeted else 1


def main():
    if "--no-page" in sys.argv[1:]:
        a = sys.argv[1:]; lang = a[a.index("--lang") + 1] if "--lang" in a and a.index("--lang") + 1 < len(a) else (os.environ.get("MILA_LANG") or "en")[:2].lower()
        return no_page(lang if lang in LANGS else "en")
    if all_done():
        print("Mila is already born: her bot and her owner are set. She lives in the background:  mila status  ·  mila start")
        return 0
    path_token = secrets.token_urlsafe(24)
    handler = type("BoundHandler", (Handler,), {"path_token": path_token})
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    httpd.daemon_threads = True
    handler.port = httpd.server_address[1]
    S.stop = httpd.shutdown
    url = "http://mila.localhost:%d/%s/" % (handler.port, path_token)
    print("Mila is about to be born. Open this page:  %s" % url, flush=True)
    if os.environ.get("MILA_BIRTH_NO_OPEN") != "1":
        try:
            webbrowser.open(url)
        except Exception:
            pass
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped", flush=True)
        return 130
    finally:
        httpd.server_close()
    print("Mila is born. This page has done its work and is closed.", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
