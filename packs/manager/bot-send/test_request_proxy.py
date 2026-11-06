#!/usr/bin/env python3
"""bot-send in Mila Agent: no operator, no host service — the consent proxy shows the owner the text and the chat, and after
«yes» the owner's bot sends exactly it. A real proxy, a fake Bot API. Run: python3 test_request_proxy.py"""
import http.server, json, os, shutil, socket, subprocess, sys, tempfile, threading, time, urllib.parse
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.abspath(os.path.join(HERE, "..", "..", "..")); ok = n = 0
def check(name, c, x=""):
    global ok, n; n += 1; ok += bool(c); print(("✅ " if c else "❌ ") + name + ("" if c else "  ← " + str(x)[:300]))
T = tempfile.mkdtemp(prefix="bs-"); SD = tempfile.mkdtemp(prefix="bss-", dir="/tmp" if os.path.isdir("/tmp") else None)
OWNER = str(int("555" + "000111")); POSTS = []
class Fake(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_POST(self):
        POSTS.append(dict(urllib.parse.parse_qsl(self.rfile.read(int(self.headers.get("Content-Length") or 0)).decode())))
        b = b'{"ok": true, "result": {"message_id": 5}}'; self.send_response(200); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Fake); threading.Thread(target=srv.serve_forever, daemon=True).start()
CFG = os.path.join(T, "c.json")
json.dump({"owner_id_env": "MILA_OWNER_ID", "bot_token_env": "BOT_TOKEN", "home": T, "state_dir": os.path.join(T, "s"), "session_socket": os.path.join(SD, "c.sock"),
           "io_socket": os.path.join(SD, "io.sock"), "default_lang": "ru",
           "categories": {"send_as_owner": {"enabled": True, "title": "сообщение от бота", "fields": ["text", "targets"], "exec": [sys.executable, os.path.join(REPO, "consent", "executors", "tg_send.py")]}}}, open(CFG, "w"))
px = subprocess.Popen([sys.executable, os.path.join(REPO, "consent", "consent_proxy.py"), "serve", "--config", CFG],
                      env=dict(os.environ, MILA_OWNER_ID=OWNER, BOT_TOKEN="1:x", TELEGRAM_API_ROOT="http://127.0.0.1:%d" % srv.server_port), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
for _ in range(50):
    if os.path.exists(os.path.join(SD, "io.sock")) and os.path.exists(os.path.join(SD, "c.sock")): break
    time.sleep(0.1)
def press():
    data = json.loads([p for p in POSTS if "reply_markup" in p][-1]["reply_markup"])["inline_keyboard"][0][0]["callback_data"]
    s = socket.socket(socket.AF_UNIX); s.connect(os.path.join(SD, "io.sock")); s.sendall((json.dumps({"op": "callback", "data": data, "from_id": OWNER, "chat_id": OWNER}) + "\n").encode()); s.recv(4096); s.close()
ENV = dict(os.environ, MILA_CONSENT_SOCKET=os.path.join(SD, "c.sock"), MILA_KIT=REPO, MILA_WORK=os.path.join(T, "work"))
def R(*a):
    r = subprocess.run([sys.executable, os.path.join(HERE, "request_send.py")] + list(a), env=ENV, capture_output=True, text=True, timeout=60)
    try: return r.returncode, json.loads(r.stdout or r.stderr)
    except ValueError: return r.returncode, {"raw": r.stdout + r.stderr}
rc, d = R("personal", "--to", "42", "--text", "Ваш заказ готов")
check("без «да»: карточка владельцу (текст целиком), клиенту ничего", rc != 0 and d.get("waiting") == "asked" and "Ваш заказ готов" in POSTS[-1]["text"] and POSTS[-1]["chat_id"] == OWNER, (rc, d))
press(); rc, d = R("personal", "--to", "42", "--text", "Ваш заказ готов")
check("после «да» — отправлено ровно это и ровно ему, без оператора и карточки в аргументах", rc == 0 and d["ok"] and POSTS[-1] == {"chat_id": "42", "text": "Ваш заказ готов"}, (rc, d, POSTS[-1:]))
rc, d = R("personal", "--to", "@client", "--text", "x"); check("@имя вместо id — отказ (в Mila Agent только числовые id)", rc != 0 and "числовые id" in d.get("error", ""), d)
rc, d = R("personal", "--to", "42", "--text", "x", "--buttons", '[[{"label":"a","url":"https://a.b"}]]'); check("кнопки — честный отказ, не тихая потеря", rc != 0 and "кнопки" in d.get("error", ""), d)
px.terminate(); px.wait(); srv.shutdown(); shutil.rmtree(T, ignore_errors=True); shutil.rmtree(SD, ignore_errors=True)
print("итог %d/%d" % (ok, n)); sys.exit(0 if ok == n else 1)
