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

When the copy cannot be used (missing, changed, or itself failing), the guard must not go on letting everything through:
a stub takes its place and refuses every call of the guard's zone, with the reason and the way out («mila update» from a
terminal). The stub is used instead of the hook's onFailure field on purpose: onFailure stops a guard that crashes, not one
that exits 0 having refused nothing. The update knows the stub by its hash and replaces it with the release guard. A guard
that cannot refuse by design (a PostToolUse one, pd-mask) gets no stub — it stays «broken» in the state until repaired.

This is a guard against a typo or a failed write, not against intent: the copy and its hash are written by the same user
as the guard itself.

  guard_check.py            check, repair what can be repaired, write the state file, print one line per finding
  guard_check.py --no-fix   check only
  guard_check.py --json     the state as JSON
  guard_check.py --start    for the SessionStart hook: the same, and a line to the administrator's inbox when something changed
  guard_check.py --hook     for a PostToolUse hook on Write|Edit|MultiEdit: check only when the edited file is a hook
Exit code: 0 — all required guards work (after repair too); 1 — a required guard is broken or blocked."""
import hashlib, json, os, stat, subprocess, sys, tempfile, time

CLAUDE = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(os.path.expanduser("~"), ".claude")
STATE = os.path.join(CLAUDE, "mila-update")
VERSION = os.path.join(STATE, "version.json")
COPIES = os.path.join(STATE, "guards")
STATE_FILE = os.path.join(STATE, "guards-state.json")
TIMEOUT = 10
ADMIN_INBOX = os.environ.get("MILA_SENIOR_INBOX") or os.path.join(os.environ.get("MILA_WORK") or os.path.join(os.path.expanduser("~"), "work"), "inbox", "to-admin.jsonl")
STUB_MARK = "# mila-guard-stub"
STUB = '''#!/usr/bin/env python3
# mila-guard-stub: %(name)s — this guard was broken and its release copy could not be used. Until «mila update» puts the
# real guard back, every call of its zone is refused: a guard that lets everything through in silence is worse than a stop.
import json, sys
ZONE = %(zone)r
try:
    p = json.loads(sys.stdin.read() or "{}")
except Exception:
    p = {}
t = str(p.get("tool_name") or "") if isinstance(p, dict) else ""
if not t or any((k == "=" and t == v) or (k == "$" and t.endswith(v)) for k, v in ZONE):
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                             "permissionDecisionReason": "Сторож %(name)s сломан и не восстановлен — инструменты его зоны остановлены. Починка: «mila update» из терминала."}}, ensure_ascii=False))
    sys.exit(2)
sys.exit(0)
'''


def zone_of(matcher):
    """The guard's zone from its hook matcher, without regular expressions in the stub: «A|B» → exact names; a name of an MCP
    tool («…__reply») → its suffix after the last «__», so both spellings of the plugin's name match."""
    out = []
    for alt in str(matcher or "").split("|"):
        alt = alt.strip()
        if not alt: continue
        out.append(("$", "__" + alt.rsplit("__", 1)[1]) if "__" in alt else ("=", alt))
    return tuple(dict.fromkeys(out))


def stub_text(name, matcher):
    return STUB % {"name": name, "zone": zone_of(matcher)}


def sha16(path):
    try: return hashlib.sha256(open(path, "rb").read()).hexdigest()[:16]
    except OSError: return None


def load_state():
    try:
        d = json.load(open(STATE_FILE, encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


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


def put_stub(path, name, matcher, now=None):
    """The broken guard → <name>.broken-<time>; a refusing stub in its place (same mode). → the stub's sha16, or None."""
    if not zone_of(matcher): return None
    text = stub_text(name, matcher).encode("utf-8")
    try:
        mode = 0o755
        if os.path.lexists(path):
            if os.path.islink(path): return None
            mode = stat.S_IMODE(os.lstat(path).st_mode)
            base = "%s.broken-%s" % (path, time.strftime("%Y%m%d-%H%M%S", time.localtime(now))); broken, n = base, 0
            while os.path.lexists(broken): n += 1; broken = "%s-%d" % (base, n)
            os.rename(path, broken)
        tmp = path + ".new"
        try: os.unlink(tmp)
        except FileNotFoundError: pass
        os.makedirs(os.path.dirname(path), exist_ok=True)
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode)
        try: os.fchmod(fd, mode); os.write(fd, text)
        finally: os.close(fd)
        os.replace(tmp, path)
    except OSError:
        return None
    return hashlib.sha256(text).hexdigest()[:16]


def repair(key, path, want_sha, control, now=None, keep_broken=True):
    """Put the release copy in place of a broken guard. → '' when done, otherwise why not.
    keep_broken=False — what stands in the guard's place is our own stub: it is simply replaced, no .broken file from it."""
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
            if keep_broken:
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
    """Check every required guard; repair when allowed; block what cannot be repaired. → state dict (also written to the state file)."""
    v = load_version(); prev = load_state()
    required = [k for k in (v.get("guards_required") or []) if isinstance(k, str)]
    copies = v.get("guard_copies") if isinstance(v.get("guard_copies"), dict) else {}
    controls = v.get("guard_controls") if isinstance(v.get("guard_controls"), dict) else {}
    zones = v.get("guard_zones") if isinstance(v.get("guard_zones"), dict) else {}
    stubs = {p: h for p, h in (prev.get("stubs") or {}).items() if isinstance(p, str) and isinstance(h, str)} if isinstance(prev.get("stubs"), dict) else {}
    out = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(now)), "guards": "ok", "checked": [], "replaced": [], "broken": [], "blocked": [], "stubs": {}}
    for key in required:
        path = guard_path(key)
        if not path: continue
        name = os.path.basename(path); out["checked"].append(name)
        is_stub = path in stubs and sha16(path) == stubs[path]       # our own stub, byte for byte; an owner's edit on top of it is not
        if is_stub:
            not_done = repair(key, path, copies.get(key), controls.get(key), now, keep_broken=False) if fix else "починка не запрошена"
            if not not_done: out["replaced"].append({"name": name, "why": "стояла заглушка"})
            else: out["blocked"].append({"name": name, "why": not_done}); out["stubs"][path] = stubs[path]
            continue
        why = check_file(path, controls.get(key))
        if not why: continue
        if fix:
            not_done = repair(key, path, copies.get(key), controls.get(key), now)
            if not not_done:
                out["replaced"].append({"name": name, "why": why}); continue
            why = "%s; %s" % (why, not_done)
            # no usable copy: a guard that can refuse gets a refusing stub; one that cannot (no control, e.g. PostToolUse) stays «broken»
            h = put_stub(path, name, zones.get(key), now) if isinstance(controls.get(key), dict) else None
            if h:
                out["blocked"].append({"name": name, "why": why}); out["stubs"][path] = h; continue
        out["broken"].append({"name": name, "why": why})
    out["guards"] = "blocked" if out["blocked"] else "broken" if out["broken"] else "replaced" if out["replaced"] else "ok"
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
    out["_changed"] = _summary(out) != _summary(prev)
    return out


def _summary(st):
    return [st.get("guards"), sorted(x.get("name", "") for k in ("replaced", "broken", "blocked") for x in (st.get(k) or []) if isinstance(x, dict))]


def tell_admin(st):
    """One line to the administrator's inbox of this home — only when the picture changed since the last check, and only when
    there is something to say. The folder must already exist (a home without the channel gets nothing written)."""
    L = lines(st)
    if not L or not st.get("_changed") or not os.path.isdir(os.path.dirname(ADMIN_INBOX)): return False
    rec = {"id": "%s-guards" % time.strftime("%Y-%m-%dT%H:%M:%S"), "ts": time.strftime("%Y-%m-%dT%H:%M%z"), "kind": "alert", "status": "open",
           "agent": os.environ.get("MILA_AGENT", ""), "text": "Сторожа: " + " ".join(L)}
    try:
        fd = os.open(ADMIN_INBOX, os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "a", encoding="utf-8") as f: f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        return True
    except OSError:
        return False


def lines(st):
    """What a person should hear, one line per finding; nothing when all is well."""
    L = []
    for r in st["replaced"]:
        L.append("Сторож %s был сломан (%s) — заменён релизной копией; сломанный файл лежит рядом (.broken-…). Скажите хозяину и администратору." % (r["name"], r["why"]))
    for r in st.get("blocked") or []:
        L.append("Сторож %s сломан, и вернуть его не удалось (%s) — инструменты его зоны остановлены заглушкой. Починка: «mila update» из терминала. Скажите хозяину и администратору." % (r["name"], r["why"]))
    for r in st["broken"]:
        L.append("Сторож %s сломан и не защищает (%s). Нужна починка: «mila update» из терминала. Скажите хозяину и администратору." % (r["name"], r["why"]))
    return L


def edited_hook(payload):
    """Is the file a Write/Edit just touched one of this home's hooks (hooks/ or a skill's hooks/)?"""
    ti = payload.get("tool_input") if isinstance(payload, dict) else None
    f = str((ti or {}).get("file_path") or "") if isinstance(ti, dict) else ""
    if not f: return False
    real = os.path.realpath(os.path.expanduser(f)); base = os.path.realpath(CLAUDE)
    try: rel = os.path.relpath(real, base)
    except ValueError: return False
    parts = rel.split(os.sep)
    return not rel.startswith("..") and (parts[0] == "hooks" or (parts[0] == "skills" and "hooks" in parts[1:-1]))


def main(argv):
    if "--hook" in argv:                          # PostToolUse: a guard edited mid-session is checked at once, not at the next start
        try: payload = json.loads(sys.stdin.read() or "{}")
        except ValueError: return 0
        if not edited_hook(payload): return 0
        st = run(fix=True); tell_admin(st); L = lines(st)
        if L: print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": " ".join(L)}}, ensure_ascii=False))
        return 0
    st = run(fix="--no-fix" not in argv)
    if "--start" in argv: tell_admin(st)
    pub = {k: v for k, v in st.items() if not k.startswith("_")}
    if "--json" in argv: print(json.dumps(pub, ensure_ascii=False))
    else:
        for l in lines(st): print(l)
    return 1 if st["broken"] or st["blocked"] else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
