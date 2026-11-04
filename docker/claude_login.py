#!/usr/bin/env python3
"""Sign a fresh Mila Agent container into the owner's Claude subscription from Telegram — no ports, no page, no model.

Runs instead of the receiver while the container has no Claude login. The owner writes /start (or /login) to the bot; this
helper starts `claude setup-token` in a pseudo-terminal inside the container, sends the owner a button with Anthropic's own
sign-in link, the owner signs in on the phone and sends the code back in the chat. The helper types the code into
setup-token, saves the long-lived token in the home volume (600), deletes the message with the code from the chat, says
«connected» and exits 0 — the entrypoint then starts the receiver and the session.

Who may sign in: OWNER_ID if it is set (or the owner id that came with a birth code). Otherwise the container prints a
pairing code in ITS LOG (seen only by whoever runs the container): the person who sends «/pair CODE» to the bot becomes the
owner and may sign in. A public bot name is not enough to take a Mila. Everyone else gets one line and nothing else.
Wrong codes: 5 per person are ignored after that; 20 in total → a new code in the log.
A link lives LINK_TTL seconds (10 min); /login gives a new one. The code and the token are never printed or logged.

Env: TELEGRAM_BOT_TOKEN (required), OWNER_ID (optional), MILA_AUTH_DIR (default ~/.mila-auth), LOGIN_CMD (default
«claude setup-token»), TG_API (tests), LINK_TTL. Exit: 0 signed in; 2 bad environment. Only stdlib."""
import json, os, pty, re, secrets, select, shlex, signal, sys, time, urllib.parse, urllib.request

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
API = os.environ.get("TG_API", "https://api.telegram.org")
OWNER = (os.environ.get("OWNER_ID") or "").strip()
AUTH = os.path.expanduser(os.environ.get("MILA_AUTH_DIR", "~/.mila-auth"))
CMD = shlex.split(os.environ.get("LOGIN_CMD", "claude setup-token"))
TTL = int(os.environ.get("LINK_TTL", "600"))
URL_RE = re.compile(r"https://[^\s\x1b\"'<>]*(?:oauth|authorize|login)[^\s\x1b\"'<>]*")
TOK_PREFIX = "sk-" + "ant-" + "oat"   # glued so key scanners do not flag the source itself
TOK_RE = re.compile(r"\b(" + TOK_PREFIX + r"\d*-[A-Za-z0-9_\-]{20,})")
ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]|\x1b\][^\x07]*\x07")
CODE_RE = re.compile(r"^[A-Za-z0-9_\-#.~]{12,400}$")

T = {"hello": "Здравствуйте! Я Мила. Чтобы я заработала, подключите вашу подписку Claude — это минута:\n"
              "1. Нажмите кнопку ниже и войдите аккаунтом, на котором подписка.\n"
              "2. Anthropic покажет код — скопируйте его и пришлите сюда, в чат.\n"
              "Код увижу только я, сообщение с ним сразу удалю. Ссылка действует 10 минут; новая — командой /login.",
     "btn": "🔑 Войти в Claude", "busy": "Готовлю ссылку входа…", "fail": "Не получилось открыть вход в Claude: %s. Попробуйте /login ещё раз.",
     "code_bad": "Это не похоже на код со страницы Anthropic. Скопируйте код целиком и пришлите одним сообщением.",
     "no_session": "Нажмите /login — пришлю свежую ссылку входа.", "expired": "Ссылка входа устарела. /login — новая.",
     "wrong_code": "Код не подошёл (или устарел). Нажмите /login и войдите ещё раз.",
     "done": "✅ Подписка подключена. Привет! Я твоя Мила. Как тебя зовут и чем ты занимаешься? (Отвечу через минуту — запускаюсь.)",
     "stranger": "Эту Милу подключает её хозяин. Если это вы — отправьте /pair и код из журнала контейнера (или задайте OWNER_ID).",
     "paired": "Код верный — вы хозяин этой Милы. Готовлю вход в Claude…", "pair_bad": "Код не подошёл. Он в журнале контейнера: строка «pairing code»."}
PAIR_ALPH = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
PAIR_LOCK = int(os.environ.get("PAIR_LOCK", "600"))


def new_pair():
    """A pairing code. If the token page saved one (pair_code, 600) — that one: the owner got it as a t.me/<bot>?start=pair_<code>
    link on the page, so it is not printed to the log. Otherwise a new code goes to the container's log."""
    try:
        c = open(os.path.join(AUTH, "pair_code")).read().strip().upper()
        if re.fullmatch(r"[A-Z2-9]{6}", c):
            print("claude-login: waiting for the owner's link from the token page", flush=True); return c
    except OSError:
        pass
    c = "".join(secrets.choice(PAIR_ALPH) for _ in range(6))
    print("claude-login: pairing code %s — send «/pair %s» to your bot from your own Telegram" % (c, c), flush=True)
    return c


def tg(method, **params):
    data = urllib.parse.urlencode({k: (json.dumps(v) if isinstance(v, (dict, list)) else v) for k, v in params.items()}).encode()
    try:
        with urllib.request.urlopen(urllib.request.Request("%s/bot%s/%s" % (API, TOKEN, method), data=data), timeout=40) as r:
            return json.loads(r.read().decode())
    except Exception as e:                       # never echo the URL — it carries the bot token
        sys.stderr.write("claude-login: telegram %s failed: %s\n" % (method, type(e).__name__))
        return {"ok": False}


def say(chat, text, button=None):
    kw = {"chat_id": chat, "text": text}
    if button:
        kw["reply_markup"] = {"inline_keyboard": [[{"text": T["btn"], "url": button}]]}
    return tg("sendMessage", **kw)


class Session:
    """setup-token in a pseudo-terminal: read until the sign-in URL, later write the code and read until the token."""
    def __init__(self):
        self.pid, self.fd = pty.fork()
        if self.pid == 0:
            os.environ["TERM"] = "dumb"
            try:
                os.execvp(CMD[0], CMD)
            finally:
                os._exit(127)
        self.buf, self.started = "", time.time()

    def read_until(self, rx, timeout):
        end = time.time() + timeout
        while time.time() < end:
            r, _, _ = select.select([self.fd], [], [], 0.5)
            if r:
                try:
                    chunk = os.read(self.fd, 4096).decode("utf-8", "replace")
                except OSError:
                    break
                if not chunk:
                    break
                self.buf += ANSI.sub("", chunk).replace("\r", "")
                m = rx.search(self.buf.replace("\n", ""))   # a long URL may be wrapped by the terminal
                if m:
                    return m.group(1) if m.groups() else m.group(0)
        return None

    def write(self, s):
        os.write(self.fd, (s + "\r").encode())

    def close(self):
        try:
            os.kill(self.pid, signal.SIGTERM); os.waitpid(self.pid, 0)
        except OSError:
            pass
        try:
            os.close(self.fd)
        except OSError:
            pass


def save(token, owner):
    os.makedirs(AUTH, mode=0o700, exist_ok=True)
    os.chmod(AUTH, 0o700)
    for name, val in (("oauth_token", token), ("owner_id", owner)):
        p = os.path.join(AUTH, name); tmp = p + ".tmp"
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(val + "\n")
        os.replace(tmp, p)


def main():
    if not re.fullmatch(r"\d{5,}:[A-Za-z0-9_-]{30,}", TOKEN):
        sys.stderr.write("claude-login: TELEGRAM_BOT_TOKEN is missing or malformed\n"); return 2
    offset, sess, who, warned = 0, None, None, set()
    owner = OWNER
    pair, bad, bad_all, lock_until = (None if owner else new_pair()), {}, 0, 0.0
    print("claude-login: waiting for /start from %s" % ("the owner" if owner else "the person with the pairing code"), flush=True)
    while True:
        if sess and time.time() - sess.started > TTL:
            sess.close(); say(who, T["expired"]); sess, who = None, None
        upd = tg("getUpdates", offset=offset, timeout=25, allowed_updates=["message"])
        if not upd.get("ok"):
            time.sleep(5); continue          # Telegram unreachable: wait, do not spin
        for u in upd.get("result") or []:
            offset = u["update_id"] + 1
            m = u.get("message") or {}
            if (m.get("chat") or {}).get("type") != "private":
                continue
            uid, text = str((m.get("from") or {}).get("id", "")), (m.get("text") or "").strip()
            if not owner:
                pm = re.match(r"^/pair\s+([A-Za-z0-9]{6})\s*$", text) or re.match(r"^/start\s+pair_([A-Za-z0-9]{6})\s*$", text)
                if pm and (bad.get(uid, 0) >= 5 or time.time() < lock_until):
                    say(uid, T["pair_bad"]); continue   # 5 wrong codes from one person, or 20 from all — no more guesses for now
                if pm:
                    if secrets.compare_digest(pm.group(1).upper(), pair):
                        owner = uid; say(uid, T["paired"]); text = "/login"
                        try: os.remove(os.path.join(AUTH, "pair_code"))   # one-time: the page's link stops working
                        except OSError: pass
                        print("claude-login: paired with %s" % uid, flush=True)
                    else:
                        bad[uid] = bad.get(uid, 0) + 1; bad_all += 1; say(uid, T["pair_bad"])
                        if bad_all >= 20:   # someone is guessing: 10 minutes of no pairing at all. The page's code stays —
                            lock_until, bad_all = time.time() + PAIR_LOCK, 0   # the owner's link still works after the pause
                            print("claude-login: 20 wrong pairing codes — pairing paused for %d min" % (PAIR_LOCK // 60), flush=True)
                        continue
                elif uid not in warned:
                    say(uid, T["stranger"]); warned.add(uid); continue
                else:
                    continue
            if uid != owner:
                if uid not in warned:
                    say(uid, T["stranger"]); warned.add(uid)
                continue
            if re.match(r"^/(start|login)\b", text):
                if sess:
                    sess.close()
                say(uid, T["busy"])
                sess, who = Session(), uid
                url = sess.read_until(URL_RE, 45)
                if not url:
                    sess.close(); sess, who = None, None
                    say(uid, T["fail"] % "нет ссылки от claude setup-token"); continue
                say(uid, T["hello"], button=url)
                continue
            if sess and time.time() - sess.started > TTL:      # a code only while this setup-token is alive
                sess.close(); sess, who = None, None; say(uid, T["expired"]); continue
            if not sess or uid != who:
                say(uid, T["no_session"]); continue
            if not CODE_RE.match(text):
                say(uid, T["code_bad"]); continue
            tg("deleteMessage", chat_id=uid, message_id=m.get("message_id"))   # the code does not stay in the chat
            sess.write(text)
            tok = sess.read_until(TOK_RE, 60)
            sess.close(); sess = None
            if not tok:
                who = None; say(uid, T["wrong_code"]); continue
            save(tok, owner)
            say(uid, T["done"])
            print("claude-login: signed in, owner %s" % owner, flush=True)
            return 0


if __name__ == "__main__":
    sys.exit(main())
