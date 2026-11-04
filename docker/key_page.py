#!/usr/bin/env python3
"""key_page.py deepgram|groq — one key, once, through a page instead of the chat: Mila runs it when the owner wants her to hear voice
messages. It prints one line — a one-time link https://<public address>/k/<token> — for Mila to send to the owner, then listens
on $PORT until the key is saved or 10 minutes pass.

The key is checked with the service (Deepgram: GET /v1/projects, Groq: GET /openai/v1/models), saved in ~/work/secrets/<kind>.env (600, folder 700) — the
file the voice script already reads — and the page closes. The token in the link is 32 random characters and works once;
wrong path → 404; 5 attempts in total. Neither the key nor the link token is written to any log.
Without a public address (no RAILWAY_PUBLIC_DOMAIN / MILA_PUBLIC_URL) it says so in one line: then the key goes into the
platform's variables (GROQ_API_KEY). Only stdlib. Exit 0 = saved, 3 = closed without a key, 2 = cannot open a page here."""
import html, http.server, json, os, re, secrets, sys, threading, time, urllib.parse, urllib.request

KINDS = {"deepgram": {"field": "DEEPGRAM_API_KEY", "file": "deepgram.env", "re": r"^[A-Za-z0-9]{32,64}$", "auth": "Token ",
                      "check": "https://api.deepgram.com/v1/projects", "where": "console.deepgram.com",
                      "title": {"en": "Voice: Deepgram key", "ru": "Голос: ключ Deepgram", "uz": "Ovoz: Deepgram kaliti"},
                      "intro": {"en": "So that I can hear your voice messages: open console.deepgram.com, sign up, create an API key and paste it here. New accounts get a free trial credit.",
                                "ru": "Чтобы я слышала ваши голосовые: откройте console.deepgram.com, зарегистрируйтесь, создайте API-ключ и вставьте сюда. Новым аккаунтам даётся бесплатный пробный кредит.",
                                "uz": "Ovozli xabarlaringizni eshitishim uchun: console.deepgram.com ni oching, ro‘yxatdan o‘ting, API kalit yarating va shu yerga qo‘ying. Yangi akkauntlarga bepul sinov krediti beriladi."}},
         "groq": {"field": "GROQ_API_KEY", "file": "groq.env", "re": r"^gsk_[A-Za-z0-9]{20,}$",
                  "check": "https://api.groq.com/openai/v1/models", "where": "console.groq.com/keys", "auth": "Bearer ",
                  "title": {"en": "Voice: Groq key", "ru": "Голос: ключ Groq", "uz": "Ovoz: Groq kaliti"},
                  "intro": {"en": "So that I can hear your voice messages: open console.groq.com/keys, create a key (free) and paste it here.",
                            "ru": "Чтобы я слышала ваши голосовые: откройте console.groq.com/keys, создайте ключ (бесплатно) и вставьте сюда.",
                            "uz": "Ovozli xabarlaringizni eshitishim uchun: console.groq.com/keys ni oching, kalit yarating (bepul) va shu yerga qo‘ying."}}}
TTL = int(os.environ.get("KEY_PAGE_TTL", "600"))
TRIES = 5
SECRETS = os.path.expanduser(os.environ.get("MILA_SECRETS", "~/work/secrets"))
OK = {"en": "✅ Saved. Send me a voice message — I'll hear it.", "ru": "✅ Сохранила. Пришлите голосовое — я услышу.",
      "uz": "✅ Saqladim. Ovozli xabar yuboring — eshitaman."}
BAD = {"en": "The service did not accept this key. Copy it again in full.", "ru": "Сервис не принял этот ключ. Скопируйте его ещё раз целиком.",
       "uz": "Xizmat bu kalitni qabul qilmadi. Uni qayta to‘liq nusxalang."}
GONE = {"en": "This link no longer works. Ask Mila for a new one.", "ru": "Ссылка больше не работает. Попросите у Милы новую.",
        "uz": "Havola endi ishlamaydi. Miladan yangisini so‘rang."}
BTN = {"en": "Save", "ru": "Сохранить", "uz": "Saqlash"}


def lang(h, q=""):
    """The conversation's language (?l= on Mila's link) first, then the browser's, English by default."""
    if q[:2] in OK: return q[:2]
    for part in (h or "").split(","):
        c = part.split(";")[0].strip().lower()[:2]
        if c in OK: return c
    return "en"


def page(body, lg):
    return ("<!doctype html><html lang=%s><head><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>"
            "<meta name=robots content=noindex><title>Mila</title><style>body{font-family:system-ui,sans-serif;max-width:30rem;margin:3rem auto;"
            "padding:0 1.2rem;color:#1d2b2a;background:#f4faf8}.c{background:#fff;border-radius:1rem;padding:1.4rem;box-shadow:0 .4rem 1.4rem #0001}"
            "input{width:100%%;padding:.8rem;font-size:1rem;border:1px solid #bcd;border-radius:.6rem;box-sizing:border-box}"
            "button{margin-top:1rem;padding:.8rem 1.4rem;font-size:1rem;background:#2a9d8f;color:#fff;border:0;border-radius:.6rem}"
            ".e{color:#b3261e}</style></head><body><div class=c>%s</div></body></html>" % (lg, body)).encode()


def check(kind, key):
    try:
        r = urllib.request.Request(os.environ.get("KEY_CHECK_URL") or KINDS[kind]["check"], headers={"Authorization": KINDS[kind]["auth"] + key})
        with urllib.request.urlopen(r, timeout=15) as x:
            return x.status == 200
    except Exception:
        return False   # never echo the key


def save(kind, key):
    os.makedirs(SECRETS, mode=0o700, exist_ok=True); os.chmod(SECRETS, 0o700)
    p = os.path.join(SECRETS, KINDS[kind]["file"]); tmp = "%s.%d.tmp" % (p, os.getpid())
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w") as f: f.write("%s='%s'\n" % (KINDS[kind]["field"], key))
    os.replace(tmp, p)


def serve(kind, port, token):
    st = {"tries": 0, "saved": False, "start": time.time()}
    k = KINDS[kind]; path = "/k/" + token

    class H(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a): pass

        def send(self, code, body):
            self.send_response(code)
            for a, b in (("Content-Type", "text/html; charset=utf-8"), ("Cache-Control", "no-store"), ("Referrer-Policy", "no-referrer"),
                         ("X-Frame-Options", "DENY"), ("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'"),
                         ("Content-Length", str(len(body)))):
                self.send_header(a, b)
            self.end_headers(); self.wfile.write(body)

        def live(self):
            return not st["saved"] and st["tries"] < TRIES and time.time() - st["start"] < TTL

        def form(self, lg, err=""):
            return page("<h2>%s</h2><p>%s</p><form method=post autocomplete=off action='?l=%s'><input name=k type=text required autofocus autocomplete=off "
                        "spellcheck=false data-1p-ignore data-lpignore=true>%s<button type=submit>%s</button></form>"
                        % (html.escape(k["title"][lg]), html.escape(k["intro"][lg]), lg, ("<p class=e>%s</p>" % html.escape(err)) if err else "",
                           BTN[lg]), lg)

        def lg_(self):
            return lang(self.headers.get("Accept-Language"), (urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query).get("l") or [""])[0])

        def do_GET(self):
            lg = self.lg_()
            if self.path.split("?")[0] != path: return self.send(404, page("", lg))
            if not self.live(): return self.send(410, page("<p>%s</p>" % GONE[lg], lg))
            self.send(200, self.form(lg))

        def do_POST(self):
            lg = self.lg_()
            if self.path.split("?")[0] != path: return self.send(404, page("", lg))
            if not self.live(): return self.send(410, page("<p>%s</p>" % GONE[lg], lg))
            n = min(int(self.headers.get("Content-Length") or 0), 2048)
            key = (urllib.parse.parse_qs(self.rfile.read(n).decode("utf-8", "replace")).get("k") or [""])[0].strip()
            if not re.match(k["re"], key):
                return self.send(200, self.form(lg, BAD[lg]))
            st["tries"] += 1
            if not check(kind, key):
                return self.send(200, self.form(lg, BAD[lg]))
            save(kind, key); st["saved"] = True
            self.send(200, page("<h2>%s</h2>" % html.escape(OK[lg]), lg))
            threading.Thread(target=self.server.shutdown, daemon=True).start()

    srv = http.server.ThreadingHTTPServer((os.environ.get("BIND", "0.0.0.0"), port), H)
    threading.Thread(target=lambda: (time.sleep(TTL + 1), srv.shutdown()), daemon=True).start()
    srv.serve_forever(); srv.server_close()
    return st["saved"]


def main(argv):
    kind = argv[1] if len(argv) > 1 else ""
    lq = argv[argv.index("--lang") + 1][:2].lower() if "--lang" in argv and argv.index("--lang") + 1 < len(argv) else ""
    if kind not in KINDS: print("usage: key_page.py " + "|".join(KINDS)); return 2
    base = (os.environ.get("MILA_PUBLIC_URL") or ("https://" + os.environ["RAILWAY_PUBLIC_DOMAIN"] if os.environ.get("RAILWAY_PUBLIC_DOMAIN") else "")).rstrip("/")
    port = os.environ.get("PORT")
    if not base or not port:
        print("key-page: no public address here — put %s into the platform's variables (key from %s)" % (KINDS[kind]["field"], KINDS[kind]["where"]), flush=True)
        return 2
    token = secrets.token_urlsafe(24)
    print("%s/k/%s%s" % (base, token, ("?l=" + lq) if lq in OK else ""), flush=True)   # the one line for Mila to send to the owner; not logged anywhere else
    if os.fork():   # the page lives in the background, Mila's command returns at once
        return 0
    os.setsid()
    dn = os.open(os.devnull, os.O_RDWR)   # let go of the caller's pipes: Mila's command must not wait for the page
    for fd in (0, 1, 2): os.dup2(dn, fd)
    os._exit(0 if serve(kind, int(port), token) else 3)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
