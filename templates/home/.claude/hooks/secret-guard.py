#!/usr/bin/env python3
"""secret-guard.py — PreToolUse on Bash, Read, Grep, Glob, Edit, Write: the model does not touch the owner's sign-in token
and the safe's files with its own tools.

The token of the owner's Claude subscription lives in ~/.mila-auth (and in the session's environment), the keys of the safe in
~/work/secrets. Mila never needs to read them herself: the helpers that use a key read it at the moment of the action
(transcribe-voice.sh, safe_read.py). So a tool call that names these places, dumps the environment or reads another
process's environment is denied with one line.

This is a layer, not a wall: the session runs as the same user, and a determined command can be phrased so that no pattern
sees it. The wall is an isolated sandbox (CLAUDE_CODE_SUBPROCESS_ENV_SCRUB, it needs bubblewrap); where the platform allows it,
turn it on. Fail open: input it cannot read → allow (the send-guard still stops a key from leaving through Telegram).

Every refusal is one line in ~/.claude/mila-guard/secret-guard.jsonl (600): time, tool, which rule, what matched — a place or a
variable's name, never the command and never a value. So a false refusal can be seen and the rule tuned."""
import json, os, re, sys, time

PLACES = re.compile(r"\.mila-auth|work/secrets|/proc/[^/\s]*/environ|\.credentials\.json", re.I)
NAMES = re.compile(r"CLAUDE_CODE_OAUTH_TOKEN|ANTHROPIC_API_KEY|OPENROUTER_API_KEY|DEEPGRAM_API_KEY|GROQ_API_KEY|TELEGRAM_BOT_TOKEN", re.I)
# the whole environment: env / printenv / export -p / set / declare -x on their own (or piped)
DUMP = re.compile(r"(^|[;&|(`]\s*|\$\(\s*)(env|printenv|export\s+-p|declare\s+-[a-z]*x[a-z]*|set)\s*($|[;&|)`>])", re.I)
# helpers that legitimately read a key at the moment of the action
ALLOWED = re.compile(r"(transcribe-voice\.sh|safe_read\.py|key_page\.py|seif\.py|vault\.py)\b")


def check(tool, args):
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
    return None


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
        c = check(p.get("tool_name") or "", p.get("tool_input") or {})
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
