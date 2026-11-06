#!/usr/bin/env python3
"""mila_keyd.py против поддельных Anthropic/Deepgram/Groq: ключ кладётся только через сокет (неверный формат — отказ),
файл 600 в папке 700; каждый маршрут ставит свой заголовок (подписка — Bearer + oauth-бета к уже переданным бетам,
ключ API — x-api-key, Deepgram — Token, Groq — Bearer); что прислал клиент как ключ — выброшено; поток идёт кусками,
не копится; /status — да/нет без значений; чужой маршрут — 404, нет ключа — 503; ключа нет ни в ответах, ни в журнале.
Run: python3 test_mila_keyd.py"""
import http.client, http.server, json, os, shutil, socket, subprocess, sys, tempfile, threading, time
H = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, H); import mila_keyd
ok = n = 0
def check(name, c, x=""):
    global ok, n; n += 1; ok += bool(c); print(("✅ " if c else "❌ ") + name + ("" if c else "  ← " + str(x)[:300]))
SEEN = []; DEAD = set()   # keys the fake provider no longer takes (the keeper's «alive» check gets 401)
class Up(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    def log_message(self, *a): pass
    def do_POST(self):
        n_ = int(self.headers.get("Content-Length") or 0); body = self.rfile.read(n_)
        auth = (self.headers.get("Authorization") or "") + (self.headers.get("x-api-key") or "")
        if self.command == "GET" and self.path.endswith(("/v1/models", "/v1/projects", "/getMe")):   # the keeper's own «alive» check
            st = 401 if any(k in auth for k in DEAD) else 200
            self.send_response(st); self.send_header("Content-Length", "2"); self.end_headers(); self.wfile.write(b"{}"); return
        SEEN.append((self.path, dict(self.headers), body))
        if b'"stream"' in body:
            self.send_response(200); self.send_header("Content-Type", "text/event-stream"); self.send_header("Transfer-Encoding", "chunked"); self.end_headers()
            for i in range(3):
                ch = ("event: ping\ndata: %d\n\n" % i).encode(); self.wfile.write(b"%x\r\n%s\r\n" % (len(ch), ch)); self.wfile.flush(); time.sleep(0.6)
            self.wfile.write(b"0\r\n\r\n"); return
        b = (b'{"ok": true, "result": {"message_id": 41, "chat": {"id": 1, "type": "private"}, "text": "hello there"}}' if self.path.endswith("/sendMessage") else b'{"ok": true}')
        self.send_response(200); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
    do_GET = do_POST
up = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Up); threading.Thread(target=up.serve_forever, daemon=True).start()
T = tempfile.mkdtemp(prefix="keyd-"); K = os.path.join(T, "keys"); SOCK = os.path.join(T, "put.sock"); os.mkdir(os.path.join(T, "out"))
s = socket.socket(); s.bind(("127.0.0.1", 0)); PORT = s.getsockname()[1]; s.close()
UPB = "http://127.0.0.1:%d" % up.server_port
env = dict(os.environ, KEYS_DIR=K, KEYD_PORT=str(PORT), KEYD_SOCK=SOCK, KEYD_UPSTREAM_ANTHROPIC=UPB + "/a", KEYD_UPSTREAM_DEEPGRAM=UPB + "/d", KEYD_UPSTREAM_GROQ=UPB + "/g", KEYD_UPSTREAM_GUEST=UPB + "/a",
           KEYD_UPSTREAM_TELEGRAM=UPB + "/t", MILA_ARCHIVE_SPOOL=os.path.join(T, "out"), MILA_ARCHIVE_SPOOL_MAX="3", MILA_IO_UID=str(os.getuid()), MILA_RECEIVER_UP=os.path.join(T, "receiver.up"))
LOG = open(os.path.join(T, "keyd.log"), "w")
p = subprocess.Popen([sys.executable, os.path.join(H, "mila_keyd.py")], env=env, stderr=LOG, stdout=LOG)
for _ in range(50):
    try: socket.create_connection(("127.0.0.1", PORT), 0.2).close(); break
    except OSError: time.sleep(0.1)
def req(method, path, body=None, headers=None):
    c = http.client.HTTPConnection("127.0.0.1", PORT, timeout=20); c.request(method, path, body=body, headers=headers or {}); r = c.getresponse(); return r.status, r.read().decode(errors="replace")
OAT = "sk-" + "ant-" + "oat01-" + "A" * 40; API = "sk-" + "ant-" + "api03-" + "B" * 40; DG = "c0ffee12" * 5; GQ = "gs" + "k_" + "C" * 40
check("/status без ключей — все «нет»", json.loads(req("GET", "/status")[1]) == {"anthropic": False, "deepgram": False, "groq": False, "telegram": False, "guest": False, "anthropic_kind": "", "telegram_bot_id": ""})
check("нет ключа — 503, к поставщику не ходим", req("POST", "/anthropic/v1/messages", b"{}")[0] == 503 and not SEEN)
check("неверный формат ключа через сокет — отказ, файла нет", not mila_keyd.put_remote("anthropic", "hello", SOCK) and not os.path.exists(os.path.join(K, "anthropic")))
check("неизвестный вид ключа — отказ", not mila_keyd.put_remote("openai", OAT, SOCK))
check("токен подписки через сокет (ключа ещё нет) — принят; файл 600 в папке 700", mila_keyd.put_remote("anthropic", OAT, SOCK) and oct(os.stat(os.path.join(K, "anthropic")).st_mode & 0o777) == "0o600"
      and oct(os.stat(K).st_mode & 0o777) == "0o700")
c, b = req("POST", "/anthropic/v1/messages?beta=true", b'{"m":1}', {"Authorization": "Bearer dummy", "x-api-key": "dummy2", "anthropic-beta": "tools-2024", "anthropic-version": "2023-06-01"})
path, hd, body = SEEN[-1]; hl = {k.lower(): v for k, v in hd.items()}
check("подписка: к поставщику — Bearer токена, путь и тело без изменений", c == 200 and hl.get("authorization") == "Bearer " + OAT and path == "/a/v1/messages?beta=true" and body == b'{"m":1}', (c, path, hl))
check("подписка: oauth-бета добавлена к переданным, anthropic-version как был", hl.get("anthropic-beta") == "tools-2024,oauth-2025-04-20" and hl.get("anthropic-version") == "2023-06-01", hl)
check("ключ, присланный клиентом (dummy, x-api-key), — выброшен", "dummy" not in json.dumps(hl) and "x-api-key" not in hl, hl)
check("подмена живого ключа через сокет — отказ, ключ прежний", not mila_keyd.put_remote("anthropic", API, SOCK) and open(os.path.join(K, "anthropic")).read().strip() == OAT)
DEAD.add(OAT)
check("старый ключ поставщик больше не принимает — новый принят (повторный вход)", mila_keyd.put_remote("anthropic", API, SOCK) and open(os.path.join(K, "anthropic")).read().strip() == API)
req("POST", "/anthropic/v1/messages", b"{}"); hl = {k.lower(): v for k, v in SEEN[-1][1].items()}
check("ключ API Anthropic — x-api-key, без Authorization и без oauth-беты", hl.get("x-api-key") == API and "authorization" not in hl and "oauth" not in hl.get("anthropic-beta", ""), hl)
mila_keyd.put_remote("deepgram", DG, SOCK); mila_keyd.put_remote("groq", GQ, SOCK)
req("POST", "/deepgram/v1/listen?model=nova-3", b"x"); hl = {k.lower(): v for k, v in SEEN[-1][1].items()}
check("Deepgram — Authorization: Token <ключ>, путь /v1/listen", hl.get("authorization") == "Token " + DG and SEEN[-1][0] == "/d/v1/listen?model=nova-3", hl)
req("POST", "/groq/openai/v1/audio/transcriptions", b"x"); hl = {k.lower(): v for k, v in SEEN[-1][1].items()}
check("Groq — Authorization: Bearer <ключ>", hl.get("authorization") == "Bearer " + GQ, hl)
check("/status — только да/нет и вид (подписка или ключ API)", json.loads(req("GET", "/status")[1]) == {"anthropic": True, "deepgram": True, "groq": True, "telegram": False, "guest": False, "anthropic_kind": "key", "telegram_bot_id": ""})
check("чужой маршрут — 404", req("GET", "/etc/passwd")[0] == 404 and req("GET", "/openai/v1")[0] == 404)
n0 = len(SEEN)
check("управляющие ручки поставщика (новый ключ Deepgram, проекты, баланс, организации Anthropic) — 403, к поставщику не ходим",
      req("POST", "/deepgram/v1/projects/x/keys", b"{}")[0] == 403 and req("GET", "/deepgram/v1/projects")[0] == 403 and req("GET", "/deepgram/v1/projects/x/balances")[0] == 403
      and req("GET", "/anthropic/v1/organizations/x/api_keys")[0] == 403 and req("GET", "/anthropic/api/oauth/profile")[0] == 403 and req("DELETE", "/groq/openai/v1/models")[0] == 403 and len(SEEN) == n0)
cc = http.client.HTTPConnection("127.0.0.1", PORT, timeout=20); t0 = time.time(); cc.request("POST", "/anthropic/v1/messages", b'{"stream": true}'); r = cc.getresponse()
first = r.read1(100); t1 = time.time() - t0; rest = r.read()
check("поток: первый кусок приходит сразу, не после всего ответа (SSE не копится)", b"data: 0" in first and t1 < 1.0 and b"data: 2" in rest, (first, t1))
# the sign-in helper and the key page hand keys to the keeper, not to files the session can read
os.environ["KEYD_SOCK"] = SOCK; AUTHD = os.path.join(T, "auth"); SECD = os.path.join(T, "secrets")
os.environ["MILA_AUTH_DIR"] = AUTHD; os.environ["MILA_SECRETS"] = SECD
import importlib; cl = importlib.import_module("claude_login"); kp = importlib.import_module("key_page")
OAT2 = "sk-" + "ant-" + "oat01-" + "D" * 40; GQ2 = "gs" + "k_" + "E" * 40
DEAD.add(API); cl.AUTH = AUTHD; cl.save(OAT2, "4242")
check("вход в Claude при хранителе: токен у хранителя, файла oauth_token нет, владелец записан", open(os.path.join(K, "anthropic")).read().strip() == OAT2
      and not os.path.exists(os.path.join(AUTHD, "oauth_token")) and open(os.path.join(AUTHD, "owner_id")).read().strip() == "4242")
DEAD.add(GQ); kp.SECRETS = SECD; kp.save("groq", GQ2)
check("страница ключа при хранителе: ключ у хранителя, папки secrets нет", open(os.path.join(K, "groq")).read().strip() == GQ2 and not os.path.exists(SECD))
# migration (root step, here as a plain function): old files and variables move to the keeper, old files are wiped
HM = os.path.join(T, "hm"); os.makedirs(os.path.join(HM, ".mila-auth")); os.makedirs(os.path.join(HM, "work", "secrets"))
OAT3 = "sk-" + "ant-" + "oat01-" + "F" * 40; DG3 = "abcd1234" * 5; GQ3 = "gs" + "k_" + "G" * 40; GQ4 = "gs" + "k_" + "H" * 40
open(os.path.join(HM, ".mila-auth", "oauth_token"), "w").write(OAT3 + "\n")
open(os.path.join(HM, "work", "secrets", "deepgram.env"), "w").write("DEEPGRAM_API_KEY='%s'\n" % DG3)
open(os.path.join(HM, "work", "secrets", "groq.env"), "w").write("GROQ_API_KEY='%s'\n" % GQ3)
mila_keyd.KEYS = os.path.join(HM, ".keys"); os.environ["GROQ_API_KEY"] = GQ4
moved = mila_keyd.migrate(HM); del os.environ["GROQ_API_KEY"]
kk = lambda k: open(os.path.join(HM, ".keys", k)).read().strip()
check("перенос: токен и ключи из старых файлов — у хранителя, старые файлы стёрты", moved == ["anthropic", "deepgram", "groq"] and kk("anthropic") == OAT3 and kk("deepgram") == DG3
      and not os.path.exists(os.path.join(HM, ".mila-auth", "oauth_token")) and not os.path.exists(os.path.join(HM, "work", "secrets", "groq.env")), moved)
check("перенос: переменная платформы сильнее старого файла (хозяин поменял её в панели)", kk("groq") == GQ4)
# the bot: the token lives in the keeper, the caller sends a placeholder in the path
BOT = "555" + "000111:" + "T" * 35; PH = "555" + "000111:mila-keyd-placeholder-not-a-token"
check("токен бота через сокет — принят; /status даёт только id бота", mila_keyd.put_remote("telegram", BOT, SOCK) and json.loads(req("GET", "/status")[1]).get("telegram_bot_id") == "555" + "000111")
req("POST", "/telegram/bot%s/sendMessage" % PH, b'{"chat_id": 1, "text": "x"}')
OD = os.path.join(T, "out"); _names = sorted(os.listdir(OD)); _raw = [open(os.path.join(OD, nm)).read() for nm in _names]
_sp = [json.loads(r) for r in _raw]
check("исходящее для архива: ответ Telegram на sendMessage — файлом в папку спула (метод, чат, id, текст), без токена, без недописанных",
      len(_sp) == 1 and _names[0].endswith(".json") and _sp[0] == {**_sp[0], "method": "sendMessage", "chat_id": "1", "message_id": 41, "text": "hello there"}
      and not any(BOT in r for r in _raw), _names)
for i in range(2): open(os.path.join(OD, "0-0-%d.json" % i), "w").write("{}")
req("POST", "/telegram/bot%s/sendMessage" % PH, b'{"chat_id": 1, "text": "x"}')
check("спул в памяти с потолком: полная папка (3 из 3) — отправка не копируется, папка не растёт", len(os.listdir(OD)) == 3, os.listdir(OD))
for nm in os.listdir(OD): os.unlink(os.path.join(OD, nm))
check("Telegram: заглушка в пути заменена настоящим токеном, остальное как было", SEEN[-1][0] == "/t/bot%s/sendMessage" % BOT, SEEN[-1][0])
req("GET", "/telegram/file/bot%s/documents/file_1.pdf" % PH)
check("Telegram: скачивание файла — тоже с настоящим токеном", SEEN[-1][0] == "/t/file/bot%s/documents/file_1.pdf" % BOT, SEEN[-1][0])
req("POST", "/telegram/bot%s/getMe" % BOT, b"{}")   # an old script still sending the real token: it works, and the journal must not show it
n1 = len(SEEN)
check("Telegram: setWebhook, logOut, close — 403 (бот не уходит чужому адресу), к Telegram не ходим",
      req("POST", "/telegram/bot%s/setWebhook" % PH, b"{}")[0] == 403 and req("POST", "/telegram/bot%s/logOut" % PH, b"{}")[0] == 403
      and req("GET", "/telegram/bot%s/close" % PH)[0] == 403 and len(SEEN) == n1)
n2 = len(SEEN)
codes = [req("POST", "/telegram/bot%s/%s" % (PH, m_), b"{}")[0] for m_ in ("setwebhook", "SETWEBHOOK", "SetWebhook", "logout", "LogOut", "Close", "getWebhookInfo", "setMyName")]
check("Telegram: методы без учёта регистра — setwebhook, SETWEBHOOK, LogOut, Close и всё не из списка — 403, к Telegram не ходим", codes == [403] * 8 and len(SEEN) == n2, codes)
check("Telegram: законные closeForumTopic и closeGeneralForumTopic проходят", req("POST", "/telegram/bot%s/closeForumTopic" % PH, b"{}")[0] == 200 and req("POST", "/telegram/bot%s/closeGeneralForumTopic" % PH, b"{}")[0] == 200)
n3 = len(SEEN)
check("Telegram: «..» в пути файла — 403", req("GET", "/telegram/file/bot%s/../../x" % PH)[0] == 403 and req("GET", "/telegram/file/bot%s/documents/../x" % PH)[0] == 403 and len(SEEN) == n3)
# boot forks the keeper: the child must let go of the caller's pipe, or the entrypoint (… | sed) waits forever — an empty log
SCRIPT = ("import os, sys, time; sys.path.insert(0, sys.argv[1]); import mila_keyd\n"
          "if os.fork() == 0:\n    os.setsid(); mila_keyd.detach_stdio(sys.argv[2]); print('child'); time.sleep(6); os._exit(0)\n"
          "print('up', flush=True)\n")
t0 = time.time(); r = subprocess.run([sys.executable, "-c", SCRIPT, H, os.path.join(T, "child.log")], capture_output=True, text=True, timeout=20)
check("старт хранителя отпускает трубу entrypoint: вызывающий получает вывод сразу, не ждёт живого хранителя",
      time.time() - t0 < 3 and r.stdout.strip() == "up", (round(time.time() - t0, 1), r.stdout))
cc2 = socket.create_connection(("127.0.0.1", PORT)); cc2.sendall(b"POST /anthropic/v1/messages HTTP/1.1\r\nHost: x\r\nContent-Length: zz\r\n\r\n"); time.sleep(0.5); cc2.close()   # a broken request
# reading updates: the receiver over the unix socket (its OS user) — always; anyone over TCP — only while the receiver is not up
class UConn(http.client.HTTPConnection):
    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM); self.sock.connect(os.path.join(T, "api.sock"))
def ureq(path):
    c = UConn("keeper"); c.request("POST", path, b"{}"); r = c.getresponse(); r.read(); return r.status
n4 = len(SEEN)
check("getUpdates по TCP, пока приёмник не поднят (вход в Claude до первого старта), — проходит", req("POST", "/telegram/bot%s/getUpdates" % PH, b"{}")[0] == 200)
open(os.path.join(T, "receiver.up"), "w").write("1")
n5 = len(SEEN)
check("приёмник поднят: getUpdates и deleteWebhook по TCP (сессия) — 403, к Telegram не ходим",
      req("POST", "/telegram/bot%s/getUpdates" % PH, b"{}")[0] == 403 and req("POST", "/telegram/bot%s/deletewebhook" % PH, b"{}")[0] == 403 and len(SEEN) == n5)
check("приёмник (его пользователь, unix-сокет) — getUpdates проходит", ureq("/telegram/bot%s/getUpdates" % PH) == 200)
check("обычные методы по TCP при поднятом приёмнике — как раньше", req("POST", "/telegram/bot%s/sendMessage" % PH, b"{}")[0] == 200)
# who is on a TCP connection: the uid column of the socket table; not found while the lane's user exists — refused
TB = os.path.join(T, "tcp"); open(TB, "w").write("  sl  local_address rem_address   st tx_queue rx_queue tr tm->when retrnsmt   uid\n"
    "   0: 0100007F:D431 0100007F:2056 01 00000000:00000000 00:00000000 00000000  1004        0 1 1\n")
check("таблица сокетов: соединение пользователя полосы — guest", mila_keyd.tcp_peer(("127.0.0.1", 0xD431), ("127.0.0.1", 0x2056), (TB,)) == "guest")
check("таблица сокетов: другой пользователь — tcp", mila_keyd.tcp_peer(("127.0.0.1", 0xD431), ("127.0.0.1", 0x2057), (TB,)) in ("tcp", "unknown"))
_g = mila_keyd.guest_user_exists; mila_keyd.guest_user_exists = lambda: True
check("таблица сокетов: соединение не нашлось, а пользователь полосы есть — unknown (отказ)", mila_keyd.tcp_peer(("127.0.0.1", 1), ("127.0.0.1", 2), (TB,)) == "unknown")
mila_keyd.guest_user_exists = lambda: False
check("…пользователя полосы нет (обычная машина) — tcp, как раньше", mila_keyd.tcp_peer(("127.0.0.1", 1), ("127.0.0.1", 2), (TB,)) == "tcp")
mila_keyd.guest_user_exists = _g
# strangers' lane: an Anthropic API key (never a subscription token) reachable only by the lane's own OS user
GK_ = "sk-" + "ant-" + "api03-" + "G" * 40
check("ключ для чужих: токен подписки — отказ (подписка не для чужих)", not mila_keyd.put_remote("guest", OAT, SOCK))
check("ключ для чужих: ключ API — принят", mila_keyd.put_remote("guest", GK_, SOCK) and json.loads(req("GET", "/status")[1]).get("guest") is True)
n6 = len(SEEN)
check("маршрут чужих по TCP (сессия) — 403, к поставщику не ходим", req("POST", "/guest/v1/messages", b"{}")[0] == 403 and len(SEEN) == n6)
check("маршрут чужих с сокета другим пользователем (здесь — приёмник) — 403", ureq("/guest/v1/messages") == 403 and len(SEEN) == n6)
# a second keeper where this test's OS user is the lane's user
T2 = tempfile.mkdtemp(prefix="keyd-g-"); s2 = socket.socket(); s2.bind(("127.0.0.1", 0)); P2 = s2.getsockname()[1]; s2.close()
LOG2 = open(os.path.join(T2, "keyd.log"), "w")
p2 = subprocess.Popen([sys.executable, os.path.join(H, "mila_keyd.py")], env=dict(env, KEYD_PORT=str(P2), KEYD_SOCK=os.path.join(T2, "put.sock"),
                      MILA_IO_UID="1", MILA_GUEST_UID=str(os.getuid())), stderr=LOG2, stdout=LOG2)
for _ in range(50):
    if os.path.exists(os.path.join(T2, "api.sock")): break
    time.sleep(0.1)
class GConn(http.client.HTTPConnection):
    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM); self.sock.connect(os.path.join(T2, "api.sock"))
def greq(path):
    c = GConn("keeper"); c.request("POST", path, b"{}"); r = c.getresponse(); r.read(); return r.status
check("пользователь полосы: маршрут чужих — проходит, к поставщику x-api-key ключа для чужих",
      greq("/guest/v1/messages") == 200 and {k.lower(): v for k, v in SEEN[-1][1].items()}.get("x-api-key") == GK_ and SEEN[-1][0] == "/a/v1/messages")
n7 = len(SEEN)
check("пользователь полосы: подписка владельца, Telegram, голос — 403", greq("/anthropic/v1/messages") == 403 and greq("/telegram/bot%s/sendMessage" % PH) == 403
      and greq("/groq/openai/v1/models") == 403 and len(SEEN) == n7)
check("пользователь полосы: только сообщения — список моделей и прочее 403", greq("/guest/v1/models") == 403 and len(SEEN) == n7)
def treq(method, path):   # the lane's user over TCP 127.0.0.1 — the kernel's socket table tells the keeper who it is
    c = http.client.HTTPConnection("127.0.0.1", P2, timeout=20); c.request(method, path, body=b"{}"); r = c.getresponse(); r.read(); return r.status
n8 = len(SEEN)
check("пользователь полосы по TCP: подписка владельца и Telegram — 403 (uid соединения из /proc/net/tcp)",
      treq("POST", "/anthropic/v1/messages") == 403 and treq("POST", "/telegram/bot%s/sendMessage" % PH) == 403 and treq("POST", "/groq/openai/v1/audio/transcriptions") == 403 and len(SEEN) == n8)
check("пользователь полосы по TCP: свой маршрут — проходит", treq("POST", "/guest/v1/messages") == 200)
p2.terminate(); p2.wait(); LOG2.close(); shutil.rmtree(T2, ignore_errors=True)
p.terminate(); p.wait(); LOG.close(); logtxt = open(os.path.join(T, "keyd.log")).read()
check("в журнале нет ни ключей, ни заголовков, ни трассировок — только метод, маршрут, код", all(k not in logtxt for k in (OAT, API, DG, GQ, OAT2, GQ2, BOT, GK_, "T" * 35, "dummy", "Bearer")) and "Traceback" not in logtxt and "POST anthropic/v1/messages → 200" in logtxt, logtxt[-300:])
up.shutdown(); shutil.rmtree(T, ignore_errors=True); print("итог %d/%d" % (ok, n)); sys.exit(0 if ok == n else 1)
