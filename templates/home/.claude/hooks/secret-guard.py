#!/usr/bin/env python3
"""secret-guard.py — PreToolUse on Bash, Read, Grep, Glob, Edit, Write: the model does not touch the owner's sign-in token
and the safe's files with its own tools.

The token of the owner's Claude subscription lives in ~/.mila-auth (and in the session's environment), the keys of the safe in
~/work/secrets. Mila never needs to read them herself: the helpers that use a key read it at the moment of the action
(transcribe-voice.sh, safe_read.py). So a tool call that names these places, dumps the environment or reads another
process's environment is denied with one line.

This is a layer, not a wall: the session runs as the same user, and a determined command can be phrased so that no pattern
sees it. The wall is an isolated sandbox (CLAUDE_CODE_SUBPROCESS_ENV_SCRUB, it needs bubblewrap); where the platform allows it,
turn it on. Fail open: input it cannot read → allow (the send-guard still stops a key from leaving through Telegram)."""
import json, re, sys

PLACES = re.compile(r"\.mila-auth|work/secrets|/proc/[^/\s]*/environ|\.credentials\.json", re.I)
NAMES = re.compile(r"CLAUDE_CODE_OAUTH_TOKEN|ANTHROPIC_API_KEY|OPENROUTER_API_KEY|DEEPGRAM_API_KEY|GROQ_API_KEY|TELEGRAM_BOT_TOKEN", re.I)
# the whole environment: env / printenv / export -p / set / declare -x on their own (or piped)
DUMP = re.compile(r"(^|[;&|(`]\s*|\$\(\s*)(env|printenv|export\s+-p|declare\s+-[a-z]*x[a-z]*|set)\s*($|[;&|)`>])", re.I)
# helpers that legitimately read a key at the moment of the action
ALLOWED = re.compile(r"(transcribe-voice\.sh|safe_read\.py|key_page\.py|seif\.py|vault\.py)\b")


def why(tool, args):
    if tool == "Bash":
        cmd = str(args.get("command") or "")
        if ALLOWED.search(cmd) and not DUMP.search(cmd):
            return None
        if PLACES.search(cmd): return "команда трогает файлы входа или сейфа"
        if NAMES.search(cmd): return "команда называет переменную с ключом"
        if DUMP.search(cmd): return "команда выводит всё окружение (там ключи)"
        return None
    target = " ".join(str(args.get(k) or "") for k in ("file_path", "path", "pattern", "glob"))
    if PLACES.search(target): return "это файлы входа или сейфа — ключи читают только инструменты в момент действия"
    return None


def main():
    try:
        p = json.loads(sys.stdin.read() or "{}")
        r = why(p.get("tool_name") or "", p.get("tool_input") or {})
    except Exception:
        return 0
    if r:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
              "permissionDecisionReason": "Не делаю: %s. Ключи хозяина я не читаю сама — их берут нужные инструменты." % r}}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
