#!/usr/bin/env bash
# шаг «подключить сторожа ядра»: недостающие сторожа из release.json (guards) дописываются в settings.json дома;
# свои хуки дома и их порядок не трогаются; повторный запуск ничего не меняет; сломанный файл сторожа не подключается;
# settings.json-ссылка и кривой JSON не трогаются; шаблон рождения подключает ровно guards.
# снятый хозяином сторож не возвращается (version.json помнит подключённых), возврат — по --take; событие не списком — пропуск;
# откат настроек из бэкапа сохраняет режим.
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"; REPO="$(cd "$HERE/../.." && pwd)"
T="$(mktemp -d)"; trap 'chmod -R u+w "$T" 2>/dev/null; rm -rf "$T"' EXIT; export HOME="$T/home" CLAUDE_CONFIG_DIR="$T/home/.claude" MILA_WORK="$T/home/work"
mkdir -p "$CLAUDE_CONFIG_DIR" "$MILA_WORK"; echo "знакомство: пройдено" > "$MILA_WORK/USER.md"
cp -R "$REPO" "$T/rel"; rm -rf "$T/rel/.git"
export MILA_CC_VERSION=2.1.310      # версия Claude Code — заданная, не та, что нашлась на машине: счёт сторожей от неё зависит
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
chk "план: строка «Подключу сторожей ядра: 17» (18 без уже стоящего send-guard; два из них придут в папке навыка) и риск «высокий»" "grep -q 'Подключу сторожей ядра: 17 (' $T/p.txt && grep -q 'Риск: высокий' $T/p.txt"
$U apply --src "$T/rel" --yes "тест: сторожа" >/dev/null 2>&1
K=$(keys)
chk "все сторожа ядра подключены" "for k in SessionStart:session-start.py SessionStart:task-open.py SessionStart:crons-keeper.py UserPromptSubmit:telegram-inbox-feed.py PreToolUse:send-guard.py PreToolUse:secret-guard.py PostToolUse:task-sent.py PostToolUse:crons-keeper.py PostToolUse:pd-mask.py PostToolUse:guard_check.py Stop:reply-required.py; do echo \"$K\" | grep -q \"\$k\" || exit 1; done"
chk "свой хук дома на месте и первым в своём событии" "python3 -c \"import json,sys; d=json.load(open('$S')); sys.exit(0 if 'my-own.py' in d['hooks']['PreToolUse'][0]['hooks'][0]['command'] else 1)\""
chk "план: «Расширю зону сторожа безопасности: send-guard.py (+topic, widget, widget_data)» и «Добавлю запреты на места ключей: 4»" "grep -q 'Расширю зону сторожа безопасности: send-guard.py (+topic, widget, widget_data)' $T/p.txt && grep -q 'Добавлю запреты на места ключей: 4\.' $T/p.txt"
chk "зона уже подключённого send-guard расширена до зоны релиза, запись та же (путь дома не переписан)" "python3 - <<PY
import json, sys
d = json.load(open('$S'))['hooks']['PreToolUse']; m = [g for g in json.load(open('$REPO/release.json'))['guards'] if g['key'] == 'hooks/send-guard.py'][0]['matcher']
e = [g for g in d if 'send-guard.py' in json.dumps(g)]
sys.exit(0 if len(e) == 1 and set(e[0]['matcher'].split('|')) == set(m.split('|')) and e[0]['hooks'][0]['command'] == 'python3 /home/x/.claude/hooks/send-guard.py' else 1)
PY"
chk "запреты на места ключей записаны: четыре правила из deny_required, без повтора" "python3 -c \"import json,sys; d=json.load(open('$S'))['permissions']['deny']; r=json.load(open('$REPO/release.json'))['deny_required']; sys.exit(0 if d == r and len(r) == 4 else 1)\""
chk "send-guard не задвоен (уже был с другим путём)" "[ \$(grep -o 'send-guard.py' $S | wc -l) -eq 1 ]"
chk "права settings.json те же (600): настройки не открываются группе" "[ \"\$(stat -c %a $S 2>/dev/null || stat -f %Lp $S)\" = 600 ]"
chk "прочие настройки (env) целы" "python3 -c \"import json,sys; sys.exit(0 if json.load(open('$S'))['env']=={'X':'1'} else 1)\""
chk "бэкап settings.json до правки есть" "ls $CLAUDE_CONFIG_DIR/mila-update/backups/*guards.tgz >/dev/null 2>&1"
cp "$S" "$T/s1"; $U apply --src "$T/rel" --yes "тест: повтор" >/dev/null 2>&1
chk "повторный apply ничего не меняет" "cmp -s $S $T/s1 && [ \$(ls $CLAUDE_CONFIG_DIR/mila-update/backups/*guards.tgz | wc -l) -eq 1 ]"
$U plan --src "$T/rel" > "$T/p2.txt" 2>&1
chk "план после — строки про сторожей нет" "! grep -q 'Подключу сторожей' $T/p2.txt"
V="$CLAUDE_CONFIG_DIR/mila-update/version.json"
chk "version.json помнит подключённых сторожей (18, «событие:key») и запреты (4)" "python3 -c \"import json,sys; v=json.load(open('$V')); g=v['guards']; sys.exit(0 if len(g)==18 and 'Stop:hooks/reply-required.py' in g and len(v['deny'])==4 else 1)\""
GC="$CLAUDE_CONFIG_DIR/mila-update/guards"
chk "релизные копии обязательных сторожей лежат вне hooks/ (три файла, 600, папка 700), удобства — нет" "[ \"\$(ls $GC | sort | tr '\\n' ' ')\" = 'pd-mask.py secret-guard.py send-guard.py ' ] && [ \"\$(stat -c %a $GC/secret-guard.py 2>/dev/null || stat -f %Lp $GC/secret-guard.py)\" = 600 ] && [ \"\$(stat -c %a $GC 2>/dev/null || stat -f %Lp $GC)\" = 700 ]"
chk "копия равна файлу релиза, и её sha256 записан в version.json (guard_copies), там же список обязательных" "python3 - <<PY
import json, hashlib, sys
v = json.load(open('$V')); c = v['guard_copies']
ok = sorted(c) == ['hooks/pd-mask.py', 'hooks/secret-guard.py', 'hooks/send-guard.py'] and v['guards_required'] == sorted(c)
for k in c:
    name = k.split('/')[-1]; data = open('$GC/' + name, 'rb').read()
    rel = [p for p in ('$T/rel/templates/home/.claude/hooks/' + name, '$T/rel/install/' + name) if __import__('os').path.isfile(p)]
    ok = ok and hashlib.sha256(data).hexdigest() == c[k] and rel and open(rel[0], 'rb').read() == data
sys.exit(0 if ok else 1)
PY"
# хозяин снял сторожа сам — обновление его не возвращает (иначе снятое возвращалось бы каждым обновлением)
python3 - "$S" <<'PY'
import json, sys
p = sys.argv[1]; d = json.load(open(p)); d["hooks"]["Stop"] = [g for g in d["hooks"]["Stop"] if "reply-required" not in json.dumps(g)]; json.dump(d, open(p, "w"))
PY
$U plan --src "$T/rel" > "$T/p3.txt" 2>&1
chk "снятый хозяином: план говорит «не возвращаю» и не обещает подключить" "grep -q 'снятых вами, не возвращаю: 1 (reply-required.py)' $T/p3.txt && ! grep -q 'Подключу сторожей' $T/p3.txt"
cp "$S" "$T/s2"; $U apply --src "$T/rel" --yes "тест: снятый" >/dev/null 2>&1
chk "снятый хозяином сторож обновлением не возвращается (settings.json тот же)" "cmp -s $S $T/s2 && ! grep -q 'reply-required' $S"
# запрет на место ключей обязателен, как сторож безопасности: снятое правило возвращаю и говорю в плане; reply-required при этом остаётся снятым
DR="$REPO/release.json"
python3 - "$S" "$DR" <<'PY'
import json, sys
p = sys.argv[1]; first = json.load(open(sys.argv[2]))["deny_required"][0]
d = json.load(open(p)); d["permissions"]["deny"] = [r for r in d["permissions"]["deny"] if r != first]; json.dump(d, open(p, "w"))
PY
D1=$(python3 -c "import json; print(json.load(open('$DR'))['deny_required'][0])")
$U plan --src "$T/rel" > "$T/p7.txt" 2>&1
chk "снят запрет: план — «Верну снятого: запрет на места ключей — 1 (…)», риск высокий; про reply-required — «не возвращаю»" "grep -qF \"Верну снятого: запрет на места ключей — 1 ($D1)\" $T/p7.txt && grep -q 'Риск: высокий' $T/p7.txt && grep -q 'снятых вами, не возвращаю: 1 (reply-required.py)' $T/p7.txt"
$U apply --src "$T/rel" --yes "тест: снятый запрет" >/dev/null 2>&1
chk "снятый запрет возвращён обновлением (4 правила, по одному), снятый reply-required — нет" "python3 -c \"import json,sys; d=json.load(open('$S')); r=d['permissions']['deny']; sys.exit(0 if sorted(r)==sorted(json.load(open('$DR'))['deny_required']) and 'reply-required' not in json.dumps(d['hooks']) else 1)\""
python3 - "$S" <<'PY'
import json, sys
p = sys.argv[1]; d = json.load(open(p)); d["permissions"]["deny"] = "всё"; json.dump(d, open(p, "w"))
PY
cp "$S" "$T/s2b"; $U apply --src "$T/rel" --yes "тест: deny не список" > "$T/a2b.txt" 2>&1
chk "permissions.deny не списком — чужое устройство: обновление проходит, settings.json не тронут" "grep -q '\"ok\": true' $T/a2b.txt && cmp -s $S $T/s2b"
python3 - "$S" "$DR" <<'PY'
import json, sys
p = sys.argv[1]; d = json.load(open(p)); d["permissions"]["deny"] = json.load(open(sys.argv[2]))["deny_required"]; json.dump(d, open(p, "w"))
PY
$U apply --src "$T/rel" --yes "тест: снятый, второй раз" >/dev/null 2>&1
chk "и вторым обновлением тоже (запись о нём в version.json не теряется)" "! grep -q 'reply-required' $S && grep -q 'Stop:hooks/reply-required.py' $V"
$U apply --src "$T/rel" --yes "тест: вернуть" --take reply-required.py >/dev/null 2>&1
chk "хозяин сам назвал сторожа (--take reply-required.py) — сторож возвращается" "[ \$(grep -o 'reply-required.py' $S | wc -l) -eq 1 ]"
chk "права после возврата те же (600)" "[ \"\$(stat -c %a $S 2>/dev/null || stat -f %Lp $S)\" = 600 ]"
# сторож безопасности (release.json → guards_required) обязателен: снятого возвращаю и говорю об этом в плане
python3 - "$S" <<'PY'
import json, sys
p = sys.argv[1]; d = json.load(open(p)); d["hooks"]["PreToolUse"] = [g for g in d["hooks"]["PreToolUse"] if "send-guard" not in json.dumps(g)]; json.dump(d, open(p, "w"))
PY
$U plan --src "$T/rel" --json > "$T/p5.json" 2>/dev/null; $U plan --src "$T/rel" > "$T/p5.txt" 2>&1
chk "снят сторож безопасности: план — «Верну снятого сторожа безопасности: 1 (send-guard.py)», риск высокий" "grep -q 'Верну снятого сторожа безопасности: 1 (send-guard.py)' $T/p5.txt && grep -q 'Риск: высокий' $T/p5.txt && ! grep -q 'Подключу сторожей' $T/p5.txt && python3 -c \"import json,sys; d=json.load(open('$T/p5.json')); sys.exit(0 if d['guards_returned'] == ['send-guard.py'] and d['guards_missing'] == ['send-guard.py'] else 1)\""
$U apply --src "$T/rel" --yes "тест: обязательный" >/dev/null 2>&1
chk "сторож безопасности возвращён обновлением, строка в журнале" "[ \$(grep -o 'send-guard.py' $S | wc -l) -eq 1 ] && grep -q guards_returned $CLAUDE_CONFIG_DIR/mila-update/journal.jsonl"
chk "обязательные — ровно три сторожа безопасности (send-guard, secret-guard, pd-mask), все есть в guards" "python3 -c \"import json,sys; m=json.load(open('$REPO/release.json')); r=m['guards_required']; sys.exit(0 if sorted(r) == ['hooks/pd-mask.py', 'hooks/secret-guard.py', 'hooks/send-guard.py'] and set(r) <= {g['key'] for g in m['guards']} else 1)\""
python3 - "$S" <<'PY'
import json, sys
p = sys.argv[1]; d = json.load(open(p))
for ev in ("PreToolUse", "PostToolUse"): d["hooks"][ev] = [g for g in d["hooks"][ev] if "secret-guard" not in json.dumps(g) and "pd-mask" not in json.dumps(g)]
json.dump(d, open(p, "w"))
PY
$U plan --src "$T/rel" > "$T/p6.txt" 2>&1
chk "сняты secret-guard и pd-mask: план — «Верну снятого сторожа безопасности: 2 (pd-mask.py, secret-guard.py)»" "grep -q 'Верну снятого сторожа безопасности: 2 (pd-mask.py, secret-guard.py)' $T/p6.txt"
$U apply --src "$T/rel" --yes "тест: два обязательных" >/dev/null 2>&1
chk "secret-guard и pd-mask возвращены обновлением (по одному разу, права 600)" "[ \$(grep -o 'secret-guard.py' $S | wc -l) -eq 1 ] && [ \$(grep -o 'pd-mask.py' $S | wc -l) -eq 1 ] && [ \"\$(stat -c %a $S 2>/dev/null || stat -f %Lp $S)\" = 600 ]"
# событие в settings.json не списком (валидный JSON) — не падаю посреди обновления, чужое не трогаю
python3 - "$S" "$V" <<'PY'
import json, sys
p, v = sys.argv[1:3]; d = json.load(open(p)); d["hooks"]["Stop"] = {"hooks": []}; json.dump(d, open(p, "w"))
w = json.load(open(v)); w["guards"] = [g for g in w["guards"] if not g.startswith("Stop:")]; json.dump(w, open(v, "w"))
PY
cp "$S" "$T/s3"; $U apply --src "$T/rel" --yes "тест: не список" > "$T/a3.txt" 2>&1; rc=$?
chk "событие не списком: обновление проходит, settings.json не тронут, строка в журнале" "[ $rc -eq 0 ] && grep -q '\"ok\": true' $T/a3.txt && cmp -s $S $T/s3 && grep -q guards_skipped $CLAUDE_CONFIG_DIR/mila-update/journal.jsonl"
$U plan --src "$T/rel" > "$T/p4.txt" 2>&1
chk "событие не списком: план не обещает подключить" "! grep -q 'Подключу сторожей' $T/p4.txt"
python3 - "$S" <<'PY'
import json, sys
p = sys.argv[1]; d = json.load(open(p)); d["hooks"]["Stop"] = []; json.dump(d, open(p, "w"))
PY
$U apply --src "$T/rel" --yes "тест: снова список" >/dev/null 2>&1
chk "ещё не подключавшийся сторож (нет в version.json) подключается" "grep -q 'reply-required' $S"
# откат настроек из бэкапа: режим как у файла до правки, не по umask
cat > "$T/restore.py" <<'PY'
import glob, os, stat, sys
sys.path.insert(0, sys.argv[1]); import update as U
p = sys.argv[2]; st = os.lstat(p); want = open(p, 'rb').read()
b = U.backup([p], 'test-restore'); open(p, 'w').write('{}'); os.chmod(p, 0o644)
U.restore_settings(b, p, st)
sys.exit(0 if open(p, 'rb').read() == want and stat.S_IMODE(os.lstat(p).st_mode) == 0o600 and not glob.glob(p + '.restore') else 1)
PY
chk "откат settings.json из бэкапа сохраняет режим (600 при umask 022)" "(umask 022; python3 $T/restore.py $HERE $S)"
python3 - "$S" "$V" <<'PY'
import json, sys
p, v = sys.argv[1:3]; d = json.load(open(p)); d["hooks"]["PostToolUse"] = [g for g in d["hooks"]["PostToolUse"] if "pd-mask" not in json.dumps(g)]; json.dump(d, open(p, "w"))
w = json.load(open(v)); w["guards"] = [g for g in w["guards"] if "pd-mask" not in g]; json.dump(w, open(v, "w"))   # как будто ещё не подключали
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
# заглушка на месте сломанного сторожа — наш файл: обновление возвращает релизный сторож без --take; правка хозяина поверх неё — его
F="$T/home2"; export HOME="$F" CLAUDE_CONFIG_DIR="$F/.claude" MILA_WORK="$F/work"; mkdir -p "$CLAUDE_CONFIG_DIR" "$MILA_WORK"; echo "знакомство: пройдено" > "$MILA_WORK/USER.md"
echo '{}' > "$CLAUDE_CONFIG_DIR/settings.json"; $U apply --src "$T/rel" --yes "тест: чистый дом" >/dev/null 2>&1
SG="$CLAUDE_CONFIG_DIR/hooks/secret-guard.py"; GCK="python3 $CLAUDE_CONFIG_DIR/hooks/guard_check.py"; REL_SG="$T/rel/templates/home/.claude/hooks/secret-guard.py"
chk "подготовка: в чистом доме сторож тайны равен релизному, проверка сторожей — ok" "cmp -s $SG $REL_SG && $GCK --json | grep -q '\"guards\": \"ok\"'"
printf 'def (:\n' > "$SG"; rm "$CLAUDE_CONFIG_DIR/mila-update/guards/secret-guard.py"; $GCK >/dev/null 2>&1
chk "подготовка: сторож сломан, копии нет → стоит заглушка, состояние blocked" "grep -q 'mila-guard-stub' $SG && $GCK --json --no-fix | grep -q '\"guards\": \"blocked\"'"
$U plan --src "$T/rel" > "$T/p7.txt" 2>&1; $U apply --src "$T/rel" --yes "тест: заглушка" >/dev/null 2>&1
chk "apply без --take заменяет заглушку релизным сторожем; после него проверка — ok" "cmp -s $SG $REL_SG && $GCK --json | grep -q '\"guards\": \"ok\"'"
printf 'def (:\n' > "$SG"; rm "$CLAUDE_CONFIG_DIR/mila-update/guards/secret-guard.py"; $GCK >/dev/null 2>&1; echo '# правка хозяина' >> "$SG"
$U apply --src "$T/rel" --yes "тест: правка поверх заглушки" >/dev/null 2>&1
chk "правка хозяина поверх заглушки — «ваша правка»: обновление её не затирает" "grep -q 'правка хозяина' $SG"
export HOME="$T/home" CLAUDE_CONFIG_DIR="$T/home/.claude" MILA_WORK="$T/home/work"
chk "шаблон рождения: каждая его запись есть в guards слово в слово; сверх шаблона в guards — только ход работы (hod-stream ×4, его включают установка и раскатка)" "python3 - <<'PY'
import json, sys
m = json.load(open('$REPO/release.json'))['guards']; t = json.load(open('$REPO/templates/home/.claude/settings.json'))['hooks']
want = sorted((g['event'], g.get('matcher') or '', json.dumps(g['hook'], sort_keys=True)) for g in m)
have = sorted((ev, grp.get('matcher') or '', json.dumps(h, sort_keys=True)) for ev, l in t.items() for grp in l for h in grp['hooks'])
extra = [w for w in want if w not in have]
sys.exit(0 if all(h in want for h in have) and len(have) == len(set(have)) == 14 and sorted(e[0] for e in extra) == ['PostToolUse', 'PreToolUse', 'Stop', 'UserPromptSubmit'] and all('hod-stream.py' in e[2] for e in extra) else 1)
PY"
chk "запреты шаблона рождения — те же deny_required" "python3 -c \"import json,sys; t=json.load(open('$REPO/templates/home/.claude/settings.json')).get('permissions',{}).get('deny',[]); r=json.load(open('$REPO/release.json'))['deny_required']; sys.exit(0 if len(r) == 4 and all(x in t for x in r) else 1)\""
# один список: всё, что подключал tools/hooks_sync.py до объединения (версия 1.7.14, список заморожен здесь), есть в guards
chk "каждая запись прежнего hooks_sync есть в guards (событие, зона, файл) — 13 сторожей и 2 от mila-tasks; запреты — те же четыре" "python3 - <<'PY'
import json, os, sys
SEND = '|'.join('mcp__plugin_(mila-)?telegram_telegram__' + t for t in ('reply', 'edit_message', 'topic', 'widget', 'widget_data'))
OLD = [('PreToolUse', SEND, 'send-guard.py'), ('PreToolUse', SEND, 'done-guard.py'), ('PostToolUseFailure', '', 'done-guard.py'),
       ('PreToolUse', 'Bash|Read|Grep|Glob|Edit|Write|MultiEdit|WebFetch|Monitor', 'secret-guard.py'), ('UserPromptSubmit', '', 'skill-hint.py'),
       ('PreToolUse', '', 'hod-stream.py'), ('PostToolUse', '', 'hod-stream.py'), ('Stop', '', 'hod-stream.py'), ('UserPromptSubmit', '', 'hod-stream.py'),
       ('PostToolUse', 'Write|Edit|MultiEdit', 'pd-mask.py'), ('SessionStart', '', 'crons-keeper.py'), ('PostToolUse', 'CronCreate|CronDelete', 'crons-keeper.py'),
       ('Stop', '', 'reply-required.py'), ('PostToolUse', 'mcp__plugin_(mila-)?telegram_telegram__reply', 'task-sent.py'), ('SessionStart', '', 'task-open.py')]
m = json.load(open('$REPO/release.json'))
have = {(g['event'], g.get('matcher') or '', os.path.basename(g['key'])) for g in m['guards']}
fail = [g for g in m['guards'] if g['key'] == 'hooks/done-guard.py' and g['event'] == 'PostToolUseFailure'][0]
send = [g for g in m['guards'] if g['key'] == 'hooks/send-guard.py'][0]
src = open('$REPO/tests/fixtures/hooks_sync_1_7_14.py', encoding='utf-8').read()
old_deny = [r for r in m['deny_required'] if json.dumps(r) in src]
sys.exit(0 if all(o in have for o in OLD) and len(OLD) == 15 and fail.get('min_cc') == '2.1.295' and send['hook'].get('onFailure') == 'block'
         and len(m['deny_required']) == 4 and old_deny == m['deny_required'] and all(o[2] in src for o in OLD) else 1)
PY"
# дом, собранный прежним hooks_sync (как у живых Мил после раскатки), обновление не меняет ни на байт
B="$T/b"; mkdir -p "$B/.claude/hooks" "$B/.claude/skills/mila-tasks/hooks" "$B/work"; echo "знакомство: пройдено" > "$B/work/USER.md"
cp "$REPO"/templates/home/.claude/hooks/*.py "$B/.claude/hooks/"; for f in telegram-inbox-feed crons-keeper reply-required pd-mask; do cp "$REPO/install/$f.py" "$B/.claude/hooks/"; done
cp "$REPO"/skills/mila-tasks/hooks/*.py "$B/.claude/skills/mila-tasks/hooks/"
printf '{"env": {"X": "1"}, "hooks": {"SessionStart": [{"hooks": [{"type": "command", "command": "python3 %s/.claude/hooks/session-start.py"}]}], "UserPromptSubmit": [{"hooks": [{"type": "command", "command": "%s/.claude/hooks/telegram-inbox-feed.py"}]}]}}' "$B" "$B" > "$B/.claude/settings.json"
python3 -I "$REPO/tests/fixtures/hooks_sync_1_7_14.py" --home "$B" --guards > "$T/b0.json"
cp "$B/.claude/settings.json" "$T/b1"
UB="env HOME=$B CLAUDE_CONFIG_DIR=$B/.claude MILA_WORK=$B/work python3 $HERE/update.py"
$UB plan --src "$T/rel" > "$T/pb.txt" 2>&1
chk "прежний hooks_sync записал 15 строк (13 сторожей и 2 mila-tasks) и 4 запрета" "python3 -c \"import json,sys; a=json.load(open('$T/b0.json'))['added']; sys.exit(0 if len([x for x in a if not x.startswith('deny')]) == 15 and len([x for x in a if x.startswith('deny')]) == 4 else 1)\""
chk "дом после прежнего hooks_sync: план обещает одно — подключить новый сторож проверки сторожей; ни расширить, ни добавить запрет" "grep -q 'Подключу сторожей ядра: 1 (guard_check.py)' $T/pb.txt && ! grep -qE 'Расширю зону|запрет' $T/pb.txt"
$UB apply --src "$T/rel" --yes "тест: дом после hooks_sync" > "$T/ab.txt" 2>&1
chk "дом после прежнего hooks_sync: обновление прошло; всё прежнее в settings.json то же и в том же порядке, добавлена ровно одна запись — guard_check на PostToolUse (её прежний hooks_sync не знал)" "grep -q '\"ok\": true' $T/ab.txt && python3 - <<PY
import json, sys
a = json.load(open('$T/b1')); b = json.load(open('$B/.claude/settings.json'))
new = b['hooks']['PostToolUse'][-1]
b['hooks']['PostToolUse'] = b['hooks']['PostToolUse'][:-1]
sys.exit(0 if json.dumps(a, ensure_ascii=False) == json.dumps(b, ensure_ascii=False) and list(a) == list(b) and 'guard_check.py --hook' in new['hooks'][0]['command'] and new['matcher'] == 'Write|Edit|MultiEdit' else 1)
PY"
cp "$B/.claude/settings.json" "$T/b1"; $UB apply --src "$T/rel" --yes "тест: дом после hooks_sync, второй раз" > /dev/null 2>&1
chk "второе обновление того же дома — settings.json байт в байт тот же" "cmp -s $B/.claude/settings.json $T/b1"
python3 -I "$REPO/tools/hooks_sync.py" --home "$B" --guards > "$T/b2.json"
chk "и новый hooks_sync --guards (тот же код обновления) там ничего не добавляет" "grep -q '\"added\": \[\]' $T/b2.json && cmp -s $B/.claude/settings.json $T/b1"
# и наоборот: пустой дом, собранный новым hooks_sync --guards, обновление тоже не меняет
C="$T/c"; mkdir -p "$C/.claude/skills/mila-tasks" "$C/work"; cp -R "$B/.claude/hooks" "$C/.claude/hooks"; cp -R "$B/.claude/skills/mila-tasks/hooks" "$C/.claude/skills/mila-tasks/hooks"; echo "знакомство: пройдено" > "$C/work/USER.md"
echo '{}' > "$C/.claude/settings.json"; chmod 600 "$C/.claude/settings.json"
python3 -I "$REPO/tools/hooks_sync.py" --home "$C" --guards --dry-run > "$T/c0.json"
chk "hooks_sync --guards --dry-run: называет 18 сторожей и 4 запрета, файл не тронут" "python3 -c \"import json,sys; a=json.load(open('$T/c0.json'))['added']; sys.exit(0 if len([x for x in a if not x.startswith('deny')]) == 18 and len([x for x in a if x.startswith('deny')]) == 4 else 1)\" && [ \"\$(cat $C/.claude/settings.json)\" = '{}' ]"
python3 -I "$REPO/tools/hooks_sync.py" --home "$C" --guards > "$T/c1.json"; cp "$C/.claude/settings.json" "$T/c1"
UC="env HOME=$C CLAUDE_CONFIG_DIR=$C/.claude MILA_WORK=$C/work python3 $HERE/update.py"
$UC apply --src "$T/rel" --yes "тест: дом после нового hooks_sync" > "$T/ac.txt" 2>&1
chk "дом после нового hooks_sync --guards: обновление не меняет settings.json ни на байт, права 600" "grep -q '\"ok\": true' $T/ac.txt && cmp -s $C/.claude/settings.json $T/c1 && [ \"\$(stat -c %a $C/.claude/settings.json 2>/dev/null || stat -f %Lp $C/.claude/settings.json)\" = 600 ]"
# старая Claude Code: событие PostToolUseFailure и поле onFailure ей незнакомы — не пишу
D="$T/d"; mkdir -p "$D/.claude"; cp -R "$B/.claude/hooks" "$D/.claude/hooks"; echo '{}' > "$D/.claude/settings.json"
MILA_CC_VERSION=2.1.200 python3 -I "$REPO/tools/hooks_sync.py" --home "$D" --guards > /dev/null
chk "старая Claude Code: нет PostToolUseFailure, send-guard без onFailure; сторожа на месте" "python3 -c \"import json,sys; h=json.load(open('$D/.claude/settings.json'))['hooks']; j=json.dumps(h); sys.exit(0 if 'PostToolUseFailure' not in h and 'onFailure' not in j and 'send-guard.py' in j and 'secret-guard.py' in j else 1)\""
MILA_CC_VERSION=2.1.310 python3 -I "$REPO/tools/hooks_sync.py" --home "$D" --guards > "$T/d1.json"
chk "Claude Code обновилась: следующий запуск дописывает PostToolUseFailure (одну запись)" "python3 -c \"import json,sys; a=json.load(open('$T/d1.json'))['added']; sys.exit(0 if a == ['done-guard.py (PostToolUseFailure)'] else 1)\""
# зону расширяю только обязательным: сторож удобства с зоной уже, чем в релизе, — решение дома, не трогаю и второй записью не дублирую
E="$T/e"; mkdir -p "$E/.claude"; cp -R "$B/.claude/hooks" "$E/.claude/hooks"
echo '{"hooks": {"PostToolUse": [{"matcher": "CronCreate", "hooks": [{"type": "command", "command": "python3 h/crons-keeper.py"}]}]}}' > "$E/.claude/settings.json"
python3 -I "$REPO/tools/hooks_sync.py" --home "$E" --guards > "$T/e1.json"
chk "сторож удобства с узкой зоной (crons-keeper на один CronCreate): зона та же, второй записи нет, в ответе о нём ни слова" "python3 -c \"import json,sys; d=json.load(open('$E/.claude/settings.json'))['hooks']['PostToolUse']; c=[g for g in d if 'crons-keeper' in json.dumps(g)]; a=json.load(open('$T/e1.json'))['added']; sys.exit(0 if len(c) == 1 and c[0]['matcher'] == 'CronCreate' and not any('crons-keeper.py (PostToolUse)' in x or x.startswith('matcher: crons') for x in a) else 1)\""
# запись прошла, а запрета на месте нет (проверка после записи) — откат из бэкапа, дом как был
F="$T/f"; mkdir -p "$F/.claude"; cp -R "$B/.claude/hooks" "$F/.claude/hooks"; echo '{"env": {"X": "1"}}' > "$F/.claude/settings.json"; cp "$F/.claude/settings.json" "$T/f1"
cat > "$T/after.py" <<'PY'
import sys
sys.path.insert(0, sys.argv[1]); import update as U
real, calls = U.missing_deny, []
def fake(src, cfg):
    calls.append(1)
    return real(src, cfg) if len(calls) == 1 else ["не записалось"]
U.missing_deny = fake
sys.exit(0 if U.connect_guards(sys.argv[2], "test-after") is None and len(calls) == 2 else 1)
PY
chk "после записи запрета нет на месте — подключение отказано, settings.json возвращён из бэкапа байт в байт, строка guards_failed" "env HOME=$F MILA_HOME=$F CLAUDE_CONFIG_DIR=$F/.claude python3 $T/after.py $HERE $T/rel && cmp -s $F/.claude/settings.json $T/f1 && grep -q guards_failed $F/.claude/mila-update/journal.jsonl"
# обёртка не глотает сбой обновления: код 3 и «ok: false», а не «добавлено: ничего»
cp -R "$T/rel" "$T/rel2"; echo 'import sys; sys.exit(1)' > "$T/rel2/skills/mila-update/update.py"
python3 -I "$T/rel2/tools/hooks_sync.py" --home "$F" --guards > "$T/f2.json" 2>/dev/null; rc=$?
chk "hooks_sync --guards: обновление упало — код 3, «ok: false», settings.json не тронут" "[ $rc -eq 3 ] && grep -q '\"ok\": false' $T/f2.json && cmp -s $F/.claude/settings.json $T/f1"
echo "итог $ok/$n"; [ $ok -eq $n ]
