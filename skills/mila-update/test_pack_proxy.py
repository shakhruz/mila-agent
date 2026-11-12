#!/usr/bin/env python3
"""Mila Agent: a pack goes in only after the owner's «yes» through the consent proxy — update.py asks the proxy (a card to the
owner), then finds «confirmed» for exactly this pack in the proxy's decisions journal. A real proxy, a fake Telegram.
Run: python3 test_pack_proxy.py"""
import http.server, json, os, shutil, socket, subprocess, sys, tempfile, threading, time
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.abspath(os.path.join(HERE, "..", "..")); ok = n = 0
def check(name, c, x=""):
    global ok, n; n += 1; ok += bool(c); print(("✅ " if c else "❌ ") + name + ("" if c else "  ← " + str(x)[:300]))
T = tempfile.mkdtemp(prefix="pp-"); SD = tempfile.mkdtemp(prefix="pps-", dir="/tmp" if os.path.isdir("/tmp") else None)
HOME = os.path.join(T, "home"); CL = os.path.join(HOME, ".claude"); WORK = os.path.join(HOME, "work"); TG = os.path.join(CL, "channels", "telegram")
os.makedirs(os.path.join(TG, "io", "consent")); os.makedirs(WORK)
OWNER = str(int("555" + "000111")); CARDS = []
class Fake(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length") or 0)).decode()
        import urllib.parse; q = dict(urllib.parse.parse_qsl(body)); CARDS.append(q)
        b = b'{"ok": true, "result": {"message_id": 1}}'; self.send_response(200); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Fake); threading.Thread(target=srv.serve_forever, daemon=True).start()
CFG = os.path.join(T, "consent.json")
json.dump({"owner_id_env": "MILA_OWNER_ID", "bot_token_env": "BOT_TOKEN", "home": HOME, "state_dir": os.path.join(TG, "io", "consent"),
           "session_socket": os.path.join(SD, "c.sock"), "io_socket": os.path.join(SD, "io.sock"), "default_lang": "ru",
           "categories": {"pack": {"enabled": True, "title": "пак", "fields": ["text"]}, "update": {"enabled": True, "title": "обновление", "fields": ["text"]}}}, open(CFG, "w"))
px = subprocess.Popen([sys.executable, os.path.join(REPO, "consent", "consent_proxy.py"), "serve", "--config", CFG],
                      env=dict(os.environ, MILA_OWNER_ID=OWNER, BOT_TOKEN="1:x", TELEGRAM_API_ROOT="http://127.0.0.1:%d" % srv.server_port),
                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
for _ in range(50):
    if os.path.exists(os.path.join(SD, "c.sock")) and os.path.exists(os.path.join(SD, "io.sock")): break
    time.sleep(0.1)
def io(obj):
    s = socket.socket(socket.AF_UNIX); s.connect(os.path.join(SD, "io.sock")); s.sendall((json.dumps(obj) + "\n").encode()); r = s.recv(4096); s.close(); return json.loads(r)
ENV = dict(os.environ, HOME=HOME, CLAUDE_CONFIG_DIR=CL, MILA_WORK=WORK, MILA_PACKS=os.path.join(REPO, "packs"), TELEGRAM_STATE_DIR=TG,
           MILA_CONSENT_SOCKET=os.path.join(SD, "c.sock"), MILA_KIT=REPO, CLAUDECODE="1")
def U(*args):
    r = subprocess.run([sys.executable, os.path.join(HERE, "update.py")] + list(args), env=ENV, capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=60)
    try: return r.returncode, json.loads(r.stdout or r.stderr or "{}")
    except ValueError: return r.returncode, {"raw": (r.stdout + r.stderr)[:300]}
rc, d = U("install-pack", "jev")
check("без «да»: карточка владельцу через посредника, пак не поставлен", rc != 0 and d.get("waiting") == "asked" and CARDS and not os.path.isdir(os.path.join(CL, "skills", "jev")), (rc, d))
check("в карточке — название пака по-человечески и метка архива", "Поставить талант «" in CARDS[-1]["text"] and "#pack-" in CARDS[-1]["text"], CARDS[-1]["text"])
btn = json.loads(CARDS[-1]["reply_markup"])["inline_keyboard"][0]
check("нажатие чужого — посредник не принимает", io({"op": "callback", "data": btn[0]["callback_data"], "from_id": "42", "chat_id": "42"})["status"] == "ignored")
check("нажатие владельца в личке — granted", io({"op": "callback", "data": btn[0]["callback_data"], "from_id": OWNER, "chat_id": OWNER})["status"] == "granted")
rc, d = U("install-pack", "jev")
check("после «да» — пак поставлен, в журнале обновлений id согласия", rc == 0 and d.get("ok") and os.path.isdir(os.path.join(CL, "skills", "jev")), (rc, d))
jr = [json.loads(l) for l in open(os.path.join(CL, "mila-update", "journal.jsonl")) if l.strip()]
check("журнал update: install-pack с id согласия посредника", any(r.get("event") == "install-pack" and r.get("consent") for r in jr), jr[-2:])
n0 = len(CARDS); rc, d = U("install-pack", "jev")
check("то же «да» второй раз не годится — снова карточка", rc != 0 and d.get("waiting") == "asked" and len(CARDS) == n0 + 1, (rc, d))
dj = os.path.join(TG, "io", "consent", "decisions.jsonl"); L = open(dj).read().splitlines()
x = json.loads(L[1]); x["ev"] = "granted!"; open(dj, "w").write("\n".join([L[0], json.dumps(x)] + L[2:]) + "\n")
btn = json.loads(CARDS[-1]["reply_markup"])["inline_keyboard"][0]; io({"op": "callback", "data": btn[0]["callback_data"], "from_id": OWNER, "chat_id": OWNER})
rc, d = U("install-pack", "jev")
check("журнал решений подправлен — update.py не ставит («нет да в журнале»)", rc != 0 and "журнале решений" in d.get("error", ""), (rc, d))
io({"op": "callback", "data": json.loads(CARDS[-1]["reply_markup"])["inline_keyboard"][0][0]["callback_data"], "from_id": OWNER, "chat_id": OWNER})
open(dj, "w").write("\n".join(L) + "\n")   # the journal back as it was — but the press was on the line written after: start clean below
shutil.rmtree(os.path.join(TG, "io", "consent")); os.makedirs(os.path.join(TG, "io", "consent"))
rc, d = U("remove-pack", "jev")
check("убрать пак — тоже через посредника: карточка «Убрать талант», ничего не снято", rc != 0 and d.get("waiting") == "asked" and "Убрать талант «" in CARDS[-1]["text"] and os.path.isdir(os.path.join(CL, "skills", "jev")), (rc, d, CARDS[-1].get("text")))
io({"op": "callback", "data": json.loads(CARDS[-1]["reply_markup"])["inline_keyboard"][0][0]["callback_data"], "from_id": OWNER, "chat_id": OWNER})
rc, d = U("remove-pack", "jev")
check("…после «да» — снят", rc == 0 and not os.path.isdir(os.path.join(CL, "skills", "jev")), (rc, d))
# a core update: also only through the proxy — a --yes string from the session is not an owner's «yes»
R = os.path.join(T, "rel"); os.makedirs(os.path.join(R, "skills", "demo")); os.makedirs(os.path.join(HOME, "work"), exist_ok=True)
open(os.path.join(R, "release.json"), "w").write(json.dumps({"version": "9.9.9", "tag": "v9.9.9", "zones": [{"what": "навыки", "src": "skills/*", "dst": "{claude}/skills/*", "kind": "dir"}]}))
open(os.path.join(R, "skills", "demo", "SKILL.md"), "w").write('---\nname: demo\ndescription: "демо"\n---\n# demo\n')
rc, d = U("apply", "--src", R, "--yes", "хозяин сказал да")
check("обновление ядра: строка --yes не считается — карточка у владельца, ничего не поставлено", rc != 0 and d.get("waiting") == "asked" and "Обновить ядро" in CARDS[-1]["text"]
      and not os.path.isdir(os.path.join(CL, "skills", "demo")), (rc, d))
io({"op": "callback", "data": json.loads(CARDS[-1]["reply_markup"])["inline_keyboard"][0][0]["callback_data"], "from_id": OWNER, "chat_id": OWNER})
rc, d = U("apply", "--src", R)
check("…после «да» владельца — обновлено, в журнале «consent:<id>»", rc == 0 and os.path.isdir(os.path.join(CL, "skills", "demo"))
      and any(str(r.get("yes", "")).startswith("consent:") for r in (json.loads(l) for l in open(os.path.join(CL, "mila-update", "journal.jsonl")) if l.strip())), (rc, d))
px.terminate(); px.wait(); srv.shutdown(); shutil.rmtree(T, ignore_errors=True); shutil.rmtree(SD, ignore_errors=True)
print("итог %d/%d" % (ok, n)); sys.exit(0 if ok == n else 1)
