#!/usr/bin/env python3
"""home_template.py: новый дом — файлы на месте; наш прежний CLAUDE.md (sha в SHIPPED) — заменён, старый в .bak-;
правленный хозяином — оставлен, новый рядом .new (один раз); USER.md хозяина не трогается; ссылка — не трогается;
текущие шаблоны ядра — в списке SHIPPED (иначе их следующая версия не дойдёт до домов). Run: python3 test_home_template.py"""
import glob, hashlib, os, shutil, string, subprocess, sys, tempfile
H = os.path.dirname(os.path.abspath(__file__)); KIT = os.path.dirname(H); ok = n = 0
def check(name, c, x=""):
    global ok, n; n += 1; ok += bool(c); print(("✅ " if c else "❌ ") + name + ("" if c else "  ← " + str(x)[:300]))
def run(kit, work): return subprocess.run([sys.executable, os.path.join(H, "home_template.py"), kit, work], capture_output=True, text=True).stdout
DIG = str.maketrans(string.digits, "ghijklmnop"); sha = lambda p: hashlib.sha256(open(p, "rb").read()).hexdigest().translate(DIG)
listed = {l.split()[0] for l in open(os.path.join(KIT, "templates/work/SHIPPED.sha256")) if l.strip() and not l.startswith("#")}
check("текущие CLAUDE.md и конституции ядра — в SHIPPED.sha256", all(sha(os.path.join(KIT, f)) in listed for f in ("templates/work/CLAUDE.md", "CONSTITUTION.md", "CONSTITUTION.en.md")))
T = tempfile.mkdtemp(); K = os.path.join(T, "kit"); W = os.path.join(T, "work")
for f in ("templates/work/CLAUDE.md", "templates/work/USER.md", "CONSTITUTION.md", "CONSTITUTION.en.md"):
    os.makedirs(os.path.dirname(os.path.join(K, f)), exist_ok=True); open(os.path.join(K, f), "w").write("v1 " + f)
open(os.path.join(K, "templates/work/SHIPPED.sha256"), "w").write("# list\n" + "".join("%s  x\n" % hashlib.sha256(("v1 " + f).encode()).hexdigest().translate(DIG) for f in ("templates/work/CLAUDE.md", "CONSTITUTION.md", "CONSTITUTION.en.md")))
out = run(K, W)
check("новый дом: CLAUDE.md, USER.md, canon/ — на месте", all(os.path.isfile(os.path.join(W, f)) for f in ("CLAUDE.md", "USER.md", "canon/CONSTITUTION.md", "canon/CONSTITUTION.en.md")), out)
open(os.path.join(W, "USER.md"), "w").write("моё")
open(os.path.join(K, "templates/work/CLAUDE.md"), "w").write("v2"); open(os.path.join(K, "templates/work/USER.md"), "w").write("v2 user")
open(os.path.join(K, "CONSTITUTION.md"), "w").write("v2 const")
open(os.path.join(W, "canon/CONSTITUTION.md"), "w").write("правка хозяина")
out = run(K, W)
check("наш прежний CLAUDE.md заменён новым, старый — в .bak-", open(os.path.join(W, "CLAUDE.md")).read() == "v2" and glob.glob(os.path.join(W, "CLAUDE.md.bak-*")), out)
check("USER.md хозяина не тронут", open(os.path.join(W, "USER.md")).read() == "моё")
check("правленная хозяином конституция оставлена, новая — рядом .new, одна строка в журнал", open(os.path.join(W, "canon/CONSTITUTION.md")).read() == "правка хозяина"
      and open(os.path.join(W, "canon/CONSTITUTION.md.new")).read() == "v2 const" and "CONSTITUTION.md.new" in out, out)
out2 = run(K, W)
check("повторный старт — без новых строк (.new уже лежит, CLAUDE.md свежий)", out2.strip() == "", out2)
os.remove(os.path.join(W, "CLAUDE.md")); os.symlink("/etc/hostname", os.path.join(W, "CLAUDE.md")); out3 = run(K, W)
check("CLAUDE.md-ссылка — не трогаю, не пишу по ней", os.path.islink(os.path.join(W, "CLAUDE.md")) and "link" in out3, out3)
check("в SHIPPED нет длинных серий цифр (страж номеров)", not __import__("re").search(r"[0-9]{9,}", open(os.path.join(KIT, "templates/work/SHIPPED.sha256")).read()))
shutil.rmtree(T); print("итог %d/%d" % (ok, n)); sys.exit(0 if ok == n else 1)
