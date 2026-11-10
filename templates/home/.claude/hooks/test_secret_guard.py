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
# audit 09.11 №13: the same places for every reader by the real path; a search with lines over a root that holds a key file
FH = tempfile.mkdtemp(prefix="sguard-home-"); W = os.path.join(FH, "work")
for d in (".mila-auth", "work/secrets", "work/notes", ".claude/channels/telegram"): os.makedirs(os.path.join(FH, d))
open(os.path.join(FH, ".claude/channels/telegram/.env"), "w").write("BOT=x\n"); open(os.path.join(W, "secrets/groq.env"), "w").write("K=x\n")
open(os.path.join(FH, ".mila-auth/oauth_token"), "w").write("x\n"); open(os.path.join(W, "notes/a.md"), "w").write("hi\n")
os.symlink(os.path.join(FH, ".mila-auth"), os.path.join(W, "notes/look")); os.symlink(os.path.join(FH, ".claude/channels/telegram/.env"), os.path.join(W, "cfg.txt"))
EH = dict(ENV, HOME=FH)
def dh(tool, cwd=None, **a):
    r = subprocess.run([sys.executable, G], input=json.dumps({"tool_name": tool, "tool_input": a, "cwd": cwd or W}), capture_output=True, text=True, timeout=20, env=EH)
    return "deny" if r.stdout.strip() else "allow"
chk("№13 Grep со строками по ~/.claude (там .env плагина) — стоп", dh("Grep", pattern="BOT", path=os.path.join(FH, ".claude"), output_mode="content"), "deny")
chk("№13 Grep со строками без пути из дома — стоп", dh("Grep", cwd=FH, pattern="BOT", output_mode="content"), "deny")
chk("№13 Grep со строками по ~/work (там secrets/) — стоп", dh("Grep", pattern="K=", path=W, output_mode="content"), "deny")
chk("№13 Grep по .env плагина прямо — стоп", dh("Grep", pattern="BOT", path=os.path.join(FH, ".claude/channels/telegram/.env")), "deny")
chk("№13 Read по ссылке в ~/work на .env плагина — стоп", dh("Read", file_path=os.path.join(W, "cfg.txt")), "deny")
chk("№13 Grep по ссылке-папке на .mila-auth — стоп", dh("Grep", pattern="x", path=os.path.join(W, "notes/look")), "deny")
chk("№13 Read относительным путём через ссылку — стоп", dh("Read", file_path="cfg.txt"), "deny")
chk("№13 Grep со строками по ~/work с glob '*.env' — стоп", dh("Grep", pattern="K=", path=W, glob="*.env", output_mode="content"), "deny")
chk("№13 Grep списком файлов по ~/work — пропуск (строк нет)", dh("Grep", pattern="hi", path=W), "allow")
chk("№13 Grep со строками по ~/work/notes — пропуск", dh("Grep", pattern="hi", path=os.path.join(W, "notes"), output_mode="content"), "allow")
chk("№13 Grep со строками по ~/work с glob '*.{md,py}' — пропуск", dh("Grep", pattern="hi", path=W, glob="*.{md,py}", output_mode="content"), "allow")
chk("№13 Glob по дому — пропуск (только имена)", dh("Glob", pattern="**/*.md", path=FH), "allow")
chk("№13 Read обычного файла — пропуск", dh("Read", file_path=os.path.join(W, "notes/a.md")), "allow")
chk("№13 Grep со строками по ~/work, ключа там нет — пропуск до жёсткой ссылки", dh("Grep", pattern="hi", path=os.path.join(W, "notes"), output_mode="content"), "allow")
# Quality 10.11: a hard link has no other real path — the inode tells it; a second link closes lines-search anywhere
os.link(os.path.join(FH, ".mila-auth/oauth_token"), os.path.join(W, "notes/notes.txt"))
chk("№13 Read жёсткой ссылки на ключ в ~/work — стоп", dh("Read", file_path=os.path.join(W, "notes/notes.txt")), "deny")
chk("№13 Grep со строками по ~/work/notes при второй ссылке ключа — стоп", dh("Grep", pattern="hi", path=os.path.join(W, "notes"), output_mode="content"), "deny")
chk("№13 Grep списком файлов при второй ссылке — пропуск", dh("Grep", pattern="hi", path=os.path.join(W, "notes")), "allow")
chk("№13 Read обычного файла рядом — пропуск", dh("Read", file_path=os.path.join(W, "notes/a.md")), "allow")
chk("№13 путь, который не разобрать (NUL) — стоп, не пропуск", dh("Read", file_path=W + "/a\u0000b"), "deny")
shutil.rmtree(FH, ignore_errors=True)
shutil.rmtree(CFG, ignore_errors=True)
print("итог %d/%d" % (ok, n)); sys.exit(0 if ok == n else 1)
