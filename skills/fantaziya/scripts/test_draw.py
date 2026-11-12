#!/usr/bin/env python3
"""draw.py — фантазия: цена без сети; не активирована, выключена, без ключа, потолок дня — отказ без сети; ключ и описание уходят
только на адрес из кода, с моделью из кода; картинка — только base64 PNG/JPEG из ответа (ссылка не скачивается, не-картинка и
слишком большая — ошибка); файл 600 в папке 700; расход в records; ключа нет ни в одном выводе. Сеть подменена внутри процесса.
python3 test_draw.py"""
import base64, contextlib, io, json, os, shutil, sys, tempfile, time
sys.dont_write_bytecode = True; os.umask(0o022)
H = os.path.dirname(os.path.abspath(__file__)); SK = os.path.dirname(os.path.dirname(H))
T = tempfile.mkdtemp(prefix="fantaziya-"); WORK = os.path.join(T, "work"); SAFE = os.path.join(WORK, "secrets"); os.makedirs(SAFE, mode=0o700)
os.environ.update(MILA_WORK=WORK, SAFE_DIR=SAFE, MILA_RECORDS_DIR=os.path.join(T, "records"))
sys.path.insert(0, H)
import draw as D
sys.path.insert(0, os.path.join(SK, "konnektory", "scripts")); import connectors as C
ok = n = 0
def chk(m, c, x=""):
    global ok, n
    n += 1; ok += bool(c); print(("✅ " if c else "❌ ") + m + ("" if c else "  ← " + str(x)[:400]))
KEY = "sk" + "-or-v1-" + "a" * 40                              # выдуманный ключ, склейкой
PNG = b"\x89PNG\r\n\x1a\n" + b"\0" * 64
calls = []; everything = []
def service(code, body):
    def post_json(url, headers, body_, timeout=120):
        calls.append((url, dict(headers), body_)); return code, body
    return post_json
def answer(url, rid="gen-1", cost=0.039):
    return {"id": rid, "choices": [{"message": {"content": "", "images": [{"type": "image_url", "image_url": {"url": url}}]}}], "usage": {"cost": cost}}
def b64(data, kind="png"):
    return "data:image/%s;base64,%s" % (kind, base64.b64encode(data).decode())
def run(*argv):
    out = io.StringIO(); code = 0
    with contextlib.redirect_stdout(out):
        try: D.main(["draw.py"] + list(argv))
        except SystemExit as e: code = e.code or 0
    raw = out.getvalue(); everything.append(raw)
    try: return code, json.loads(raw)
    except ValueError: return code, {"raw": raw}
fetched = []
import urllib.request
urllib.request.urlopen = lambda *a, **k: fetched.append(a) or (_ for _ in ()).throw(OSError("no network in the test"))
try:
    D.post_json = service(200, answer(b64(PNG)))
    code, d = run("--price")
    chk("цена до первой картинки — из паспорта, с датой прайса, без сети", code == 0 and "0.04" in d["line"] and "2026-11-12" in d["line"] and not calls, d)
    code, d = run("кот на подоконнике")
    chk("не активирована — отказ словами, в сеть не иду", code == 1 and "не активирована" in d["why"] and not calls, d)
    C.set_state("fantaziya", "active")
    code, d = run("кот на подоконнике")
    chk("активирована, но ключа в сейфе нет — отказ, в сеть не иду", code == 1 and not calls, d)
    open(os.path.join(SAFE, "openrouter.env"), "w").write("%s=%s\n" % ("OPENROUTER_" + "API_KEY", KEY)); os.chmod(os.path.join(SAFE, "openrouter.env"), 0o600)
    code, d = run("кот на подоконнике", "--ratio", "16:9")
    f = d.get("file", "")
    chk("картинка: файл в work/media/fantaziya, 600, папка 700, PNG как в ответе", code == 0 and f.startswith(os.path.join(WORK, "media", "fantaziya"))
        and oct(os.stat(f).st_mode & 0o777) == "0o600" and oct(os.stat(os.path.dirname(f)).st_mode & 0o777) == "0o700" and open(f, "rb").read() == PNG, d)
    u, hd, body = calls[-1]
    chk("ключ и описание ушли только на openrouter.ai, модель из кода, формат 16:9, заголовком Bearer", u == "https://openrouter.ai/api/v1/chat/completions"
        and hd == {"Authorization": "Bearer " + KEY} and body["model"] == "google/gemini-2.5-flash-image" and body["image_config"] == {"aspect_ratio": "16:9"}
        and body["messages"][0]["content"] == "кот на подоконнике", (u, body))
    sys.path.insert(0, os.path.join(SK, "..", "install")); import records as R
    rows = R.read_external(provider="openrouter", service="image")
    chk("расход записан в records: openrouter/image, $0.039, id ответа; описания в строке нет", len(rows) == 1 and abs(rows[0]["usd"] - 0.039) < 1e-9
        and rows[0]["request_id"] == "gen-1" and "подоконнике" not in json.dumps(rows, ensure_ascii=False), rows)
    code, d = run("--price"); chk("после картинки цена — по прошлой", "0.039" in d["line"] and "прошлая" in d["line"], d)
    # ответы, которые не картинка
    D.post_json = service(200, answer("https://example.com/cat.png", rid="gen-2")); fetched.clear()
    code, d = run("кот")
    chk("в ответе ссылка, не base64 — не скачиваю, честная ошибка", code == 1 and not fetched and "ссылки не скачиваю" in d["why"], (d, fetched))
    D.post_json = service(200, answer(b64(b"<html>hi</html>"), rid="gen-3")); code, d = run("кот")
    chk("в ответе не PNG и не JPEG — не сохраняю", code == 1 and "не PNG" in d["why"], d)
    keep = D.MAX_BYTES; D.MAX_BYTES = 32
    D.post_json = service(200, answer(b64(PNG), rid="gen-4")); code, d = run("кот"); D.MAX_BYTES = keep
    chk("картинка больше потолка размера — не беру", code == 1 and "20 МБ" in d["why"], d)
    D.post_json = service(401, {}); code, d = run("кот"); chk("ключ не принят — «нужен новый ключ»", code == 1 and "новый ключ" in d["why"], d)
    D.post_json = service(402, {}); code, d = run("кот"); chk("на счёте нет денег — «пополните счёт»", code == 1 and "пополните" in d["why"], d)
    D.post_json = service(200, answer(b64(PNG), rid="gen-5")); code, d = run("кот", "--ratio", "2:1"); chk("формат не из списка — отказ", code == 1 and "формат" in d["why"], d)
    # потолок дня: десять картинок сегодня
    for i in range(8): R.record_external("openrouter", "image", 0.01, request_id="pad-%d" % i)
    n_before = len(calls); code, d = run("кот")
    chk("потолок дня (10 картинок) — отказ без сети, вопрос хозяину", code == 1 and d.get("cap") is True and len(calls) == n_before, d)
    R.record_external("openrouter", "image", 0.01, request_id="old", ts=time.time() - 3 * 86400)
    code, d = run("кот"); chk("вчерашние и старые картинки в потолок дня не входят (счёт с полуночи)", d.get("today", {}).get("images") == 12, d)   # 4 answers above (each is paid, a failed one too) + 8 today; the old one is not counted
    # выключено
    shutil.rmtree(os.path.join(T, "records")); open(os.path.join(WORK, "connectors", "fantaziya.off"), "w").close()
    n_before = len(calls); code, d = run("кот"); chk("выключена (fantaziya.off) — отказ, в сеть не иду", code == 1 and len(calls) == n_before, d)
    chk("ни в одном выводе ключа нет", not any(KEY in x for x in everything))
    src = open(os.path.join(H, "draw.py"), encoding="utf-8").read()
    chk("адрес и модель не берутся из окружения или паспорта", src.count("environ") == 1 and 'd.get("model")' not in src and 'd["model"]' not in src)
    p = json.load(open(os.path.join(SK, "fantaziya", "connector.json"), encoding="utf-8"))
    chk("паспорт: четыре языка, платная проба, цена с датой, потолок дня, «описание уходит в OpenRouter и Google»", all(set(p[k]) == set(C.LANGS) for k in ("sense", "offer", "steps", "trial", "removal"))
        and p["paid_trial"] is True and p["price"]["date"] and p["daily_cap"]["images"] == 10 and all("OpenRouter" in v and "Google" in v for v in p["passport"]["needs"].values()), p.get("price"))
finally:
    shutil.rmtree(T, ignore_errors=True)
print("итог %d/%d" % (ok, n)); sys.exit(0 if ok == n else 1)
