#!/usr/bin/env python3
"""birth_claim.py против поддельного relay: верный код → bot_token и owner_id в томе (600, папка 700), токен не напечатан; relay 404 —
«refused», ничего не записано, код 1; плохой формат — код 2 без запроса; http без тестового флага — код 2; ответ без токена — код 1.
Плюс entrypoint: BIRTH_CODE → токен из тома → дальше помощник входа ждёт /start. Run: python3 test_birth_claim.py"""
import http.server, json, os, shutil, subprocess, sys, tempfile, threading
OWN, OTH, STR = "555" + "000111", "555" + "000222", "555" + "000999"   # glued: no long id literals in the core
H = os.path.dirname(os.path.abspath(__file__)); R = os.path.dirname(H); ok = n = 0
def check(name, c, x=""):
    global ok, n; n += 1; ok += bool(c); print(("✅ " if c else "❌ ") + name + ("" if c else "  ← " + str(x)[:300]))
TOK = "7654321" + ":" + "B" * 35; GOOD = "MILA-ABCD-EFGH-JKLM"; HITS = []
class Relay(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_POST(self):
        d = json.loads(self.rfile.read(int(self.headers["Content-Length"]))); HITS.append(d.get("code"))
        if d.get("code") == GOOD: code, body = 200, {"ok": True, "bot_token": TOK, "owner_id": OWN}
        elif d.get("code") == "MILA-NOTO-KENX-XXXX": code, body = 200, {"ok": True}
        else: code, body = 404, {"ok": False}
        b = json.dumps(body).encode(); self.send_response(code); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Relay); threading.Thread(target=srv.serve_forever, daemon=True).start()
URL = "http://127.0.0.1:%d/birth/api/claim" % srv.server_port
T = tempfile.mkdtemp(prefix="birthc-")
def run(code, auth, insecure=True, relay=URL):
    env = dict(os.environ, BIRTH_CODE=code, BIRTH_RELAY=relay, MILA_AUTH_DIR=auth)
    if insecure: env["BIRTH_RELAY_INSECURE_TEST"] = "1"
    return subprocess.run([sys.executable, os.path.join(H, "birth_claim.py")], capture_output=True, text=True, env=env)
A = os.path.join(T, "a"); r = run(GOOD.lower(), A)
check("верный код (строчными тоже) → код 0, токен в томе", r.returncode == 0 and open(os.path.join(A, "bot_token")).read().strip() == TOK, r.stdout)
check("owner_id записан; файлы 600, папка 700", open(os.path.join(A, "owner_id")).read().strip() == OWN and oct(os.stat(os.path.join(A, "bot_token")).st_mode & 0o777) == "0o600" and oct(os.stat(A).st_mode & 0o777) == "0o700")
check("токен не напечатан", TOK not in r.stdout + r.stderr)
B = os.path.join(T, "b"); r = run("MILA-ZZZZ-ZZZZ-ZZZZ", B)
check("relay 404 → «refused», ничего не записано, код 1", r.returncode == 1 and "refused" in r.stdout and not os.path.exists(os.path.join(B, "bot_token")), r.stdout)
h0 = len(HITS); r = run("hello", B)
check("плохой формат → код 2, в relay не ходили", r.returncode == 2 and len(HITS) == h0)
r = run(GOOD, B, insecure=False)
check("relay не https без тестового флага → код 2", r.returncode == 2 and "https" in r.stdout)
r = run("MILA-NOTO-KENX-XXXX", B)
check("ответ без токена → код 1, ничего не записано", r.returncode == 1 and not os.path.exists(os.path.join(B, "bot_token")))
# entrypoint: BIRTH_CODE only — the token comes from the relay, then the sign-in helper waits for /start
HM = os.path.join(T, "home"); os.makedirs(HM); py = os.path.dirname(shutil.which("python3"))
env = {"HOME": HM, "PATH": py + ":/usr/bin:/bin", "MILA_KIT": R, "BIRTH_CODE": GOOD, "BIRTH_RELAY": URL, "BIRTH_RELAY_INSECURE_TEST": "1",
       "BIRTH_HELPER": os.path.join(H, "birth_claim.py"), "LOGIN_HELPER": os.path.join(H, "claude_login.py"), "TG_API": "http://127.0.0.1:9"}
r = subprocess.run(["timeout", "4", "bash", os.path.join(H, "entrypoint.sh")], capture_output=True, text=True, env=env)
o = r.stdout + r.stderr
check("entrypoint: BIRTH_CODE → «birth code accepted» → помощник входа ждёт /start; токен не в логе", "birth code accepted" in o and "waiting for /start" in o and TOK not in o, o[-400:])
check("…второй старт не ходит в relay снова (токен уже в томе)", (lambda h: (subprocess.run(["timeout", "3", "bash", os.path.join(H, "entrypoint.sh")], capture_output=True, text=True, env=env), len(HITS) == h)[1])(len(HITS)))
srv.shutdown(); shutil.rmtree(T, ignore_errors=True); print("итог %d/%d" % (ok, n)); sys.exit(0 if ok == n else 1)
