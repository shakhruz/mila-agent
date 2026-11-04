#!/usr/bin/env python3
"""Журнал доставки для скриптов ядра, которые шлют в Telegram сами, мимо плагина (heartbeat, bot_send, limit_watch, subscription_watch).
Тот же формат, файл и соль, что у плагина mila-telegram (delivery.mjs): $TELEGRAM_STATE_DIR (по умолчанию ~/.claude/channels/telegram)/
delivery.jsonl (600), чат — HMAC с солью delivery.salt (600, вне журнала), без текста; delivery-status.json — счёт по классам за сутки.
Сигнал хозяину о сбое шлёт плагин; здесь только запись — скрипт не должен будить хозяина сам.
    from tg_delivery import record, call
    ok = call(urlopen_request_fn, "sendMessage", chat_id)   # или record(method, chat_id, ok, code, desc)"""
import datetime as dt, hashlib, hmac, json, os, re, secrets, urllib.error

NOISE = re.compile(r"message is not modified|message to (edit|react|delete) not found|query is too old|MESSAGE_NOT_MODIFIED", re.I)


def state_dir():
    return os.path.expanduser(os.environ.get("TELEGRAM_STATE_DIR") or "~/.claude/channels/telegram")


def classify(code, desc):
    d = str(desc or "")
    if not code:
        return "network"
    if NOISE.search(d):
        return "noise"
    if code == 429:
        return "rate"
    if re.search(r"bot was blocked by the user|user is deactivated|USER_IS_BLOCKED", d, re.I):
        return "blocked"
    if re.search(r"chat not found|bot was kicked|group chat was deleted|bot is not a member|PEER_ID_INVALID|chat was upgraded", d, re.I):
        return "no_chat"
    if re.search(r"not enough rights|have no rights|CHAT_WRITE_FORBIDDEN|need administrator rights|CHAT_ADMIN_REQUIRED", d, re.I):
        return "no_rights"
    return "other"


def _salt(d):
    p = os.path.join(d, "delivery.salt")
    try:
        s = open(p).read().strip()
        if re.fullmatch(r"[0-9a-f]{64}", s):
            return s
    except OSError:
        pass
    s = secrets.token_hex(32)
    fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(s)
    return s


def _kind(chat):
    c = str(chat)
    return "channel_or_super" if c.startswith(("-100", "@")) else "group" if c.startswith("-") else "dm"


def record(method, chat, ok, code=None, desc=None, via="core", now=None):
    """Одна строка в журнал доставки. Ошибки записи не роняют скрипт."""
    try:
        d = state_dir(); os.makedirs(d, mode=0o700, exist_ok=True)
        h = hmac.new(_salt(d).encode(), str(chat).encode(), hashlib.sha256).hexdigest()[:16]
        cls = "ok" if ok else classify(code, desc)
        t = now or dt.datetime.now(dt.timezone.utc)
        row = {"ts": t.isoformat().replace("+00:00", "Z"), "m": method, "chat": h, "kind": _kind(chat), "ok": bool(ok), "cls": cls, "via": via}
        if not ok:
            row["code"] = code; row["desc"] = str(desc or "")[:120]
        fd = os.open(os.path.join(d, "delivery.jsonl"), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        with os.fdopen(fd, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
        sp = os.path.join(d, "delivery-status.json")
        try:
            st = json.load(open(sp))
        except (OSError, ValueError):
            st = {}
        try:   # сутки — по тому же поясу, что у плагина (TZ или Ташкент), иначе общий счёт обнуляется ночью
            from zoneinfo import ZoneInfo
            day = t.astimezone(ZoneInfo(os.environ.get("TZ") or "Asia/Tashkent")).strftime("%Y-%m-%d")
        except Exception:
            day = t.astimezone().strftime("%Y-%m-%d")
        if st.get("day") != day:
            st = {"day": day, "ok": 0, "fail": {}}
        if ok:
            st["ok"] = st.get("ok", 0) + 1
        elif cls != "noise":
            st.setdefault("fail", {})[cls] = st.get("fail", {}).get(cls, 0) + 1
        tmp = sp + ".tmp"
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            json.dump(st, f)
        os.replace(tmp, sp)
        return cls
    except Exception:
        return None


def call(do, method, chat, via="core"):
    """do() — сам HTTP-запрос к Bot API, возвращает разобранный JSON ответа. Пишет строку и возвращает (ok, ответ).
    HTTPError Telegram (400/403/429) разбирается: его description — в журнал; сеть — класс network. Исключение наружу не летит."""
    try:
        r = do()
        ok = bool(r.get("ok"))
        record(method, chat, ok, r.get("error_code"), r.get("description"), via)
        return ok, r
    except urllib.error.HTTPError as e:
        try:
            body = json.loads(e.read().decode() or "{}")
        except Exception:
            body = {}
        record(method, chat, False, e.code, body.get("description") or str(e), via)
        return False, body
    except Exception as e:
        record(method, chat, False, None, type(e).__name__, via)
        return False, {}
