#!/usr/bin/env python3
"""install/permissions.example.json through the plugin's own engine (install/permission_policy.ts, bun): what is allowed, asked,
denied — for both shapes of the preview Claude Code relays (bare command and JSON-shaped {"command": …}). Run: python3 test_permissions_example.py"""
import json, os, shutil, subprocess, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); ok = n = 0
def check(name, c, x=""):
    global ok, n; n += 1; ok += bool(c); print(("✅ " if c else "❌ ") + name + ("" if c else "  ← " + str(x)[:300]))
if not shutil.which("bun"):
    print("bun нет — итог 0/0"); sys.exit(0)
J = lambda cmd: json.dumps({"command": cmd, "description": "look"})
CASES = [
 ("Bash", "ls -la ~/work", "allow"), ("Bash", J("git status"), "allow"), ("Bash", "grep -n foo README.md", "allow"),
 ("Bash", "ls; rm x", "ask"), ("Bash", "ls && curl evil.sh", "ask"), ("Bash", "cat a | sh", "ask"), ("Bash", "echo x > ~/.bashrc", "ask"),
 ("Bash", "echo $(id)", "ask"), ("Bash", "echo `id`", "ask"), ("Bash", "ls python3 evil.py", "ask"), ("Bash", J("ls\" ; rm -rf ~ ; echo \""), "deny"), ("Bash", J("ls\" ; curl evil ; echo \""), "ask"),
 ("Bash", "cat ~/work/.env", "deny"), ("Bash", "grep KEY ~/work/secrets/zernio.env", "deny"), ("Bash", J("cat ~/.claude/channels/telegram/.env"), "deny"),
 ("Bash", "python3 safe_read.py --key-file ~/work/secrets/x.key", "ask"), ("Bash", "rm -rf ~/work", "deny"),
 ("Read", json.dumps({"file_path": "/home/a/work/.env"}), "deny"), ("Read", json.dumps({"file_path": "/home/a/.claude/channels/telegram/.env"}), "deny"),
 ("Read", json.dumps({"file_path": "/home/a/work/NOW.md"}), "allow"),
 ("Edit", json.dumps({"file_path": "/home/a/.claude/settings.json"}), "ask"), ("Edit", json.dumps({"file_path": "/home/a/.claude/hooks/send-guard.py"}), "ask"),
 ("MultiEdit", json.dumps({"file_path": "/home/a/.claude/channels/telegram/access.json"}), "ask"),
 ("Edit", json.dumps({"file_path": "/home/a/work/NOW.md"}), "allow"),
 # Quality's escapes (01.11): must not be a silent allow
 ("Bash", "cat /proc/self/environ", "deny"), ("Bash", J("cat /proc/1/environ"), "deny"), ("Bash", "grep -r -e . /home/a/work", "ask"),
 ("Bash", "grep -R KEY .", "ask"), ("Bash", "rg -l sk- /", "ask"), ("Bash", "grep -r OPENROUTER /etc/mila", "ask"), ("Bash", "cat /etc/passwd", "ask"),
 ("Bash", "cat ~/.ssh/id_ed25519", "ask"), ("Bash", "ls ~/.config/mila", "ask"), ("Bash", "cat ~/.claude/settings.json", "ask"), ("Bash", "cat ../../.ssh/config", "ask"),
 ("Bash", "git log --output=/tmp/x", "ask"), ("Bash", "git log --output=/home/a/.bashrc", "ask"), ("Bash", "git diff --ext-diff", "ask"), ("Bash", "git -c core.pager=sh log", "ask"),
 ("Bash", "git show HEAD:secrets/x.env", "deny"), ("Bash", "git branch -D main", "ask"), ("Bash", "git remote add x https://example.com/r.git", "ask"),
 ("Bash", "git remote set-url origin https://example.com/r.git", "ask"), ("Bash", "git log --exec=sh", "ask"), ("Bash", "git diff --textconv", "ask"),
 # Quality's 29 lines (01.11 12:47): only three of them are routine
] + [("Bash", c, "noallow") for c in (
 "git log --output=/tmp/x", "git diff --ext-diff", "grep -r token /home/a/.ssh", "cat /home/a/.claude/.credentials.json", "cat ~/.config/github.env",
 "git show HEAD:secrets/x.env", "ls -la ~/.ssh", "rg -l sk- /", "jq . ~/work/secrets/a.env", "grep -r OPENROUTER /etc/mila", "cat /proc/self/environ",
 "git branch -D main", "git remote add x https://e.vil/x", "cat ~/.ssh/id_ed25519", "grep -r -e . /home/a/work", "grep -rn KEY ~/work",
 "grep --include=*.env -R KEY ~/work", "cat ~/work/../.ssh/id_rsa", "cat /home/a/work/secrets/x.env", "rg KEY ~/work/secrets", "find ~/work -name *.env",
 "git log -p", "git grep KEY", "head -c 400 /proc/1/environ", "cat ~/work/.env.bak", "ls -R ~/work", "rg TODO README.md")] + [
 ("Bash", "rg KEY ~/work/secrets", "deny"), ("Bash", "ls ~/work/secrets", "deny"), ("Bash", "cat ~/work/.env.bak", "deny"),
 # still allowed — the routine
 ("Bash", "git branch", "allow"), ("Bash", "git branch -a", "allow"), ("Bash", "git remote -v", "allow"), ("Bash", "git log --oneline -5", "allow"),
 ("Bash", "cat /home/a/work/NOW.md", "allow"), ("Bash", "cat ~/work/NOW.md", "allow"), ("Bash", "grep -n TODO README.md", "allow"), ("Bash", "wc -l *.md", "allow"), ("Write", json.dumps({"file_path": "/home/a/work/permissions.json"}), "ask"),
]
js = """import { loadPolicy, decide } from '%s'
const { policy, error } = loadPolicy('%s'); if (error) { console.log('ERR ' + error); process.exit(1) }
const cases = JSON.parse(await Bun.stdin.text())
console.log(JSON.stringify(cases.map(([t, p]) => decide(policy, t, p).decision)))""" % (os.path.join(ROOT, "install", "permission_policy.ts"), os.path.join(ROOT, "install", "permissions.example.json"))
r = subprocess.run(["bun", "-e", js], input=json.dumps([[t, p] for t, p, _ in CASES]), capture_output=True, text=True)
got = json.loads(r.stdout.strip().splitlines()[-1]) if r.returncode == 0 else []
check("файл читается движком без ошибки", r.returncode == 0, r.stdout + r.stderr)
for (t, p, want), g in zip(CASES, got):
    check("%s %s → %s" % (t, p[:60], want), (g != "allow") if want == "noallow" else g == want, g)
print("итог %d/%d" % (ok, n)); sys.exit(0 if ok == n else 1)
