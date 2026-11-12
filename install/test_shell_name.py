#!/usr/bin/env python3
"""shell_name.py — the owner's own shell is asked whether `mila` is ours: a function or an alias from an rc file or a file it
sources is named with its file and lines; an rc file is never edited; a shell that hangs gives no false alarm. bash — real;
zsh — a stand-in that answers as zsh's `whence -v` does, after the probe's mark (no zsh on this machine: the zsh path is checked on a Mac by CI).
python3 test_shell_name.py"""
import json, os, shutil, subprocess, sys, tempfile, time
H = os.path.dirname(os.path.abspath(__file__)); S = os.path.join(H, "shell_name.py"); ok = n = 0
def chk(m, c, x=""):
    global ok, n; n += 1; ok += bool(c); print(("✅ " if c else "❌ ") + m + ("" if c else "  ← " + str(x)[:300]))
def home():
    T = tempfile.mkdtemp(prefix="shname-"); os.makedirs(os.path.join(T, ".local", "bin")); os.makedirs(os.path.join(T, "bin"))
    m = os.path.join(T, ".local", "bin", "mila"); open(m, "w").write("#!/bin/sh\necho ours\n"); os.chmod(m, 0o755)
    return T, m
def run(T, m, *extra, shell="/bin/bash", path=None):
    env = {k: v for k, v in os.environ.items() if k not in ("BASH_ENV", "ENV")}
    env.update(HOME=T, SHELL=shell, PATH=path or (os.path.join(T, "bin") + ":/usr/bin:/bin"))
    t0 = time.time(); r = subprocess.run([sys.executable, "-B", S, m] + list(extra), capture_output=True, text=True, env=env, timeout=40)
    return r.returncode, r.stdout, time.time() - t0
try:
    T, m = home()
    rc, out, _ = run(T, m, path=os.path.join(T, ".local", "bin") + ":/usr/bin:/bin")
    chk("чисто: mila — наша, ничего не сказано, код 0", rc == 0 and out == "", out)
    rc_text = "# claw\nmila() {\n  claw \"$@\"\n}\n"; open(os.path.join(T, ".bashrc"), "w").write(rc_text)
    rc, out, _ = run(T, m)
    chk("функция в ~/.bashrc: оболочка, вид, файл, строка 2; полный путь и uninstall полным путём", rc == 1 and "bash is a shell function (~/.bashrc)" in out
        and "2: mila() {" in out and "~/.local/bin/mila uninstall" in out, out)
    chk("rc-файл не тронут", open(os.path.join(T, ".bashrc")).read() == rc_text)
    rc, out, _ = run(T, m, "--short"); chk("--short — одна строка «bash function in ~/.bashrc»", rc == 1 and out.strip() == "bash function in ~/.bashrc", out)
    os.makedirs(os.path.join(T, ".claw")); open(os.path.join(T, ".claw", "sh.sh"), "w").write("alias mila='claw'\n")
    open(os.path.join(T, ".bashrc"), "w").write("source ~/.claw/sh.sh\n")
    rc, out, _ = run(T, m); chk("алиас из подключаемого файла — назван", rc == 1 and "is an alias" in out and "alias mila='claw'" in out, out)
    open(os.path.join(T, ".bashrc"), "w").write('echo "Welcome back!"\nfortune_line() { :; }\nmila() { claw; }\n')
    rc, out, _ = run(T, m); chk("rc печатает приветствие при старте — перехват всё равно назван", rc == 1 and "bash is a shell function (~/.bashrc)" in out, out)
    open(os.path.join(T, ".bashrc"), "w").write("sleep 30\n")
    rc, out, dt = run(T, m); chk("оболочка зависла на rc — через ~5 с без ложной тревоги", rc == 0 and out == "" and dt < 15, (rc, out, dt))
    # zsh: a stand-in that answers like zsh's whence -v
    os.remove(os.path.join(T, ".bashrc")); z = os.path.join(T, "bin", "zsh")
    open(os.path.join(T, ".zshrc"), "w").write("export A=1\nfunction mila {\n  claw\n}\n")
    open(z, "w").write('#!/bin/sh\necho "Welcome back!"\necho "mila is a shell function from %s/.zshrc"\necho __MILA_PROBE__\necho "mila is a shell function from %s/.zshrc"\n' % (T, T)); os.chmod(z, 0o755)
    rc, out, _ = run(T, m, shell="/bin/zsh")
    chk("zsh (подставной whence -v): функция из ~/.zshrc, строка 2 «function mila {»", rc == 1 and "zsh is a shell function (~/.zshrc)" in out and "2: function mila {" in out, out)
    open(z, "w").write('#!/bin/sh\necho "mila is a shell function from %s/.zshrc"\necho __MILA_PROBE__\necho "mila is %s"\n' % (T, m)); os.chmod(z, 0o755)
    rc, out, _ = run(T, m, shell="/bin/zsh"); chk("zsh: mila — наш файл → тихо (строка до метки — не ответ)", rc == 0 and out == "", out)
    open(z, "w").write('#!/bin/sh\necho "mila is a shell function from %s/.zshrc"\n' % T); os.chmod(z, 0o755)
    rc, out, _ = run(T, m, shell="/bin/zsh"); chk("zsh не дошёл до запроса (нет метки) — ничего не утверждаю", rc == 0 and out == "", out)
    shutil.rmtree(T)
finally:
    for d in os.listdir(tempfile.gettempdir()):
        if d.startswith("shname-"): shutil.rmtree(os.path.join(tempfile.gettempdir(), d), ignore_errors=True)
print("итог %d/%d" % (ok, n)); sys.exit(0 if ok == n else 1)
