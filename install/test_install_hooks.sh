#!/usr/bin/env bash
# каждый хук, который install.sh прописал в settings.json, лежит файлом (иначе Stop-хук без файла = код 2 = сессия не останавливается).
set -u; unset TELEGRAM_STATE_DIR
REPO="$(cd "$(dirname "$0")/.." && pwd)"; T="$(mktemp -d)"; trap 'chmod -R u+w "$T" "${T2:-}" 2>/dev/null; rm -rf "$T" "${T2:-}"' EXIT; mkdir -p "$T/home/.claude"
export MILA_CC_VERSION=2.1.310
OID="555""000111"   # вымышленный id владельца (tests/fixtures/fake_people.py), склейкой
HOME="$T/home" CLAUDE_CONFIG_DIR="$T/home/.claude" MILA_OWNER_ID=$OID PATH=/usr/bin:/bin:/usr/local/bin bash "$REPO/install/install.sh" >/dev/null 2>&1
ok=0; n=0; chk() { n=$((n+1)); if eval "$2"; then ok=$((ok+1)); echo "✅ $1"; else echo "❌ $1"; fi; }
miss=$(python3 - "$T/home/.claude/settings.json" <<'PY'
import json, os, sys, shlex
d = json.load(open(sys.argv[1])); miss = []
for ev, lst in d.get("hooks", {}).items():
    for e in lst:
        for h in e.get("hooks", []):
            parts = shlex.split(h.get("command", "")); f = next((p for p in parts if p.endswith((".py", ".sh", ".ts"))), None)
            if f and not os.path.isfile(f): miss.append(ev + ":" + f)
print(" ".join(miss))
PY
)
chk "все хуки из settings.json лежат файлами" "[ -z \"$miss\" ]"
chk "envelope.py рядом с хуком входящих (хук строит им конверт)" "[ -f $T/home/.claude/hooks/envelope.py ]"
chk "Stop: reply-required.py установлен" "[ -x $T/home/.claude/hooks/reply-required.py ]"
chk "PostToolUse: pd-mask.py установлен" "[ -x $T/home/.claude/hooks/pd-mask.py ]"
chk "ключ хранилища ПДн создан, 600" "python3 -c \"import os,sys; sys.exit(0 if os.stat(sys.argv[1]).st_mode & 0o777 == 0o600 else 1)\" $T/home/.config/mila/pd.key"
S="$T/home/.claude/settings.json"
chk "PreToolUse send-guard зарегистрирован и лежит файлом" "grep -q 'send-guard.py' $S && [ -x $T/home/.claude/hooks/send-guard.py ]"
chk "done-guard: PreToolUse и PostToolUseFailure зарегистрированы, файл лежит" "python3 -c \"import json;h=json.load(open('$S'))['hooks'];assert any('done-guard.py' in json.dumps(e) for e in h['PreToolUse']) and any('done-guard.py' in json.dumps(e) for e in h['PostToolUseFailure'])\" && [ -x $T/home/.claude/hooks/done-guard.py ]"
chk "secret-guard зарегистрирован, лежит файлом; deny Read/Edit на ~/.mila-auth и ~/work/secrets" "grep -q 'secret-guard.py' $S && [ -x $T/home/.claude/hooks/secret-guard.py ] && python3 -c \"import json;d=json.load(open('$S'))['permissions']['deny'];assert 'Read(~/.mila-auth/**)' in d and 'Read(~/work/secrets/**)' in d\""
chk "skill-hint: UserPromptSubmit зарегистрирован, файл лежит" "grep -q 'skill-hint.py' $S && [ -x $T/home/.claude/hooks/skill-hint.py ]"
chk "task-sent (PostToolUse reply) и task-open (SessionStart) зарегистрированы" "grep -q 'task-sent.py' $S && grep -q 'task-open.py' $S"
chk "OWNER_ID из MILA_OWNER_ID — в env settings.json" "python3 -c \"import json;assert json.load(open('$S'))['env']['OWNER_ID']=='$OID'\""
chk "повторная установка не дублирует хуки" "HOME=$T/home CLAUDE_CONFIG_DIR=$T/home/.claude MILA_OWNER_ID=$OID PATH=/usr/bin:/bin:/usr/local/bin bash $REPO/install/install.sh >/dev/null 2>&1; [ \$(grep -c 'send-guard.py' $S) -eq 1 ] && [ \$(grep -c 'done-guard.py' $S) -eq 2 ]"
# сторож отправки — с "onFailure": "block" и при установке, и у старой записи без ключа
sgok() { python3 -c "import json,sys; d=json.load(open(sys.argv[1])); h=[h for e in d['hooks']['PreToolUse'] for h in e['hooks'] if 'send-guard.py' in h['command']]; sys.exit(0 if h and all(x.get('onFailure')=='block' for x in h) else 1)" "$S"; }
chk "SG-ONFAIL: установка пишет send-guard с onFailure: block" "sgok"
python3 -c "import json,sys; d=json.load(open(sys.argv[1])); [h.pop('onFailure',None) for e in d['hooks']['PreToolUse'] for h in e['hooks']]; json.dump(d,open(sys.argv[1],'w'))" "$S"
HOME=$T/home CLAUDE_CONFIG_DIR=$T/home/.claude MILA_OWNER_ID=$OID PATH=/usr/bin:/bin:/usr/local/bin bash "$REPO/install/install.sh" >/dev/null 2>&1
chk "SG-ONFAIL: повторная установка дописывает ключ старой записи (без дубля хука)" "sgok && [ \$(grep -c 'send-guard.py' $S) -eq 1 ]"
# a topic's name is checked too: a new install has __topic in the guard's matcher; a home from before gets it on the next install
sgtopic() { python3 -c "import json,sys; d=json.load(open(sys.argv[1])); m=[e.get('matcher','') for e in d['hooks']['PreToolUse'] if 'send-guard.py' in json.dumps(e)]; sys.exit(0 if m and all('telegram__topic' in x for x in m) else 1)" "$S"; }
chk "SG-TOPIC: сторож отправки смотрит и название темы (matcher с __topic)" "sgtopic"
python3 -c "import json,sys; d=json.load(open(sys.argv[1])); [e.__setitem__('matcher', 'mcp__plugin_(mila-)?telegram_telegram__reply|mcp__plugin_(mila-)?telegram_telegram__edit_message') for e in d['hooks']['PreToolUse'] if 'send-guard.py' in json.dumps(e)]; json.dump(d,open(sys.argv[1],'w'))" "$S"
HOME=$T/home CLAUDE_CONFIG_DIR=$T/home/.claude MILA_OWNER_ID=$OID PATH=/usr/bin:/bin:/usr/local/bin bash "$REPO/install/install.sh" >/dev/null 2>&1
chk "SG-TOPIC: старая запись (только reply|edit_message) — повторная установка дописывает __topic, без дубля" "sgtopic && [ \$(grep -c 'send-guard.py' $S) -eq 1 ]"
# a widget is checked too: a new install has __widget and __widget_data in the guard's matcher; a home from before the widget tools gets them
sgwidget() { python3 -c "import json,sys; d=json.load(open(sys.argv[1])); m=[e.get('matcher','') for e in d['hooks']['PreToolUse'] if 'send-guard.py' in json.dumps(e)]; sys.exit(0 if m and all('telegram__widget|' in x and x.endswith('telegram__widget_data') for x in m) else 1)" "$S"; }
chk "SG-WIDGET: сторож отправки смотрит и виджет (matcher с __widget и __widget_data)" "sgwidget"
python3 -c "import json,sys; d=json.load(open(sys.argv[1])); [e.__setitem__('matcher', e['matcher'].split('|mcp__plugin_(mila-)?telegram_telegram__widget')[0]) for e in d['hooks']['PreToolUse'] if 'send-guard.py' in json.dumps(e)]; json.dump(d,open(sys.argv[1],'w'))" "$S"
chk "SG-WIDGET: (подготовка) запись дома до виджетов — без __widget" "! sgwidget && sgtopic"
HOME=$T/home CLAUDE_CONFIG_DIR=$T/home/.claude MILA_OWNER_ID=$OID PATH=/usr/bin:/bin:/usr/local/bin bash "$REPO/install/install.sh" >/dev/null 2>&1
chk "SG-WIDGET: дом до виджетов — повторная установка дописывает виджет, без дубля" "sgwidget && [ \$(grep -c 'send-guard.py' $S) -eq 1 ]"
T2="$(mktemp -d)"; mkdir -p "$T2/home/.claude"
MILA_CC_VERSION=2.1.200 HOME="$T2/home" CLAUDE_CONFIG_DIR="$T2/home/.claude" PATH=/usr/bin:/bin:/usr/local/bin bash "$REPO/install/install.sh" > "$T2/out" 2>&1
chk "SG-ONFAIL: старая CC (2.1.200) — хук сторожа есть, ключа нет, строка «пропущен»" "grep -q 'send-guard.py' $T2/home/.claude/settings.json && ! grep -q onFailure $T2/home/.claude/settings.json && ! grep -q PostToolUseFailure $T2/home/.claude/settings.json && grep -q 'onFailure пропущен' $T2/out"
rm -rf "$T2"
chk "шаблон settings.json без зашитого /home/companion" "! grep -q '/home/companion' $REPO/templates/home/.claude/settings.json"
[ -n "$miss" ] && echo "нет файлов: $miss"
echo "итог $ok/$n"; rm -rf "$T"
