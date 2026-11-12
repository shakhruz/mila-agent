#!/usr/bin/env python3
"""«Свой Сейф» (С1): Мила владельца на его машине — seif.py own поднимает страницу на 127.0.0.1 на одну ссылку; сохранили — закрылась,
ключ в ~/work/secrets/<имя>.env (600); срок вышел — закрылась, ничего не записано; адрес — только 127.0.0.1. python3 test_seif_own.py"""
import json, os, shutil, subprocess, sys, tempfile, time, urllib.parse, urllib.request
H = os.path.dirname(os.path.abspath(__file__)); T = tempfile.mkdtemp(prefix="seif-own-"); ok = n = 0
def check(name, c, x=""):
    global ok, n; n += 1; ok += bool(c); print(("✅ " if c else "❌ ") + name + ("" if c else "  " + str(x)[:300]))
env = {k: v for k, v in os.environ.items() if not k.startswith("SEIF_")}; env.update(HOME=T, SEIF_DIR=os.path.join(T, "seif"))
KEY = "or-" + os.urandom(12).hex()
p = subprocess.Popen([sys.executable, os.path.join(H, "seif.py"), "own", "OPENROUTER_API_KEY", "--name", "openrouter", "--lang", "ru"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
first = json.loads(p.stdout.readline()); url = first["url"]
check("ссылка только на 127.0.0.1, случайный порт, срок 10 мин", url.startswith("http://127.0.0.1:") and first["expires_min"] == 10, first)
with urllib.request.urlopen(url) as r: b = r.read().decode()
check("страница открывается, поле ключа скрыто", "name=OPENROUTER_API_KEY type=password" in b)
ORIGIN = "http://" + urllib.parse.urlsplit(url).netloc
with urllib.request.urlopen(urllib.request.Request(url, data=urllib.parse.urlencode({"OPENROUTER_API_KEY": KEY}).encode(), method="POST", headers={"Origin": ORIGIN})) as r: b2 = r.read().decode()
out, err = p.communicate(timeout=20); last = json.loads(out.strip().splitlines()[-1])
envp = os.path.join(T, "work", "secrets", "openrouter.env")
check("сохранили — страница закрылась сама, процесс вышел с «ok»", p.returncode == 0 and last.get("ok") is True and "Сохранено" in b2, (last, err[-200:]))
check("ключ в ~/work/secrets/openrouter.env, файл 600, папка 700", os.path.exists(envp) and oct(os.stat(envp).st_mode & 0o777) == "0o600" and oct(os.stat(os.path.dirname(envp)).st_mode & 0o777) == "0o700")
check("значения нет ни в выводе, ни в журнале", KEY not in out and KEY not in open(os.path.join(T, "seif", "journal.jsonl")).read())
try: urllib.request.urlopen(url, timeout=2); closed = False
except Exception: closed = True
check("после сохранения страница недоступна", closed)
p2 = subprocess.Popen([sys.executable, os.path.join(H, "seif.py"), "own", "SITE_PASSWORD", "--ttl", "0.05"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
u2 = json.loads(p2.stdout.readline())["url"]; out2, _ = p2.communicate(timeout=30); last2 = json.loads(out2.strip().splitlines()[-1])
check("срок вышел — закрылась, «ничего не сохранено», файла нет", last2 == {"ok": False, "closed": True, "why": "срок вышел — ничего не сохранено"} and not os.path.exists(os.path.join(T, "work", "secrets", "keys.env")), last2)
check("ссылка после срока не оживает (токен удалён)", not os.listdir(os.path.join(T, "seif", "tokens")))
_gone = [json.load(open(os.path.join(H, "locales", f), encoding="utf-8")).get("seif.gone.p", "") for f in sorted(os.listdir(os.path.join(H, "locales"))) if f.endswith(".json")]
check("страница «ссылка не работает» не называет минут: у своего Сейфа срок 10, у службы 30", _gone and all(t and not any(c.isdigit() for c in t) for t in _gone), _gone)
# the own page does not ask the network for its own name: socket.getfqdn can hang for half a minute on a Mac (CI 12.11)
import socket; sys.path.insert(0, H); sys.argv = ["seif.py"]; import seif as SE
asked = []; _fq = socket.getfqdn; socket.getfqdn = lambda *a: asked.append(a) or _fq(*a)
srv_ = SE.OwnServer(("127.0.0.1", 0), SE.H); socket.getfqdn = _fq
check("свой Сейф поднимает страницу без socket.getfqdn (на Маке он висит)", not asked and srv_.server_name == "127.0.0.1", asked); srv_.server_close()
shutil.rmtree(T, ignore_errors=True); print(f"итог {ok}/{n}"); sys.exit(0 if ok == n else 1)
