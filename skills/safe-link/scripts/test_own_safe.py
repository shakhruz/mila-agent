#!/usr/bin/env python3
"""own_safe.py — свой Сейф из фонового сеанса: ключ коннектора страницей на этом компьютере. Страница отвечает только своему
имени и порту, POST — только со своим Origin; seif.py — только из корня набора и только свой; ключа и ссылки нет в выводе и журналах.
python3 test_own_safe.py"""
import json, os, shutil, subprocess, sys, tempfile, time, urllib.error, urllib.parse, urllib.request
H = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.normpath(os.path.join(H, "..", "..", ".."))
ok = n = 0
def check(name, c, x=""):
    global ok, n; n += 1; ok += bool(c); print(("✅ " if c else "❌ ") + name + ("" if c else "  " + str(x)[:300]))

def home():
    T = tempfile.mkdtemp(prefix="own-safe-"); os.chmod(T, 0o700)
    os.makedirs(os.path.join(T, "mila", "tools")); shutil.copytree(os.path.join(ROOT, "tools", "seif"), os.path.join(T, "mila", "tools", "seif"),
                                                                 ignore=shutil.ignore_patterns("__pycache__", "test_*"))
    for d in ("safe-link", "konnektory", "sluh"):
        shutil.copytree(os.path.join(ROOT, "skills", d), os.path.join(T, ".claude", "skills", d), ignore=shutil.ignore_patterns("__pycache__"))
    for dp, dn, fn in os.walk(T):
        for x in dn: os.chmod(os.path.join(dp, x), 0o755)
    os.chmod(T, 0o700)
    b = os.path.join(T, "bin"); os.makedirs(b)
    with open(os.path.join(b, "xdg-open"), "w") as f: f.write('#!/bin/sh\necho "$1" > "%s/opened"\n' % T)
    shutil.copy(os.path.join(b, "xdg-open"), os.path.join(b, "open")); os.chmod(os.path.join(b, "xdg-open"), 0o755); os.chmod(os.path.join(b, "open"), 0o755)
    return T

def run(T, *a, display=True, extra=None):
    env = {k: v for k, v in os.environ.items() if not k.startswith("SEIF_") and k not in ("DISPLAY", "WAYLAND_DISPLAY")}
    env.update(HOME=T, PATH=os.path.join(T, "bin") + os.pathsep + env.get("PATH", ""), PYTHONDONTWRITEBYTECODE="1")
    if display: env["DISPLAY"] = ":0"
    env.update(extra or {})
    t0 = time.time()
    try:
        p = subprocess.run([sys.executable, "-B", os.path.join(T, ".claude", "skills", "safe-link", "scripts", "own_safe.py")] + list(a),
                           capture_output=True, text=True, env=env, timeout=60)
    except subprocess.TimeoutExpired as e:   # say which call hung and what it had printed — a red run on a runner nobody can log into
        print("   own_safe.py %s did not return in 60 s; stdout=%r stderr=%r" % (" ".join(a), (e.stdout or b"")[-300:], (e.stderr or b"")[-300:]))
        return {"timeout": True}, -1, time.time() - t0, ""
    try: d = json.loads(p.stdout.strip().splitlines()[-1])
    except Exception: d = {"raw": p.stdout, "err": p.stderr}
    return d, p.returncode, time.time() - t0, p.stdout

def req(url, data=None, host=None, origin=None):
    h = {}
    if host: h["Host"] = host
    if origin is not None: h["Origin"] = origin
    r = urllib.request.Request(url, data=urllib.parse.urlencode(data).encode() if data is not None else None, headers=h, method="POST" if data is not None else "GET")
    try:
        with urllib.request.urlopen(r, timeout=5) as x: return x.status, x.read().decode()
    except urllib.error.HTTPError as e: return e.code, e.read().decode()

KEY = "dg" + os.urandom(16).hex()
T = home()
d, rc, dt, raw = run(T, "sluh", "--lang", "ru", extra={"SEIF_DIR": os.path.join(T, "evil")})
url = d.get("url", ""); net = urllib.parse.urlsplit(url).netloc; port = net.split(":")[-1]
check("ссылка этого компьютера, команда вернулась сразу, браузер открыт сам", rc == 0 and d.get("ok") and url.startswith("http://127.0.0.1:") and d.get("open") is True and dt < 8, (d, dt))
check("браузеру отдана та же ссылка", os.path.exists(os.path.join(T, "opened")) and open(os.path.join(T, "opened")).read().strip() == url)
check("SEIF_* окружения вызывающего не берётся (токены не в подложенной папке)", not os.path.exists(os.path.join(T, "evil")))
s, b = req(url, host="evil.example:" + port)
check("чужой Host → 403", s == 403, s)
s, b = req(url, host="mila.localhost:" + str(int(port) + 1))
check("свой адрес, чужой порт → 403", s == 403, s)
s, b = req(url)
check("свой Host → форма с полем записи из паспорта (DEEPGRAM_API_KEY, скрыто)", s == 200 and "name=DEEPGRAM_API_KEY type=password" in b, (s, b[-200:]))
s, _ = req(url, {"DEEPGRAM_API_KEY": KEY})
check("POST без Origin → 403", s == 403, s)
s, _ = req(url, {"DEEPGRAM_API_KEY": KEY}, origin="http://evil.example")
check("POST с чужим Origin → 403", s == 403, s)
envp = os.path.join(T, "work", "secrets", "deepgram.env")
check("после отказов ничего не записано", not os.path.exists(envp))
s, b = req(url, {"DEEPGRAM_API_KEY": KEY}, origin="http://" + net)
time.sleep(1.5)
check("свой Origin → сохранено: work/secrets/deepgram.env 600, папка 700", s == 200 and os.path.exists(envp) and oct(os.stat(envp).st_mode & 0o777) == "0o600"
      and oct(os.stat(os.path.dirname(envp)).st_mode & 0o777) == "0o700" and ("DEEPGRAM_API_KEY='%s'" % KEY in open(envp).read() or "DEEPGRAM_API_KEY=%s" % KEY in open(envp).read()), (s, b[-200:]))
tok = urllib.parse.urlsplit(url).path.strip("/").split("/")[-1]
texts = raw + "".join(open(os.path.join(dp, f), errors="replace").read() for base in (os.path.join(T, ".local"), os.path.join(T, "work", "inbox")) for dp, _, fs in os.walk(base) for f in fs)
check("ни ключа, ни токена ссылки в выводе, журнале сейфа и записке", KEY not in texts and tok not in texts.replace(url, ""), "")
check("записка «в сейфе появились» есть — без значения", "DEEPGRAM_API_KEY" in open(os.path.join(T, "work", "inbox", "senior.jsonl")).read())
try: urllib.request.urlopen(url, timeout=2); alive = True
except Exception: alive = False
check("после сохранения страница закрылась", not alive)

# пятая ошибка закрывает ссылку словами
d, rc, _, _ = run(T, "sluh", "--lang", "ru"); u2 = d.get("url", ""); o2 = "http://" + urllib.parse.urlsplit(u2).netloc
codes = [req(u2, {"DEEPGRAM_API_KEY": ""}, origin=o2)[0] for _ in range(4)]
s, b = req(u2, {"DEEPGRAM_API_KEY": ""}, origin=o2)
s6, b6 = req(u2)
check("пятая неверная попытка — страница «Ссылка уже не действует … попросите у Милы новую», ссылка мертва", codes == [200] * 4 and s == 410 and "Попросите у Милы новую" in b and "Ссылка уже не действует" in b and s6 == 410, (codes, s, s6))

# отказы до запуска
d, rc, _, _ = run(T, "nope")
check("чужой коннектор — отказ, страницы нет", rc == 1 and d.get("ok") is False, d)
d, rc, _, _ = run(T, "sluh", display=False)
if sys.platform == "darwin":   # a Mac opens a page with `open`, no DISPLAY is involved
    check("Мак без DISPLAY — страница открыта командой open, ссылка дана", rc == 0 and d.get("open") is True and d.get("url", "").startswith("http://127.0.0.1:"), d)
else:
    check("нет экрана (нет DISPLAY) — open: false, ссылка всё равно дана", rc == 0 and d.get("open") is False and d.get("url", "").startswith("http://127.0.0.1:"), d)
if d.get("url"): req(d["url"], {"DEEPGRAM_API_KEY": "x"}, origin="http://" + urllib.parse.urlsplit(d["url"]).netloc)   # the page closes, no process outlives the test
time.sleep(1.5); shutil.rmtree(T, ignore_errors=True)

T = home(); S = os.path.join(T, "mila", "tools", "seif", "seif.py"); out_ = tempfile.mkdtemp(prefix="own-safe-out-")
shutil.copy(S, os.path.join(out_, "seif.py")); os.remove(S); os.symlink(os.path.join(out_, "seif.py"), S)
d, rc, _, _ = run(T, "sluh")
check("seif.py — ссылка (наружу) → отказ, ничего не запущено", rc == 1 and "ссылка" in d.get("why", ""), d)
os.remove(S); shutil.copy(os.path.join(out_, "seif.py"), S)
os.chmod(os.path.join(T, "mila", "tools", "seif"), 0o775)
d, rc, _, _ = run(T, "sluh")
check("папка сейфа открыта на запись группе → отказ", rc == 1 and "чужие" in d.get("why", ""), d)
os.chmod(os.path.join(T, "mila", "tools", "seif"), 0o755); os.chmod(S, 0o666)
d, rc, _, _ = run(T, "sluh")
check("seif.py пишут все → отказ", rc == 1 and "чужие" in d.get("why", ""), d)
os.chmod(S, 0o644)
shutil.rmtree(os.path.join(T, "mila", "tools", "seif")); os.symlink(os.path.join(ROOT, "tools", "seif"), os.path.join(T, "mila", "tools", "seif"))
d, rc, _, _ = run(T, "sluh")
check("папка tools/seif — ссылка за пределы набора → отказ", rc == 1 and "пределы" in d.get("why", ""), d)
os.remove(os.path.join(T, "mila", "tools", "seif"))
d, rc, _, _ = run(T, "sluh")
check("в наборе нет seif.py → отказ со словами «обновите набор»", rc == 1 and "обновите набор" in d.get("why", ""), d)
time.sleep(0.5); shutil.rmtree(T, ignore_errors=True); shutil.rmtree(out_, ignore_errors=True)
print(f"итог {ok}/{n}"); sys.exit(0 if ok == n else 1)
