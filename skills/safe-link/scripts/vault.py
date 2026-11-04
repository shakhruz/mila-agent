#!/usr/bin/env python3
"""Ключи Милы по слотам — для плеера рождения и Пульта. Значения не печатает никогда.
  vault.py has <слот>     → {"slot": …, "has": true, "from": "env"|"safe"}
  vault.py probe <слот>   → {"slot": …, "ok": true, …} — живая проба ключа у поставщика (без значения и без начала ключа)
  в коде: from vault import has, probe
Слоты: openrouter_key, groq_key, bot_token. Где ищем: сначала переменная окружения (Docker -e и поля хостинга важнее файла),
потом сейф work/secrets/<имя>.env (его пишет seif.py по одноразовой ссылке; права шире 600 — не читаем)."""
import json, os, sys, urllib.error, urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from safe_read import read_safe, SafeError

SLOTS = {
    "openrouter_key": ("OPENROUTER_API_KEY", "openrouter"),
    "groq_key": ("GROQ_API_KEY", "groq"),
    "bot_token": ("TELEGRAM_BOT_TOKEN", "telegram"),
}
UA = "mila-agent-vault/1.0"   # поставщики за Cloudflare: Python-urllib получает 403 «error code: 1010»


def _find(slot, env=os.environ):
    if slot not in SLOTS:
        raise SafeError("нет такого слота: %s" % slot)
    var, name = SLOTS[slot]
    if (env.get(var) or "").strip():
        return env[var].strip(), "env"
    try:
        v = (read_safe(name).get(var) or "").strip()
    except SafeError as e:
        if "права" in str(e):
            raise
        v = ""
    return (v, "safe") if v else ("", "")


def has(slot, env=os.environ):
    v, src = _find(slot, env)
    return {"slot": slot, "has": bool(v), "from": src or None}


def _get(url, headers, opener, timeout):
    req = urllib.request.Request(url, headers={**headers, "User-Agent": UA})
    try:
        with opener(req, timeout=timeout) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, {}
    except Exception as e:
        return 0, {"_err": type(e).__name__}


def probe(slot, env=os.environ, opener=urllib.request.urlopen, timeout=15):
    v, src = _find(slot, env)
    if not v:
        return {"slot": slot, "ok": False, "why": "ключа нет — положить через Сейф"}
    if slot == "openrouter_key":
        st, j = _get("https://openrouter.ai/api/v1/key", {"Authorization": "Bearer " + v}, opener, timeout)
        if st == 200:
            d = j.get("data") or {}
            # limit_remaining — остаток ЛИМИТА КЛЮЧА (часто дневного), не деньги на счёте: человеку не называть «балансом»
            return {"slot": slot, "ok": True, "from": src, "free_tier": bool(d.get("is_free_tier")),
                    "key_limit_remaining": d.get("limit_remaining"), "limit_reset": d.get("limit_reset"), "usage": d.get("usage")}
    elif slot == "groq_key":
        st, j = _get("https://api.groq.com/openai/v1/models", {"Authorization": "Bearer " + v}, opener, timeout)
        if st == 200:
            ids = [m.get("id", "") for m in j.get("data") or []]
            return {"slot": slot, "ok": True, "from": src, "whisper": any("whisper" in i for i in ids)}
    else:
        st, j = _get("https://api.telegram.org/bot%s/getMe" % v, {}, opener, timeout)
        if st == 200 and j.get("ok"):
            return {"slot": slot, "ok": True, "from": src, "username": (j.get("result") or {}).get("username")}
    why = {401: "ключ не принят (401)", 402: "нет средств на ключе (402)", 403: "отказ поставщика (403)", 404: "ключ не принят (404)",
           429: "предел запросов (429)", 0: "поставщик не ответил"}.get(st, "ошибка поставщика (%s)" % st)
    return {"slot": slot, "ok": False, "from": src, "status": st, "why": why}


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] not in ("has", "probe"):
        sys.exit(__doc__)
    try:
        out = (has if sys.argv[1] == "has" else probe)(sys.argv[2])
    except SafeError as e:
        out = {"slot": sys.argv[2], "ok": False, "why": str(e)}
    print(json.dumps(out, ensure_ascii=False))
    sys.exit(0 if out.get("ok", out.get("has")) else 1)
