#!/usr/bin/env bash
# шаг «подключить сторожа ядра»: недостающие сторожа из release.json (guards) дописываются в settings.json дома;
# свои хуки дома и их порядок не трогаются; повторный запуск ничего не меняет; сломанный файл сторожа не подключается;
# settings.json-ссылка и кривой JSON не трогаются; шаблон рождения подключает ровно guards.
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"; REPO="$(cd "$HERE/../.." && pwd)"
T="$(mktemp -d)"; trap 'chmod -R u+w "$T" 2>/dev/null; rm -rf "$T"' EXIT; export HOME="$T/home" CLAUDE_CONFIG_DIR="$T/home/.claude" MILA_WORK="$T/home/work"
mkdir -p "$CLAUDE_CONFIG_DIR" "$MILA_WORK"; echo "знакомство: пройдено" > "$MILA_WORK/USER.md"
cp -R "$REPO" "$T/rel"; rm -rf "$T/rel/.git"
U="python3 $HERE/update.py"; ok=0; n=0
chk() { n=$((n+1)); if eval "$2"; then ok=$((ok+1)); echo "✅ $1"; else echo "❌ $1"; fi; }
S="$CLAUDE_CONFIG_DIR/settings.json"
cat > "$S" <<'J'
{"env": {"X": "1"}, "hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "python3 $HOME/.claude/hooks/my-own.py"}]},
 {"matcher": "mcp__plugin_(mila-)?telegram_telegram__reply|mcp__plugin_(mila-)?telegram_telegram__edit_message", "hooks": [{"type": "command", "command": "python3 /home/x/.claude/hooks/send-guard.py", "onFailure": "block"}]}]}}
J
keys() { python3 - "$S" <<'PY'
import json, sys
d = json.load(open(sys.argv[1])); print(" ".join(sorted("%s:%s" % (ev, c["command"].split("hooks/")[-1].split(";")[0].split()[0].strip('"')) for ev, l in d.get("hooks", {}).items() for g in l for c in g["hooks"])))
PY
}
chmod 600 "$S"
$U plan --src "$T/rel" > "$T/p.txt" 2>&1
chk "план: строка «Подключу сторожей ядра» и риск «высокий»" "grep -q 'Подключу сторожей ядра: ' $T/p.txt && grep -q 'Риск: высокий' $T/p.txt"
$U apply --src "$T/rel" --yes "тест: сторожа" >/dev/null 2>&1
K=$(keys)
chk "все сторожа ядра подключены" "for k in SessionStart:session-start.py SessionStart:task-open.py SessionStart:crons-keeper.py UserPromptSubmit:telegram-inbox-feed.py PreToolUse:send-guard.py PostToolUse:task-sent.py PostToolUse:crons-keeper.py PostToolUse:pd-mask.py Stop:reply-required.py; do echo \"$K\" | grep -q \"\$k\" || exit 1; done"
chk "свой хук дома на месте и первым в своём событии" "python3 -c \"import json,sys; d=json.load(open('$S')); sys.exit(0 if 'my-own.py' in d['hooks']['PreToolUse'][0]['hooks'][0]['command'] else 1)\""
chk "send-guard не задвоен (уже был с другим путём)" "[ \$(grep -o 'send-guard.py' $S | wc -l) -eq 1 ]"
chk "права settings.json те же (600): настройки не открываются группе" "[ \"\$(stat -c %a $S 2>/dev/null || stat -f %Lp $S)\" = 600 ]"
chk "прочие настройки (env) целы" "python3 -c \"import json,sys; sys.exit(0 if json.load(open('$S'))['env']=={'X':'1'} else 1)\""
chk "бэкап settings.json до правки есть" "ls $CLAUDE_CONFIG_DIR/mila-update/backups/*guards.tgz >/dev/null 2>&1"
cp "$S" "$T/s1"; $U apply --src "$T/rel" --yes "тест: повтор" >/dev/null 2>&1
chk "повторный apply ничего не меняет" "cmp -s $S $T/s1 && [ \$(ls $CLAUDE_CONFIG_DIR/mila-update/backups/*guards.tgz | wc -l) -eq 1 ]"
$U plan --src "$T/rel" > "$T/p2.txt" 2>&1
chk "план после — строки про сторожей нет" "! grep -q 'Подключу сторожей' $T/p2.txt"
python3 - "$S" <<'PY'
import json, sys
p = sys.argv[1]; d = json.load(open(p)); d["hooks"]["PostToolUse"] = [g for g in d["hooks"]["PostToolUse"] if "pd-mask" not in json.dumps(g)]; json.dump(d, open(p, "w"))
PY
echo "def сломан(:" >> "$CLAUDE_CONFIG_DIR/hooks/pd-mask.py"
$U apply --src "$T/rel" --yes "тест: сломанный" >/dev/null 2>&1
chk "сломанный файл сторожа не подключаю" "! grep -q 'pd-mask' $S"
mv "$S" "$T/real.json"; echo '{}' > "$T/real.json"; ln -s "$T/real.json" "$S"
$U apply --src "$T/rel" --yes "тест: ссылка" >/dev/null 2>&1
chk "settings.json — ссылка: не трогаю (и ссылка осталась ссылкой)" "[ -L $S ] && [ \"\$(cat $T/real.json)\" = '{}' ]"
rm "$S"; echo '{"hooks": ' > "$S"
$U apply --src "$T/rel" --yes "тест: кривой" >/dev/null 2>&1
chk "кривой settings.json не чиню и не затираю" "[ \"\$(cat $S)\" = '{\"hooks\": ' ]"
chk "шаблон рождения подключает ровно guards из release.json" "python3 - <<'PY'
import json, sys
m = json.load(open('$REPO/release.json'))['guards']; t = json.load(open('$REPO/templates/home/.claude/settings.json'))['hooks']
want = sorted((g['event'], g.get('matcher') or '', g['hook']['command']) for g in m)
have = sorted((ev, grp.get('matcher') or '', h['command']) for ev, l in t.items() for grp in l for h in grp['hooks'])
sys.exit(0 if want == have else 1)
PY"
echo "итог $ok/$n"; [ $ok -eq $n ]
