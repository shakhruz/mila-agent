#!/usr/bin/env python3
"""A live Mila whose ~/.claude/settings.json lacks the hooks of the mila-tasks skill gets them: PostToolUse(reply) task-sent.py
and SessionStart task-open.py. Idempotent (a second run changes nothing), keeps a backup, never touches other hooks.
--guards: also the core's hooks and the deny rules for the key places. This part is NOT a second list any more — it calls
`skills/mila-update/update.py guards`, the same code the update runs on every apply, and that code reads the one list in
release.json (guards, guards_required, deny_required). So the birth template, the update and this tool cannot drift apart.
Only guards whose file is in the home and compiles, and who are not wired yet; without the mila-tasks skill, --guards wires the guards only.
  python3 hooks_sync.py [--home DIR] [--dry-run] [--guards]     prints JSON {added:[…], hooks_dir, backup}"""
import datetime, json, os, subprocess, sys

REPLY = "mcp__plugin_(mila-)?telegram_telegram__reply"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def guards(home, dry):
    """Wire the core's guards with the update's own code. → (labels of what was added, backup path or None)."""
    env = dict(os.environ, HOME=home, MILA_HOME=home, CLAUDE_CONFIG_DIR=os.path.join(home, ".claude"))
    cmd = [sys.executable, "-I", os.path.join(ROOT, "skills", "mila-update", "update.py"), "guards", "--src", ROOT] + (["--dry-run"] if dry else [])
    r = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=120)
    try: o = json.loads(r.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError): o = None
    if r.returncode != 0 or not isinstance(o, dict) or o.get("ok") is not True:
        print(json.dumps({"ok": False, "error": "update.py guards: " + (r.stderr.strip().splitlines() or ["no answer"])[-1][:200]}, ensure_ascii=False)); sys.exit(3)
    return list(o.get("added") or []) + ["matcher: " + w for w in o.get("widened") or []] + ["deny: " + d for d in o.get("deny") or []], o.get("backup")


def find_tasks(home):
    for d in (os.path.join(home, ".claude", "skills", "mila-tasks", "hooks"), os.path.join(home, ".claude", "hooks")):
        if os.path.isfile(os.path.join(d, "task-sent.py")):
            return d
    return None


def main():
    a = sys.argv[1:]
    home = a[a.index("--home") + 1] if "--home" in a else os.path.expanduser("~")
    dry = "--dry-run" in a
    with_guards = "--guards" in a
    p = os.path.join(home, ".claude", "settings.json")
    d = find_tasks(home)
    if not d and not with_guards:
        print(json.dumps({"ok": False, "error": "нет task-sent.py (навык mila-tasks не установлен) — сначала mila-update install-skill mila-tasks"}, ensure_ascii=False)); sys.exit(2)
    added, gbackup = guards(home, dry) if with_guards else ([], None)     # first: the update's code writes settings.json itself
    raw = open(p, encoding="utf-8").read() if os.path.exists(p) else "{}"
    cfg = json.loads(raw or "{}"); hooks = cfg.setdefault("hooks", {})
    n0 = len(added)
    has = lambda ev, name: any(name in json.dumps(x) for x in hooks.get(ev, [])) or (name + " (" + ev + ")") in added   # the second half: a dry run of the guards has named it already
    if d and not has("PostToolUse", "task-sent.py"):
        hooks.setdefault("PostToolUse", []).append({"matcher": REPLY, "hooks": [{"type": "command", "command": "python3 " + os.path.join(d, "task-sent.py")}]})
        added.append("PostToolUse(reply): task-sent.py")
    if d and os.path.isfile(os.path.join(d, "task-open.py")) and not has("SessionStart", "task-open.py"):
        hooks.setdefault("SessionStart", []).append({"hooks": [{"type": "command", "command": "python3 " + os.path.join(d, "task-open.py")}]})
        added.append("SessionStart: task-open.py")
    backup = gbackup
    if len(added) > n0 and not dry:      # the mila-tasks hooks from the old place (~/.claude/hooks) — the only thing this tool still writes itself
        if os.path.exists(p):
            backup = p + ".bak-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
            open(backup, "w", encoding="utf-8").write(raw)
        tmp = p + ".tmp"
        open(tmp, "w", encoding="utf-8").write(json.dumps(cfg, ensure_ascii=False, indent=2))
        os.replace(tmp, p)
    print(json.dumps({"ok": True, "added": added, "hooks_dir": d, "backup": backup, "dry_run": dry}, ensure_ascii=False))


if __name__ == "__main__":
    main()
