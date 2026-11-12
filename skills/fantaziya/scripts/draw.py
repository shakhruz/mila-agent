#!/usr/bin/env python3
"""draw.py — фантазия: картинка по словам хозяина через OpenRouter, его ключом и с его счёта.
  draw.py --price [--lang ru]                         → {"ok": true, "usd": 0.04, "line": "≈ $0.04 за картинку …"} — без сети
  draw.py "<описание>" [--ratio 1:1|16:9|9:16|4:3|3:4] → {"ok": true, "file": "~/work/media/fantaziya/<время>.png", "usd": …}
Перед картинкой Мила называет цену (--price) и ждёт «да» хозяина; эта команда — уже после «да».
Границы:
- модель и адрес — только здесь, в коде (MODEL, URL); ни паспорт, ни окружение их не меняют. Ключ — из сейфа (safe_read),
  в вывод и журналы не попадает.
- фантазия не активирована или выключена (work/connectors/fantaziya.off) — отказ словами, в сеть не иду.
- потолок дня из паспорта (daily_cap: картинок и долларов) — счёт по records (external-spend.db) с полуночи; дошли — отказ без сети,
  вопрос хозяину решает Мила.
- картинка — только base64 PNG/JPEG из ответа, ≤ 20 МБ, по сигнатуре; ссылки из ответа не скачиваю никуда. Иначе — честная ошибка.
- описание — данные хозяина: уходит только в OpenRouter (и дальше в Google — так сказано в паспорте), в журнал не пишется.
- расход каждой картинки — records.record_external("openrouter", "image", usage.cost, request_id=id ответа).
Код выхода: 0 — картинка готова (или цена), 1 — отказ (причина в "why")."""
import base64, datetime, json, os, re, secrets, sys, time, urllib.error, urllib.request

HERE = os.path.dirname(os.path.realpath(__file__))
SKILLS = os.path.dirname(os.path.dirname(HERE))
WORK = os.environ.get("MILA_WORK") or os.path.expanduser("~/work")
MODEL = "google/gemini-2.5-flash-image"                       # the closed list: one model
URL = "https://openrouter.ai/api/v1/chat/completions"         # the only address the key and the description go to
RATIOS = ("1:1", "16:9", "9:16", "4:3", "3:4")
MAX_BYTES = 20 * 1024 * 1024
SIGS = ((b"\x89PNG\r\n\x1a\n", "png"), (b"\xff\xd8\xff", "jpg"))
WORDS = {
    "price": {"ru": "≈ $%s за картинку (прайс OpenRouter на %s), с вашего счёта OpenRouter", "en": "≈ $%s a picture (OpenRouter's price on %s), from your OpenRouter account"},
    "price_last": {"ru": "≈ $%s за картинку (столько стоила прошлая), с вашего счёта OpenRouter", "en": "≈ $%s a picture (what the last one cost), from your OpenRouter account"},
}


def out(d, code=0):
    print(json.dumps(d, ensure_ascii=False), flush=True); sys.exit(code)


def w(key, lang):
    return WORDS[key].get(lang) or WORDS[key]["en"]


def connectors():
    sys.path.insert(0, os.path.join(SKILLS, "konnektory", "scripts"))
    import connectors as C
    return C


def records():
    for p in (os.path.join(os.path.dirname(SKILLS), "hooks"), os.path.join(os.path.dirname(SKILLS), "install")):
        if os.path.isfile(os.path.join(p, "records.py")):
            sys.path.insert(0, p)
            import records as R
            return R
    return None


def post_json(url, headers, body, timeout=120):
    """The one door to the network (replaced in the test). → (HTTP status, JSON body or {})."""
    try:
        req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=dict(headers, **{"Content-Type": "application/json"}), method="POST")
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read(MAX_BYTES * 2)
            try: return r.status, json.loads(raw.decode("utf-8", "replace"))
            except ValueError: return r.status, {}
    except urllib.error.HTTPError as e:
        return e.code, {}
    except (urllib.error.URLError, OSError, ValueError):
        return 0, {}


def today_spend(R):
    """→ (pictures today, dollars today) by the records; (0, 0.0) when there are none."""
    if R is None: return 0, 0.0
    start = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
    try: rows = R.read_external(since=start, provider="openrouter", service="image")
    except Exception: return 0, 0.0
    return len(rows), round(sum(float(r.get("usd") or 0) for r in rows), 4)


def last_cost(R):
    if R is None: return None
    try: rows = R.read_external(provider="openrouter", service="image", limit=1, order="desc")
    except Exception: return None
    return float(rows[0]["usd"]) if rows and rows[0].get("usd") else None


def picture(body):
    """→ (bytes, ext) or (None, why). Only base64 data in the answer; a link is never fetched."""
    try: imgs = body["choices"][0]["message"].get("images") or []
    except (KeyError, IndexError, TypeError, AttributeError): imgs = []
    for im in imgs:
        u = str(((im or {}).get("image_url") or {}).get("url") or "")
        m = re.match(r"data:image/(png|jpeg|jpg);base64,", u)
        if not m:
            continue   # a URL or anything else: not fetched
        if len(u) > MAX_BYTES * 4 // 3 + 100: return None, "картинка в ответе больше 20 МБ — не беру"
        try: data = base64.b64decode(u[m.end():], validate=False)
        except ValueError: return None, "картинка в ответе испорчена"
        if len(data) > MAX_BYTES: return None, "картинка в ответе больше 20 МБ — не беру"
        for sig, ext in SIGS:
            if data.startswith(sig): return data, ext
        return None, "в ответе не PNG и не JPEG — не сохраняю"
    return None, "сервис не прислал картинку (только ссылку или текст) — ссылки не скачиваю; попробую ещё раз или другое описание"


def save(data, ext):
    d = os.path.join(WORK, "media", "fantaziya")
    os.makedirs(d, mode=0o700, exist_ok=True); os.chmod(d, 0o700)
    p = os.path.join(d, time.strftime("%Y%m%d-%H%M%S") + "-%s.%s" % (secrets.token_hex(4), ext))   # two pictures in one second do not collide
    fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
    with os.fdopen(fd, "wb") as f: f.write(data)
    return p


def main(argv):
    lang = argv[argv.index("--lang") + 1] if "--lang" in argv and argv.index("--lang") + 1 < len(argv) else "ru"
    C = connectors()
    try: d = C.load("fantaziya")
    except Exception as e: out({"ok": False, "why": str(e)[:200]}, 1)
    R = records()
    price = d.get("price") or {}
    if "--price" in argv:
        lc = last_cost(R)
        line = w("price_last", lang) % ("%.3f" % lc).rstrip("0").rstrip(".") if lc else w("price", lang) % (price.get("usd"), price.get("date"))
        out({"ok": True, "usd": lc or price.get("usd"), "line": line})
    words = [x for i, x in enumerate(argv[1:], 1) if not x.startswith("--") and argv[i - 1] not in ("--ratio", "--lang")]
    prompt = " ".join(words).strip()
    if not prompt: out({"ok": False, "why": "нет описания: draw.py \"<что нарисовать>\""}, 1)
    if len(prompt) > 2000: out({"ok": False, "why": "описание длиннее 2000 знаков — сократите"}, 1)
    ratio = argv[argv.index("--ratio") + 1] if "--ratio" in argv and argv.index("--ratio") + 1 < len(argv) else "1:1"
    if ratio not in RATIOS: out({"ok": False, "why": "формат — один из: " + ", ".join(RATIOS)}, 1)
    if C.state_of("fantaziya") != "active" or os.path.exists(os.path.join(C.DIR, "fantaziya.off")):
        out({"ok": False, "why": "фантазия не активирована или выключена — в сеть не иду; активировать: connectors.py offer fantaziya"}, 1)
    cap = d.get("daily_cap") or {}
    n, usd = today_spend(R)
    if n >= int(cap.get("images") or 10) or usd >= float(cap.get("usd") or 1.0):
        out({"ok": False, "cap": True, "today": {"images": n, "usd": usd},
             "why": "потолок дня дошёл (%d картинок, $%s) — дальше только по вашему слову; в сеть не иду" % (n, usd)}, 1)
    key, why = C.read_key(d)
    if not key: out({"ok": False, "why": why}, 1)
    body = {"model": MODEL, "messages": [{"role": "user", "content": prompt}], "modalities": ["image", "text"],
            "image_config": {"aspect_ratio": ratio}, "usage": {"include": True}}
    code, resp = post_json(URL, {"Authorization": "Bearer " + key}, body)
    key = None
    if code in (401, 403): out({"ok": False, "why": "OpenRouter не принял ключ (HTTP %d) — нужен новый ключ: connectors.py steps fantaziya" % code}, 1)
    if code == 402: out({"ok": False, "why": "на счёте OpenRouter нет денег (HTTP 402) — пополните счёт там"}, 1)
    if code != 200: out({"ok": False, "why": "OpenRouter ответил %s — попробую позже" % (code or "молчанием")}, 1)
    data, why = picture(resp)   # on success «why» is the extension
    cost = float(((resp.get("usage") or {}).get("cost")) or 0) if isinstance(resp, dict) else 0.0
    rid = str(resp.get("id") or "") if isinstance(resp, dict) else ""
    if R is not None and rid:
        try: R.record_external("openrouter", "image", cost, request_id=rid, model=MODEL, units=1 if data else 0, unit_kind="картинки")
        except Exception: pass
    if not data: out({"ok": False, "why": why, "usd": cost}, 1)
    p = save(data, why)
    out({"ok": True, "file": p, "usd": cost, "ratio": ratio})


if __name__ == "__main__":
    main(sys.argv)
