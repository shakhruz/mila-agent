#!/usr/bin/env python3
"""vault: слот из env важнее сейфа; сейф 644 — отказ; проба без значения в ответе; 401/402/429 — понятная причина; User-Agent свой.
  python3 skills/safe-link/scripts/test_vault.py"""
import io, json, os, subprocess, sys, tempfile, urllib.error
H = os.path.dirname(os.path.abspath(__file__))
T = tempfile.mkdtemp(); os.environ["SAFE_DIR"] = T
sys.path.insert(0, H)
import vault
from safe_read import SafeError, read_safe
ok = n = 0
def chk(m, c, x=""):
    global ok, n
    n += 1; ok += bool(c); print(("✅ " if c else "❌ ") + m + ("" if c else "  ← " + str(x)[:300]))
KEY = "sk-" + "or-v1-" + "test" + "0" * 20          # склейкой: сканеры секретов не видят цельного префикса
GKEY = "gsk" + "_" + "test" + "1" * 20
def put(name, line, mode=0o600):
    p = os.path.join(T, name + ".env"); open(p, "w").write(line + "\n"); os.chmod(p, mode)
class R:
    def __init__(s, st, body): s.status = st; s.b = json.dumps(body).encode()
    def read(s): return s.b
    def __enter__(s): return s
    def __exit__(s, *a): pass
seen = []
def opener_for(st, body):
    def op(req, timeout=0):
        seen.append(req)
        if st != 200: raise urllib.error.HTTPError(req.full_url, st, "x", {}, io.BytesIO(b""))
        return R(st, body)
    return op

chk("нет ключа нигде — has false", vault.has("openrouter_key", env={}) == {"slot": "openrouter_key", "has": False, "from": None})
put("openrouter", "OPENROUTER_API_KEY='%s'" % KEY)
chk("ключ в сейфе — has true, from safe", vault.has("openrouter_key", env={})["from"] == "safe")
chk("env важнее сейфа (Docker -e)", vault.has("openrouter_key", env={"OPENROUTER_API_KEY": "x" + KEY})["from"] == "env")
os.chmod(os.path.join(T, "openrouter.env"), 0o644)
try: vault.has("openrouter_key", env={}); r = False
except SafeError: r = True
chk("сейф открыт другим (644) — отказ, не «ключа нет»", r)
os.chmod(os.path.join(T, "openrouter.env"), 0o600)
try: vault.has("nope", env={}); r = False
except SafeError: r = True
chk("неизвестный слот — отказ", r)

p = vault.probe("openrouter_key", env={}, opener=opener_for(200, {"data": {"is_free_tier": False, "limit_remaining": 2.9, "limit_reset": "daily", "usage": 0.1}}))
chk("проба OpenRouter: остаток — key_limit_remaining + limit_reset, слов balance/limit_remaining нет", p["key_limit_remaining"] == 2.9 and p["limit_reset"] == "daily" and "balance" not in json.dumps(p) and "\"limit_remaining\"" not in json.dumps(p), p)
p = vault.probe("openrouter_key", env={}, opener=opener_for(200, {"data": {"is_free_tier": True, "limit_remaining": None, "usage": 0}}))
chk("проба OpenRouter 200: ok, free_tier", p["ok"] and p["free_tier"] is True, p)
chk("проба: значения ключа нет в ответе", KEY not in json.dumps(p) and KEY[:12] not in json.dumps(p))
chk("проба: свой User-Agent (не Python-urllib — Cloudflare 1010)", seen[-1].get_header("User-agent") == vault.UA)
chk("проба: ключ уходит только в Authorization к openrouter.ai", seen[-1].full_url == "https://openrouter.ai/api/v1/key" and seen[-1].get_header("Authorization") == "Bearer " + KEY)
for st, word in ((401, "не принят"), (402, "нет средств"), (429, "предел")):
    p = vault.probe("openrouter_key", env={}, opener=opener_for(st, {}))
    chk("проба %d → ok false, «%s»" % (st, word), not p["ok"] and word in p["why"] and p["status"] == st, p)
def boom(req, timeout=0): raise OSError("net")
p = vault.probe("openrouter_key", env={}, opener=boom)
chk("сеть упала → «поставщик не ответил», без исключения", not p["ok"] and "не ответил" in p["why"], p)
chk("проба без ключа → «положить через Сейф», в сеть не ходим", vault.probe("groq_key", env={}, opener=boom)["why"].endswith("через Сейф"))

put("groq", "GROQ_API_KEY='%s'" % GKEY)
p = vault.probe("groq_key", env={}, opener=opener_for(200, {"data": [{"id": "whisper-large-v3"}, {"id": "llama"}]}))
chk("Groq 200: ok и whisper есть (слух)", p["ok"] and p["whisper"] is True, p)
TOK = "123456" + ":" + "AA" + "test" * 5
p = vault.probe("bot_token", env={"TELEGRAM_BOT_TOKEN": TOK}, opener=opener_for(200, {"ok": True, "result": {"username": "test_bot"}}))
chk("бот: getMe → username, токена в ответе нет", p["ok"] and p["username"] == "test_bot" and TOK not in json.dumps(p), p)

env = {**os.environ, "SAFE_DIR": T, "OPENROUTER_API_KEY": ""}
r = subprocess.run([sys.executable, "-I", os.path.join(H, "vault.py"), "has", "openrouter_key"], capture_output=True, text=True, env=env)
chk("CLI has: код 0, JSON, значения нет", r.returncode == 0 and json.loads(r.stdout)["has"] and KEY not in r.stdout + r.stderr, r.stdout + r.stderr)
r = subprocess.run([sys.executable, "-I", os.path.join(H, "vault.py"), "has", "groq"], capture_output=True, text=True, env=env)
chk("CLI: неизвестный слот → код 1 и причина", r.returncode == 1 and "нет такого слота" in r.stdout, r.stdout)
for i, line in enumerate(("GROQ_API_KEY=\"%s\"" % GKEY, "GROQ_API_KEY=%s\r" % GKEY, "GROQ_API_KEY=%s " % GKEY, "export GROQ_API_KEY=%s" % GKEY, "GROQ_API_KEY = %s" % GKEY), 1):
    p_ = os.path.join(T, "groq.env"); open(p_, "w", newline="").write(line + "\n"); os.chmod(p_, 0o600)
    seen.clear(); r_ = read_safe("groq")
    vault.probe("groq_key", env={}, opener=opener_for(200, {"data": []}))
    chk("ручная форма %d (кавычки/CRLF/пробел/export/« = ») — read_safe и заголовок: ровно ключ" % i, r_.get("GROQ_API_KEY") == GKEY and len(seen) == 1 and seen[0].get_header("Authorization") == "Bearer " + GKEY, (repr(r_.get("GROQ_API_KEY", ""))[-12:], len(seen)))
open(os.path.join(T, "groq.env"), "w").write(("GROQ_API_KEY" "=" "old1\n" "GROQ_API_KEY" "=%s\n") % GKEY)
chk("две строки поля — read_safe берёт последнюю (как sh)", read_safe("groq")["GROQ_API_KEY"] == GKEY)
import shutil; shutil.rmtree(T)
print("итог %d/%d" % (ok, n)); sys.exit(0 if ok == n else 1)
