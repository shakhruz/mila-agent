#!/usr/bin/env python3
"""secret-guard.py — PreToolUse on Bash, Read, Grep, Glob, Edit, Write: the model does not touch the owner's sign-in token
and the safe's files with its own tools.

The token of the owner's Claude subscription lives in ~/.mila-auth (and in the session's environment), the keys of the safe in
~/work/secrets. Mila never needs to read them herself: the helpers that use a key read it at the moment of the action
(transcribe-voice.sh, safe_read.py). So a tool call that names these places, dumps the environment or reads another
process's environment is denied with one line.

This is a layer, not a wall: the session runs as the same user, and a determined command can be phrased so that no pattern
sees it. The wall is an isolated sandbox (CLAUDE_CODE_SUBPROCESS_ENV_SCRUB, it needs bubblewrap); where the platform allows it,
turn it on. Fail open: input it cannot read → allow (the send-guard still stops a key from leaving through Telegram); a path it cannot resolve → deny. A hard link to a key is told by its inode; a key with a second link closes lines-search everywhere.

Every refusal is one line in ~/.claude/mila-guard/secret-guard.jsonl (600): time, tool, which rule, what matched — a place or a
variable's name, never the command and never a value. So a false refusal can be seen and the rule tuned."""
import fnmatch, json, os, re, stat, sys, time

PLACES = re.compile(r"\.mila-auth|work/secrets|/proc/[^/\s]*/environ|\.credentials\.json|channels/[^/\s\"']+/\.env", re.I)
NAMES = re.compile(r"CLAUDE_CODE_OAUTH_TOKEN|ANTHROPIC_API_KEY|OPENROUTER_API_KEY|DEEPGRAM_API_KEY|GROQ_API_KEY|TELEGRAM_BOT_TOKEN", re.I)
# the whole environment: env / printenv / export -p / set / declare -x on their own (or piped)
DUMP = re.compile(r"(^|[;&|(`]\s*|\$\(\s*)(env|printenv|export\s+-p|declare\s+-[a-z]*x[a-z]*|set)\s*($|[;&|)`>])", re.I)
# helpers that legitimately read a key at the moment of the action
ALLOWED = re.compile(r"(transcribe-voice\.sh|safe_read\.py|key_page\.py|seif\.py|vault\.py)\b")


def secret_places(home):
    """The places by their real path — a link in ~/work to ~/.mila-auth is the same file (audit 09.11 №13)."""
    out = [os.path.join(home, ".mila-auth"), os.path.join(home, "work", "secrets"), os.path.join(home, ".claude", ".credentials.json")]
    ch = os.path.join(home, ".claude", "channels")
    try: out += [os.path.join(ch, d, ".env") for d in sorted(os.listdir(ch))]
    except OSError: pass
    return [(p, os.path.realpath(p)) for p in out]


def inside(p, root):
    try: return os.path.commonpath([p, root]) == root
    except ValueError: return False


def globs(g):
    """'*.{ts,tsx}' → ['*.ts', '*.tsx']; one level of braces is what the tool takes in practice."""
    m = re.search(r"\{([^{}]*)\}", g)
    return [g[:m.start()] + x + g[m.end():] for x in m.group(1).split(",")] if m else [g]


def key_files(real):
    """Files of one place (a file or a folder's top level) — enough to test a search's glob against."""
    if os.path.isdir(real):
        try: return [os.path.join(real, f) for f in os.listdir(real)]
        except OSError: return []
    return [real] if os.path.exists(real) else []


DEEP_CAP = 5000


def key_inodes(real):
    """(device, inode) of every file of one place, sub-folders too (os.walk, links not followed); (set, linked). Past DEEP_CAP
    files the place counts as linked — lines-search closes rather than a key going unseen (Quality 10.11: secrets/sub/deep)."""
    keys, linked, seen = set(), False, 0
    if os.path.isdir(real) and not os.path.islink(real):
        walk = ((dp, fns) for dp, _dns, fns in os.walk(real, followlinks=False))
    else:
        walk = [(os.path.dirname(real), [os.path.basename(real)])]
    for dp, fns in walk:
        for f in fns:
            seen += 1
            if seen > DEEP_CAP: return keys, True
            try: st = os.lstat(os.path.join(dp, f))
            except OSError: continue
            if stat.S_ISREG(st.st_mode): keys.add((st.st_dev, st.st_ino)); linked = linked or st.st_nlink > 1
    return keys, linked


def by_real_path(tool, args, cwd):
    """The same places for every reader by the real path, and a search whose root holds a place prints no lines from it."""
    home = os.path.expanduser("~")
    raw = str(args.get("file_path") or args.get("notebook_path") or args.get("path") or "")
    if not raw and tool not in ("Grep", "Glob"): return None
    real = os.path.realpath(os.path.join(cwd or os.getcwd(), os.path.expanduser(raw)))
    places = secret_places(home)
    for p, rp in places:
        if inside(real, rp):
            return "это файлы входа или сейфа (по настоящему пути) — ключи читают только инструменты в момент действия", "place", "~/" + os.path.relpath(p, home)
    # a hard link has no other real path: the same file is told by (device, inode); a second link anywhere closes lines-search
    keys, linked = set(), False
    for p, rp in places:
        k, l = key_inodes(rp); keys |= k; linked = linked or l
    try: st = os.stat(real)
    except OSError: st = None
    if st is not None and stat.S_ISREG(st.st_mode) and (st.st_dev, st.st_ino) in keys:
        return "это файл ключа под другим именем (жёсткая ссылка)", "hardlink", "inode"
    if tool != "Grep" or (args.get("output_mode") or "files_with_matches") != "content":
        return None   # names and counts of files, not their lines
    if linked:
        return "у файла ключа есть вторая жёсткая ссылка — поиск со строками закрыт, скажите хозяину", "hardlink", "nlink"
    g = str(args.get("glob") or "")
    for p, rp in places:
        if not inside(rp, real): continue
        files = key_files(rp)
        if g and not any(fnmatch.fnmatch(os.path.basename(f), x) or fnmatch.fnmatch(f, "*/" + x) for f in files for x in globs(g)):
            continue
        if files:
            return "поиск со строками захватывает %s — сузьте путь или укажите glob" % ("~/" + os.path.relpath(p, home)), "root", "~/" + os.path.relpath(p, home)
    return None


def check(tool, args, cwd=None):
    """(reason, rule, what matched) or None."""
    if tool == "Bash":
        cmd = str(args.get("command") or "")
        if ALLOWED.search(cmd) and not DUMP.search(cmd):
            return None
        m = PLACES.search(cmd)
        if m: return "команда трогает файлы входа или сейфа", "place", m.group(0)
        m = NAMES.search(cmd)
        if m: return "команда называет переменную с ключом", "name", m.group(0).upper()
        m = DUMP.search(cmd)
        if m: return "команда выводит всё окружение (там ключи)", "dump", m.group(2).split()[0].lower()
        return None
    target = " ".join(str(args.get(k) or "") for k in ("file_path", "path", "pattern", "glob"))
    m = PLACES.search(target)
    if m: return "это файлы входа или сейфа — ключи читают только инструменты в момент действия", "place", m.group(0)
    try: return by_real_path(tool, args, cwd)
    except Exception: return "не разобрала путь — для файлов ключей это значит «нет»", "error", "path"


def why(tool, args):
    c = check(tool, args)
    return c[0] if c else None


def journal(tool, rule, what):
    """One line per refusal; never the command, never a value. A journal that cannot be written does not change the answer."""
    try:
        d = os.path.join(os.environ.get("CLAUDE_CONFIG_DIR") or os.path.expanduser("~/.claude"), "mila-guard")
        os.makedirs(d, mode=0o700, exist_ok=True)
        p = os.path.join(d, "secret-guard.jsonl")
        fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "tool": tool, "rule": rule, "what": what}, ensure_ascii=False) + "\n")
    except Exception:
        pass


def main():
    try:
        p = json.loads(sys.stdin.read() or "{}")
        c = check(p.get("tool_name") or "", p.get("tool_input") or {}, p.get("cwd"))
    except Exception:
        return 0
    r = c[0] if c else None
    if c:
        journal(p.get("tool_name") or "", c[1], c[2])
    if r:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
              "permissionDecisionReason": "Не делаю: %s. Ключи хозяина я не читаю сама — их берут нужные инструменты." % r}}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
