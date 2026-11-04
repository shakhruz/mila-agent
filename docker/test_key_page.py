#!/usr/bin/env python3
"""key_page.py groq против поддельной проверки Groq: одна строка-ссылка на публичный адрес; чужой путь — 404; не ключ и ключ,
который сервис не принял, — просьба, ничего не сохранено; верный — groq.env 600 в папке 700 (тот файл, что читает скрипт голоса),
страница гаснет; без публичного адреса — строка про переменную, страница не открывается; ключ не в выводе.
Run: python3 test_key_page.py"""
import http.server, json, os, re, shutil, socket, subprocess, sys, tempfile, threading, time, urllib.error, urllib.parse, urllib.request
H = os.path.dirname(os.path.abspath(__file__)); ok = n = 0
def check(name, c, x=""):
    global ok, n; n += 1; ok += bool(c); print(("✅ " if c else "❌ ") + name + ("" if c else "  ← " + str(x)[:300]))
GOOD = "gsk_" + "A" * 40; BAD = "gsk_" + "B" * 40
class Fake(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        okk = self.headers.get("Authorization") == "Bearer " + GOOD
        b = b'{"data": []}' if okk else b'{"error": "invalid"}'
        self.send_response(200 if okk else 401); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
api = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Fake); threading.Thread(target=api.serve_forever, daemon=True).start()
T = tempfile.mkdtemp(prefix="kpage-"); SEC = os.path.join(T, "secrets")
def free():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p
def env(port, **k):
    return dict(os.environ, PORT=str(port), BIND="127.0.0.1", MILA_SECRETS=SEC, KEY_CHECK_URL="http://127.0.0.1:%d/models" % api.server_port,
                MILA_PUBLIC_URL="http://127.0.0.1:%d" % port, **k)
def req(url, data=None):
    r = urllib.request.Request(url, data=urllib.parse.urlencode(data).encode() if data else None)
    try:
        with urllib.request.urlopen(r, timeout=20) as x: return x.status, x.read().decode()
    except urllib.error.HTTPError as e: return e.code, e.read().decode()
def wait_port(port):
    for _ in range(50):
        try: socket.create_connection(("127.0.0.1", port), timeout=0.2).close(); return True
        except OSError: time.sleep(0.1)
    return False
port = free()
r = subprocess.run([sys.executable, os.path.join(H, "key_page.py"), "groq"], env=env(port), capture_output=True, text=True, timeout=20)
url = r.stdout.strip()
check("одна строка — одноразовая ссылка на публичный адрес /k/<токен>", r.returncode == 0 and re.fullmatch(r"http://127\.0\.0\.1:%d/k/[A-Za-z0-9_-]{30,}" % port, url), r.stdout)
check("страница поднялась в фоне", wait_port(port))
check("чужой путь — 404", req("http://127.0.0.1:%d/k/wrong" % port)[0] == 404)
c, b = req(url); check("по ссылке — форма про Groq (по-английски по умолчанию)", c == 200 and "console.groq.com/keys" in b)
c, b = req(url, {"k": "hello"}); check("не ключ — просьба, ничего не сохранено", "did not accept" in b and not os.path.exists(os.path.join(SEC, "groq.env")))
c, b = req(url, {"k": BAD}); check("ключ, который сервис не принял, — просьба, ничего не сохранено", "did not accept" in b and not os.path.exists(os.path.join(SEC, "groq.env")))
c, b = req(url, {"k": GOOD})
f = os.path.join(SEC, "groq.env")
check("верный ключ — groq.env 600 в папке 700, строка GROQ_API_KEY='…' (её читает скрипт голоса)", c == 200 and os.path.exists(f)
      and oct(os.stat(f).st_mode & 0o777) == "0o600" and oct(os.stat(SEC).st_mode & 0o777) == "0o700" and open(f).read().strip() == "GROQ_API_KEY='%s'" % GOOD)
time.sleep(1.0)
check("после сохранения страница погасла (порт свободен)", not wait_port(port) if False else (lambda: (lambda s: (s.connect_ex(("127.0.0.1", port)) != 0, s.close())[0])(socket.socket()))())
check("ключ нигде не в выводе команды", GOOD not in r.stdout + r.stderr)
# script reads the saved key
H2 = os.path.join(os.path.dirname(H), "install", "transcribe-voice.sh")
out = subprocess.run(["bash", "-c", 'source <(sed -n "/^safe_key()/,/^  *sed -E/p" "$1"); safe_key groq GROQ_API_KEY', "x", H2], env=dict(os.environ, SAFE_DIR=SEC), capture_output=True, text=True).stdout.strip()
check("скрипт голоса читает этот ключ (safe_key groq)", out == GOOD, out[:12])
r = subprocess.run([sys.executable, os.path.join(H, "key_page.py"), "groq"], env=dict(os.environ, PORT=str(free()), MILA_SECRETS=SEC, MILA_PUBLIC_URL="", RAILWAY_PUBLIC_DOMAIN=""), capture_output=True, text=True, timeout=20)
check("нет публичного адреса — код 2 и строка «put GROQ_API_KEY into the platform's variables»", r.returncode == 2 and "GROQ_API_KEY" in r.stdout and "/k/" not in r.stdout, r.stdout)
r = subprocess.run([sys.executable, os.path.join(H, "key_page.py"), "x"], capture_output=True, text=True, timeout=20)
check("неизвестный вид ключа — код 2", r.returncode == 2)
# Deepgram: the same page, its own header (Token) and file
DGK = "a1b2c3d4" * 5
class FakeDG(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        okk = self.headers.get("Authorization") == "Token " + DGK
        b = b'{"projects": []}'; self.send_response(200 if okk else 401); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
dg = http.server.ThreadingHTTPServer(("127.0.0.1", 0), FakeDG); threading.Thread(target=dg.serve_forever, daemon=True).start()
port = free(); e = env(port); e["KEY_CHECK_URL"] = "http://127.0.0.1:%d/v1/projects" % dg.server_port
r = subprocess.run([sys.executable, os.path.join(H, "key_page.py"), "deepgram"], env=e, capture_output=True, text=True, timeout=20)
url = r.stdout.strip(); wait_port(port)
c, b = req(url); check("deepgram: форма про console.deepgram.com", c == 200 and "console.deepgram.com" in b)
c, b = req(url, {"k": DGK}); f2 = os.path.join(SEC, "deepgram.env")
check("deepgram: ключ проверен заголовком Token и сохранён в deepgram.env 600", c == 200 and os.path.exists(f2) and open(f2).read().strip() == "DEEPGRAM_API_KEY='%s'" % DGK
      and oct(os.stat(f2).st_mode & 0o777) == "0o600")
dg.shutdown()
api.shutdown(); shutil.rmtree(T, ignore_errors=True); print("итог %d/%d" % (ok, n)); sys.exit(0 if ok == n else 1)
