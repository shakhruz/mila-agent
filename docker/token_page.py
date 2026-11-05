#!/usr/bin/env python3
"""One field, once: a fresh Mila Agent container with no bot token opens a tiny page on $PORT, the person pastes the token
from @BotFather, the page checks it with Telegram (getMe), saves it in the volume (600) and closes for good.

Why: on Railway, Hostinger and similar panels the simplest person does not want to look for a «Variables» tab. The service
already has a public address; the page lives there for a few minutes only.

Threat: the address (*.up.railway.app and the like) is not a secret — a stranger could paste HIS bot token first. So:
  · the page lives PAGE_TTL seconds after the container starts (default 30 min), then closes without saving; restart = new window;
  · attempts are limited: 5 per address in 10 minutes, 20 in total — then the page closes;
  · a saved token does not make anyone the owner. The page shows a one-time pairing link t.me/<bot>?start=pair_<code>;
    the owner of this Mila is the person who opens it (the sign-in helper checks the code). A stranger who pasted his own bot
    gets a Mila on HIS bot — nothing of the real owner's;
  · after a save the marker file token_page.done is written and the page never listens again, even after restarts.
Neither the token nor the code is printed to the log. Only stdlib.
Env: PORT (required), MILA_AUTH_DIR (default ~/.mila-auth), TG_API, PAGE_TTL. Exit 0 = saved, 3 = closed without a token."""
import html, http.server, json, os, re, secrets, sys, threading, time, urllib.parse, urllib.request

AUTH = os.path.expanduser(os.environ.get("MILA_AUTH_DIR", "~/.mila-auth"))
API = os.environ.get("TG_API", "https://api.telegram.org")
TTL = int(os.environ.get("PAGE_TTL", "1800"))
TOKEN_RE = re.compile(r"^\d{5,}:[A-Za-z0-9_-]{30,}$")
PAIR_ALPH = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
PER_ADDR, PER_ADDR_WINDOW, TOTAL = 5, 600, 20
DONE = os.path.join(AUTH, "token_page.done")

FACE = ""
try:   # Mila's face, 240 px webp (~4 KB), inside the page as data: — no outside requests
    import base64
    FACE = base64.b64encode(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "mila-face.webp"), "rb").read()).decode()
except OSError:
    pass

CSS = ("body{font-family:system-ui,-apple-system,'Segoe UI',Roboto,sans-serif;max-width:30rem;margin:2.5rem auto;padding:0 1.2rem;"
       "color:#1d2b2a;background:#f4faf8}.c{background:#fff;border-radius:1.2rem;padding:1.6rem;box-shadow:0 .4rem 1.6rem #0001}"
       ".h{display:flex;align-items:center;gap:1rem}.h img{width:84px;height:84px;border-radius:50%}h1{font-size:1.5rem;margin:0}"
       "input:focus{outline:2px solid #2a9d8f;border-color:#2a9d8f}input{width:100%;padding:.8rem;font-size:1rem;border:1px solid #bcd;border-radius:.6rem;box-sizing:border-box;margin-top:.6rem}"
       "button,a.b{display:inline-block;margin-top:1rem;padding:.8rem 1.4rem;font-size:1rem;background:#2a9d8f;color:#fff;border:0;"
       "border-radius:.6rem;text-decoration:none;cursor:pointer}small{color:#6a7b7a}.e{color:#b3261e}")

# Greeting carousel, pure CSS (no script, no outside fonts): big words fade in and out one after another.
HELLOS = ["hello", "hola", "здравствуйте", "salom", "你好", "bonjour", "merhaba", "hallo", "مرحبا", "こんにちは"]
STEP = 2.4   # seconds per word
_n = len(HELLOS); _in, _out = 100 / _n * 0.25, 100 / _n * 0.85
HERO_CSS = (".w{position:relative;height:5.5rem;margin:1rem 0 1.4rem;text-align:center}"
            ".w span{position:absolute;left:0;right:0;font-size:clamp(2rem,10vw,3.6rem);font-weight:600;white-space:nowrap;letter-spacing:-.02em;opacity:0;"
            "background:linear-gradient(90deg,#2a9d8f,#5e60ce);-webkit-background-clip:text;background-clip:text;color:transparent;"
            "animation:hi %.1fs ease-in-out infinite}" % (_n * STEP)
            + "".join(".w span:nth-child(%d){animation-delay:%.1fs}" % (i + 1, i * STEP) for i in range(_n))
            + "@keyframes hi{0%%{opacity:0;transform:translateY(.6rem) scale(.98);filter:blur(4px)}%.1f%%{opacity:1;transform:none;filter:none}"
              "%.1f%%{opacity:1;transform:none;filter:none}%.1f%%{opacity:0;transform:translateY(-.6rem);filter:blur(4px)}100%%{opacity:0}}"
              % (_in, _out, 100 / _n)
            + "@media (prefers-reduced-motion:reduce){.w span{animation:none}.w span:first-child{opacity:1}}")
HERO = "<div class=w aria-hidden=true>%s</div>" % "".join("<span>%s</span>" % h for h in HELLOS)
# Mila wakes up on the «done» screen — the moment she is born (SVG + CSS, no script, no outside request; reduced motion — a smile
# at once). Made by Mila Video, checked by Quality.
WAKE = """<style>
.mila-wake{width:min(320px,70vw);height:auto;display:block;margin:0 auto}
.mila-wake *{transform-box:fill-box;transform-origin:center}
.mw-face{animation:mw-bob 2.8s ease-out both}
.mw-open{animation:mw-open 2.8s ease-in-out both}
.mw-blink{animation:mw-blink 6.5s 3.6s ease-in-out infinite}
.mw-look{animation:mw-look 2.8s ease-in-out both}
.mw-closed{opacity:0;animation:mw-closed 2.8s both}
.mw-mark{animation:mw-mark 2.8s ease-out both}
.mw-glow{opacity:.45;animation:mw-glow 2.8s ease-out both}
.mw-neutral{opacity:0;animation:mw-neutral 2.8s both}
.mw-o{opacity:0;animation:mw-o 2.8s both}
.mw-smile{animation:mw-smile 2.8s ease-out both}
.mw-blush{animation:mw-blush 2.8s ease-out both}
@keyframes mw-bob{0%{transform:translateY(8px)}30%{transform:translateY(0)}84%{transform:translateY(0)}89%{transform:translateY(-6px)}100%{transform:translateY(0)}}
@keyframes mw-open{0%,22%{transform:scaleY(.06)}31%,37%{transform:scaleY(1)}40%{transform:scaleY(.08)}44%,82%{transform:scale(1)}88%{transform:scale(1.16)}100%{transform:scale(1)}}
@keyframes mw-blink{0%,95%,100%{transform:scaleY(1)}97.5%{transform:scaleY(.08)}}
@keyframes mw-look{0%,46%{transform:translateX(0)}53%,61%{transform:translateX(-13px)}69%,76%{transform:translateX(13px)}82%,100%{transform:translateX(0)}}
@keyframes mw-closed{0%,22%{opacity:1}27%,100%{opacity:0}}
@keyframes mw-mark{0%{opacity:.25;transform:scale(.6)}24%{opacity:1;transform:scale(1.25)}34%,100%{opacity:1;transform:scale(1)}}
@keyframes mw-glow{0%{opacity:0}24%{opacity:.9}40%,100%{opacity:.45}}
@keyframes mw-neutral{0%,81%{opacity:1}83%,100%{opacity:0}}
@keyframes mw-o{0%,81%{opacity:0}83%,90%{opacity:1}93%,100%{opacity:0}}
@keyframes mw-smile{0%,90%{opacity:0;transform:scaleX(.6)}96%{opacity:1;transform:scaleX(1.08)}100%{opacity:1;transform:scaleX(1)}}
@keyframes mw-blush{0%,82%{opacity:.35}92%,100%{opacity:1}}
@media (prefers-reduced-motion:reduce){.mila-wake *{animation:none!important}}
</style>
<svg class="mila-wake" viewBox="0 0 512 512" role="img" aria-label="Мила" xmlns="http://www.w3.org/2000/svg">
<defs><filter id="mw-b" x="-1" y="-1" width="3" height="3"><feGaussianBlur stdDeviation="9"/></filter>
<radialGradient id="mw-f" cx=".5" cy=".38" r=".62"><stop offset="0" stop-color="#F7F1E6"/><stop offset=".8" stop-color="#F4EDE0"/><stop offset="1" stop-color="#EBDCC4"/></radialGradient></defs>
<g class="mw-face" stroke="#0B2420" stroke-width="9" stroke-linecap="round" stroke-linejoin="round">
 <path d="M92 262 C88 40 424 40 420 262" fill="none" stroke="#0B2420" stroke-width="30"/>
 <path d="M92 262 C88 40 424 40 420 262" fill="none" stroke="#4FBFAE" stroke-width="14"/>
 <circle cx="256" cy="280" r="168" fill="url(#mw-f)"/>
 <ellipse cx="90" cy="282" rx="36" ry="66" fill="#4FBFAE"/><ellipse cx="422" cy="282" rx="36" ry="66" fill="#4FBFAE"/><path d="M70 300 Q90 336 112 300" fill="none" stroke="#3E9C8E" stroke-width="10" opacity=".7"/><path d="M400 300 Q422 336 444 300" fill="none" stroke="#3E9C8E" stroke-width="10" opacity=".7"/>
 <circle class="mw-glow" cx="256" cy="178" r="22" fill="#2DD9C4" stroke="none" filter="url(#mw-b)"/>
 <circle class="mw-mark" cx="256" cy="178" r="12" fill="#2DD9C4" stroke="none"/>
 <g class="mw-closed" fill="none"><path d="M176 262 Q200 282 224 262"/><path d="M288 262 Q312 282 336 262"/></g>
 <g class="mw-look" stroke="none">
  <g class="mw-open"><g class="mw-blink"><ellipse cx="200" cy="262" rx="28" ry="31" fill="#0B2420"/><circle cx="210" cy="250" r="8" fill="#fff"/></g></g>
  <g class="mw-open"><g class="mw-blink"><ellipse cx="312" cy="262" rx="28" ry="31" fill="#0B2420"/><circle cx="322" cy="250" r="8" fill="#fff"/></g></g>
 </g>
 <g class="mw-blush" stroke="none" fill="#F4A6A6"><ellipse cx="150" cy="322" rx="30" ry="16"/><ellipse cx="362" cy="322" rx="30" ry="16"/></g>
 <path class="mw-neutral" d="M240 330 Q256 334 272 330" fill="none" stroke-width="8"/>
 <ellipse class="mw-o" cx="256" cy="334" rx="13" ry="16" fill="#0B2420" stroke="none"/>
 <path class="mw-smile" d="M222 322 Q256 352 290 322" fill="none" stroke-width="8"/>
</g></svg>"""


L = {
 "en": {"hi": "Hi, I am Mila 👋", "intro": "Paste your bot token from @BotFather and I wake up. One field, shown once.", "ph": "12345…:AAH…",
        "btn": "Wake Mila up", "small": "This page closes after one token or %d minutes.", "fmt": "This does not look like a bot token: digits, a colon, letters.",
        "tg": "Telegram did not recognise this token. Copy it from @BotFather in full.", "ok": "✅ I'm awake!",
        "ok_p": "Last step: open the bot from your own Telegram — this is how I know you are my owner.", "open": "Open @%s",
        "once": "The link works once. This page will not open again.", "closed": "This page is closed", "closed_p": "Restart the service to open it again.",
        "many": "Too many attempts", "many_p": "Please wait 10 minutes."},
 "ru": {"hi": "Привет, я Мила 👋", "intro": "Вставьте токен вашего бота от @BotFather — и я проснусь. Поле одно и появится один раз.", "ph": "12345…:AAH…",
        "btn": "Разбудить Милу", "small": "Страница закроется после одного токена или через %d минут.", "fmt": "Это не похоже на токен бота: цифры, двоеточие, буквы.",
        "tg": "Telegram не узнал этот токен. Скопируйте его из @BotFather целиком.", "ok": "✅ Я проснулась!",
        "ok_p": "Последний шаг: откройте бота со своего Telegram — так я узнаю, что хозяин вы.", "open": "Открыть @%s",
        "once": "Ссылка одноразовая. Эта страница больше не откроется.", "closed": "Страница закрыта", "closed_p": "Перезапустите сервис, чтобы открыть её снова.",
        "many": "Слишком много попыток", "many_p": "Подождите 10 минут."},
 "uz": {"hi": "Salom, men Milaman 👋", "intro": "@BotFather bergan bot tokenini qo‘ying — men uyg‘onaman. Maydon bitta va bir marta chiqadi.", "ph": "12345…:AAH…",
        "btn": "Milani uyg‘otish", "small": "Sahifa bitta tokendan keyin yoki %d daqiqada yopiladi.", "fmt": "Bu bot tokeniga o‘xshamaydi: raqamlar, ikki nuqta, harflar.",
        "tg": "Telegram bu tokenni tanimadi. Uni @BotFather’dan to‘liq nusxalang.", "ok": "✅ Uyg‘ondim!",
        "ok_p": "Oxirgi qadam: botni o‘z Telegramingizdan oching — shunda egam siz ekaningizni bilaman.", "open": "@%s ni ochish",
        "once": "Havola bir martalik. Bu sahifa boshqa ochilmaydi.", "closed": "Sahifa yopilgan", "closed_p": "Qayta ochish uchun xizmatni qayta ishga tushiring.",
        "many": "Urinishlar juda ko‘p", "many_p": "10 daqiqa kuting."},
 "es": {"hi": "Hola, soy Mila 👋", "intro": "Pega el token de tu bot de @BotFather y me despierto. Un solo campo, una sola vez.", "ph": "12345…:AAH…",
        "btn": "Despertar a Mila", "small": "Esta página se cierra tras un token o en %d minutos.", "fmt": "No parece un token de bot: dígitos, dos puntos, letras.",
        "tg": "Telegram no reconoce este token. Cópialo completo de @BotFather.", "ok": "✅ ¡Ya estoy despierta!",
        "ok_p": "Último paso: abre el bot desde tu propio Telegram; así sé que eres mi dueño.", "open": "Abrir @%s",
        "once": "El enlace es de un solo uso. Esta página no volverá a abrirse.", "closed": "Página cerrada", "closed_p": "Reinicia el servicio para abrirla de nuevo.",
        "many": "Demasiados intentos", "many_p": "Espera 10 minutos."},
 "zh": {"hi": "你好，我是 Mila 👋", "intro": "粘贴你从 @BotFather 获得的机器人令牌，我就会醒来。只有一个输入框，只出现一次。", "ph": "12345…:AAH…",
        "btn": "唤醒 Mila", "small": "提交一个令牌后或 %d 分钟后此页面关闭。", "fmt": "这不像机器人令牌：数字、冒号、字母。",
        "tg": "Telegram 无法识别此令牌。请从 @BotFather 完整复制。", "ok": "✅ 我醒了！",
        "ok_p": "最后一步：用你自己的 Telegram 打开机器人——这样我就知道你是我的主人。", "open": "打开 @%s",
        "once": "链接只能使用一次。此页面不会再打开。", "closed": "页面已关闭", "closed_p": "重启服务即可再次打开。",
        "many": "尝试次数过多", "many_p": "请等待 10 分钟。"},
}


def lang(header):
    """Language from the browser (Accept-Language), English by default."""
    for part in (header or "").split(","):
        code = part.split(";")[0].strip().lower()[:2]
        if code in L: return code
    return "en"


def page(body, lg="en"):
    face = "<img alt='' src='data:image/webp;base64,%s'>" % FACE if FACE else ""
    return ("<!doctype html><html lang=%s><head><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>"
            "<meta name=robots content=noindex><title>Mila</title><style>%s%s</style></head><body>%s<div class=c><div class=h>%s<h1>%s</h1></div>%s"
            "</div></body></html>" % (lg, CSS, HERO_CSS, HERO, face, html.escape(L[lg]["hi"]), body)).encode()


def form(lg, err=""):
    t = L[lg]
    return page("<p>%s</p><form method=post autocomplete=off><input name=bt type=text placeholder='%s' required autofocus autocomplete=off autocapitalize=off autocorrect=off spellcheck=false data-1p-ignore data-lpignore=true data-form-type=other>"
                "<button type=submit>%s</button></form>%s<p><small>%s</small></p>"
                % (html.escape(t["intro"]), t["ph"], html.escape(t["btn"]), ("<p class=e>%s</p>" % html.escape(t[err])) if err else "",
                   html.escape(t["small"] % (TTL // 60))), lg)


def note(lg, h, p):
    return page("<h2>%s</h2><p>%s</p>" % (html.escape(L[lg][h]), html.escape(L[lg][p])), lg)


def write_private(name, data):
    os.makedirs(AUTH, mode=0o700, exist_ok=True); os.chmod(AUTH, 0o700)
    p = os.path.join(AUTH, name); tmp = "%s.%d.tmp" % (p, os.getpid())
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w") as f: f.write(data + "\n")
    os.replace(tmp, p)


def get_me(token):
    try:
        with urllib.request.urlopen("%s/bot%s/getMe" % (API, token), timeout=15) as r:
            d = json.loads(r.read().decode())
        return d["result"] if d.get("ok") and (d.get("result") or {}).get("is_bot") else None
    except Exception:
        return None   # never echo the URL — it carries the token


class State:
    def __init__(self):
        self.start, self.hits, self.total, self.saved, self.lock = time.time(), {}, 0, None, threading.Lock()

    def open(self):
        return self.saved is None and time.time() - self.start < TTL and self.total < TOTAL


S = State()


class H(http.server.BaseHTTPRequestHandler):
    server_version = "mila"

    def log_message(self, *a):   # no request log: the form body carries the token
        pass

    def send(self, code, body):
        self.send_response(code)
        for k, v in (("Content-Type", "text/html; charset=utf-8"), ("Cache-Control", "no-store"), ("Referrer-Policy", "no-referrer"),
                     ("X-Frame-Options", "DENY"), ("Content-Security-Policy", "default-src 'none'; img-src data:; style-src 'unsafe-inline'; form-action 'self'"),
                     ("Content-Length", str(len(body)))):
            self.send_header(k, v)
        self.end_headers(); self.wfile.write(body)

    def addr(self):
        xff = [a.strip() for a in (self.headers.get("X-Forwarded-For") or "").split(",") if a.strip()]
        return xff[-1] if xff else self.client_address[0]   # the hop the platform's proxy added, not what the client claims

    def do_GET(self):
        lg = lang(self.headers.get("Accept-Language"))
        if not S.open():
            return self.send(410, note(lg, "closed", "closed_p"))
        self.send(200, form(lg))

    def do_POST(self):
        lg = lang(self.headers.get("Accept-Language"))
        with S.lock:
            if not S.open():
                return self.send(410, note(lg, "closed", "closed_p"))
            a = self.addr(); now = time.time()
            h = [t for t in S.hits.get(a, []) if now - t < PER_ADDR_WINDOW]
            if len(h) >= PER_ADDR:
                return self.send(429, note(lg, "many", "many_p"))
            S.hits[a] = h + [now]
            n = int(self.headers.get("Content-Length") or 0)
            if n > 2048:
                return self.send(413, note(lg, "fmt", "fmt"))
            tok = (urllib.parse.parse_qs(self.rfile.read(n).decode("utf-8", "replace")).get("bt") or [""])[0].strip()
            if not TOKEN_RE.match(tok):
                return self.send(200, form(lg, "fmt"))   # empty or not a token: does not count toward the 20 — a stranger cannot close the page with junk
            S.total += 1
            me = get_me(tok)
            if not me:
                return self.send(200, form(lg, "tg"))
            code = "".join(secrets.choice(PAIR_ALPH) for _ in range(6))
            write_private("bot_token", tok); write_private("pair_code", code); write_private("token_page.done", "1")
            S.saved = me.get("username") or ""
            link = "https://t.me/%s?start=pair_%s" % (urllib.parse.quote(S.saved), code)
            t = L[lg]
            self.send(200, page("<h2>%s</h2><p>%s</p>%s<a class=b href='%s'>%s</a><p><small>%s</small></p>"
                                % (html.escape(t["ok"]), html.escape(t["ok_p"]), WAKE, html.escape(link, quote=True),
                                   html.escape(t["open"] % S.saved), html.escape(t["once"])), lg))
        threading.Thread(target=self.server.shutdown, daemon=True).start()


def main():
    if os.path.lexists(DONE) or os.path.lexists(os.path.join(AUTH, "bot_token")):
        return 0   # once saved — never listen again
    port = int(os.environ["PORT"])
    srv = http.server.ThreadingHTTPServer((os.environ.get("BIND", "0.0.0.0"), port), H)
    threading.Thread(target=lambda: (time.sleep(TTL + 1), srv.shutdown()), daemon=True).start()
    print("token-page: open this service's public address and paste the bot token from @BotFather — one field (closes in %d min)" % (TTL // 60), flush=True)
    srv.serve_forever()
    srv.server_close()
    if S.saved is not None:
        print("token-page: token saved for @%s; the page is closed for good" % S.saved, flush=True)
        return 0
    print("token-page: closed without a token (time or attempts ran out) — restart the service to open it again", flush=True)
    return 3


if __name__ == "__main__":
    sys.exit(main())
