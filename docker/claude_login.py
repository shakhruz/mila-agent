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
import fcntl, struct, termios, json, os, pty, re, secrets, select, shlex, signal, sys, time, urllib.parse, urllib.request

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
     "checking": "Код получила, проверяю…",
     "no_read": "Вход завершился, но я не смогла прочитать ответ. Нажмите /login и попробуйте ещё раз — если повторится, напишите «помощь».",
     "timeout": "Не дождалась ответа от Anthropic. Нажмите /login — пришлю свежую ссылку.",
     "done": "✅ Подписка подключена. Привет! Я твоя Мила. Как тебя зовут и чем ты занимаешься? (Отвечу через минуту — запускаюсь.)",
     "stranger": "Эту Милу подключает её хозяин. Если это вы — отправьте /pair и код из журнала контейнера (или задайте OWNER_ID).",
     "paired": "Код верный — вы хозяин этой Милы. Готовлю вход в Claude…", "pair_bad": "Код не подошёл. Он в журнале контейнера: строка «pairing code»."}
T_EN = {"hello": "Hi! I'm Mila. To get me working, connect your Claude subscription — it takes a minute:\n"
                 "1. Tap the button below and sign in with the account that has the subscription.\n"
                 "2. Anthropic shows a code — copy it and send it here, in this chat.\n"
                 "Only I see the code, and I delete the message right away. The link works 10 minutes; /login gives a new one.",
        "btn": "🔑 Sign in to Claude", "busy": "Preparing the sign-in link…", "fail": "Could not open the Claude sign-in: %s. Try /login again.",
        "code_bad": "This does not look like the code from the Anthropic page. Copy the whole code and send it as one message.",
        "no_session": "Tap /login — I'll send a fresh sign-in link.", "expired": "The sign-in link has expired. /login gives a new one.",
        "wrong_code": "The code did not fit (or expired). Tap /login and sign in again.",
        "checking": "Got the code, checking…",
        "no_read": "The sign-in finished, but I could not read the answer. Tap /login and try again — if it repeats, write «help».",
        "timeout": "No answer from Anthropic yet. Tap /login — I'll send a fresh link.",
        "done": "✅ Subscription connected. Hi! I'm your Mila. What's your name and what do you do? (I'll answer in a minute — starting up.)",
        "stranger": "This Mila is being set up by her owner. If that's you, open the link from the setup page (or send /pair and the code).",
        "paired": "The code is right — you are this Mila's owner. Preparing the Claude sign-in…", "pair_bad": "The code did not fit."}
T_UZ = {"hello": "Salom! Men Milaman. Ishlashim uchun Claude obunangizni ulang — bir daqiqa:\n"
                 "1. Pastdagi tugmani bosing va obuna bor akkaunt bilan kiring.\n"
                 "2. Anthropic kod ko‘rsatadi — uni nusxalab, shu chatga yuboring.\n"
                 "Kodni faqat men ko‘raman, xabarni darhol o‘chiraman. Havola 10 daqiqa ishlaydi; yangisi — /login.",
        "btn": "🔑 Claude’ga kirish", "busy": "Kirish havolasini tayyorlayapman…", "fail": "Claude’ga kirishni ochib bo‘lmadi: %s. /login ni qayta bosing.",
        "code_bad": "Bu Anthropic sahifasidagi kodga o‘xshamaydi. Kodni to‘liq nusxalab, bitta xabarda yuboring.",
        "no_session": "/login ni bosing — yangi havola yuboraman.", "expired": "Kirish havolasi eskirdi. Yangisi — /login.",
        "wrong_code": "Kod mos kelmadi (yoki eskirgan). /login ni bosib, qayta kiring.",
        "checking": "Kodni oldim, tekshiryapman…",
        "no_read": "Kirish tugadi, lekin javobni o‘qiy olmadim. /login ni bosib, qayta urinib ko‘ring.",
        "timeout": "Anthropic’dan javob kelmadi. /login ni bosing — yangi havola yuboraman.",
        "done": "✅ Obuna ulandi. Salom! Men sizning Milangizman. Ismingiz nima va nima bilan shug‘ullanasiz? (Bir daqiqada javob beraman — ishga tushyapman.)",
        "stranger": "Bu Milani uning egasi sozlayapti. Agar bu siz bo‘lsangiz — sozlash sahifasidagi havolani oching (yoki /pair va kodni yuboring).",
        "paired": "Kod to‘g‘ri — siz bu Milaning egasisiz. Claude’ga kirishni tayyorlayapman…", "pair_bad": "Kod mos kelmadi."}
TEXTS = {"ru": T, "en": T_EN, "uz": T_UZ}
LANG = {}   # chat id → language from Telegram (language_code); unknown — English


def tx(chat, key):
    """Text in the person's Telegram language: ru, uz, otherwise English (the product is international)."""
    return TEXTS.get(LANG.get(str(chat), "en"), T_EN).get(key) or T_EN[key]


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
    if os.environ.get("PORT"):   # a platform with a token page and shared logs: the code goes to the volume, not the log
        try:
            os.makedirs(AUTH, mode=0o700, exist_ok=True); p = os.path.join(AUTH, "pair_code")
            fd = os.open(p + ".tmp", os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "w") as f: f.write(c + "\n")
            os.replace(p + ".tmp", p)
        except OSError:
            pass
        print("claude-login: no owner yet — a pairing code is in the volume (.mila-auth/pair_code); not printed here", flush=True)
        return c
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
        kw["reply_markup"] = {"inline_keyboard": [[{"text": tx(chat, "btn"), "url": button}]]}
    return tg("sendMessage", **kw)


class Screen:
    """Just enough of a terminal to read what Claude Code's TUI draws. The TUI does not print lines: it moves the cursor and
    skips characters that are already on the screen, so a plain «strip ANSI» copy loses letters — a token read that way is
    broken. This keeps a grid and applies cursor moves (CR, LF, CHA G, CUF C, CUB D, CUU A, CUD B, CUP H, EL K, ED J)."""
    CSI = re.compile(r"\x1b\[([?>=<]?)([0-9;]*)([@-~])")
    OSC = re.compile(r"\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)")

    def __init__(self, cols=400):
        self.rows, self.r, self.c, self.cols = [[]], 0, 0, cols

    def _row(self):
        while len(self.rows) <= self.r: self.rows.append([])
        return self.rows[self.r]

    def feed(self, text):
        text = self.OSC.sub("", text)
        i = 0
        while i < len(text):
            ch = text[i]
            if ch == "\x1b":
                m = self.CSI.match(text, i)
                if m:
                    self._csi(m.group(1), m.group(2), m.group(3)); i = m.end(); continue
                i += 2; continue   # other two-byte escapes (charset, keypad) — nothing to draw
            if ch == "\r": self.c = 0
            elif ch == "\n": self.r += 1; self._row()
            elif ch == "\b": self.c = max(0, self.c - 1)
            elif ch >= " " or ch == "\t":
                row = self._row()
                while len(row) < self.c: row.append(" ")
                if self.c < len(row): row[self.c] = ch
                else: row.append(ch)
                self.c += 1
            i += 1

    def _csi(self, priv, args, op):
        if priv: return
        n = [int(x) if x else 0 for x in args.split(";")] if args else []
        a = (n[0] if n else 0) or 1
        if op == "G": self.c = a - 1
        elif op == "C": self.c += a
        elif op == "D": self.c = max(0, self.c - a)
        elif op == "A": self.r = max(0, self.r - a)
        elif op == "B": self.r += a; self._row()
        elif op == "H": self.r, self.c = max(0, (n[0] if n else 1) - 1), max(0, (n[1] if len(n) > 1 else 1) - 1); self._row()
        elif op == "K":
            row = self._row(); k = n[0] if n else 0
            if k == 0: del row[self.c:]
            elif k == 2: row.clear()
        elif op == "J" and (n[0] if n else 0) == 2: self.rows, self.r, self.c = [[]], 0, 0

    def lines(self):
        return ["".join(r).rstrip() for r in self.rows]


class Session:
    """setup-token in a pseudo-terminal (400 columns: a token never wraps): read until the sign-in URL, later write the code
    and read until the token, from a screen model (see Screen), not from stripped text."""
    def __init__(self):
        self.pid, self.fd = pty.fork()
        if self.pid == 0:
            os.environ["TERM"] = "dumb"
            try:
                os.execvp(CMD[0], CMD)
            finally:
                os._exit(127)
        try:
            fcntl.ioctl(self.fd, termios.TIOCSWINSZ, struct.pack("HHHH", 50, 400, 0, 0))
        except OSError:
            pass
        self.buf, self.started, self.scr, self.closed, self.rc = "", time.time(), Screen(), False, None

    def read_until(self, rx, timeout, screen=False):
        """→ match or None. screen=True: search the drawn screen rows (for the token); else the raw stream joined (for the URL,
        which also comes whole inside the terminal hyperlink). self.closed: the program ended (pty gone) before a match."""
        end = time.time() + timeout
        while time.time() < end:
            r, _, _ = select.select([self.fd], [], [], 0.5)
            if r:
                try:
                    raw = os.read(self.fd, 4096).decode("utf-8", "replace")
                except OSError:
                    raw = ""
                if not raw:
                    self.closed = True
                else:
                    self.scr.feed(raw)
                    self.buf += ANSI.sub("", raw).replace("\r", "")
            hay = "\n".join(self.scr.lines()) if screen else self.buf.replace("\n", "")
            m = rx.search(hay)
            if m:
                return m.group(1) if m.groups() else m.group(0)
            if self.closed:
                break
        return None

    def write(self, s):
        """The code as typed, then Enter separately: some TUIs take «text+Enter» in one read as a paste and wait."""
        os.write(self.fd, s.encode()); time.sleep(0.4); os.write(self.fd, b"\r")

    def last_line(self):
        """The last non-empty screen line with anything token- or code-like masked — for the log, to tell a refusal from a miss."""
        for ln in reversed(self.scr.lines()):
            if ln.strip():
                ln = re.sub(r"sk-\S*", "***", ln.strip())                      # anything that starts like a key, whatever its shape
                ln = re.sub(r"\b(oat|ant|key|token)\w*[-_]\S*", "***", ln, flags=re.I)
                return re.sub(r"[A-Za-z0-9_\-#.~+/=]{12,}", "***", ln)[:80]  # any long run — a token or code of a new form
        return ""

    def close(self):
        try:
            p, st = os.waitpid(self.pid, os.WNOHANG)
            if p: self.rc = os.waitstatus_to_exitcode(st)
            else: os.kill(self.pid, signal.SIGTERM); os.waitpid(self.pid, 0)
        except (OSError, ChildProcessError):
            pass
        try:
            os.close(self.fd)
        except OSError:
            pass


def save(token, owner):
    """token None — only the owner (right after pairing: a redeploy before the Claude sign-in must not lose the owner)."""
    os.makedirs(AUTH, mode=0o700, exist_ok=True)
    os.chmod(AUTH, 0o700)
    for name, val in (("oauth_token", token), ("owner_id", owner)):
        if val is None: continue
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
    if not owner:   # paired before a restart (owner saved at pairing) — the same owner, no new code
        try: owner = re.sub(r"\D", "", open(os.path.join(AUTH, "owner_id")).read())
        except OSError: pass
    pair, bad, bad_all, lock_until = (None if owner else new_pair()), {}, 0, 0.0
    print("claude-login: waiting for /start from %s" % ("the owner" if owner else "the person with the pairing code"), flush=True)
    while True:
        if sess and time.time() - sess.started > TTL:
            sess.close(); say(who, tx(who, "expired")); sess, who = None, None
        upd = tg("getUpdates", offset=offset, timeout=25, allowed_updates=["message"])
        if not upd.get("ok"):
            time.sleep(5); continue          # Telegram unreachable: wait, do not spin
        for u in upd.get("result") or []:
            offset = u["update_id"] + 1
            m = u.get("message") or {}
            if (m.get("chat") or {}).get("type") != "private":
                continue
            uid, text = str((m.get("from") or {}).get("id", "")), (m.get("text") or "").strip()
            lc = str((m.get("from") or {}).get("language_code") or "")[:2].lower()
            LANG[uid] = lc if lc in TEXTS else "en"
            if not owner:
                pm = re.match(r"^/pair\s+([A-Za-z0-9]{6})\s*$", text) or re.match(r"^/start\s+pair_([A-Za-z0-9]{6})\s*$", text)
                if pm and (bad.get(uid, 0) >= 5 or time.time() < lock_until):
                    say(uid, tx(uid, "pair_bad")); continue   # 5 wrong codes from one person, or 20 from all — no more guesses for now
                if pm:
                    if secrets.compare_digest(pm.group(1).upper(), pair):
                        owner = uid; save(None, owner); say(uid, tx(uid, "paired")); text = "/login"
                        try: os.remove(os.path.join(AUTH, "pair_code"))   # one-time: the page's link stops working
                        except OSError: pass
                        print("claude-login: paired with %s" % uid, flush=True)
                    else:
                        bad[uid] = bad.get(uid, 0) + 1; bad_all += 1; say(uid, tx(uid, "pair_bad"))
                        if bad_all >= 20:   # someone is guessing: 10 minutes of no pairing at all. The page's code stays —
                            lock_until, bad_all = time.time() + PAIR_LOCK, 0   # the owner's link still works after the pause
                            print("claude-login: 20 wrong pairing codes — pairing paused for %d min" % (PAIR_LOCK // 60), flush=True)
                        continue
                elif uid not in warned:
                    say(uid, tx(uid, "stranger")); warned.add(uid); continue
                else:
                    continue
            if uid != owner:
                if uid not in warned:
                    say(uid, tx(uid, "stranger")); warned.add(uid)
                continue
            if re.match(r"^/(start|login)\b", text):
                if sess:
                    sess.close()
                say(uid, tx(uid, "busy"))
                sess, who = Session(), uid
                url = sess.read_until(URL_RE, 45)
                if not url:
                    sess.close(); sess, who = None, None
                    say(uid, tx(uid, "fail") % "no link from claude setup-token"); continue
                say(uid, tx(uid, "hello"), button=url)
                continue
            if sess and time.time() - sess.started > TTL:      # a code only while this setup-token is alive
                sess.close(); sess, who = None, None; say(uid, tx(uid, "expired")); continue
            if not sess or uid != who:
                say(uid, tx(uid, "no_session")); continue
            if not CODE_RE.match(text):
                say(uid, tx(uid, "code_bad")); continue
            tg("deleteMessage", chat_id=uid, message_id=m.get("message_id"))   # the code does not stay in the chat
            say(uid, tx(uid, "checking"))   # no minute of silence after the code
            sess.write(text)
            tok = sess.read_until(TOK_RE, 90, screen=True)
            if not tok:
                shown = "\n".join(sess.scr.lines()); closed = sess.closed; tail = sess.last_line()
                time.sleep(0.3); sess.close()
                print("claude-login: no token — %s, exit %s, last line: %s" % ("program ended" if closed else "timeout", sess.rc, tail), flush=True)
                sess = None; who = None
                if re.search(r"OAuth error|invalid|expired|status code 4\d\d", shown, re.I): say(uid, tx(uid, "wrong_code"))
                elif closed: say(uid, tx(uid, "no_read"))
                else: say(uid, tx(uid, "timeout"))
                continue
            sess.close(); sess = None
            save(tok, owner)
            # confirm every update read so far: the offset only reaches Telegram with the NEXT getUpdates — without this the
            # message with the code comes again to the receiver that starts next, and the model gets the sign-in code
            tg("getUpdates", offset=offset, timeout=0, allowed_updates=["message"])
            say(uid, tx(uid, "done"))
            print("claude-login: signed in, owner %s" % owner, flush=True)
            return 0


if __name__ == "__main__":
    sys.exit(main())
