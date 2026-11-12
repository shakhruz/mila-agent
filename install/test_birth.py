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
                       {"update_id": 11, "message": {"chat": {"type": "private", "id": S["owner"]}, "from": {"id": S["owner"], "first_name": "Ada"}, "text": S["msg"] if S.get("msg") else S["code"].upper()}}]
            r = {"ok": True, "result": res}
        elif method == "sendMessage":
            S["sent"].append(body); r = {"ok": True, "result": {}}
        elif method == "sendPhoto":
            S["photos"].append(body); r = {"ok": True, "result": {}}
        else:
            r = {"ok": False, "description": "?"}
        b = json.dumps(r).encode()
        self.send_response(200); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)


GOODCODE, NOOWNER, NOTOKEN, DOWN = "MILA-ABCD-EFGH-JKLM", "MILA-NOOW-NERX-ABCD", "MILA-NOTK-NXXX-ABCD", "MILA-DOWN-DOWN-DOWN"
HITS = []


class Relay(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def do_POST(self):
        d = json.loads(self.rfile.read(int(self.headers["Content-Length"]))); HITS.append(d.get("code"))
        c = d.get("code")
        if c == GOODCODE: code, body = 200, {"ok": True, "bot_token": TOKEN, "owner_id": str(S["owner2"])}
        elif c == NOOWNER: code, body = 200, {"ok": True, "bot_token": TOKEN}
        elif c == NOTOKEN: code, body = 200, {"ok": True}
        elif c == DOWN: code, body = 500, {"ok": False}
        else: code, body = 404, {"ok": False}
        b = json.dumps(body).encode(); self.send_response(code); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)


S["owner2"] = 555003
relay = ThreadingHTTPServer(("127.0.0.1", 0), Relay); threading.Thread(target=relay.serve_forever, daemon=True).start()
tg = ThreadingHTTPServer(("127.0.0.1", 0), TG); threading.Thread(target=tg.serve_forever, daemon=True).start()
T = tempfile.mkdtemp()
CL = os.path.join(T, "claude")
open(CL, "w").write('#!/bin/sh\nF="%s/loggedin"\nif [ "$2" = status ]; then [ -f "$F" ] && echo \'{"loggedIn": true, "authMethod": "claude.ai"}\' || echo \'{"loggedIn": false}\'; fi\n'
                    'if [ "$2" = login ]; then touch "$F"; fi\n' % T)
os.chmod(CL, 0o755)
CFG = os.path.join(T, ".claude")
ENV = dict(os.environ, HOME=T, CLAUDE_CONFIG_DIR=CFG, TELEGRAM_STATE_DIR=os.path.join(T, "tg"), MILA_SKIP_TIMERS="1",
           MILA_TG_API="http://127.0.0.1:%d" % tg.server_port, MILA_CLAUDE=CL, MILA_BIRTH_NO_OPEN="1",
           BIRTH_RELAY="http://127.0.0.1:%d/birth/api/claim" % relay.server_port, BIRTH_RELAY_INSECURE_TEST="1", MILA_RUN_STATE=os.path.join(T, "run"))
# a stand-in launcher: notes that the page asked to start Mila in the background
os.makedirs(os.path.join(T, ".local", "bin")); open(os.path.join(T, ".local", "bin", "mila"), "w").write('#!/bin/bash\necho "$*" >> "%s/mila.calls"\n' % T)
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
chk("страница не ходит наружу: из адресов только https://t.me/, ни CDN, ни шрифтов, ни скриптов", all(u.startswith("https://t.me/") for u in urls)
    and not re.search(r"<(script|link|img|iframe)[^>]+(src|href)=[\"']?(https?:)?//", page) and "@import" not in page and "__PORTRAIT__" not in page)
chk("страница: без «двенадцати слов» (это другой модуль), без мёртвых кнопок", "twelve" not in page.lower() and 'href="#"' not in page.replace('id="bopen" href="#"', "").replace('id="b4" href="#"', ""))
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
S["msg"] = "/start wrong2"
r = json.loads(req("GET", BASE + "api/pair/poll")[1])
chk("`/start` с чужим кодом не делает хозяином", r.get("paired") is False and not os.path.exists(os.path.join(T, "tg", "access.json")))
S["msg"] = "/start " + code.upper()
r = json.loads(req("GET", BASE + "api/pair/poll")[1])
acc = json.load(open(os.path.join(T, "tg", "access.json"))) if os.path.exists(os.path.join(T, "tg", "access.json")) else {}
sett = json.load(open(os.path.join(CFG, "settings.json"))) if os.path.exists(os.path.join(CFG, "settings.json")) else {}
chk("`/start <код>` (ссылка t.me/бот?start=код) из личного чата: хозяин как в onboard (allowFrom, dmPolicy allowlist, OWNER_ID); из группы — не считается",
    r.get("paired") is True and acc.get("allowFrom") == [str(S["owner"])] and acc.get("dmPolicy") == "allowlist" and sett.get("env", {}).get("OWNER_ID") == str(S["owner"]))
chk("страница при привязке хозяина сама ему ничего не шлёт: первые слова скажет Мила из фона («Paired», «Claude Code», «terminal» — нет)",
    not any(re.search(r"Paired|owner|Claude Code|terminal|mila", x) for x in S["sent"] + S["photos"]))

S["msg"] = None
sys.path.insert(0, HERE)
import onboard as ob
ups = lambda t: [{"message": {"chat": {"type": "private"}, "from": {"id": 9}, "text": t}}]
chk("общий сопоставитель onboard: «код», «/start код», «/start@бот КОД» — да; «/start другой», «код лишний» — нет",
    all(ob.code_from(ups(t), "abc234") for t in ("abc234", "ABC234", "/start abc234", "/start@some_bot ABC234", " /START abc234 ")) and not any(ob.code_from(ups(t), "abc234") for t in ("/start", "/start other1", "abc234 more", "/start abc234 x")))
chk("алфавит кода пары годится для параметра start в Telegram (A-Za-z0-9_-, до 64)", re.fullmatch(r"[A-Za-z0-9_-]{1,64}", code) is not None)
chk("страница делает кнопку «Открыть моего бота» из @username бота и текущего кода (t.me/<бот>?start=<код>)",
    '"https://t.me/"+encodeURIComponent(botName)+"?start="+encodeURIComponent(r.code)' in page and 'id="bopen"' in page)

# --- born ------------------------------------------------------------------------
rec_file = os.path.join(CFG, "mila-birth.json")
chk("до «родилась» записи нет", not os.path.exists(rec_file))
chk("…и Милу в фоне страница ещё не запускала", not os.path.exists(os.path.join(T, "mila.calls")))
st, aw = req("GET", BASE + "api/awake")
chk("до её первых слов страница знает: «ещё не написала» (awake greeted=false)", json.loads(aw).get("greeted") is False)
st, b1 = api("born", {"lang": "ru"})
rec = b1.get("record", {})
on_disk = json.load(open(rec_file)) if os.path.exists(rec_file) else {}
chk("запись о рождении: дата с часовым поясом, @username, имя хозяина; в ответе — для сертификата",
    b1.get("ok") is True and re.match(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d[+-]\d\d:\d\d$", rec.get("born_at", "")) and rec.get("bot_username") == "test_birth_bot"
    and rec.get("owner_first_name") == "Ada" and on_disk == rec)
chk("в записи — язык страницы рождения (на нём она скажет первые слова)", rec.get("lang") == "ru")
def _calls():
    try: return open(os.path.join(T, "mila.calls")).read().split()
    except OSError: return []
_t = time.time()
while not _calls() and time.time() - _t < 10: time.sleep(0.1)
chk("после «родилась» страница сама запускает Милу в фоне (mila start), терминал человеку не нужен", _calls() == ["start"])
os.makedirs(os.path.join(T, "run"), exist_ok=True); open(os.path.join(T, "run", "greeted"), "w").close()
st, aw = req("GET", BASE + "api/awake")
chk("её первые слова ушли — страница узнаёт об этом (awake greeted=true) и только тогда говорит «она ждёт»", json.loads(aw).get("greeted") is True)
chk("страница: «она ждёт» показывается по факту — сначала «просыпается», опрос awake, при молчании — честная строка; ум подключается в чате",
    'data-i="wake"' in page and 'api("awake")' in page and 'wakeKey="p4"' in page and 'wakeKey="wake_late"' in page and "if(!st.claude.done)return enter2()" not in page
    and all(len(re.findall(r'"%s":' % k, page)) == 4 for k in ("wake", "wake_late")))
raw = open(rec_file).read() if os.path.exists(rec_file) else ""
chk("в записи нет секретов (ни ключа бота, ни id хозяина)", TOKEN not in raw and str(S["owner"]) not in raw and set(on_disk) <= {"born_at", "bot_username", "owner_first_name", "lang"})
time.sleep(1.1)
st, b2 = api("born")
chk("запись пишется один раз: повторный вызов и существующий файл не перезаписываются", b2.get("record") == rec and json.load(open(rec_file)) == rec)
chk("…и второй раз фон не запускается", _calls() == ["start"])

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

# --- the one-tap path: birth code through the relay ----------------------------------------
def reset_state():
    for f in (rec_file, os.path.join(T, "tg", "access.json"), envf, os.path.join(T, "loggedin"), os.path.join(CFG, "settings.json")):
        if os.path.exists(f): os.remove(f)


def serve(env):
    global PORT, PTOK, BASE
    pp, f1, rr = start(env)
    mm = re.search(r"http://mila\.localhost:(\d+)/([A-Za-z0-9_-]{20,})/", f1)
    PORT, PTOK = int(mm.group(1)), mm.group(2); BASE = "/%s/" % PTOK
    return pp, f1, rr


reset_state()
p4, first4, rest4 = serve(dict(ENV, MILA_BIRTH_PARENT="my_parent_bot"))
page4 = req("GET", BASE)[1]
chk("кнопка «одним нажатием» ведёт на t.me/<MILA_BIRTH_PARENT>?start=birth_<язык>; по умолчанию — mila_gpt_bot и английский",
    'href="https://t.me/my_parent_bot?start=birth_en"' in page4 and 'href="https://t.me/mila_gpt_bot?start=birth_en"' in page and "__PARENT__" not in page4)
chk("…язык страницы идёт в ссылку: при смене языка ссылка получает метку birth_<язык> (бот ответит на языке страницы)",
    '$("bone").href="https://t.me/my_parent_bot?start=birth_"+l' in page4 and page4.index('function L(l){') < page4.index('$("bone").href=')
    and all('data-l="%s"' % l in page4 for l in ("en", "ru", "uz", "zh")) and 'start=birth"' not in page4)
chk("новые тексты на четырёх языках: кнопки, строка про родительского бота, ошибки, «Открыть моего бота»",
    len(re.findall(r'"(?:en|ru|uz|zh)":\{"t0"', page4)) == 4 and all(len(re.findall(r'"%s":' % k, page4)) == 4 for k in ("bone", "bbot", "bothint", "honest", "e_input", "e_code_refused", "e_relay", "e_relay_no_token", "bopen", "orsend", "sub4")))
chk("шаг «адрес»: одно поле (код или ключ), одна кнопка «Дальше»; кнопки «одним нажатием» и «Открыть @BotFather» над ним; второго поля и <details> нет",
    page4.index('id="bone"') < page4.index('id="bbot"') < page4.index('id="pasted"') < page4.index('id="bgo"') and 'href="https://t.me/BotFather"' in page4
    and page4.count("<input") == 1 and "<details" not in page4 and 'id="tok"' not in page4 and 'id="bcodein"' not in page4 and '"own"' not in page4)
chk("страница различает вставленное по формату: ключ бота → api/token, код рождения → api/code, остальное — ошибка e_input",
    'k==="code"?{code:v}:{token:v}' in page4 and "api(k," in page4 and '"e_input"' in page4 and "MILA-XXXX-XXXX-XXXX / 1234567890:AA" in page4)
chk("шаги названы: «A place to meet», «Her mind», «You»; «A voice» нет", '"t1":"A place to meet"' in page4 and '"t2":"Her mind"' in page4 and '"t3":"You"' in page4 and "A voice" not in page4 and "Место встречи" in page4 and "Её ум" in page4)
nothing = lambda: not os.path.exists(envf) and not os.path.exists(os.path.join(T, "tg", "access.json"))
r = api("code", {"code": "hello"})[1]
chk("код не того вида: отказ code_format, в relay не ходили, ничего не сохранено", r.get("error") == "code_format" and not HITS and nothing())
r = api("code", {"code": "MILA-ZZZZ-ZZZZ-ZZZZ"})[1]
chk("relay ответил 404 (использован/истёк/опечатка): отказ code_refused, ничего не сохранено", r.get("error") == "code_refused" and nothing())
r = api("code", {"code": NOTOKEN})[1]
chk("relay ответил без токена: relay_no_token, ничего не сохранено", r.get("error") == "relay_no_token" and nothing())
r = api("code", {"code": DOWN})[1]
chk("relay ответил 500: relay (недоступен), ничего не сохранено", r.get("error") == "relay" and nothing())
st, body = req("POST", BASE + "api/code", body={"code": NOOWNER.lower().replace("-", " ")})
r = json.loads(body)
chk("relay без owner_id: токен сохранён, paired false, шаг пары обязателен (код выдаётся, хозяина нет); строчные и пробелы вместо дефисов приняты",
    r.get("ok") is True and r.get("paired") is False and r.get("username") == "test_birth_bot" and TOKEN not in body and HITS[-1] == NOOWNER
    and bool(api("pair/start")[1].get("code")) and not os.path.exists(os.path.join(T, "tg", "access.json")) and json.loads(req("GET", BASE + "api/status")[1])["pair"]["done"] is False)
os.remove(envf)
st, body = req("POST", BASE + "api/code", body={"code": GOODCODE.lower().replace("-", "")})
r = json.loads(body)
acc = json.load(open(os.path.join(T, "tg", "access.json"))) if os.path.exists(os.path.join(T, "tg", "access.json")) else {}
sett = json.load(open(os.path.join(CFG, "settings.json"))) if os.path.exists(os.path.join(CFG, "settings.json")) else {}
chk("верный код (строчными, без дефисов): токен сохранён 600/700, хозяин из owner_id как в finish_pair, paired true, токена в ответе нет",
    r.get("ok") is True and r.get("paired") is True and HITS[-1] == GOODCODE and TOKEN not in body and TOKEN in open(envf).read()
    and stat.S_IMODE(os.stat(envf).st_mode) == 0o600 and stat.S_IMODE(os.stat(os.path.join(T, "tg")).st_mode) == 0o700
    and acc.get("allowFrom") == [str(S["owner2"])] and acc.get("dmPolicy") == "allowlist" and sett.get("env", {}).get("OWNER_ID") == str(S["owner2"]))
c = subprocess.run([sys.executable, os.path.join(HERE, "onboard.py"), "--check"], env=ENV, capture_output=True, text=True, timeout=60)
chk("`onboard --check`: ключ бота и хозяин готовы (✓ 1/3 и 3/3), Claude ещё нет", "✓ 1/3" in c.stdout and "✓ 3/3" in c.stdout and "✗ 2/3" in c.stdout)
pr = api("pair/start")[1]
chk("шаг пары пропущен: pair/start сразу done, кода не просит", pr.get("done") is True and "code" not in pr)
api("claude/login")
for _ in range(40):
    time.sleep(0.25)
    if json.loads(req("GET", BASE + "api/claude")[1]).get("done"): break
b = api("born")[1]
api("done")
try: p4.wait(timeout=15)
except subprocess.TimeoutExpired: pass
log4 = first4 + "".join(rest4)
chk("после Claude — сразу «родилась»; сервер завершился; ключа бота нет в выводе сервера", b.get("ok") is True and p4.returncode == 0 and TOKEN not in log4)
c = subprocess.run([sys.executable, os.path.join(HERE, "onboard.py"), "--check"], env=ENV, capture_output=True, text=True, timeout=60)
chk("`onboard --check` после пути «одним нажатием»: все три шага ✓", c.returncode == 0 and c.stdout.count("✓") == 3)

reset_state(); h0 = len(HITS)
env5 = dict(ENV); env5.pop("BIRTH_RELAY_INSECURE_TEST")
p5, first5, rest5 = serve(env5)
r = api("code", {"code": GOODCODE})[1]
chk("relay по http без тестового флага отклонён: в relay не ходили, ничего не сохранено", r.get("error") == "relay" and len(HITS) == h0 and nothing())
p5.terminate(); p5.wait(timeout=10)
os.environ["BIRTH_RELAY_INSECURE_TEST"] = "1"
import birth_relay as br
chk("normalize_code: регистр, дефисы, пробелы, без MILA; мусор и чужой алфавит — нет",
    all(br.normalize_code(x) == GOODCODE for x in ("milaabcdefghjklm", "MILA ABCD EFGH JKLM", "abcd-efgh-jklm", " abcdefghjklm ")) and br.normalize_code("MILA-ABC0-EFGH-JKLM") is None and br.normalize_code("hello") is None and br.normalize_code("") is None)
chk("claim: relay недоступен (порт закрыт) → unreachable", br.claim(GOODCODE, "http://127.0.0.1:1/x")["error"] == "unreachable")
print("итог %d/%d" % (ok, n))
sys.exit(0 if ok == n else 1)
