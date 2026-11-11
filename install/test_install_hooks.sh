#!/usr/bin/env bash
# каждый хук, который install.sh прописал в settings.json, лежит файлом (иначе Stop-хук без файла = код 2 = сессия не останавливается).
export MILA_SKIP_TIMERS=1   # the installer writes its timers and never loads them here: a test must not start a job on the machine that runs it
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
# ── the Scheduler's pass every minute: both kinds of machine, by a fake `uname` (and `systemctl`) first in PATH; nothing is loaded
sched() {   # $1 — what uname says, $2 — home; prints the installer's output
  local fb="$T/fakebin-$1"; mkdir -p "$fb" "$2/.claude"
  printf '#!/bin/sh\necho %s\n' "$1" > "$fb/uname"
  for tool in systemctl launchctl; do printf '#!/bin/sh\necho "%s $*" >> "%s/calls"\nexit 0\n' "$tool" "$fb" > "$fb/$tool"; done   # stand-ins that write down every call
  chmod +x "$fb/uname" "$fb/systemctl" "$fb/launchctl"
  HOME="$2" CLAUDE_CONFIG_DIR="$2/.claude" MILA_OWNER_ID=$OID PATH="$fb:/usr/bin:/bin:/usr/local/bin" bash "$REPO/install/install.sh" 2>&1
}
SM="$T/mac"; sched Darwin "$SM" > "$T/mac.out"; PL="$SM/Library/LaunchAgents/com.milagpt.scheduler.plist"
chk "Мак: служба Планировщика записана — проход раз в минуту по этому дому, установленным baraban.py, с -B" "grep -q '<integer>60</integer>' $PL && grep -q '<string>-B</string>' $PL && grep -q '<string>tick</string>' $PL && grep -q \"<string>$SM</string>\" $PL && grep -q \"<string>$SM/.claude/hooks/baraban.py</string>\" $PL"
chk "Мак: в тесте служба записана, но не загружена — так и сказано" "grep -q 'com.milagpt.scheduler — written, not loaded' $T/mac.out"
chk "Мак: при MILA_SKIP_TIMERS launchctl не вызван ни разу — ни для сбора ходов, ни для Планировщика; обе службы записаны файлами" "[ ! -e $T/fakebin-Darwin/calls ] && [ -f $SM/Library/LaunchAgents/com.milagpt.turns-collect.plist ] && [ -f $PL ] && grep -q 'com.milagpt.turns-collect — written, not loaded' $T/mac.out"
SMR="$T/mac-real"; (unset MILA_SKIP_TIMERS; sched Darwin "$SMR" > "$T/mac-real.out")   # the stand-in launchctl is first in PATH: nothing of the machine is touched
chk "Мак без флага (launchctl — подставной): обе службы загружаются — по bootout и bootstrap на каждую" "[ \$(grep -c '^launchctl bootout .*/com.milagpt.turns-collect\$' $T/fakebin-Darwin/calls) -eq 1 ] && [ \$(grep -c '^launchctl bootstrap .*com.milagpt.turns-collect.plist\$' $T/fakebin-Darwin/calls) -eq 1 ] && [ \$(grep -c '^launchctl bootout .*/com.milagpt.scheduler\$' $T/fakebin-Darwin/calls) -eq 1 ] && [ \$(grep -c '^launchctl bootstrap .*com.milagpt.scheduler.plist\$' $T/fakebin-Darwin/calls) -eq 1 ]"
rm -f "$T/fakebin-Darwin/calls"
SL="$T/lin"; sched Linux "$SL" > "$T/lin.out"; UN="$SL/.config/systemd/user"
chk "Linux: при MILA_SKIP_TIMERS systemctl не вызван ни разу; оба таймера записаны файлами" "[ ! -e $T/fakebin-Linux/calls ] && [ -f $UN/mila-turns-collect.timer ] && [ -f $UN/mila-scheduler.timer ] && grep -q 'mila-turns-collect.timer — written, not enabled' $T/lin.out"
SLR="$T/lin-real"; (unset MILA_SKIP_TIMERS; sched Linux "$SLR" > "$T/lin-real.out")
chk "Linux без флага (systemctl — подставной): оба таймера включаются" "grep -q '^systemctl --user enable --now mila-turns-collect.timer\$' $T/fakebin-Linux/calls && grep -q '^systemctl --user enable --now mila-scheduler.timer\$' $T/fakebin-Linux/calls"
rm -f "$T/fakebin-Linux/calls"
chk "Linux: таймер и служба записаны — раз в минуту, тот же проход, без записи __pycache__ (-B)" "grep -q 'OnCalendar=minutely' $UN/mila-scheduler.timer && grep -q \"ExecStart=.* -B $SL/.claude/hooks/baraban.py tick --home $SL\$\" $UN/mila-scheduler.service"
chk "Linux: в тесте таймер записан, но не включён" "grep -q 'mila-scheduler.timer — written, not enabled' $T/lin.out"
chk "baraban.py лежит в хуках рядом с остальными" "[ -f $SL/.claude/hooks/baraban.py ] && [ -f $SL/.claude/skills/raspisanie/cronspec.py ]"
mkdir -p "$SL/.claude/channels/telegram/inbound"; printf '{"allowFrom": ["%s"]}' "$OID" > "$SL/.claude/channels/telegram/access.json"
out=$(env -u XDG_STATE_HOME -u BARABAN_STATE HOME="$SL" python3 -B "$SL/.claude/hooks/baraban.py" tick --home "$SL" 2>&1); BEAT="$SL/.local/state/mila/baraban/$(basename "$SL").beat"
chk "проход установленной копией, как его зовёт таймер (без --owner и --state): хозяин — подключённый, отметка прохода на месте" "echo '$out' | grep -q '\"fired\"' && [ -f $BEAT ] && grep -q '^20[0-9][0-9]-' $BEAT"
alive=$(env -u XDG_STATE_HOME -u BARABAN_STATE -u MILA_SCHEDULER_BEAT python3 -B -c "import sys, datetime; sys.path.insert(0, '$SL/.claude/skills/raspisanie'); import cronspec; a = cronspec.last_beat('$SL'); print(int((datetime.datetime.now(datetime.timezone.utc) - a).total_seconds() <= cronspec.BEAT_FRESH))" 2>&1)
chk "эту отметку видит то же правило, по которому судят сторож и доктор: Планировщик жив" "[ \"$alive\" = 1 ]"
rm -rf "$SL/.claude/channels" "$BEAT"; out=$(env -u XDG_STATE_HOME -u BARABAN_STATE HOME="$SL" python3 -B "$SL/.claude/hooks/baraban.py" tick --home "$SL" 2>&1)
chk "хозяин не подключён — это не проход: отметки нет (доставлять некому)" "echo '$out' | grep -q '\"fired\": \[\]' && [ ! -e $BEAT ]"
SE="$T/else"; mkdir -p "$SE/state/baraban"; python3 -c "import datetime; print(datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds'))" > "$SE/state/baraban/$(basename "$SE").beat"
sched Linux "$SE" > "$T/else.out"
chk "по дому уже проходит другой Планировщик (свежая отметка, таймер не наш) — второй не ставится, так и сказано" "grep -q 'already passing for this home' $T/else.out && [ ! -e $SE/.config/systemd/user/mila-scheduler.timer ]"
mkdir -p "$SL/.claude/channels/telegram"; printf '{"allowFrom": ["%s"]}' "$OID" > "$SL/.claude/channels/telegram/access.json"
env -u XDG_STATE_HOME -u BARABAN_STATE HOME="$SL" python3 -B "$SL/.claude/hooks/baraban.py" tick --home "$SL" >/dev/null 2>&1; rm -f "$UN/mila-scheduler.service"
sched Linux "$SL" > "$T/lin2.out"
chk "повторная установка там, где таймер наш и он проходит (отметка свежая): своя отметка не мешает — служба записана заново" "[ -f $BEAT ] && [ -f $UN/mila-scheduler.service ] && ! grep -q 'already passing' $T/lin2.out"
# ── a used skill is not a customised skill: __pycache__ left by a script's run does not make the next install back the skill up
# a kit as a clone gives it — tracked files only, no __pycache__ of this working tree — installed into a fresh home
KIT="$T/kit"; mkdir -p "$KIT" "$T/clean/.claude"
if (cd "$REPO" && git ls-files -z 2>/dev/null | tar --null -T - -cf - 2>/dev/null) | tar -xf - -C "$KIT" 2>/dev/null && [ -f "$KIT/install/install.sh" ]; then
  fbc="$T/fakebin-Linux"; env -u PYTHONDONTWRITEBYTECODE HOME="$T/clean" CLAUDE_CONFIG_DIR="$T/clean/.claude" MILA_OWNER_ID=$OID PATH="$fbc:/usr/bin:/bin:/usr/local/bin" bash "$KIT/install/install.sh" >/dev/null 2>&1   # the runner's own «no bytecode» setting must not hide what the installer leaves
  chk "установка из чистого набора не оставляет в навыках дома ни одного __pycache__ (её проверка «уже проходит» идёт с -B)" "[ -d $T/clean/.claude/skills/raspisanie ] && [ -z \"\$(find $T/clean/.claude/skills -name __pycache__ | head -1)\" ]"
else
  chk "(набор не из git — проверка чистоты __pycache__ пропущена)" "true"
fi
SP="$T/pyc"; sched Linux "$SP" > /dev/null; mkdir -p "$SP/.claude/skills/raspisanie/__pycache__"; echo x > "$SP/.claude/skills/raspisanie/__pycache__/cronspec.cpython-312.pyc"
sched Linux "$SP" > "$T/pyc.out"
chk "навык, которым пользовались (__pycache__ внутри), при повторной установке «без изменений», копии нет" "grep -q 'raspisanie — unchanged' $T/pyc.out && [ -z \"\$(ls -d $SP/.claude/skills/raspisanie.bak-* 2>/dev/null)\" ]"
# a clock that stands still: both installs get the same second in the backup's name — the collision, every time
printf '#!/bin/sh\ncase "$1" in +%%Y*) echo 20260504-090000;; *) exec /bin/date "$@";; esac\n' > "$T/fakebin-Linux/date"; chmod +x "$T/fakebin-Linux/date"
echo '# моя правка' >> "$SP/.claude/skills/raspisanie/SKILL.md"; sched Linux "$SP" > "$T/pyc2.out"; echo '# ещё правка' >> "$SP/.claude/skills/raspisanie/SKILL.md"; sched Linux "$SP" > "$T/pyc3.out"; rcx=$?
rm -f "$T/fakebin-Linux/date"
chk "навык, который хозяин правил, по-прежнему получает копию; две установки подряд (в одну секунду) — две копии, без падения" "grep -q 'raspisanie — exists, keeping a copy' $T/pyc2.out && grep -q 'raspisanie — exists, keeping a copy' $T/pyc3.out && [ $rcx -eq 0 ] && [ \$(ls -d $SP/.claude/skills/raspisanie.bak-* | wc -l) -eq 2 ] && grep -q 'Done' $T/pyc3.out"
[ -n "$miss" ] && echo "нет файлов: $miss"
echo "итог $ok/$n"; rm -rf "$T"
