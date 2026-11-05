#!/usr/bin/env python3
"""Mila Agent: a paid generation is approved through the consent proxy — a card with what, where and the forecast; or inside a
standing permission the owner opened (no card, a receipt). A real proxy, a fake Telegram. Run: python3 test_spend_proxy.py"""
import http.server, json, os, shutil, socket, subprocess, sys, tempfile, threading, time, urllib.parse
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.abspath(os.path.join(HERE, "..", "..", "..")); ok = n = 0
def check(name, c, x=""):
    global ok, n; n += 1; ok += bool(c); print(("✅ " if c else "❌ ") + name + ("" if c else "  ← " + str(x)[:300]))
T = tempfile.mkdtemp(prefix="sp-"); SD = tempfile.mkdtemp(prefix="sps-", dir="/tmp" if os.path.isdir("/tmp") else None)
HOME = os.path.join(T, "home"); TG = os.path.join(HOME, ".claude", "channels", "telegram"); os.makedirs(os.path.join(TG, "io", "consent"))
OWNER = str(int("555" + "000111")); CARDS = []
class Fake(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_POST(self):
        CARDS.append(dict(urllib.parse.parse_qsl(self.rfile.read(int(self.headers.get("Content-Length") or 0)).decode())))
        b = b'{"ok": true, "result": {"message_id": 1}}'; self.send_response(200); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Fake); threading.Thread(target=srv.serve_forever, daemon=True).start()
CFG = os.path.join(T, "c.json")
json.dump({"owner_id_env": "MILA_OWNER_ID", "bot_token_env": "BOT_TOKEN", "home": HOME, "state_dir": os.path.join(TG, "io", "consent"),
           "session_socket": os.path.join(SD, "c.sock"), "io_socket": os.path.join(SD, "io.sock"), "default_lang": "ru",
           "categories": json.load(open(os.path.join(REPO, "consent", "categories.json")))}, open(CFG, "w"))
px = subprocess.Popen([sys.executable, os.path.join(REPO, "consent", "consent_proxy.py"), "serve", "--config", CFG],
                      env=dict(os.environ, MILA_OWNER_ID=OWNER, BOT_TOKEN="1:x", TELEGRAM_API_ROOT="http://127.0.0.1:%d" % srv.server_port), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
for _ in range(50):
    if os.path.exists(os.path.join(SD, "io.sock")) and os.path.exists(os.path.join(SD, "c.sock")): break
    time.sleep(0.1)
def sock(name, obj):
    s = socket.socket(socket.AF_UNIX); s.connect(os.path.join(SD, name)); s.sendall((json.dumps(obj) + "\n").encode()); r = s.recv(8192); s.close(); return json.loads(r)
def press(): return sock("io.sock", {"op": "callback", "data": json.loads(CARDS[-1]["reply_markup"])["inline_keyboard"][0][0]["callback_data"], "from_id": OWNER, "chat_id": OWNER})
ENV = dict(os.environ, HOME=HOME, RASHOD_HOME=os.path.join(HOME, "work", "rashod"), MILA_CONSENT_SOCKET=os.path.join(SD, "c.sock"), MILA_KIT=REPO)
def S(*a):
    r = subprocess.run([sys.executable, os.path.join(HERE, "spend.py")] + list(a), env=ENV, capture_output=True, text=True, timeout=60); return r.returncode, (r.stdout + r.stderr).strip()
rc, out = S("plan", "--service", "fal", "--what", "видео 10 с", "--est", "2", "--by", OWNER); rid = json.loads(out)["id"]
rc, out = S("approve", rid)
check("одобрение без «да» — карточка владельцу с прогнозом, не одобрено", rc != 0 and "карточка у владельца" in out and "~$2.20" in CARDS[-1]["text"], (rc, out, CARDS[-1:]))
check("«да» владельца — granted", press()["status"] == "granted")
rc, out = S("approve", rid); check("после «да» — одобрено", rc == 0 and out == "ok", (rc, out))
check("check — можно", S("check", rid)[0] == 0)
r = sock("c.sock", {"op": "mandate", "category": "spend", "targets": ["fal"], "days": 1, "per_day": 3, "usd_day": 5})
check("полномочие на генерации fal: карточка", r["status"] == "asked" and "Полномочие" in CARDS[-1]["text"], r)
press(); n0 = len(CARDS)
rc, out = S("plan", "--service", "fal", "--what", "картинка", "--est", "1", "--by", OWNER); rid2 = json.loads(out)["id"]
rc, out = S("approve", rid2)
check("в пределах полномочия — одобрено без новой карточки, владельцу квитанция", rc == 0 and out == "ok" and len(CARDS) == n0 + 1 and "по полномочию" in CARDS[-1]["text"], (rc, out, CARDS[-1:]))
rc, out = S("plan", "--service", "heygen", "--what", "аватар", "--est", "1", "--by", OWNER); rid3 = json.loads(out)["id"]
rc, out = S("approve", rid3); check("другой сервис — вне полномочия: карточка", rc != 0 and "карточка у владельца" in out, (rc, out))
px.terminate(); px.wait(); srv.shutdown(); shutil.rmtree(T, ignore_errors=True); shutil.rmtree(SD, ignore_errors=True)
print("итог %d/%d" % (ok, n)); sys.exit(0 if ok == n else 1)
