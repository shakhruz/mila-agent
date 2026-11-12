#!/usr/bin/env python3
"""token_page.py против поддельного Telegram (getMe): форма на английском по умолчанию и на языке браузера; не токен и чужой
токен — ошибка без сохранения; верный — файлы 600 в папке 700 (токен, код пары, метка), ссылка t.me/<бот>?start=pair_<код>,
страница гаснет; второй запуск не слушает вовсе; срок вышел и предел попыток — закрыта без токена (код 3);
ни токен, ни код не в выводе. Run: python3 test_token_page.py"""
import http.server, json, os, re, shutil, socket, subprocess, sys, tempfile, threading, time, urllib.error, urllib.parse, urllib.request
H = os.path.dirname(os.path.abspath(__file__)); ok = n = 0
def check(name, c, x=""):
    global ok, n; n += 1; ok += bool(c); print(("✅ " if c else "❌ ") + name + ("" if c else "  ← " + str(x)[:300]))
GOOD = "1234567" + ":" + "A" * 35; OTHER = "7654321" + ":" + "B" * 35
class Fake(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        ok_ = GOOD in self.path
        b = json.dumps({"ok": ok_, "result": {"is_bot": True, "username": "mila_demo_bot"}} if ok_ else {"ok": False}).encode()
        self.send_response(200 if ok_ else 401); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
tg = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Fake); threading.Thread(target=tg.serve_forever, daemon=True).start()
T = tempfile.mkdtemp(prefix="tpage-")
def free():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p
def run(auth, ttl="60"):
    port = free()
    p = subprocess.Popen([sys.executable, os.path.join(H, "token_page.py")], env=dict(os.environ, PORT=str(port), BIND="127.0.0.1", MILA_AUTH_DIR=auth,
                         TG_API="http://127.0.0.1:%d" % tg.server_port, PAGE_TTL=ttl), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    for _ in range(50):
        try: socket.create_connection(("127.0.0.1", port), timeout=0.2).close(); break
        except OSError: time.sleep(0.1)
    return p, "http://127.0.0.1:%d/" % port
def req(url, data=None, lang=None, xff=None):
    r = urllib.request.Request(url, data=urllib.parse.urlencode(data).encode() if data else None)
    if lang: r.add_header("Accept-Language", lang)
    if xff: r.add_header("X-Forwarded-For", xff)
    try:
        with urllib.request.urlopen(r, timeout=20) as x: return x.status, x.read().decode()
    except urllib.error.HTTPError as e: return e.code, e.read().decode()
A = os.path.join(T, "auth"); p, U = run(A)
c, b = req(U); check("форма: по умолчанию английский, лицо Милы внутри (data:), без внешних адресов", c == 200 and "Hi, I am Mila" in b and "data:image/webp;base64," in b and not re.search(r"(src|href)=['\"]?https?:", b), b[:200])
check("единый вид: общий стиль страницы рождения (portrait, card, serif heading), поле не меньше 16 px, без внешних адресов", "class=card" in b and "class=av" in b and "Georgia" in b and "font:16px" in b and "color-scheme" in b and not re.search(r"https?://(?!www\.w3\.org)", b), b[:300])
check("приветствия сменяют друг друга: hello, hola, здравствуйте, salom, 你好 — только CSS, без скриптов", all(w in b for w in ("hello", "hola", "здравствуйте", "salom", "你好")) and "@keyframes" in b and "<script" not in b)
c, b = req(U, lang="ru-RU,ru;q=0.9,en;q=0.8"); check("поле не похоже на пароль: type=text, без автозаполнения и менеджеров паролей", "type=text" in b and "type=password" not in b and "autocomplete=off" in b and "data-1p-ignore" in b and "name=bt" in b)
check("язык браузера ru → форма по-русски", "Привет, я Мила" in b and 'lang=ru' in b)
c, b = req(U, lang="uz"); check("uz → по-узбекски", "Salom, men Milaman" in b)
c, b = req(U, {"bt": "hello"}); check("не токен — просьба, ничего не сохранено", "not look like a bot token" in b and not os.path.exists(os.path.join(A, "bot_token")))
c, b = req(U, {"bt": OTHER}); check("Telegram не узнал токен — просьба, ничего не сохранено", "did not recognise" in b and not os.path.exists(os.path.join(A, "bot_token")))
c, b = req(U, {"bt": GOOD}, lang="en")
code = (re.search(r"start=pair_([A-Z2-9]{6})", b) or [None, ""])[1]
check("верный токен — ссылка t.me/<бот>?start=pair_<код>", c == 200 and "https://t.me/mila_demo_bot?start=pair_" in b and len(code) == 6, b[-400:])
check("экран «готово»: Мила просыпается (.mila-wake) — без <script> и без внешних адресов, кроме ссылки на бота",
      'class="mila-wake"' in b and "<script" not in b.lower() and not [u for u in re.findall(r"https?://[^\s'\"<>]+", b) if not u.startswith(("https://t.me/", "http://www.w3.org/"))],
      re.findall(r"https?://[^\s'\"<>]+", b))
check("токен, код пары и метка — файлы 600, папка 700", open(os.path.join(A, "bot_token")).read().strip() == GOOD and open(os.path.join(A, "pair_code")).read().strip() == code
      and all(oct(os.stat(os.path.join(A, f)).st_mode & 0o777) == "0o600" for f in ("bot_token", "pair_code", "token_page.done")) and oct(os.stat(A).st_mode & 0o777) == "0o700")
check("страница погасла сама, код 0", p.wait(timeout=10) == 0)
out, err = p.communicate()
check("ни токен, ни код не в выводе", GOOD not in out + err and code not in out + err and "token saved for @mila_demo_bot" in out, out + err)
p2 = subprocess.run([sys.executable, os.path.join(H, "token_page.py")], env=dict(os.environ, PORT=str(free()), MILA_AUTH_DIR=A), capture_output=True, text=True, timeout=10)
check("второй запуск после сохранения — сразу выход, порт не слушается", p2.returncode == 0 and p2.stdout == "")
A2 = os.path.join(T, "a2"); p, U = run(A2, ttl="2"); time.sleep(2.3)
check("срок вышел — страница не принимает токен (410) ещё до выхода процесса", req(U, {"bt": GOOD})[0] == 410 and not os.path.exists(os.path.join(A2, "bot_token")))
time.sleep(1.2)
check("срок вышел — закрыта без токена, код 3, строка «restart the service»", p.wait(timeout=10) == 3 and "restart the service" in p.stdout.read() and not os.path.exists(os.path.join(A2, "bot_token")))
A3 = os.path.join(T, "a3"); p, U = run(A3)
codes = [req(U, {"bt": "x"}, xff="1.2.3.4")[0] for _ in range(6)]
for i in range(30): req(U, {"bt": ""}, xff="10.1.0.%d" % i)
check("30 пустых или «не токенов» с разных адресов — страница НЕ закрыта (в общий предел не идут)", req(U, xff="10.2.0.1")[0] == 200)
check("5 попыток с одного адреса за 10 мин, шестая — 429", codes[:5] == [200] * 5 and codes[5] == 429, codes)
for i in range(20): req(U, {"bt": OTHER}, xff="10.0.0.%d" % i)
c, b = req(U, {"bt": GOOD}, xff="10.9.9.9")
check("20 настоящих попыток (токен Telegram не узнал) — страница закрыта даже для верного", c == 410 and not os.path.exists(os.path.join(A3, "bot_token")), (c, b[:100]))
p.terminate(); p.wait()
tg.shutdown(); shutil.rmtree(T, ignore_errors=True); print("итог %d/%d" % (ok, n)); sys.exit(0 if ok == n else 1)
