#!/usr/bin/env python3
"""install/backup.py scrub (audit 09.11 №16): Groq and Deepgram keys in settings.json, the inbound journal and env lines are
cut — with synthetic keys; the field names stay, ordinary text stays. Usage: python3 test_backup_keys.py"""
import json, os, sys
H = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, H)
import backup as B
ok = n = 0
def check(name, cond, x=""):
    global ok, n
    n += 1; ok += bool(cond); print(("✅ " if cond else "❌ ") + name + ("" if cond else "  ← " + str(x)[:300]))
GQ = "gs" + "k_" + "Q" * 40
DG = "a1b2c3d4" * 5
DGN = "DEEPGRAM" + "_API_KEY"
GQN = "GROQ" + "_API_KEY"
settings = json.dumps({"env": {DGN: DG, GQN: GQ, "TZ": "Asia/Tashkent", "MILA_TOKEN_PAGE_PORT": "8080"}}, indent=1)
out, hits = B.scrub(settings)
check("settings.json: ключ Deepgram (непрозрачное значение) вырезан", DG not in out, out)
check("settings.json: ключ Groq вырезан", GQ not in out, out)
check("имена полей остались (по ним ищут)", '"%s"' % DGN in out and '"%s"' % GQN in out)
check("обычные значения не тронуты (TZ, порт)", "Asia/Tashkent" in out and '"8080"' in out, out)
ev = json.dumps({"text": "вот мой ключ " + GQ + " и deepgram " + DG})
out, _ = B.scrub(ev)
check("журнал входящих: ключ Groq в тексте вырезан", GQ not in out, out)
env = "export %s=%s\n%s='%s'\nTZ=Asia/Tashkent\n" % (DGN, DG, GQN, GQ)
out, _ = B.scrub(env)
check(".env-строки: оба ключа вырезаны, имена и TZ на месте", DG not in out and GQ not in out and DGN + "=" in out and "TZ=Asia/Tashkent" in out, out)
plain = "Встреча с Иваном в 15:00, тема — тарифы. Токен доступа к залу выдаст охрана."
check("обычный текст без ключей — без изменений", B.scrub(plain)[0] == plain)
# Quality 09.11: a client's data under names that only contain the letters — stays
for s_ in ('{"secretary": "Ivanova_Anna_V"}', 'TOKENS_USED=12345678', '{"next_page_token": "CAEaAggAQAE"}', '{"password_hint": "first pet name"}',
           '{"max_tokens": 1200, "keywords": "secret sauce recipe"}', '{"TOKEN_COUNT": "45678901"}'):
    check("не ключ — цело: " + s_[:40], B.scrub(s_)[0] == s_, B.scrub(s_)[0])
# Quality 10.11: camelCase names of JS configs — cut; plus the ones that were right
for k in ("botToken", "accessToken", "clientSecret", "authToken", "apiKey", "refresh_token", "client_secret", "password", "OPENAI" + "_API_KEY"):
    o = B.scrub(json.dumps({k: "Zx9" + "q" * 20}))[0]
    check("ключ под именем %s — вырезан" % k, "Zx9" not in o, o)
B.CUT_BY_FIELD.clear(); B.scrub(json.dumps({DGN: DG}))
check("счётчик вырезанного по имени поля: %s ×1" % DGN, B.CUT_BY_FIELD.get(DGN) == 1, B.CUT_BY_FIELD)
# the archive check must not call an ordinary JSON field a secret (else the whole backup is deleted)
norm = json.dumps({"title": "Ежедневная сводка", "chat_id": "-1002222", "description": "длинное описание группы"})
check("проверка архива: обычные поля — не секрет", not any(B.has_secret(rx, norm) for rx, _ in B.SECRET_PATTERNS))
left = json.dumps({"botToken": "Zx9" + "q" * 20})
check("проверка архива: невычищенный ключ под именем — найден", any(B.has_secret(rx, left) for rx, _ in B.SECRET_PATTERNS))
check("проверка архива: вычищенное — уже не секрет", not any(B.has_secret(rx, B.scrub(left)[0]) for rx, _ in B.SECRET_PATTERNS), B.scrub(left)[0])
print("итог %d/%d" % (ok, n)); sys.exit(0 if ok == n else 1)
