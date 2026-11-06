#!/bin/bash
# hooks_sync.py: живая Мила без хуков mila-tasks → добавлены PostToolUse(reply) task-sent и SessionStart task-open; повтор — без изменений;
# чужие хуки целы; бэкап есть; без навыка — честный отказ. bash tools/test_hooks_sync.sh
set -u; H="$(cd "$(dirname "$0")" && pwd)"; T=$(mktemp -d); trap 'chmod -R u+w "$T" 2>/dev/null; rm -rf "$T"' EXIT; S="python3 -I $H/hooks_sync.py --home $T"
ok=0; n=0; chk(){ n=$((n+1)); if eval "$2" >/dev/null 2>&1; then ok=$((ok+1)); echo "✅ $1"; else echo "❌ $1"; fi; }
mkdir -p $T/.claude
chk "без навыка mila-tasks — отказ с подсказкой" "! $S"
mkdir -p $T/.claude/skills/mila-tasks/hooks; touch $T/.claude/skills/mila-tasks/hooks/task-sent.py $T/.claude/skills/mila-tasks/hooks/task-open.py
cat > $T/.claude/settings.json <<'J'
{"hooks": {"SessionStart": [{"hooks": [{"type": "command", "command": "python3 x/session-start.py"}]}], "PreToolUse": [{"matcher": "reply", "hooks": [{"type": "command", "command": "python3 x/send-guard.py"}]}], "Stop": [{"hooks": [{"type": "command", "command": "python3 x/reply-required.py"}]}]}, "env": {"OWNER_ID": "1"}}
J
$S > /dev/null
chk "добавлены оба хука" "grep -q 'task-sent' $T/.claude/settings.json && grep -q 'task-open' $T/.claude/settings.json"
chk "PostToolUse — на reply" "python3 -c \"import json;d=json.load(open('$T/.claude/settings.json'));assert any('telegram_telegram__reply' in x.get('matcher','') for x in d['hooks']['PostToolUse'])\""
chk "чужие хуки и env целы" "python3 -c \"import json;d=json.load(open('$T/.claude/settings.json'));assert 'send-guard' in json.dumps(d['hooks']['PreToolUse']) and 'reply-required' in json.dumps(d['hooks']['Stop']) and d['env']['OWNER_ID']=='1' and 'session-start' in json.dumps(d['hooks']['SessionStart'])\""
chk "бэкап settings.json есть" "ls $T/.claude/settings.json.bak-* "
chk "повтор — ничего не добавляет" "$S | grep -q '\"added\": \[\]'"
# --guards: a home updated by mila-update — the guards' files are in ~/.claude/hooks but not in settings.json
G=$(mktemp -d); mkdir -p $G/.claude/hooks; for f in send-guard done-guard secret-guard skill-hint pd-mask crons-keeper reply-required; do touch $G/.claude/hooks/$f.py; done
cat > $G/.claude/settings.json <<'J'
{"hooks": {"PreToolUse": [{"matcher": "reply", "hooks": [{"type": "command", "command": "python3 x/send-guard.py"}]}], "Stop": [{"hooks": [{"type": "command", "command": "python3 x/reply-required.py"}]}]}, "permissions": {"deny": ["Read(~/.mila-auth/**)"]}}
J
GS="python3 -I $H/hooks_sync.py --home $G"
chk "без --guards и без mila-tasks — отказ, как раньше" "! $GS"
MILA_CC_VERSION=2.1.310 $GS --guards > $G/out.json
chk "--guards: done-guard на отправку и на сбой, secret-guard на инструменты, skill-hint, pd-mask, crons-keeper" "python3 -c \"import json;d=json.load(open('$G/.claude/settings.json'))['hooks'];j=json.dumps
assert any('done-guard' in j(x) and 'telegram_telegram__reply' in x['matcher'] for x in d['PreToolUse'])
assert any('done-guard' in j(x) for x in d['PostToolUseFailure'])
assert any('secret-guard' in j(x) and x['matcher'].startswith('Bash|Read') for x in d['PreToolUse'])
assert 'skill-hint' in j(d['UserPromptSubmit']) and 'pd-mask' in j(d['PostToolUse']) and 'crons-keeper' in j(d['SessionStart'])\""
chk "--guards: уже записанные send-guard и reply-required не дублируются" "python3 -c \"import json;d=json.load(open('$G/.claude/settings.json'))['hooks'];assert json.dumps(d['PreToolUse']).count('send-guard')==1 and json.dumps(d['Stop']).count('reply-required')==1\""
chk "--guards: deny-правила входа и сейфа, без повтора" "python3 -c \"import json;d=json.load(open('$G/.claude/settings.json'))['permissions']['deny'];assert len(d)==4 and len(set(d))==4\""
chk "--guards на старой Claude Code — без PostToolUseFailure" "(G2=\$(mktemp -d); mkdir -p \$G2/.claude/hooks; touch \$G2/.claude/hooks/done-guard.py; echo '{}' > \$G2/.claude/settings.json; MILA_CC_VERSION=2.1.200 python3 -I $H/hooks_sync.py --home \$G2 --guards >/dev/null && python3 -c \"import json,sys;d=json.load(open(sys.argv[1]))['hooks'];assert 'PostToolUseFailure' not in d and 'done-guard' in json.dumps(d['PreToolUse'])\" \$G2/.claude/settings.json; r=\$?; rm -rf \$G2; exit \$r)"
chk "--guards: повтор ничего не добавляет" "MILA_CC_VERSION=2.1.310 $GS --guards | grep -q '\"added\": \[\]'"
rm -rf $G
echo "итог $ok/$n"; rm -rf $T; [ $ok -eq $n ]
