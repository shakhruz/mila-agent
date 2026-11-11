#!/usr/bin/env python3
"""doctor in a home that is installed but not born yet: no red line and no «broken» — one plain line «not born yet → mila onboard»,
exit code 0; the channel folder the installer creates is closed (700). A home with a token or a paired owner is not «unborn»: the
ordinary checks run. A channel folder taken from the environment and lying outside the home is said so. No network.
Run: python3 install/test_doctor_unborn.py"""
import json, os, shutil, subprocess, sys, tempfile
os.umask(0o022)   # the usual umask of a person's shell: with 077 every new folder is 700 by itself and the check below proves nothing
H = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(H)
T = tempfile.mkdtemp(prefix="unborn-"); HOME = os.path.join(T, "home"); CL = os.path.join(HOME, ".claude"); ST = os.path.join(CL, "channels", "telegram")
ok = n = 0
def chk(m, c, x=""):
    global ok, n
    n += 1; ok += bool(c); print(("✅ " if c else "❌ ") + m + ("" if c else "  ← " + str(x)[:400]))
STATE_VAR = "TELEGRAM_" + "STATE_DIR"; TOKEN_VAR = "TELEGRAM_" + "BOT_TOKEN"
BASE = {k: v for k, v in os.environ.items() if k not in (STATE_VAR, TOKEN_VAR, "CLAUDE_CONFIG_DIR", "MILA_LANG", "XDG_CONFIG_HOME")}
ENV = dict(BASE, HOME=HOME, CLAUDE_CONFIG_DIR=CL, MILA_LANG="en", MILA_SKIP_TIMERS="1", TELEGRAM_API_ROOT="http://127.0.0.1:9")
def doctor(*args, **extra):
    r = subprocess.run([sys.executable, "-B", os.path.join(CL, "hooks", "doctor.py"), *args], capture_output=True, text=True, env=dict(ENV, **extra), timeout=120)
    return r.returncode, r.stdout + r.stderr
try:
    r = subprocess.run(["bash", os.path.join(H, "install.sh")], capture_output=True, text=True, env=ENV, timeout=300)
    chk("чистая установка прошла", r.returncode == 0, r.stdout[-300:] + r.stderr[-300:])
    chk("папку канала установщик создаёт закрытой: 700", os.path.isdir(ST) and (os.stat(ST).st_mode & 0o777) == 0o700, oct(os.stat(ST).st_mode & 0o777) if os.path.isdir(ST) else "нет папки")
    rc, out = doctor()
    chk("сразу после установки у доктора нет ни одной красной строки и слова «Broken»", "🔴" not in out and "Broken" not in out, out[-600:])
    chk("одна ясная строка: ещё не родилась → mila onboard; итог тоже про это; код выхода 0", rc == 0 and "⚪" in out and out.count("not born yet") == 1 and "mila onboard" in out and "Not born yet. Next step: mila onboard" in out, out[-600:])
    chk("проверок живого канала нет: ни «token not found», ни «daemon», ни «channel in session»", "token" not in out.replace("bot token", "") and "daemon" not in out and "channel in session" not in out, out)
    rc, out = doctor("--json"); d = json.loads(out)
    chk("--json: unborn true, bad 0", rc == 0 and d.get("unborn") is True and d["bad"] == 0 and any(x["level"] == "info" for x in d["rows"]), d)
    # не «не родилась»: ключ есть (пусть и негодный) — обычные проверки, красная строка о ключе
    rc, out = doctor(**{TOKEN_VAR: "ne" + "-klyuch"})
    chk("ключ задан, но не похож на ключ бота — это уже не «не родилась»: красная строка о ключе, код 1", rc == 1 and "🔴" in out and "⚪" not in out and "does not look like a Telegram token" in out, out[-500:])
    # не «не родилась»: кто-то уже подключён, а ключа нет — это поломка, как раньше
    open(os.path.join(ST, "access" + ".json"), "w").write(json.dumps({"allowFrom": ["555" + "000111"]})); os.chmod(os.path.join(ST, "access" + ".json"), 0o600)
    rc, out = doctor()
    chk("подключённый хозяин есть, ключа нет — «token not found» красным, как раньше", rc == 1 and "token" in out and "not found" in out and "⚪" not in out, out[-500:])
    os.remove(os.path.join(ST, "access" + ".json"))
    # папка канала из окружения, вне этого дома
    other = os.path.join(T, "drugoj-dom", "channel"); os.makedirs(other, mode=0o700)
    rc, out = doctor(**{STATE_VAR: other})
    chk("папка канала взята из окружения и лежит вне дома — сказано прямо, жёлтым, с путём", "🟡" in out and "lies outside this home" in out and other in out, out[:700])
    rc, out = doctor(**{STATE_VAR: ST})
    chk("та же переменная указывает внутрь дома — предупреждения нет", "lies outside this home" not in out, out[:400])
    # существующую папку шире 700 установщик не трогает — о ней скажет доктор
    shutil.rmtree(os.path.join(CL, "channels")); os.makedirs(ST, mode=0o755); os.chmod(ST, 0o755)
    subprocess.run(["bash", os.path.join(H, "install.sh")], capture_output=True, text=True, env=ENV, timeout=300)
    rc, out = doctor()
    chk("папка канала была до установки с правами 755 — установщик её права не меняет, доктор называет это красным", (os.stat(ST).st_mode & 0o777) == 0o755 and "🔴" in out and "755" in out, out[-500:])
finally:
    shutil.rmtree(T, ignore_errors=True)
print("итог %d/%d" % (ok, n)); sys.exit(0 if ok == n else 1)
