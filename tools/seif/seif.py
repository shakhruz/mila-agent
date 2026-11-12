#!/usr/bin/env python3
"""Сейф Милы (задача №1 владельца 20.10, «Да, делаем сейф»): одноразовая ссылка, по которой ВЛАДЕЛЕЦ БИЗНЕСА сам вводит
пароли, ключи и карты для своей Милы. Значения идут прямо в закрытый файл её дома — мимо чата, почты и Милы Админ.
  seif.py link <slug> <ПОЛЕ>[,<ПОЛЕ>…] [--name acme] [--to <tg_id>] [--ttl 30]   → ссылка (одна на раз, живёт 30 мин)
  seif.py serve [--port 7693]                                                       → страница сейфа на 127.0.0.1 (Caddy: /v/<token>/)
  seif.py own <ПОЛЕ>[,<ПОЛЕ>…] [--name keys] [--ttl 10]                               → «свой Сейф» Милы на машине владельца (127.0.0.1, одна ссылка)
  seif.py forget <slug> <файл> <ПОЛЕ>[,<ПОЛЕ>…]                                       → стереть поля, когда дело закончено (журнал без значений)
Запись: $SEIF_HOMES/<slug>/home/work/secrets/<name>.env (папка 700, файл 600, хозяин SEIF_UID), прежние ключи файла сохраняются.
Настройка — только окружением: SEIF_BASE (адрес ссылок, обязателен), SEIF_HOMES (папка домов Мил, обязательна), SEIF_DIR, SEIF_UID.
Журнал SEIF_DIR/journal.jsonl: кто (tg из --to), когда, slug, файл, какие поля — БЕЗ значений. Компаньону — записка в его
work/inbox/senior.jsonl «в сейфе появились: …». Токен хранится только хешем; GET не тратит ссылку (превью Telegram открывает GET),
тратит только «Сохранить» (POST). Значения нигде не печатаются и не логируются. Только stdlib.
Язык страницы (31.10, «Мила международная»): ?lang= → язык ссылки (--lang или "lang" из work/owner.json дома) → Accept-Language → en.
Строки — locales/<код>.json рядом (SEIF_LOCALES), новый язык = один файл; недостающая строка — из en.json."""
import hashlib, html, json, os, re, secrets, stat, sys, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mila_i18n
import mila_style   # единый вид страниц Милы (копия install/mila_style.py)

SEIF_DIR = os.path.expanduser(os.environ.get("SEIF_DIR", "~/.local/share/mila-seif"))
HOMES = os.environ.get("SEIF_HOMES", "")
SELF_HOME = os.environ.get("SEIF_HOME", "")   # «свой Сейф»: один дом (Мила владельца на его машине), slug — self
BASE = os.environ.get("SEIF_BASE", "")
UID = int(os.environ.get("SEIF_UID", str(os.getuid())))
LOC = mila_i18n.load(os.environ.get("SEIF_LOCALES") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "locales"))
SECRETISH = re.compile(r"PASS|SECRET|TOKEN|KEY|CARD_NUMBER|PIN", re.I)
NAME_RE, FIELD_RE, SLUG_RE = re.compile(r"^[a-z0-9_-]{1,40}$"), re.compile(r"^[A-Z][A-Z0-9_]{1,40}$"), re.compile(r"^[a-z0-9_-]{2,40}$")


def now_iso():
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def h(tok):
    return hashlib.sha256(tok.encode()).hexdigest()


def tok_path(tok):
    return os.path.join(SEIF_DIR, "tokens", h(tok) + ".json")


def wfile(path, data, mode=0o600):
    os.makedirs(os.path.dirname(path), mode=0o700, exist_ok=True)
    if os.path.lexists(path + ".tmp"):   # подложенный .tmp (симлинк) — убрать, не идти по нему
        os.unlink(path + ".tmp")
    fd = os.open(path + ".tmp", os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(data)
    os.replace(path + ".tmp", path)


def chown(path):
    try:
        os.chown(path, UID, UID, follow_symlinks=False)
    except OSError:
        pass


def mkdir_owned(base, *parts, mode=0o700):
    """Создать base/parts… по шагу и каждой НОВОЙ папке отдать хозяина (SEIF_UID): сервис идёт от root, иначе work/inbox
    и work/secrets остаются root — компаньон не может в них писать (нашёл canary 20.10).
    31.10: сервис идёт от root, а дом пишет Мила — ни одна папка пути не симлинк, путь внутри дома, иначе OSError (ничего не пишем)."""
    p = base = os.path.realpath(base)
    for part in parts:
        p = os.path.join(p, part)
        if os.path.islink(p):
            raise OSError("seif: %s — симлинк" % part)
        if not os.path.exists(p):
            os.mkdir(p, mode)
            chown(p)
        elif not os.path.isdir(p):
            raise OSError("seif: %s — не папка" % part)
    if os.path.commonpath([os.path.realpath(p), base]) != base:
        raise OSError("seif: путь вне дома")
    return p


def journal(row):
    p = os.path.join(SEIF_DIR, "journal.jsonl"); os.makedirs(SEIF_DIR, mode=0o700, exist_ok=True)
    fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    with os.fdopen(fd, "a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": now_iso(), **row}, ensure_ascii=False) + "\n")


def luhn(d):
    t = 0
    for i, ch in enumerate(reversed(d)):
        x = int(ch)
        if i % 2:
            x = x * 2 - 9 if x > 4 else x * 2
        t += x
    return t % 10 == 0


def check_value(field, v):
    """→ (значение, ошибка). Карта: 13–19 цифр с Луной; срок ММ/ГГ → ММГГ. Остальное — одна строка до 512 знаков."""
    v = (v or "").strip()
    if not v:
        return None, "seif.err.empty"
    if "\n" in v or "\r" in v or len(v) > 512:
        return None, "seif.err.line"
    if field == "CARD_NUMBER":
        d = re.sub(r"[ -]", "", v)
        if not d.isdigit() or not 13 <= len(d) <= 19 or not luhn(d):
            return None, "seif.err.card"
        return d, None
    if field == "CARD_EXPIRY":
        m = re.fullmatch(r"(0[1-9]|1[0-2])\s*[/.\-]?\s*(\d{2})", v)
        if not m:
            return None, "seif.err.expiry"
        return m.group(1) + m.group(2), None
    return v, None


def env_quote(v):
    return "'" + v.replace("'", "'\\''") + "'"


def read_env(path):
    out = {}
    try:
        with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), encoding="utf-8") as f:   # симлинк — ELOOP, FIFO — не ждём
            if not stat.S_ISREG(os.fstat(f.fileno()).st_mode):
                raise OSError("seif: .env — не обычный файл")
            for ln in f:
                m = re.match(r"^([A-Z][A-Z0-9_]*)=(.*)$", ln.rstrip("\n"))
                if m:
                    v = m.group(2)
                    if len(v) >= 2 and v[0] == v[-1] == "'":
                        v = v[1:-1].replace("'\\''", "'")
                    out[m.group(1)] = v
    except FileNotFoundError:
        pass
    return out


def home_of(slug):
    """Дом Милы: во флоте — SEIF_HOMES/<slug>/home; у Милы владельца (SEIF_HOME) — её дом под slug «self»."""
    return SELF_HOME if SELF_HOME and slug == "self" else os.path.join(HOMES, slug, "home")


def need_env():
    miss = [k for k, v in (("SEIF_BASE", BASE), ("SEIF_HOMES или SEIF_HOME", HOMES or SELF_HOME)) if not v]
    if miss:
        sys.exit("ERROR: задайте окружение " + ", ".join(miss) + " (адрес ссылок и папку домов Мил)")


def owner_lang(slug):
    """"lang" из work/owner.json дома Милы — только внутри дома, без симлинков, до 4 КБ, код из словарей (mila_i18n.owner_lang)."""
    return mila_i18n.owner_lang(LOC, home_of(slug))


def cmd_link(a):
    need_env()
    slug, fields = a[0], [f.strip() for f in a[1].split(",") if f.strip()]
    opt = lambda k, d=None: a[a.index(k) + 1] if k in a else d
    name, to, ttl, lang = opt("--name", slug), opt("--to", ""), float(opt("--ttl", "30")), opt("--lang")
    if not SLUG_RE.match(slug) or not NAME_RE.match(name) or not fields or not all(FIELD_RE.match(f) for f in fields):
        sys.exit("ERROR: slug a-z0-9_- ; поля — ЗАГЛАВНЫЕ_С_ПОДЧЁРКИВАНИЕМ; name a-z0-9_-")
    if not os.path.isdir(home_of(slug)):
        sys.exit("ERROR: нет дома %s" % slug)
    if lang is not None and not mila_i18n.norm(LOC, lang):
        sys.exit("ERROR: --lang — один из: %s" % ", ".join(sorted(LOC)))
    lang = mila_i18n.norm(LOC, lang) if lang else owner_lang(slug)
    tok = secrets.token_urlsafe(24)
    rec = {"slug": slug, "name": name, "fields": fields, "to": str(to), "exp": time.time() + ttl * 60, "made": now_iso(), "ttl": ttl}
    if lang:
        rec["lang"] = lang
    wfile(tok_path(tok), json.dumps(rec, ensure_ascii=False))
    journal({"ev": "link", "slug": slug, "name": name, "fields": fields, "to": str(to), "ttl_min": ttl, "lang": lang or ""})
    out = {"ok": True, "url": BASE + tok + "/" + ("?lang=" + lang if lang else ""), "expires_min": ttl, "fields": fields, "lang": lang or mila_i18n.FALLBACK}
    print(json.dumps(out, ensure_ascii=False), flush=True); return out, tok


def cmd_own(a, ready=None):
    """«Свой Сейф» (С1): Мила владельца на его машине, без службы и без администратора. Страница на 127.0.0.1 на случайном порту
    ровно на одну ссылку: сохранили — страница закрывается; не сохранили за --ttl минут (10) — тоже. Ключ — в ~/work/secrets/<имя>.env.
    Ссылка открывается только на этой же машине (127.0.0.1) — с телефона нельзя; так и задумано: наружу ничего не открываем.
      seif.py own <ПОЛЕ>[,<ПОЛЕ>…] [--name keys] [--ttl 10] [--lang ru]"""
    global BASE, SELF_HOME
    SELF_HOME = SELF_HOME or os.path.expanduser("~")
    opt = lambda k, d=None: a[a.index(k) + 1] if k in a else d
    ttl = min(float(opt("--ttl", "10")), 30)
    srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
    H.own_port = srv.server_address[1]
    BASE = "http://127.0.0.1:%d/v/" % srv.server_address[1]
    args = ["self", a[0], "--name", opt("--name", "keys"), "--ttl", str(ttl)] + (["--lang", opt("--lang")] if opt("--lang") else [])
    out, tok = cmd_link(args)
    if ready: ready(out)
    import threading
    t = threading.Thread(target=srv.serve_forever, daemon=True); t.start()
    end = time.time() + ttl * 60
    while time.time() < end and os.path.exists(tok_path(tok)): time.sleep(0.5)
    srv.shutdown(); srv.server_close()
    saved = not os.path.exists(tok_path(tok))
    if not saved:
        try: os.remove(tok_path(tok))
        except OSError: pass
    journal({"ev": "own-closed", "saved": saved})
    try: print(json.dumps({"ok": saved, "closed": True, "why": "" if saved else "срок вышел — ничего не сохранено"}, ensure_ascii=False), flush=True)
    except (BrokenPipeError, OSError): pass   # own_safe.py reads only the first line and lets go of the pipe
    return saved


def cmd_forget(a):
    """Дело закончено — поля из файла сейфа убираются. Путь — те же проверки, что у записи (без симлинков, хозяин дома); в журнал —
    что стёрли и когда, без значений. Файла или поля нет — так и говорю, ничего не создаю."""
    need_env()
    slug, name, fields = a[0], a[1], [x for x in a[2].split(",") if x]
    if not SLUG_RE.match(slug) or not NAME_RE.match(name) or not fields or not all(FIELD_RE.match(f) for f in fields):
        sys.exit("seif forget: slug, имя файла или поля в неверном виде")
    home = home_of(slug)
    try:
        sdir = mkdir_owned(home, "work", "secrets"); envp = os.path.join(sdir, name + ".env"); cur = read_env(envp)
    except OSError:
        journal({"ev": "refused", "slug": slug, "why": "path"}); sys.exit("seif forget: путь не прошёл проверку — ничего не трогаю")
    gone = sorted(f for f in fields if f in cur)
    if gone:
        for f in gone: cur.pop(f)
        wfile(envp, "".join("%s=%s\n" % (k, env_quote(v)) for k, v in cur.items())); chown(envp)
    journal({"ev": "forget", "slug": slug, "file": "work/secrets/%s.env" % name, "fields": gone, "missing": sorted(set(fields) - set(gone))})
    print(json.dumps({"ok": True, "forgot": gone, "missing": sorted(set(fields) - set(gone))}, ensure_ascii=False))


def load_tok(tok):
    if not re.fullmatch(r"[A-Za-z0-9_-]{20,64}", tok or ""):
        return None
    try:
        rec = json.load(open(tok_path(tok)))
    except Exception:
        return None
    if rec.get("exp", 0) < time.time():
        try: os.remove(tok_path(tok))
        except OSError: pass
        return None
    return rec


def T(lang, key, **kw):
    return html.escape(mila_i18n.t(LOC, lang, key, **kw))


def switcher(lang):
    """Переключатель языков из словарей: ссылки ?lang= (GET ничего не тратит и не меняет)."""
    return "<div class=lang>%s</div>" % "".join(("<b>%s</b>" if c == lang else "<a href='?lang=%s' hreflang=%s>%%s</a>" % (c, c)) % html.escape(n)
                                               for c, n in mila_i18n.names(LOC))


def page(body, lang):
    return mila_style.shell(mila_i18n.t(LOC, lang, "seif.title"), lang, body, lang_bar=switcher(lang)).encode()


def form(rec, lang, errs=None):
    errs = errs or {}
    rows = []
    for f in rec["fields"]:
        k = "seif.f." + f
        lab = T(lang, k) if k in LOC[lang] or k in LOC[mila_i18n.FALLBACK] else html.escape(f.replace("_", " ").capitalize())
        typ = "password" if SECRETISH.search(f) else "text"
        im = " inputmode=numeric" if f in ("CARD_NUMBER", "CARD_EXPIRY") else ""
        e = ("<div class=e>%s</div>" % T(lang, errs[f])) if f in errs else ""
        rows.append("<label for=%s>%s</label><input id=%s name=%s type=%s autocomplete=off%s required>%s" % (f, lab, f, f, typ, im, e))
    return page("<h1>%s</h1><p>%s</p><form method=post autocomplete=off action='?lang=%s'>%s<button type=submit>%s</button></form><p class=fine>%s</p>"
                % (T(lang, "seif.h1"), T(lang, "seif.intro"), lang, "".join(rows), T(lang, "seif.save"), T(lang, "seif.once", min=int(rec.get("ttl", 30)))), lang)


OWN_NAMES = ("127.0.0.1", "localhost", "mila.localhost")
OWN_TRIES = 5


class H(BaseHTTPRequestHandler):
    server_version = "seif"
    own_port = None   # «свой Сейф» (own): the page answers only to its own loopback name and port (no DNS rebinding)
    tries = {}        # own: wrong entries per link; the sixth closes the link

    def log_message(self, *a):   # без логов запросов (в пути — токен)
        pass

    def send(self, code, body):
        self.send_response(code)
        for k, v in (("Content-Type", "text/html; charset=utf-8"), ("Cache-Control", "no-store"), ("Referrer-Policy", "no-referrer"),
                     ("X-Frame-Options", "DENY"), ("X-Content-Type-Options", "nosniff"),
                     ("Content-Security-Policy", mila_style.CSP), ("Content-Length", str(len(body)))):
            self.send_header(k, v)
        self.end_headers(); self.wfile.write(body)

    def tok(self):
        m = re.fullmatch(r"/v/([A-Za-z0-9_-]{20,64})/?", self.path.split("?")[0])
        return m.group(1) if m else None

    def lang(self, rec=None):
        q = parse_qs(urlsplit(self.path).query).get("lang") or [None]
        return mila_i18n.pick(LOC, q[0], (rec or {}).get("lang"), mila_i18n.accept_language(self.headers.get("Accept-Language")))

    def gone(self, lang=None):
        lang = lang or self.lang()
        self.send(410, page("<h1>%s</h1><p>%s</p>" % (T(lang, "seif.gone.h1"), T(lang, "seif.gone.p")), lang))

    def foreign(self, post=False):
        """own only: a Host that is not exactly this server's loopback name and port → 403; a POST whose Origin is not
        http://<that Host> → 403, and a POST with no Origin at all is refused too (a page of another site in the owner's browser)."""
        if H.own_port is None:
            return False
        host = self.headers.get("Host", "")
        bad = host not in ["%s:%d" % (x, H.own_port) for x in OWN_NAMES] or (post and self.headers.get("Origin", "") != "http://" + host)
        if bad:
            self.send(403, page("", self.lang()))
        return bad

    def do_GET(self):
        if self.foreign():
            return
        t = self.tok(); rec = load_tok(t) if t else None
        return self.send(200, form(rec, self.lang(rec))) if rec else self.gone()

    def do_POST(self):
        if self.foreign(post=True):
            return
        t = self.tok(); rec = load_tok(t) if t else None
        if not rec:
            return self.gone()
        lang = self.lang(rec)
        n = int(self.headers.get("Content-Length") or 0)
        if n > 16384:
            return self.send(413, page("<h1>%s</h1>" % T(lang, "seif.toobig"), lang))
        q = parse_qs(self.rfile.read(n).decode("utf-8", "replace"), keep_blank_values=True)
        vals, errs = {}, {}
        for f in rec["fields"]:
            v, e = check_value(f, (q.get(f) or [""])[0])
            if e:
                errs[f] = e
            else:
                vals[f] = v
        if errs:
            if H.own_port is not None:
                H.tries[t] = H.tries.get(t, 0) + 1
                if H.tries[t] >= OWN_TRIES:   # five wrong entries: the link closes, the page says so in words
                    try: os.remove(tok_path(t))
                    except OSError: pass
                    journal({"ev": "own-tries", "tries": H.tries[t]})
                    return self.gone(lang)
            return self.send(200, form(rec, lang, errs))   # ссылка не тратится, введённое назад не выводится
        home = home_of(rec["slug"])
        try:   # путь проверяем до траты ссылки: подлог в доме — ничего не пишем, ссылка цела
            sdir = mkdir_owned(home, "work", "secrets"); envp = os.path.join(sdir, rec["name"] + ".env")
            cur = read_env(envp)
        except OSError:
            journal({"ev": "refused", "slug": rec["slug"], "why": "path"})
            return self.send(409, page("<h1>%s</h1><p>%s</p>" % (T(lang, "seif.bad.h1"), T(lang, "seif.bad.p")), lang))
        try:
            os.remove(tok_path(t))   # одноразовость: сначала гасим ссылку
        except OSError:
            return self.gone(lang)
        cur.update(vals)
        wfile(envp, "".join("%s=%s\n" % (k, env_quote(v)) for k, v in cur.items())); chown(envp)
        journal({"ev": "saved", "slug": rec["slug"], "file": "work/secrets/%s.env" % rec["name"], "fields": sorted(vals), "to": rec.get("to", "")})
        try:
            ib = os.path.join(mkdir_owned(home, "work", "inbox"), "senior.jsonl")
            note = {"id": "seif-" + str(int(time.time())), "ts": now_iso(), "kind": "note", "from": "seif",
                    "text": "В сейфе появились: %s (файл work/secrets/%s.env). Значения читай только своим инструментом в момент действия, в чат — только маска ****1234." % (", ".join(sorted(vals)), rec["name"])}
            with os.fdopen(os.open(ib, os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600), "a", encoding="utf-8") as f:
                f.write(json.dumps(note, ensure_ascii=False) + "\n")
            chown(ib)
        except OSError:
            pass
        self.send(200, page("<div class=ok>✅</div><h1 style='text-align:center'>%s</h1><p style='text-align:center'>%s</p>"
                            % (T(lang, "seif.saved.h1"), T(lang, "seif.saved.p")), lang))


def main():
    a = sys.argv[1:]
    if not a:
        sys.exit(__doc__)
    if a[0] == "link" and len(a) >= 3:
        return cmd_link(a[1:])
    if a[0] == "own" and len(a) >= 2:
        return cmd_own(a[1:])
    if a[0] == "forget" and len(a) >= 4:
        return cmd_forget(a[1:])
    if a[0] == "serve":
        need_env()
        port = int(a[a.index("--port") + 1]) if "--port" in a else 7693   # как в seif.service и Caddyfile.snippet
        ThreadingHTTPServer(("127.0.0.1", port), H).serve_forever()
    sys.exit(__doc__)


if __name__ == "__main__":
    main()
