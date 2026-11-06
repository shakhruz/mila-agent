#!/usr/bin/env python3
"""secret-guard.py: модель не трогает своими инструментами токен входа и файлы сейфа; обычная работа не задевается."""
import json, os, shutil, subprocess, sys, tempfile
H = os.path.dirname(os.path.abspath(__file__)); G = os.path.join(H, "secret-guard.py"); ok = n = 0
CFG = tempfile.mkdtemp(prefix="sguard-"); ENV = dict(os.environ, CLAUDE_CONFIG_DIR=CFG)   # the refusals' journal goes here, not home
def dec(tool, **a):
    r = subprocess.run([sys.executable, G], input=json.dumps({"tool_name": tool, "tool_input": a}), capture_output=True, text=True, timeout=20, env=ENV)
    return "deny" if r.stdout.strip() and json.loads(r.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny" else "allow"
def chk(name, got, want):
    global ok, n
    n += 1; g = got == want; ok += g; print(("✅ " if g else "❌ ") + name + ("" if g else "  ← " + got))
for c in ("cat ~/.mila-auth/oauth_token", "printenv CLAUDE_CODE_OAUTH_TOKEN", "echo $CLAUDE_CODE_OAUTH_TOKEN", "env", "printenv", "env | grep -i token",
          "cat /proc/1/environ", "export -p", "declare -px", "python3 -c 'import os;print(os.environ)' ; env", "cat work/secrets/groq.env",
          "base64 ~/.mila-auth/oauth_token", "grep -r sk- ~/.claude/.credentials.json"):
    chk("Bash стоп: " + c, dec("Bash", command=c), "deny")
for c in ("ls -la", "git status", "python3 ~/.claude/skills/safe-link/scripts/safe_read.py groq GROQ_API_KEY --mask",
          "python3 /usr/local/bin/key_page.py deepgram --lang ru", "echo hello env", "grep -n environment README.md", "set -e; ls"):
    chk("Bash пропуск: " + c, dec("Bash", command=c), "allow")
chk("Read ~/.mila-auth/oauth_token — стоп", dec("Read", file_path="/home/agent/.mila-auth/oauth_token"), "deny")
chk("Read work/secrets/deepgram.env — стоп", dec("Read", file_path="/home/agent/work/secrets/deepgram.env"), "deny")
chk("Grep по .mila-auth — стоп", dec("Grep", pattern="sk-", path="/home/agent/.mila-auth"), "deny")
chk("Read USER.md — пропуск", dec("Read", file_path="/home/agent/work/USER.md"), "allow")
chk("вход не JSON — пропуск (fail open)", "allow" if not subprocess.run([sys.executable, G], input="{oops", capture_output=True, text=True).stdout.strip() else "deny", "allow")
# Известный пропуск (xfail): хук — слой от случайности, не стена. Эти обходы он НЕ ловит, и тест это фиксирует —
# чтобы зелёный счёт не приняли за защиту. Стена — CLAUDE_CODE_SUBPROCESS_ENV_SCRUB (нужен bubblewrap).
for c in ("cd ~ && cat .mila-a*/o*", "python3 -c \"import os;print(os.environ['CLAUDE_CODE_'+'OAUTH_TOKEN'])\""):
    got = dec("Bash", command=c)
    print(("⚠️  известный пропуск (xfail): " if got == "allow" else "ℹ️  теперь ловится: ") + c)
# the refusals' journal: one line per refusal — tool, rule, what matched; never the command, never the token's value
J = os.path.join(CFG, "mila-guard", "secret-guard.jsonl")
shutil.rmtree(os.path.join(CFG, "mila-guard"), ignore_errors=True)
dec("Bash", command="echo hello"); dec("Bash", command="printenv CLAUDE_CODE_OAUTH_TOKEN | head -c 4 secretvalue123")
dec("Read", file_path="/home/agent/work/secrets/deepgram.env")
rows = [json.loads(l) for l in open(J)] if os.path.exists(J) else []
chk("журнал отказов: строка на каждый отказ, пропуск — без строки", str(len(rows)), "2")
chk("журнал: инструмент, правило, что совпало", json.dumps([(r["tool"], r["rule"], r["what"]) for r in rows]),
    json.dumps([["Bash", "name", "CLAUDE_CODE_OAUTH_TOKEN"], ["Read", "place", "work/secrets"]]))
chk("журнал: ни текста команды, ни значения", "clean" if os.path.exists(J) and "secretvalue123" not in open(J).read() and "printenv" not in open(J).read() else "dirty", "clean")
chk("журнал: файл 600, папка 700", "%o/%o" % (os.stat(J).st_mode & 0o777, os.stat(os.path.dirname(J)).st_mode & 0o777) if os.path.exists(J) else "-", "600/700")
shutil.rmtree(CFG, ignore_errors=True)
print("итог %d/%d" % (ok, n)); sys.exit(0 if ok == n else 1)
