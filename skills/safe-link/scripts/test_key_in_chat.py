#!/usr/bin/env python3
"""key_in_chat: ключи ловятся до модели (вид и где перевыпустить, без значения); обычный текст, время, телефоны, ссылки — не ключи.
Все фальшивки — склейкой. python3 skills/safe-link/scripts/test_key_in_chat.py"""
import json, os, subprocess, sys
H = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, H)
from key_in_chat import detect, redact
ok = n = 0
def chk(m, c, x=""):
    global ok, n
    n += 1; ok += bool(c); print(("✅ " if c else "❌ ") + m + ("" if c else "  ← " + str(x)[:300]))
OR = "sk-" + "or-v1-" + "a1b2c3d4" * 8
ANT = "sk-" + "ant-" + "api03-" + "Zx9" * 10
GQ = "gsk" + "_" + "Q" * 52
TG = "123456" + "7890" + ":" + "AAH" + "x1Y2z3" * 6
GH = "gh" + "p_" + "A1" * 18
cases = [("openrouter", "вот мой ключ " + OR), ("anthropic", ANT), ("groq", "ключ groq: " + GQ), ("telegram_bot", "токен " + TG), ("github", GH)]
for kind, txt in cases:
    r = detect(txt)
    chk("ловит %s" % kind, r["hit"] and r["kinds"] == [kind], r)
chk("OpenRouter не дублируется общим sk-", detect(OR)["kinds"] == ["openrouter"])
chk("перевыпуск: OpenRouter → openrouter.ai/keys, бот → @BotFather /revoke", detect(OR)["revoke"] == ["https://openrouter.ai/keys"] and "/revoke" in detect(TG)["revoke"][0])
both = detect("ключ " + OR + " и токен " + TG)
chk("два ключа в одном сообщении — оба вида", both["kinds"] == ["openrouter", "telegram_bot"], both)
zw = OR[:10] + "​" + OR[10:]
chk("невидимый символ внутри ключа — всё равно пойман", detect(zw)["hit"])
url = "https://api.telegram.org/bot" + TG + "/getMe"
chk("токен бота в ссылке API (…/bot<id>:…/getMe) — пойман, в redact его нет", detect(url)["kinds"] == ["telegram_bot"] and TG not in redact(url) and TG.split(":")[1] not in redact(url), redact(url))
chk("«bot<id>:<хвост>» без ссылки — пойман", detect("bot" + TG)["hit"] and TG.split(":")[1] not in redact("bot" + TG))
for ch in ("\u00ad", "\u200e", "\u202e", "\u2066", "\u180e"):
    k = OR[:20] + ch + OR[20:]
    chk("символ U+%04X внутри ключа — пойман как openrouter, хвоста в redact нет" % ord(ch), detect(k)["kinds"] == ["openrouter"] and OR[20:] not in redact(k) and OR[24:] not in redact(k), redact(k))
out = json.dumps([detect(t) for _, t in cases])
chk("в ответе detect нет значений ключей", not any(v in out or v[:14] in out for v in (OR, ANT, GQ, TG, GH)))
rd = redact("мой ключ " + OR + ", бот " + TG + " — проверьте")
chk("redact: ключей нет, метки вида есть, остальной текст цел", OR not in rd and TG not in rd and "[ключ скрыт: openrouter]" in rd and "[ключ скрыт: telegram_bot]" in rd and rd.startswith("мой ключ ") and rd.endswith(" — проверьте"), rd)
for txt in ("Встреча в 12:30, звоните +998 90 000 00 00", "сайт https://openrouter.ai/keys — там ключи", "Цена 1 200 000 сум, счёт №4471",
            "sk-коротко", "мой бот @mila_test_bot", "skip_if и sk_ ни при чём", "12345678:коротко"):
    chk("не ключ: %s" % txt[:30], not detect(txt)["hit"], detect(txt))
r = subprocess.run([sys.executable, "-I", os.path.join(H, "key_in_chat.py")], input="держи " + GQ, capture_output=True, text=True)
chk("CLI: код 1, вид groq, значения нет", r.returncode == 1 and json.loads(r.stdout)["kinds"] == ["groq"] and GQ not in r.stdout + r.stderr, r.stdout)
r = subprocess.run([sys.executable, "-I", os.path.join(H, "key_in_chat.py")], input="привет, как дела?", capture_output=True, text=True)
chk("CLI: обычный текст — код 0", r.returncode == 0 and not json.loads(r.stdout)["hit"])
print("итог %d/%d" % (ok, n)); sys.exit(0 if ok == n else 1)
