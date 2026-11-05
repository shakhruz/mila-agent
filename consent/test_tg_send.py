#!/usr/bin/env python3
"""send_as_owner: the proxy shows the owner the exact text and recipients; after «yes» the executor sends it from the owner's bot
(through the keeper in Mila Agent) to exactly those chats. A fake Bot API. Run: python3 test_tg_send.py"""
import http.server, json, os, shutil, subprocess, sys, tempfile, threading, urllib.parse
H = os.path.dirname(os.path.abspath(__file__)); T = tempfile.mkdtemp(prefix="tgs-"); ok = n = 0
def check(name, c, x=""):
    global ok, n; n += 1; ok += bool(c); print(("✅ " if c else "❌ ") + name + ("" if c else "  ← " + str(x)[:300]))
SENT = []
class Fake(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_POST(self):
        q = dict(urllib.parse.parse_qsl(self.rfile.read(int(self.headers.get("Content-Length") or 0)).decode())); SENT.append((self.path, q))
        bad = q.get("chat_id") == "-13"
        b = json.dumps({"ok": not bad, "description": "chat not found"} if bad else {"ok": True, "result": {"message_id": 7}}).encode()
        self.send_response(400 if bad else 200); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Fake); threading.Thread(target=srv.serve_forever, daemon=True).start()
ENV = dict(os.environ, BOT_TOKEN="111:placeholder", TELEGRAM_API_ROOT="http://127.0.0.1:%d/telegram" % srv.server_port)
EX = os.path.join(H, "executors", "tg_send.py")
def run(body): r = subprocess.run([sys.executable, EX], input=json.dumps(body), capture_output=True, text=True, env=ENV, timeout=30); return r.returncode, json.loads(r.stdout)
rc, d = run({"text": "Здравствуйте! Заказ готов.", "targets": ["42", "-1001"]})
check("исполнитель: ровно этот текст ровно этим чатам, через адрес хранителя", rc == 0 and d["ok"] and [q["chat_id"] for _, q in SENT] == ["42", "-1001"]
      and all(p == "/telegram/bot111:placeholder/sendMessage" and q["text"] == "Здравствуйте! Заказ готов." for p, q in SENT), (d, SENT))
rc, d = run({"text": "x", "targets": ["@someone"]}); check("не числовой адресат — отказ, ничего не отправлено", rc != 0 and len(SENT) == 2, d)
rc, d = run({"text": "x", "targets": ["42", "-13"]}); check("один не дошёл — ok=false, причина по чату", rc != 0 and d["failed"][0]["chat"] == "-13" and d["sent"][0]["chat"] == "42", d)
rc, d = run({"text": "x", "targets": ["42"], "attachments": ["/a"]}); check("вложения этим исполнителем не шлются — отказ", rc != 0)
sys.path.insert(0, H); import consent_proxy as cp
OWNER = str(int("555" + "000111")); os.environ["MILA_OWNER_ID"] = OWNER; os.environ.update(BOT_TOKEN=ENV["BOT_TOKEN"], TELEGRAM_API_ROOT=ENV["TELEGRAM_API_ROOT"])
CARDS = []
px = cp.Proxy({"owner_id_env": "MILA_OWNER_ID", "home": T, "state_dir": os.path.join(T, "s"), "categories": {"send_as_owner": {"enabled": True, "fields": ["text", "targets"], "exec": [sys.executable, EX]}}},
              send=lambda t, kb: CARDS.append((t, kb)) or True)
P = {"text": "Ваша запись на завтра в 11:00", "targets": ["42"]}; n0 = len(SENT)
r = px.request("send_as_owner", P); check("через посредника: сначала карточка, ничего не отправлено", r["status"] == "asked" and len(SENT) == n0 and "Ваша запись" in CARDS[-1][0], r)
px.callback(CARDS[-1][1][0][0]["callback_data"], OWNER, OWNER); r = px.request("send_as_owner", P)
check("после «да» — отправлено ровно это", r["status"] == "done" and r["result"]["ok"] and SENT[-1][1] == {"chat_id": "42", "text": P["text"]}, (r, SENT[-1:]))
check("тот же текст другому адресату — новая карточка", px.request("send_as_owner", dict(P, targets=["43"]))["status"] == "asked")
srv.shutdown(); shutil.rmtree(T, ignore_errors=True); print("итог %d/%d" % (ok, n)); sys.exit(0 if ok == n else 1)
