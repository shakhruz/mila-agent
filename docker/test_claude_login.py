#!/usr/bin/env python3
"""claude_login.py против поддельного Telegram и поддельного `claude setup-token` (печатает ссылку, ждёт код, печатает токен):
/start → кнопка со ссылкой; чужой при OWNER_ID — одна строка, без ссылки; код не похож — просьба; верный код → сообщение с кодом
удалено, токен в томе 600 (папка 700), хозяин записан, «подключено», код 0; неверный код — «не подошёл», ничего не сохранено;
токен и код не попадают в вывод. Run: python3 test_claude_login.py"""
import http.server, json, os, shutil, socket, subprocess, sys, tempfile, threading, time, urllib.parse
OWN, OTH, STR = "555" + "000111", "555" + "000222", "555" + "000999"   # glued: no long id literals in the core
H = os.path.dirname(os.path.abspath(__file__)); ok = n = 0
def check(name, c, x=""):
    global ok, n; n += 1; ok += bool(c); print(("✅ " if c else "❌ ") + name + ("" if c else "  ← " + str(x)[:400]))
BOT = "1234567" + ":" + "A" * 35; TOKEN_OUT = "sk-" + "ant-" + "oat01-" + "Z" * 40; CODE = "abcDEF123456-code#state"
T = tempfile.mkdtemp(prefix="clogin-")
fake = os.path.join(T, "fake-setup-token.py")
open(fake, "w").write("""import sys, time
print("Opening browser to sign in...")
print("If the browser didn't open, visit: https://claude.ai/oauth/authorize?code=true&client_id=x&state=s")
sys.stdout.flush()
code = input("Paste code here if prompted > ").strip()
if code == %r:
    print("Your OAuth token (valid for 1 year):"); print(%r)
else:
    print("OAuth error: invalid code")
sys.stdout.flush(); time.sleep(0.2)
""" % (CODE, TOKEN_OUT))
class S:
    queue, sent, deleted = [], [], []
class Fake(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_POST(self):
        body = urllib.parse.parse_qs(self.rfile.read(int(self.headers.get("Content-Length") or 0)).decode())
        method = self.path.rsplit("/", 1)[-1]
        if method == "getUpdates":
            time.sleep(0.2); res = S.queue[:]; del S.queue[:]
        elif method == "sendMessage":
            S.sent.append({k: v[0] for k, v in body.items()}); res = {"message_id": len(S.sent)}
        elif method == "deleteMessage":
            S.deleted.append(body.get("message_id", [""])[0]); res = True
        else:
            res = True
        b = json.dumps({"ok": True, "result": res}).encode()
        try:
            self.send_response(200); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
        except OSError:
            pass   # the helper was stopped mid-poll
srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Fake); threading.Thread(target=srv.serve_forever, daemon=True).start()
uid = [0]
def msg(frm, text, mid):
    uid[0] += 1; return {"update_id": uid[0], "message": {"message_id": mid, "chat": {"id": frm, "type": "private"}, "from": {"id": frm}, "text": text}}
def start(owner="", ttl="600"):
    S.queue.clear(); S.sent.clear(); S.deleted.clear()
    env = dict(os.environ, TELEGRAM_BOT_TOKEN=BOT, TG_API="http://127.0.0.1:%d" % srv.server_port, MILA_AUTH_DIR=os.path.join(T, "auth"),
               LOGIN_CMD="%s %s" % (sys.executable, fake), OWNER_ID=owner, LINK_TTL=ttl)
    return subprocess.Popen([sys.executable, os.path.join(H, "claude_login.py")], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
def wait(cond, t=15):
    end = time.time() + t
    while time.time() < end:
        if cond(): return True
        time.sleep(0.1)
    return False
# 1) no OWNER_ID: a pairing code in the container log; a stranger who only knows the bot name gets nothing
p = start()
line = p.stdout.readline()
import re as _re
PAIR = (_re.search(r"pairing code ([A-Z2-9]{6})", line) or [None, ""])[1]
check("без OWNER_ID — код пары в журнале контейнера", len(PAIR) == 6, line)
S.queue.append(msg(int(STR), "/start", 5))
check("чужой /start без кода — «подключает её хозяин», без ссылки, вход не стартует", wait(lambda: any("подключает её хозяин" in m["text"] for m in S.sent)) and not any("reply_markup" in m for m in S.sent), S.sent)
S.queue.append(msg(int(STR), "/pair ZZZZZZ", 6))
check("неверный код пары — «не подошёл», хозяином не стал", wait(lambda: any("Код не подошёл" in m["text"] for m in S.sent)) and not any("reply_markup" in m for m in S.sent))
S.queue.append(msg(int(OWN), "/pair " + PAIR.lower(), 10))
check("/start → кнопка со ссылкой Anthropic", wait(lambda: any("reply_markup" in m and "claude.ai/oauth" in m["reply_markup"] for m in S.sent)), S.sent)
S.queue.append(msg(int(OWN), "просто текст", 11))
check("не код — просьба прислать код целиком", wait(lambda: any("не похоже на код" in m["text"] for m in S.sent)))
S.queue.append(msg(int(OWN), CODE, 12))
check("верный код → процесс завершился с кодом 0", wait(lambda: p.poll() is not None, 20) and p.returncode == 0, p.poll())
out, err = p.communicate(); out = line + out
A = os.path.join(T, "auth")
check("сообщение с кодом удалено из чата", "12" in S.deleted, S.deleted)
check("токен в томе: файл 600, папка 700, содержимое = токен", open(os.path.join(A, "oauth_token")).read().strip() == TOKEN_OUT
      and oct(os.stat(os.path.join(A, "oauth_token")).st_mode & 0o777) == "0o600" and oct(os.stat(A).st_mode & 0o777) == "0o700")
check("хозяин = тот, кто прислал код пары и прошёл вход", open(os.path.join(A, "owner_id")).read().strip() == OWN)
check("«подписка подключена» хозяину", any("подключена" in m["text"] for m in S.sent))
check("ни токен, ни код не попали в вывод и в сообщения", TOKEN_OUT not in out + err and CODE not in out + err and not any(TOKEN_OUT in json.dumps(m) or CODE in json.dumps(m) for m in S.sent))
shutil.rmtree(A)
# 2) OWNER_ID set: stranger refused; wrong code → nothing saved
p = start(owner=OWN)
S.queue.append(msg(int(OTH), "/start", 20))
check("при OWNER_ID чужой — одна строка, без ссылки", wait(lambda: any("подключает её хозяин" in m["text"] for m in S.sent)) and not any("reply_markup" in m for m in S.sent), S.sent)
S.queue.append(msg(int(OWN), "/login", 21))
wait(lambda: any("reply_markup" in m for m in S.sent))
S.queue.append(msg(int(OWN), "wrongcode123456", 22))
check("неверный код — «не подошёл», ничего не сохранено, ждёт дальше", wait(lambda: any("не подошёл" in m["text"] for m in S.sent)) and not os.path.exists(os.path.join(A, "oauth_token")) and p.poll() is None)
p.terminate(); p.wait()
# 3) bad env
r = subprocess.run([sys.executable, os.path.join(H, "claude_login.py")], env=dict(os.environ, TELEGRAM_BOT_TOKEN="x"), capture_output=True, text=True)
check("нет токена бота — код 2, понятная строка", r.returncode == 2 and "TELEGRAM_BOT_TOKEN" in r.stderr)
srv.shutdown(); shutil.rmtree(T, ignore_errors=True); print("итог %d/%d" % (ok, n)); sys.exit(0 if ok == n else 1)
