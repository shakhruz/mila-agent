#!/usr/bin/env python3
"""run-allow.py — PreToolUse on Bash, for the background session only (wired in mila-run-settings.json).

With nobody at a screen Claude Code refuses every Bash command that is not allowed beforehand. A prefix rule like
«python3 ~/.claude/skills/…» is not enough of a fence: «python3 ~/.claude/skills/../../work/x.py» has the same prefix, and the
session may write x.py itself. So there is no Bash rule in the allow-list at all; this hook allows exactly one shape of command:

    python3 [-B] <script> [arguments]        bash <script> [arguments]

where <script>, after ~ is expanded and every link is resolved, is a regular file inside ~/.claude/skills or ~/.claude/hooks
(what the kit installed — the session cannot write there), has no «..» in it as typed, and the command has nothing a shell
would act on: no ; | & ` $ < > ( ) newline, no variable assignment in front. Anything else gets NO decision from this hook —
Claude Code then refuses it by itself, as it does for every command nobody allowed.
Fail closed: input that cannot be read, any error — no decision."""
import json, os, re, shlex, sys

SHELL = re.compile(r"[;|&`$<>()\n\r\\]")


def roots():
    h = os.path.expanduser("~")
    return [os.path.realpath(os.path.join(h, ".claude", "skills")), os.path.realpath(os.path.join(h, ".claude", "hooks"))]


def own_script(cmd):
    """→ the resolved path of her own script this command runs, or '' (not that shape)."""
    if not isinstance(cmd, str) or not cmd.strip() or len(cmd) > 4000 or SHELL.search(cmd):
        return ""
    try:
        argv = shlex.split(cmd)
    except ValueError:
        return ""
    if len(argv) < 2 or argv[0] not in ("python3", "bash"):
        return ""
    i = 1
    if argv[0] == "python3" and argv[1] == "-B":
        i = 2
    if i >= len(argv):
        return ""
    typed = argv[i]
    if typed.startswith("-") or ".." in typed.replace("\\", "/").split("/"):
        return ""
    p = os.path.expanduser(typed)
    if not os.path.isabs(p):
        return ""
    real = os.path.realpath(p)
    if not os.path.isfile(real):
        return ""
    return real if any(real.startswith(r + os.sep) for r in roots()) else ""


def main():
    try:
        d = json.loads(sys.stdin.read())
        if not isinstance(d, dict) or d.get("tool_name") != "Bash":
            return 0
        real = own_script((d.get("tool_input") or {}).get("command"))
    except Exception:
        return 0
    if real:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "allow",
                                                 "permissionDecisionReason": "her own script from the kit"}}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
