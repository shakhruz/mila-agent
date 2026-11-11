#!/usr/bin/env python3
"""mila birth: the birth page's local server — on a fake Telegram and a fake `claude`, no network, no real home.
python3 install/test_birth.py"""
import http.client, json, os, re, socket, stat, subprocess, sys, tempfile, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
TOKEN = "123456789:" + "B" * 35
S = {"code": None, "sent": [], "photos": [], "owner": 555002}


class TG(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def do_POST(self): self.do_GET()

    def do_GET(self):
        n = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(n).decode("utf-8", "replace") if n else ""
        method = self.path.rsplit("/", 1)[-1].split("?")[0]
        if TOKEN not in self.path:
            r = {"ok": False, "error_code": 401, "description": "Unauthorized"}
        elif method == "getMe":
            r = {"ok": True, "result": {"id": 1, "is_bot": True, "username": "test_birth_bot", "first_name": "Test Birth"}}
        elif method == "getUpdates":
            res = []
            if S["code"]:
                res = [{"update_id": 10, "message": {"chat": {"type": "group", "id": -5}, "from": {"id": 999}, "text": S["code"]}},
                       {"update_id": 11, "message": {"chat": {"type": "private", "id": S["owner"]}, "from": {"id": S["owner"], "first_name": "Ada"}, "text": S["code"].upper()}}]
            r = {"ok": True, "result": res}
        elif method == "sendMessage":
            S["sent"].append(body); r = {"ok": True, "result": {}}
        elif method == "sendPhoto":
            S["photos"].append(body); r = {"ok": True, "result": {}}
        else:
            r = {"ok": False, "description": "?"}
        b = json.dumps(r).encode()
        self.send_response(200); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)


tg = ThreadingHTTPServer(("127.0.0.1", 0), TG); threading.Thread(target=tg.serve_forever, daemon=True).start()
T = tempfile.mkdtemp()
CL = os.path.join(T, "claude")
open(CL, "w").write('#!/bin/sh\nF="%s/loggedin"\nif [ "$2" = status ]; then [ -f "$F" ] && echo \'{"loggedIn": true, "authMethod": "claude.ai"}\' || echo \'{"loggedIn": false}\'; fi\n'
                    'if [ "$2" = login ]; then touch "$F"; fi\n' % T)
os.chmod(CL, 0o755)
CFG = os.path.join(T, ".claude")
ENV = dict(os.environ, HOME=T, CLAUDE_CONFIG_DIR=CFG, TELEGRAM_STATE_DIR=os.path.join(T, "tg"), MILA_SKIP_TIMERS="1",
           MILA_TG_API="http://127.0.0.1:%d" % tg.server_port, MILA_CLAUDE=CL, MILA_BIRTH_NO_OPEN="1")
ENV.pop("TELEGRAM_BOT_TOKEN", None)
ok = n = 0


def chk(name, cond):
    global ok, n
    n += 1; ok += bool(cond); print(("✅ " if cond else "❌ ") + name, flush=True)


def start(env=ENV):
    p = subprocess.Popen([sys.executable, os.path.join(HERE, "birth.py")], env=env, stdin=subprocess.DEVNULL,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    first = p.stdout.readline()
    rest = []
    threading.Thread(target=lambda: rest.extend(p.stdout), daemon=True).start()
    return p, first, rest


p, first, rest = start()
m = re.search(r"http://mila\.localhost:(\d+)/([A-Za-z0-9_-]{20,})/", first)
chk("печатает адрес http://mila.localhost:<порт>/<случайный токен>/", bool(m))
PORT, PTOK = int(m.group(1)), m.group(2)
BASE = "/%s/" % PTOK


def req(method, path, host="default", origin="default", body=None):
    h = "mila.localhost:%d" % PORT if host == "default" else host
    c = http.client.HTTPConnection("127.0.0.1", PORT, timeout=60)
    c.putrequest(method, path, skip_host=True, skip_accept_encoding=True)
    if h is not None: c.putheader("Host", h)
    o = (("http://" + h) if h is not None else None) if origin == "default" else origin
    if method == "POST" and o is not None: c.putheader("Origin", o)
    data = json.dumps(body if body is not None else {}).encode() if method == "POST" else b""
    c.putheader("Content-Type", "application/json"); c.putheader("Content-Length", str(len(data))); c.endheaders(data)
    r = c.getresponse(); t = r.read().decode("utf-8", "replace"); c.close()
    return r.status, t


def api(path, body=None):
    st, t = req("POST", BASE + "api/" + path, body=body)
    try: return st, json.loads(t)
    except ValueError: return st, {}


# --- bind -----------------------------------------------------------------
conclusive = []; bad = False
try:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.connect(("192.0.2.1", 9)); lan = s.getsockname()[0]; s.close()
    if not lan.startswith("127."):
        try:
            socket.create_connection((lan, PORT), timeout=3).close(); bad = True
        except OSError:
            pass
        conclusive.append("lan")
except OSError:
    pass
try:
    out = subprocess.run(["lsof", "-nP", "-a", "-iTCP:%d" % PORT, "-sTCP:LISTEN"], capture_output=True, text=True, timeout=20).stdout
    if out.strip():
        conclusive.append("lsof"); bad = bad or ("127.0.0.1:%d" % PORT not in out) or ("*:%d" % PORT in out)
except (OSError, subprocess.SubprocessError):
    pass
try:
    socket.create_connection(("::1", PORT), timeout=3).close(); bad = True
except OSError:
    pass
chk("слушает только 127.0.0.1 (не LAN-адрес, не ::1, не *)  [проверено: %s]" % (",".join(conclusive) or "только ::1"), not bad)

# --- paths, Host, Origin ----------------------------------------------------
chk("чужой путь, корень и путь без завершающего / — 404",
    all(req("GET", x)[0] == 404 for x in ("/", "/wrong/", "/" + "x" * len(PTOK) + "/", "/" + PTOK, "/favicon.ico", BASE + "nothing")))
chk("неверный Host — 403 (чужое имя, без порта, чужой порт)",
    all(req("GET", BASE, host=h)[0] == 403 for h in ("evil.example:%d" % PORT, "mila.localhost", "127.0.0.1:%d" % (PORT + 1), None)))
chk("Host mila.localhost, 127.0.0.1 и localhost с верным портом — 200",
    all(req("GET", BASE, host="%s:%d" % (h, PORT))[0] == 200 for h in ("mila.localhost", "127.0.0.1", "localhost")))
chk("POST с чужим Origin — 403; без Origin — 403; с Origin от другого порта — 403",
    all(req("POST", BASE + "api/token", origin=o, body={"token": TOKEN})[0] == 403 for o in ("http://evil.example", None, "http://mila.localhost:1")))
chk("после отклонённых POST ничего не сохранено", not os.path.exists(os.path.join(T, "tg")))

# --- the page ---------------------------------------------------------------
st, page = req("GET", BASE)
urls = set(re.findall(r"https?://[^\s\"'<>)]+", page))
chk("страница: самодостаточный HTML, четыре языка (en, ru, uz, zh), язык по браузеру",
    st == 200 and '"en":{' in page and '"ru":{' in page and '"uz":{' in page and '"zh":{' in page and "navigator.language" in page and "data:image/jpeg;base64," in page)
chk("страница не ходит наружу: из адресов только https://t.me/, ни CDN, ни шрифтов, ни скриптов", urls <= {"https://t.me/"}
    and not re.search(r"<(script|link|img|iframe)[^>]+(src|href)=[\"']?(https?:)?//", page) and "@import" not in page and "__PORTRAIT__" not in page)
chk("страница: без «двенадцати слов», без кнопки «создать бота одним нажатием»", "twelve" not in page.lower() and "one tap" not in page.lower())
chk("страница: подсказка про @BotFather и /newbot есть", "@BotFather" in page and "/newbot" in page)

# --- step 1: the voice -------------------------------------------------------
st, r = api("token", {"token": "not-a-token"})
chk("плохой формат ключа: отказ, ключ не сохранён", r.get("ok") is False and r.get("error") == "format" and not os.path.exists(os.path.join(T, "tg", ".env")))
wrong = "123456789:" + "Z" * 35
st, r = api("token", {"token": wrong})
chk("ключ в верном формате, но Telegram его не принял: отказ, ничего не сохранено, ключ в ответе не звучит",
    r.get("ok") is False and r.get("error") == "telegram" and wrong not in json.dumps(r) and not os.path.exists(os.path.join(T, "tg", ".env")))
st, body = req("POST", BASE + "api/token", body={"token": TOKEN})
r = json.loads(body)
envf = os.path.join(T, "tg", ".env")
chk("верный ключ: @username и имя бота в ответе, ключа в ответе нет",
    r.get("ok") is True and r.get("username") == "test_birth_bot" and r.get("name") == "Test Birth" and TOKEN not in body)
chk(".env 600, папка 700, внутри ключ", os.path.exists(envf) and stat.S_IMODE(os.stat(envf).st_mode) == 0o600
    and stat.S_IMODE(os.stat(os.path.join(T, "tg")).st_mode) == 0o700 and TOKEN in open(envf).read())

# --- step 2: the mind ---------------------------------------------------------
st, r = req("GET", BASE + "api/claude"); r = json.loads(r)
chk("Claude: не вошли — done false", r.get("done") is False)
st, r = api("claude/login")
done = False
for _ in range(40):
    time.sleep(0.25)
    done = json.loads(req("GET", BASE + "api/claude")[1]).get("done")
    if done: break
chk("Claude: запуск входа (`claude auth login`) и опрос статуса — вошли", r.get("ok") is True and done is True)

# --- step 3: you ---------------------------------------------------------------
st, r = api("pair/start")
code = r.get("code", "")
chk("пара: шесть знаков кода из алфавита onboard, @username бота", re.match(r"^[a-z0-9]{6}$", code) is not None and r.get("username") == "test_birth_bot")
st, r2 = api("pair/start")
chk("повторный запрос показывает тот же код", r2.get("code") == code)
r = json.loads(req("GET", BASE + "api/pair/poll")[1])
chk("код ещё не пришёл: paired false, error no_code, хозяина нет", r.get("paired") is False and r.get("error") == "no_code" and not os.path.exists(os.path.join(T, "tg", "access.json")))
S["code"] = code
r = json.loads(req("GET", BASE + "api/pair/poll")[1])
acc = json.load(open(os.path.join(T, "tg", "access.json"))) if os.path.exists(os.path.join(T, "tg", "access.json")) else {}
sett = json.load(open(os.path.join(CFG, "settings.json"))) if os.path.exists(os.path.join(CFG, "settings.json")) else {}
chk("код из личного чата: хозяин как в onboard (allowFrom, dmPolicy allowlist, OWNER_ID); из группы — не считается",
    r.get("paired") is True and acc.get("allowFrom") == [str(S["owner"])] and acc.get("dmPolicy") == "allowlist" and sett.get("env", {}).get("OWNER_ID") == str(S["owner"]))
chk("хозяину ушло приветствие в Telegram", any("Paired" in x for x in S["sent"] + S["photos"]))

# --- born ------------------------------------------------------------------------
rec_file = os.path.join(CFG, "mila-birth.json")
chk("до «родилась» записи нет", not os.path.exists(rec_file))
st, b1 = api("born")
rec = b1.get("record", {})
on_disk = json.load(open(rec_file)) if os.path.exists(rec_file) else {}
chk("запись о рождении: дата с часовым поясом, @username, имя хозяина; в ответе — для сертификата",
    b1.get("ok") is True and re.match(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d[+-]\d\d:\d\d$", rec.get("born_at", "")) and rec.get("bot_username") == "test_birth_bot"
    and rec.get("owner_first_name") == "Ada" and on_disk == rec)
raw = open(rec_file).read() if os.path.exists(rec_file) else ""
chk("в записи нет секретов (ни ключа бота, ни id хозяина)", TOKEN not in raw and str(S["owner"]) not in raw and set(on_disk) <= {"born_at", "bot_username", "owner_first_name"})
time.sleep(1.1)
st, b2 = api("born")
chk("запись пишется один раз: повторный вызов и существующий файл не перезаписываются", b2.get("record") == rec and json.load(open(rec_file)) == rec)

# --- onboard --check after the page ----------------------------------------------
c = subprocess.run([sys.executable, os.path.join(HERE, "onboard.py"), "--check"], env=ENV, capture_output=True, text=True, timeout=60)
chk("`mila onboard --check` после рождения через страницу: три шага ✓, выход 0", c.returncode == 0 and c.stdout.count("✓") == 3)

# --- done: the wrapping is removed ---------------------------------------------------
st, r = api("done")
try:
    p.wait(timeout=15); exited = p.returncode
except subprocess.TimeoutExpired:
    exited = None
time.sleep(0.3)
alive = True
try:
    socket.create_connection(("127.0.0.1", PORT), timeout=2).close()
except OSError:
    alive = False
chk("после подтверждения страницы сервер сам завершается (выход 0) и порт закрыт", r.get("ok") is True and exited == 0 and not alive)
log = first + "".join(rest)
chk("ни ключ бота, ни код пары, ни id хозяина не попали в вывод сервера", TOKEN not in log and code not in log.lower().replace(PTOK.lower(), "") and str(S["owner"]) not in log)

# --- everything is already done -------------------------------------------------------
p2, first2, rest2 = start()
p2.wait(timeout=30)
chk("всё уже сделано: одна строка «already born», выход 0, адреса нет", p2.returncode == 0 and "already born" in first2 and "http" not in first2 and not rest2)

# --- the browser is opened unless told not to -------------------------------------------
os.remove(rec_file)
for f in ("access.json",): os.remove(os.path.join(T, "tg", f))
os.remove(envf)
os.remove(os.path.join(T, "loggedin"))
opener = os.path.join(T, "opener.sh"); seen = os.path.join(T, "opened.txt")
open(opener, "w").write('#!/bin/sh\necho "$1" > "%s"\n' % seen); os.chmod(opener, 0o755)
env3 = dict(ENV, BROWSER=opener); env3.pop("MILA_BIRTH_NO_OPEN")
p3, first3, rest3 = start(env3)
for _ in range(40):
    if os.path.exists(seen): break
    time.sleep(0.25)
opened = open(seen).read().strip() if os.path.exists(seen) else ""
chk("без MILA_BIRTH_NO_OPEN сервер просит браузер открыть тот же адрес", opened != "" and opened in first3)
p3.terminate(); p3.wait(timeout=10)
print("итог %d/%d" % (ok, n))
sys.exit(0 if ok == n else 1)
