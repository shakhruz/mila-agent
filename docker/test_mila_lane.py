#!/usr/bin/env python3
"""The strangers' lane: only the receiver's OS user is served; each answer is `claude -p` with no tools, no MCP, no settings,
in an empty folder, on the keeper's /guest route; limits per chat; knowledge only from the owner's folder for people.
A fake claude records what it was given. Run: python3 test_mila_lane.py"""
import json, os, socket, subprocess, sys, tempfile, time, shutil
H = os.path.dirname(os.path.abspath(__file__)); ok = n = 0
def check(name, c, x=""):
    global ok, n; n += 1; ok += bool(c); print(("✅ " if c else "❌ ") + name + ("" if c else "  ← " + str(x)[:300]))
T = tempfile.mkdtemp(prefix="lane-t-"); REC = os.path.join(T, "rec.json"); KD = os.path.join(T, "knowledge"); os.makedirs(KD)
FAKE = os.path.join(T, "claude")
open(FAKE, "w").write("#!%s\nimport json, os, sys\nd = {'argv': sys.argv[1:], 'stdin': sys.stdin.read(), 'cwd': os.getcwd(), 'env': dict(os.environ)}\n"
                      "open(%r, 'w').write(json.dumps(d))\nprint('Hello! I will pass it to the owner.')\n" % (sys.executable, REC))
os.chmod(FAKE, 0o700)
def start(sock, io_uid, **kw):
    env = dict(os.environ, MILA_IO_UID=str(io_uid), LANE_CLAUDE=FAKE, MILA_KEYD="http://127.0.0.1:8790", LANE_PER_MIN="2", **kw)
    p = subprocess.Popen([sys.executable, os.path.join(H, "mila_lane.py"), "serve", "--sock", sock, "--knowledge", KD], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(50):
        if os.path.exists(sock): break
        time.sleep(0.1)
    return p
def ask(sock, obj):
    s = socket.socket(socket.AF_UNIX); s.settimeout(30); s.connect(sock); s.sendall((json.dumps(obj) + "\n").encode())
    b = b""
    while not b.endswith(b"\n"):
        try: ch = s.recv(65536)
        except (ConnectionResetError, socket.timeout): break
        if not ch: break
        b += ch
    s.close(); return json.loads(b) if b.strip() else None
open(os.path.join(KD, "prices.md"), "w").write("Consultation: 50 USD")
open(os.path.join(T, "secret.md"), "w").write("OWNER SECRET"); os.symlink(os.path.join(T, "secret.md"), os.path.join(KD, "link.md"))
S1 = os.path.join(T, "lane.sock"); p1 = start(S1, os.getuid())
r = ask(S1, {"chat_id": "-100", "text": "how much is a consultation?"})
check("приёмник (свой пользователь) — получает ответ полосы", r == {"ok": True, "text": "Hello! I will pass it to the owner."}, r)
d = json.load(open(REC)); a = d["argv"]
check("claude -p без инструментов, без MCP, без настроек и хуков, без сохранения сессии",
      a[:2] == ["-p", "--tools"] and a[2] == "" and "--strict-mcp-config" in a and a[a.index("--mcp-config") + 1] == '{"mcpServers": {}}'
      and a[a.index("--setting-sources") + 1] == "" and "--no-session-persistence" in a, a)
check("ходит на маршрут чужих хранителя, ключа нет (заглушка), окружение — только нужное",
      d["env"]["ANTHROPIC_BASE_URL"] == "http://127.0.0.1:8790/guest" and d["env"]["ANTHROPIC_API_KEY"] == "mila-keyd-placeholder"
      and not any(k in d["env"] for k in ("CLAUDE_CODE_OAUTH_TOKEN", "TELEGRAM_BOT_TOKEN", "GROQ_API_KEY", "MILA_IO_UID")), sorted(d["env"]))
check("пустая временная папка, и она убрана после ответа", d["cwd"].startswith(tempfile.gettempdir()) and not os.path.exists(d["cwd"]), d["cwd"])
sp = a[a.index("--system-prompt") + 1]
check("в промпте — знания из папки для людей; ссылка из папки не читается", "Consultation: 50 USD" in sp and "OWNER SECRET" not in sp, sp[-200:])
check("текст чужого — на вход, не в промпт", d["stdin"] == "how much is a consultation?" and "consultation?" not in sp)
r2 = ask(S1, {"chat_id": "-100", "text": "again"}); r3 = ask(S1, {"chat_id": "-100", "text": "and again"})
check("предел на чат: третий за минуту — отказ «limit», claude не зовём", r2["ok"] and r3 == {"ok": False, "reason": "limit"}, (r2, r3))
check("…другой чат — свой предел", ask(S1, {"chat_id": "-200", "text": "hi"})["ok"])
check("пустой текст — отказ", ask(S1, {"chat_id": "-300", "text": "  "}) == {"ok": False, "reason": "empty"})
os.remove(os.path.join(KD, "prices.md")); ask(S1, {"chat_id": "-400", "text": "price?"}); sp = json.load(open(REC))["argv"]
sp = sp[sp.index("--system-prompt") + 1]
check("пустая папка знаний — промпт велит передать вопрос владельцу", "pass it on" in sp and "Consultation" not in sp)
check("сокет 0660 — только группа полосы", oct(os.stat(S1).st_mode & 0o777) == "0o660")
p1.terminate(); p1.wait()
S2 = os.path.join(T, "lane2.sock"); p2 = start(S2, 1)   # here this test's user is not the receiver
check("чужой пользователь ОС (сессия) — ни ответа, ни запуска claude", ask(S2, {"chat_id": "-500", "text": "hi"}) is None)
p2.terminate(); p2.wait()
os.remove(FAKE); open(FAKE, "w").write("#!/bin/sh\nexit 1\n"); os.chmod(FAKE, 0o700)
S3 = os.path.join(T, "lane3.sock"); p3 = start(S3, os.getuid())
check("claude упал — «no answer», без текста", ask(S3, {"chat_id": "-600", "text": "hi"}) == {"ok": False, "reason": "no answer"})
p3.terminate(); p3.wait()
shutil.rmtree(T, ignore_errors=True); print("итог %d/%d" % (ok, n)); sys.exit(0 if ok == n else 1)
