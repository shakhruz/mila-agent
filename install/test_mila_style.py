#!/usr/bin/env python3
"""mila_style.py - the one look of the pages Mila shows the owner: the three copies (install/, docker/, tools/seif/) are identical,
the page has no outside addresses and no script, works without a portrait file, and a portrait is inlined as data:. Run: python3 test_mila_style.py"""
import importlib.util, os, re, shutil, sys, tempfile
H = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(H); ok = n = 0
def check(name, c, x=""):
    global ok, n; n += 1; ok += bool(c); print(("✅ " if c else "❌ ") + name + ("" if c else "  ← " + str(x)[:300]))
def load(path):
    sp = importlib.util.spec_from_file_location("mila_style_t", path); m = importlib.util.module_from_spec(sp); sp.loader.exec_module(m); return m
src = open(os.path.join(H, "mila_style.py"), "rb").read()
for rel in ("docker/mila_style.py", "tools/seif/mila_style.py"):
    check("копия %s совпадает с install/mila_style.py" % rel, open(os.path.join(ROOT, rel), "rb").read() == src)
check("рядом с каждой копией есть портрет (контейнер и сейф)", all(os.path.exists(os.path.join(ROOT, d, "mila-portrait.jpg")) for d in ("docker", "tools/seif")))
check("копии портрета совпадают с install/mila-portrait.jpg (тот же, что на странице рождения), до 25 КБ", all(open(os.path.join(ROOT, d, "mila-portrait.jpg"), "rb").read() == open(os.path.join(H, "mila-portrait.jpg"), "rb").read() for d in ("docker", "tools/seif")) and os.path.getsize(os.path.join(H, "mila-portrait.jpg")) < 25000)
df = open(os.path.join(ROOT, "docker", "Dockerfile")).read()
check("Dockerfile кладёт в образ mila_style.py и mila-portrait.jpg", "docker/mila_style.py" in df and "docker/mila-portrait.jpg" in df)
m = load(os.path.join(H, "mila_style.py"))
h = m.shell("T <x>", "en", "<h1>Hi</h1><p>text</p>", lang_bar="<div class=lang><b>EN</b></div>")
check("страница: карточка, портрет data:, заголовок с засечками, viewport, без скриптов и внешних адресов",
      "class=card" in h and "class=av" in h and "data:image/" in h and "Georgia" in h and "width=device-width" in h and "<script" not in h
      and not re.search(r"https?://(?!www\.w3\.org)", h) and "T &lt;x&gt;" in h, h[:200])
check("CSP: картинки только data:, ничего внешнего", "img-src data:" in m.CSP and "default-src 'none'" in m.CSP)
t = tempfile.mkdtemp(); shutil.copy(os.path.join(H, "mila_style.py"), t); m2 = load(os.path.join(t, "mila_style.py"))
h2 = m2.shell("T", "en", "<h1>Hi</h1>")
check("нет портрета на машине — страница та же, без картинки", m2.face_uri() == "" and "<img" not in h2 and "<h1>Hi</h1>" in h2, h2[:200])
shutil.rmtree(t, ignore_errors=True); print("итог %d/%d" % (ok, n)); sys.exit(0 if ok == n else 1)
