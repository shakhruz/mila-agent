#!/usr/bin/env python3
"""(20.10, после раскатки 2.0: у Мил из образа нет PostToolUse журнала исходящих — tasks/sent.jsonl не пишется, обещания не
закрываются с уликой): у уже живой Милы дописывает в ~/.claude/settings.json недостающие хуки mila-tasks — PostToolUse(reply) task-sent.py
и SessionStart task-open.py. Идемпотентно (второй запуск ничего не меняет), бэкап settings.json, чужие хуки не трогает.
mila-update settings.json не трогает, поэтому нужен этот шаг при раскатке.
--guards (06.11, канарейка v1.7.2: сторожа лежали в доме, но не были подключены): ещё и хуки из ~/.claude/hooks, которые ставит
обновление, — так же, как install.sh: send-guard и done-guard на отправку, done-guard на PostToolUseFailure (Claude Code ≥ 2.1.295),
secret-guard на инструменты с deny-правилами входа и сейфа, skill-hint, pd-mask, crons-keeper, reply-required. Только те, чей файл
есть и кто ещё не записан; без навыка mila-tasks с --guards — только сторожа.
  python3 hooks_sync.py [--home DIR] [--dry-run] [--guards]     выход: JSON {added:[…], hooks_dir, backup}"""
import datetime, json, os, re, subprocess, sys

REPLY = "mcp__plugin_(mila-)?telegram_telegram__reply"
SEND_RE = ("mcp__plugin_(mila-)?telegram_telegram__reply|mcp__plugin_(mila-)?telegram_telegram__edit_message"
           "|mcp__plugin_(mila-)?telegram_telegram__topic|mcp__plugin_(mila-)?telegram_telegram__widget|mcp__plugin_(mila-)?telegram_telegram__widget_data")   # as install/install.sh
DENY = ("Read(~/.mila-auth/**)", "Edit(~/.mila-auth/**)", "Read(~/work/secrets/**)", "Edit(~/work/secrets/**)")


def onfail_ok():
    v = os.environ.get("MILA_CC_VERSION") or ""
    if not v:
        try: v = subprocess.run(["claude", "--version"], capture_output=True, text=True, timeout=10).stdout
        except Exception: v = ""
    m = re.search(r"(\d+)\.(\d+)\.(\d+)", v)
    return bool(m) and tuple(int(x) for x in m.groups()) >= (2, 1, 295)


def guards(home, cfg, hooks, has, added):
    """The hooks mila-update delivers into ~/.claude/hooks, registered the way install.sh does it."""
    hd = os.path.join(home, ".claude", "hooks")
    cmd = lambda f: "python3 " + os.path.join(hd, f)
    here = lambda f: os.path.isfile(os.path.join(hd, f))
    of = onfail_ok()
    def add(ev, entry, label):
        hooks.setdefault(ev, []).append(entry); added.append(label)
    if here("send-guard.py") and not has("PreToolUse", "send-guard.py"):
        add("PreToolUse", {"matcher": SEND_RE, "hooks": [dict({"type": "command", "command": cmd("send-guard.py")}, **({"onFailure": "block"} if of else {}))]}, "PreToolUse(send): send-guard.py")
    if here("done-guard.py"):
        if not has("PreToolUse", "done-guard.py"):
            add("PreToolUse", {"matcher": SEND_RE, "hooks": [{"type": "command", "command": cmd("done-guard.py")}]}, "PreToolUse(send): done-guard.py")
        if of and not has("PostToolUseFailure", "done-guard.py"):
            add("PostToolUseFailure", {"hooks": [{"type": "command", "command": cmd("done-guard.py")}]}, "PostToolUseFailure: done-guard.py")
    if here("secret-guard.py"):
        if not has("PreToolUse", "secret-guard.py"):
            add("PreToolUse", {"matcher": "Bash|Read|Grep|Glob|Edit|Write|MultiEdit", "hooks": [{"type": "command", "command": cmd("secret-guard.py")}]}, "PreToolUse(tools): secret-guard.py")
        deny = cfg.setdefault("permissions", {}).setdefault("deny", [])
        for r in DENY:
            if r not in deny: deny.append(r); added.append("deny: " + r)
    if here("skill-hint.py") and not has("UserPromptSubmit", "skill-hint.py"):
        add("UserPromptSubmit", {"hooks": [{"type": "command", "command": cmd("skill-hint.py")}]}, "UserPromptSubmit: skill-hint.py")
    if here("pd-mask.py") and not has("PostToolUse", "pd-mask.py"):
        add("PostToolUse", {"matcher": "Write|Edit|MultiEdit", "hooks": [{"type": "command", "command": cmd("pd-mask.py")}]}, "PostToolUse(write): pd-mask.py")
    if here("crons-keeper.py"):
        if not has("SessionStart", "crons-keeper.py"):
            add("SessionStart", {"hooks": [{"type": "command", "command": cmd("crons-keeper.py")}]}, "SessionStart: crons-keeper.py")
        if not has("PostToolUse", "crons-keeper.py"):
            add("PostToolUse", {"matcher": "CronCreate|CronDelete", "hooks": [{"type": "command", "command": cmd("crons-keeper.py")}]}, "PostToolUse(cron): crons-keeper.py")
    if here("reply-required.py") and not has("Stop", "reply-required.py"):
        add("Stop", {"hooks": [{"type": "command", "command": cmd("reply-required.py")}]}, "Stop: reply-required.py")


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
    raw = open(p, encoding="utf-8").read() if os.path.exists(p) else "{}"
    cfg = json.loads(raw or "{}"); hooks = cfg.setdefault("hooks", {})
    d = find_tasks(home)
    if not d and not with_guards:
        print(json.dumps({"ok": False, "error": "нет task-sent.py (навык mila-tasks не установлен) — сначала mila-update install-skill mila-tasks"}, ensure_ascii=False)); sys.exit(2)
    added = []
    has = lambda ev, name: any(name in json.dumps(x) for x in hooks.get(ev, []))
    if with_guards:
        guards(home, cfg, hooks, has, added)
    if d and not has("PostToolUse", "task-sent.py"):
        hooks.setdefault("PostToolUse", []).append({"matcher": REPLY, "hooks": [{"type": "command", "command": "python3 " + os.path.join(d, "task-sent.py")}]})
        added.append("PostToolUse(reply): task-sent.py")
    if d and os.path.isfile(os.path.join(d, "task-open.py")) and not has("SessionStart", "task-open.py"):
        hooks.setdefault("SessionStart", []).append({"hooks": [{"type": "command", "command": "python3 " + os.path.join(d, "task-open.py")}]})
        added.append("SessionStart: task-open.py")
    backup = None
    if added and not dry:
        if os.path.exists(p):
            backup = p + ".bak-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
            open(backup, "w", encoding="utf-8").write(raw)
        tmp = p + ".tmp"
        open(tmp, "w", encoding="utf-8").write(json.dumps(cfg, ensure_ascii=False, indent=2))
        os.replace(tmp, p)
    print(json.dumps({"ok": True, "added": added, "hooks_dir": d, "backup": backup, "dry_run": dry}, ensure_ascii=False))


if __name__ == "__main__":
    main()
