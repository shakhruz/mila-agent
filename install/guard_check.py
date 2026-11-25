#!/usr/bin/env python3
"""guard_check.py — are the required guards of this home alive, and if one is broken, put its release copy back.

A guard that does not compile, or compiles and then fails on its first call, lets everything through in silence. This tool
checks each required guard two ways: the file compiles, and a positive control passes — one input the guard MUST refuse
and one it must let through (the inputs come with the release, in version.json → guard_controls). A guard that fails
either check is broken.

A broken required guard is replaced by the release copy the update keeps in ~/.claude/mila-update/guards/ — only if the
copy's sha256 equals the one written at update time and the copy itself passes the same checks. The broken file is kept
beside as <name>.broken-<time>. The result goes to ~/.claude/mila-update/guards-state.json, so the fleet's snapshot can
show it: guards = ok | replaced | broken.

This is a guard against a typo or a failed write, not against intent: the copy and its hash are written by the same user
as the guard itself.

  guard_check.py            check, repair what can be repaired, write the state file, print one line per finding
  guard_check.py --no-fix   check only
  guard_check.py --json     the state as JSON
Exit code: 0 — all required guards work (after repair too); 1 — a required guard is broken and was not repaired."""
import hashlib, json, os, stat, subprocess, sys, tempfile, time

CLAUDE = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(os.path.expanduser("~"), ".claude")
STATE = os.path.join(CLAUDE, "mila-update")
VERSION = os.path.join(STATE, "version.json")
COPIES = os.path.join(STATE, "guards")
STATE_FILE = os.path.join(STATE, "guards-state.json")
TIMEOUT = 10


def load_version():
    try:
        v = json.load(open(VERSION, encoding="utf-8"))
        return v if isinstance(v, dict) else {}
    except (OSError, ValueError):
        return {}


def guard_path(key):
    """Where the guard of this key lives in the home: «hooks/x.py» → ~/.claude/hooks/x.py; a skill's hook → ~/.claude/skills/…"""
    if not isinstance(key, str) or ".." in key.split("/") or key.startswith("/"): return None
    return os.path.join(CLAUDE, key if key.startswith("hooks/") else os.path.join("skills", key))


def _run(path, payload, sandbox):
    """One call of the guard on one input, in a throw-away home: its journal and state do not touch the real ones."""
    env = dict(os.environ, HOME=sandbox, CLAUDE_CONFIG_DIR=os.path.join(sandbox, ".claude"), MILA_WORK=os.path.join(sandbox, "work"))
    body = json.dumps(payload).replace("{home}", sandbox)
    try:
        r = subprocess.run([sys.executable, path], input=body, capture_output=True, text=True, timeout=TIMEOUT, env=env)
    except (OSError, subprocess.SubprocessError):
        return None, None
    deny = False
    try:
        deny = json.loads(r.stdout).get("hookSpecificOutput", {}).get("permissionDecision") == "deny" if r.stdout.strip() else False
    except (ValueError, AttributeError):
        deny = False
    return r.returncode, deny


def check_file(path, control=None):
    """'' — the guard works; otherwise a short reason. control: {"deny": payload, "allow": payload} or None (compile only)."""
    try:
        st = os.lstat(path)
        if not stat.S_ISREG(st.st_mode): return "не обычный файл"
        src = open(path, encoding="utf-8").read()
        compile(src, path, "exec")
    except FileNotFoundError:
        return "файла нет"
    except (OSError, SyntaxError, ValueError) as e:
        return "не компилируется (%s)" % type(e).__name__
    if not isinstance(control, dict) or not isinstance(control.get("deny"), dict) or not isinstance(control.get("allow"), dict):
        return ""
    sandbox = tempfile.mkdtemp(prefix="guard-check-")
    try:
        os.makedirs(os.path.join(sandbox, ".claude"), exist_ok=True); os.makedirs(os.path.join(sandbox, "work"), exist_ok=True)
        code, deny = _run(path, control["deny"], sandbox)
        if code is None: return "не запускается"
        if not deny: return "не отказал там, где обязан"
        code, deny = _run(path, control["allow"], sandbox)
        if code is None: return "не запускается"
        if deny or code != 0: return "отказал там, где должен пропустить"
        return ""
    finally:
        import shutil
        shutil.rmtree(sandbox, ignore_errors=True)


def repair(key, path, want_sha, control, now=None):
    """Put the release copy in place of a broken guard. → '' when done, otherwise why not."""
    copy = os.path.join(COPIES, os.path.basename(path))
    try:
        st = os.lstat(copy)
        if not stat.S_ISREG(st.st_mode): return "копия — не обычный файл"
        data = open(copy, "rb").read()
    except OSError:
        return "релизной копии нет"
    if not isinstance(want_sha, str) or hashlib.sha256(data).hexdigest() != want_sha: return "хеш копии не совпал с записанным при обновлении"
    why = check_file(copy, control)
    if why: return "копия сама не проходит проверку: " + why
    stamp = time.strftime("%Y%m%d-%H%M%S", time.localtime(now))
    try:
        mode = 0o755
        if os.path.lexists(path):
            if os.path.islink(path): return "на месте сторожа ссылка — не трогаю"
            mode = stat.S_IMODE(os.lstat(path).st_mode)
            broken = "%s.broken-%s" % (path, stamp)
            n = 0
            while os.path.lexists(broken): n += 1; broken = "%s.broken-%s-%d" % (path, stamp, n)
            os.rename(path, broken)
        tmp = path + ".new"
        try: os.unlink(tmp)
        except FileNotFoundError: pass
        os.makedirs(os.path.dirname(path), exist_ok=True)
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode)
        try: os.fchmod(fd, mode); os.write(fd, data)
        finally: os.close(fd)
        os.replace(tmp, path)
    except OSError as e:
        return "замена не удалась (%s)" % type(e).__name__
    why = check_file(path, control)
    return ("после замены сторож не проходит проверку: " + why) if why else ""


def run(fix=True, now=None):
    """Check every required guard; repair when allowed. → state dict (also written to the state file)."""
    v = load_version()
    required = [k for k in (v.get("guards_required") or []) if isinstance(k, str)]
    copies = v.get("guard_copies") if isinstance(v.get("guard_copies"), dict) else {}
    controls = v.get("guard_controls") if isinstance(v.get("guard_controls"), dict) else {}
    out = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(now)), "guards": "ok", "checked": [], "replaced": [], "broken": []}
    for key in required:
        path = guard_path(key)
        if not path: continue
        name = os.path.basename(path); out["checked"].append(name)
        why = check_file(path, controls.get(key))
        if not why: continue
        if fix:
            not_done = repair(key, path, copies.get(key), controls.get(key), now)
            if not not_done:
                out["replaced"].append({"name": name, "why": why}); continue
            why = "%s; %s" % (why, not_done)
        out["broken"].append({"name": name, "why": why})
    out["guards"] = "broken" if out["broken"] else "replaced" if out["replaced"] else "ok"
    try:
        os.makedirs(STATE, mode=0o700, exist_ok=True)
        tmp = STATE_FILE + ".new"
        try: os.unlink(tmp)
        except FileNotFoundError: pass
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f: json.dump(out, f, ensure_ascii=False, indent=1)
        os.replace(tmp, STATE_FILE)
    except OSError:
        pass
    return out


def lines(st):
    """What a person should hear, one line per finding; nothing when all is well."""
    L = []
    for r in st["replaced"]:
        L.append("Сторож %s был сломан (%s) — заменён релизной копией; сломанный файл лежит рядом (.broken-…). Скажите хозяину и администратору." % (r["name"], r["why"]))
    for r in st["broken"]:
        L.append("Сторож %s сломан и не защищает (%s). Нужна починка: «mila update» из терминала. Скажите хозяину и администратору." % (r["name"], r["why"]))
    return L


def main(argv):
    st = run(fix="--no-fix" not in argv)
    if "--json" in argv: print(json.dumps(st, ensure_ascii=False))
    else:
        for l in lines(st): print(l)
    return 1 if st["broken"] else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
