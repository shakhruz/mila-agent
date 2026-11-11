#!/usr/bin/env python3
"""kitchen_lint: в публичном ядре нет следов кухни (коды задач, номера чужих сообщений, время приёмок, номера раскаток);
--fix убирает только метку и пустые от неё скобки/знаки — чужие «()» в коде не трогает."""
import os, subprocess, sys
H = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, H)
import kitchen_lint as K
ok = n = 0
def chk(m, c, x=""):
    global ok, n; n += 1; ok += bool(c); print(("✅ " if c else "❌ ") + m + ("" if c else "  ← " + repr(x)[:200]))
R = os.path.dirname(H)
r = subprocess.run([sys.executable, os.path.join(H, "kitchen_lint.py")], capture_output=True, text=True, cwd=R)
chk("репозиторий: следов кухни 0", r.returncode == 0 and "следов кухни: 0" in r.stdout, r.stdout[-400:])
code = "AB" + "C-1234"; when = "Качество" + " 12:34"; who = "владелец" + " 12345"
for src, want in [
    ('x = text.strip()[:120]   # %s\n' % code, 'x = text.strip()[:120]\n'),
    ('# %s: сторож падает — сообщение не уходит\n' % code, '# сторож падает — сообщение не уходит\n'),
    ('"""%s (%s): три числа"""\n' % (code, who), '"""три числа"""\n'),
    ('f()   # слабое место (%s: {} — не улика)\n' % when, 'f()   # слабое место ({} — не улика)\n'),
    ('если пусто (%s)\n' % when, 'если пусто\n'),
    ('ROLL' + 'OUT №41, правило\n', 'правило\n'),
    ('print("ok")\n', 'print("ok")\n'),
    ('call(a, b)  # обычный\n', 'call(a, b)  # обычный\n'),
]:
    got = K.clean(src)
    chk("clean: %s" % want.strip()[:50], got == want, got)
import tempfile
G = tempfile.mkdtemp(); env = dict(os.environ, GIT_CONFIG_GLOBAL=os.path.join(G, "gc"), GIT_CONFIG_SYSTEM="/dev/null")
def g(*a): return subprocess.run(["git"] + list(a), cwd=G, capture_output=True, text=True, env=env)
g("init", "-q"); g("config", "user.email", "t@t"); g("config", "user.name", "t")
g("commit", "-q", "--allow-empty", "-m", "base")
g("commit", "-q", "--allow-empty", "-m", "Add a clean feature that helps people")
r = subprocess.run([sys.executable, os.path.join(H, "kitchen_lint.py"), "--log", "HEAD~1..HEAD"], capture_output=True, text=True, cwd=G)
chk("--log: чистое сообщение коммита → 0, код 0", r.returncode == 0 and "сообщениях коммитов: 0" in r.stdout, r.stdout)
g("commit", "-q", "--allow-empty", "-m", "Fix guard (" + "Quality" + " 11:21)")
r = subprocess.run([sys.executable, os.path.join(H, "kitchen_lint.py"), "--log", "HEAD~1..HEAD"], capture_output=True, text=True, cwd=G)
chk("--log: ссылка на приёмку «(Quality 11:21)» в сообщении → находка, код 1", r.returncode == 1 and "сообщениях коммитов: 1" in r.stdout, r.stdout)
import os as _os, tempfile as _tf
_d = _tf.mkdtemp(); _sp = "/" + "srv/mila/state/x"
for _c in (["git", "init", "-q"], ["git", "config", "user.email", "t@example.com"], ["git", "config", "user.name", "t"]): subprocess.run(_c, cwd=_d)
open(_os.path.join(_d, "a.py"), "w").write('STATE = "%s"\n' % _sp); subprocess.run(["git", "add", "a.py"], cwd=_d)
_r = subprocess.run([sys.executable, _os.path.abspath(K.__file__)], cwd=_d, capture_output=True, text=True)
chk("путь нашего сервера в коде → находка, код 1", _r.returncode == 1 and "путь нашего сервера" in _r.stdout, _r.stdout)
_r = subprocess.run([sys.executable, _os.path.abspath(K.__file__), "--fix"], cwd=_d, capture_output=True, text=True)
chk("--fix путь сервера НЕ трогает (иначе пустая строка в коде) и падает", _r.returncode == 1 and _sp in open(_os.path.join(_d, "a.py")).read(), _r.stdout)
open(_os.path.join(_d, "a.py"), "w").write('K = "%s" + "x" * 30\n' % ("sk-" + "ant-")); subprocess.run(["git", "add", "a.py"], cwd=_d)
_r = subprocess.run([sys.executable, _os.path.abspath(K.__file__)], cwd=_d, capture_output=True, text=True)
chk("префикс ключа одним куском → находка, код 1", _r.returncode == 1 and "префикс ключа" in _r.stdout, _r.stdout)
open(_os.path.join(_d, "a.py"), "w").write('K = "sk-" + "ant-" + "x" * 30\n')
_r = subprocess.run([sys.executable, _os.path.abspath(K.__file__)], cwd=_d, capture_output=True, text=True)
chk("склейкой — чисто", _r.returncode == 0, _r.stdout)
_w = "по сло" + "ву хозяина"
open(_os.path.join(_d, "a.py"), "w").write('X = 1\n'); open(_os.path.join(_d, "b.md"), "w").write("Кнопка одна — %s.\n" % _w); subprocess.run(["git", "add", "a.py", "b.md"], cwd=_d)
_r = subprocess.run([sys.executable, _os.path.abspath(K.__file__)], cwd=_d, capture_output=True, text=True)
chk("ссылка на чьё-то слово об этой правке → находка, код 1", _r.returncode == 1 and "b.md:1" in _r.stdout and "следов кухни: 1" in _r.stdout, _r.stdout)
_r = subprocess.run([sys.executable, _os.path.abspath(K.__file__), "--fix"], cwd=_d, capture_output=True, text=True)
chk("--fix её не трогает (фразу переписывает человек) и падает", _r.returncode == 1 and _w in open(_os.path.join(_d, "b.md"), encoding="utf-8").read(), _r.stdout)
open(_os.path.join(_d, "b.md"), "w").write("Кнопка одна — По Сло" + "ву Владельца.\n")
_r = subprocess.run([sys.executable, _os.path.abspath(K.__file__)], cwd=_d, capture_output=True, text=True)
chk("то же про владельца и с заглавными → находка", _r.returncode == 1, _r.stdout)
open(_os.path.join(_d, "b.md"), "w").write("Кнопка одна — по просьбе хозяина. Двенадцать сл" + "ов хозяина хранятся у него. Мила служит людям по его слову.\n")
_r = subprocess.run([sys.executable, _os.path.abspath(K.__file__)], cwd=_d, capture_output=True, text=True)
chk("«по просьбе хозяина», фраза о двенадцати словах, «по его слову» — не находка", _r.returncode == 0, _r.stdout)
g("commit", "-q", "--allow-empty", "-m", "Docs: one button, " + _w)
r = subprocess.run([sys.executable, os.path.join(H, "kitchen_lint.py"), "--log", "HEAD~1..HEAD"], capture_output=True, text=True, cwd=G)
chk("--log: та же фраза в сообщении коммита → находка, код 1", r.returncode == 1 and "сообщениях коммитов: 1" in r.stdout, r.stdout)
import shutil as _sh; _sh.rmtree(_d, ignore_errors=True); _sh.rmtree(G, ignore_errors=True)
print("итог %d/%d" % (ok, n)); sys.exit(0 if ok == n else 1)
