#!/usr/bin/env python3
"""Ключ или токен в сообщении человека — ловим ДО модели (сценарий рождения, состояние X_secret_in_chat).
  echo "<текст>" | key_in_chat.py   → {"hit": true, "kinds": ["openrouter"], "revoke": ["https://openrouter.ai/keys"]} ; код 1 — нашли
  в коде: from key_in_chat import detect, redact
Значение не возвращается никогда: только вид ключа и где его перевыпустить. redact() — текст для журнала и модели, ключ заменён.
Токен бота ловится и внутри ссылки (…/bot<id>:<хвост>/getMe). Ограничение: ключ, разорванный пробелом, ловится по первой
половине (hit, перевыпуск предложим), вторая половина в redact остаётся — поэтому при hit перевыпуск обязателен, не по желанию."""
import json, re, sys

_ZW = re.compile("[\u00ad\u180e\u200b-\u200f\u202a-\u202e\u2060\u2066-\u2069\ufeff]")   # невидимые и управляющие символы внутри ключа не спасают его от поимки
# порядок важен: частные виды раньше общего sk-
KINDS = [
    ("openrouter", r"\bsk" r"-or-v1-[A-Za-z0-9]{32,}", "https://openrouter.ai/keys"),
    ("anthropic", r"\bsk" r"-ant-[A-Za-z0-9_-]{20,}", "https://console.anthropic.com/settings/keys"),
    ("groq", r"\bgsk" r"_[A-Za-z0-9]{20,}", "https://console.groq.com/keys"),
    ("telegram_bot", r"(?<![0-9])\d{6,12}:[A-Za-z0-9_-]{30,50}\b", "@BotFather → /revoke"),
    ("github", r"\bgh[pousr]_[A-Za-z0-9]{20,}", "https://github.com/settings/tokens"),
    ("aws", r"\b(?:AK" r"IA|AS" r"IA)[0-9A-Z]{16}\b", "AWS IAM → Access keys"),
    ("slack", r"\bxox[abprs]-[A-Za-z0-9-]{10,}", "Slack → Apps → OAuth"),
    ("api_key", r"\b(?:sk|pk)[-_][A-Za-z0-9_-]{16,}", "там, где ключ выпущен"),
]
_RES = [(k, re.compile(p), r) for k, p, r in KINDS]


def _spans(text):
    t = _ZW.sub("", str(text or "")); out = []
    for kind, rx, rev in _RES:
        for m in rx.finditer(t):
            if not any(a <= m.start() < b for a, b, _, _ in out):   # ключ OpenRouter уже пойман — общий вид его не дублирует
                out.append((m.start(), m.end(), kind, rev))
    return t, sorted(out)


def detect(text):
    _, sp = _spans(text)
    kinds = list(dict.fromkeys(k for _, _, k, _ in sp))
    revoke = list(dict.fromkeys(r for _, _, _, r in sp))
    return {"hit": bool(sp), "kinds": kinds, "revoke": revoke}


def redact(text):
    t, sp = _spans(text)
    for a, b, kind, _ in reversed(sp):
        t = t[:a] + "[ключ скрыт: %s]" % kind + t[b:]
    return t


if __name__ == "__main__":
    r = detect(sys.stdin.read())
    print(json.dumps(r, ensure_ascii=False))
    sys.exit(1 if r["hit"] else 0)
