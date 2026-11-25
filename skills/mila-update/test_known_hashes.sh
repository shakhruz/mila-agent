#!/usr/bin/env bash
# прошлая версия файла ядра, поставленная не обновлением (нет в version.json), — «наша прошлая версия»: обновляется без --take.
# Своя правка хозяина (такого хеша в истории ядра нет) — по-прежнему «отличается». known-hashes.json нет или кривой — как раньше.
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"; REPO="$(cd "$HERE/../.." && pwd)"
T="$(mktemp -d)"; trap 'chmod -R u+w "$T" 2>/dev/null; rm -rf "$T"' EXIT; export HOME="$T/home" CLAUDE_CONFIG_DIR="$T/home/.claude" MILA_WORK="$T/home/work"
mkdir -p "$CLAUDE_CONFIG_DIR" "$MILA_WORK"; echo "знакомство: пройдено" > "$MILA_WORK/USER.md"
cp -R "$REPO" "$T/rel"; rm -rf "$T/rel/.git" "$T/rel/known-hashes.json"
U="python3 $HERE/update.py"; ok=0; n=0
chk() { n=$((n+1)); if eval "$2"; then ok=$((ok+1)); echo "✅ $1"; else echo "❌ $1"; fi; }
$U apply --src "$T/rel" --yes "тест: база" >/dev/null 2>&1
G="$CLAUDE_CONFIG_DIR/hooks/send-guard.py"; V="$CLAUDE_CONFIG_DIR/mila-update/version.json"
LAST=$(git -C "$REPO" tag --list 'v*' | sort -V | tail -1)
CURH=$(git -C "$REPO" rev-parse "HEAD:templates/home/.claude/hooks/send-guard.py")
OLDREV=""; for r in $(git -C "$REPO" log --format=%H -- templates/home/.claude/hooks/send-guard.py); do   # первая версия, отличная от текущей
  [ "$(git -C "$REPO" rev-parse "$r:templates/home/.claude/hooks/send-guard.py" 2>/dev/null)" != "$CURH" ] && { OLDREV=$r; break; }; done
git -C "$REPO" show "$OLDREV:templates/home/.claude/hooks/send-guard.py" > "$G"
python3 - "$V" "$G" <<'PY'
import json, sys
p, g = sys.argv[1], sys.argv[2]; v = json.load(open(p)); v["files"].pop(g, None); json.dump(v, open(p, "w"))
PY
state() { $U plan --src "$T/rel" --json | python3 -c "import json,sys; d=json.load(sys.stdin); print('отличается' if 'send-guard.py' in d.get('keep',{}).get('отличается',[]) else 'нет')"; }
chk "подготовка: стоит прошлая версия ядра, в version.json её нет" "! cmp -s $G $T/rel/templates/home/.claude/hooks/send-guard.py && ! python3 -c \"import json,sys; sys.exit(0 if any(k.endswith('hooks/send-guard.py') for k in json.load(open('$V')).get('files', {})) else 1)\""
chk "без known-hashes.json — как раньше: «отличается» (контроль)" "[ \"\$(state)\" = отличается ]"
python3 "$REPO/tools/known_hashes.py" --repo "$REPO" --out "$T/rel/known-hashes.json" >/dev/null
chk "known-hashes.json собран и содержит эту прошлую версию" "python3 -c \"import json,hashlib,sys; d=json.load(open('$T/rel/known-hashes.json'))['files']; h=hashlib.sha256(open('$G','rb').read()).hexdigest()[:16]; sys.exit(0 if h in d['{claude}/hooks/send-guard.py'] else 1)\""
chk "с known-hashes.json — прошлая версия ядра больше не «отличается»" "[ \"\$(state)\" = нет ]"
$U apply --src "$T/rel" --yes "тест: без take" >/dev/null 2>&1
chk "apply без --take обновил прошлую версию до ядра" "cmp -s $G $T/rel/templates/home/.claude/hooks/send-guard.py"
git -C "$REPO" show "$OLDREV:templates/home/.claude/hooks/send-guard.py" > "$G"   # откат хозяина: version.json файл ЗНАЕТ
staterow() { $U diff --src "$T/rel" --json | python3 -c "import json,sys; print([r['state'] for r in json.load(sys.stdin)['rows'] if r['name']=='send-guard.py'][0])"; }
chk "откат на прошлую версию ядра, а version.json файл знает — «ваша правка», не затираю" "[ \"\$(staterow)\" = 'ваша правка' ]"
$U apply --src "$T/rel" --yes "тест: откат" >/dev/null 2>&1
chk "apply без --take откат хозяина не тронул" "! cmp -s $G $T/rel/templates/home/.claude/hooks/send-guard.py"
python3 - "$V" "$G" <<'PY'
import json, sys
p, g = sys.argv[1], sys.argv[2]; v = json.load(open(p)); v["files"].pop(g, None); json.dump(v, open(p, "w"))
open(g, "a").write("# правка хозяина, которой нет в истории ядра\n")
PY
chk "своя правка хозяина (хеша нет в истории) — по-прежнему «отличается»" "[ \"\$(state)\" = отличается ]"
$U apply --src "$T/rel" --yes "тест: правка" >/dev/null 2>&1
chk "apply без --take правку хозяина не тронул" "grep -q 'правка хозяина' $G"
echo '{"files": "не словарь"}' > "$T/rel/known-hashes.json"
chk "кривой known-hashes.json — без падения, как раньше" "[ \"\$(state)\" = отличается ]"
echo '{"files": {"{claude}/hooks/send-guard.py": ["xyz", 5]}}' > "$T/rel/known-hashes.json"
chk "мусорные хеши отбрасываются" "[ \"\$(state)\" = отличается ]"
echo '{' > "$T/rel/known-hashes.json"
chk "known-hashes.json не разбирается как JSON — план строится (код 0), файл по-прежнему «отличается»" "$U plan --src $T/rel --json >/dev/null 2>&1 && [ \"\$(state)\" = отличается ]"
HG=$(python3 -c "import hashlib,sys; print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest()[:16])" "$G")
echo '{"files": {"{claude}/hooks/session-start.py": ["'$HG'"]}}' > "$T/rel/known-hashes.json"
chk "хеш записан за ДРУГИМ местом — этот файл по-прежнему «отличается» (прошлая версия узнаётся по месту, не по любому хешу)" "[ \"\$(state)\" = отличается ]"
echo '{"files": {"{claude}/hooks/send-guard.py": ["'$HG'"]}}' > "$T/rel/known-hashes.json"
chk "контроль: тот же хеш за своим местом — «наша прошлая версия»" "[ \"\$(state)\" = нет ]"
echo '{"files":[{"dst":"/etc/passwd","sha256":"'$(printf 'a%.0s' $(seq 64))'","from":"x"}]}' > "$T/extra.json"
EX="$T/exrepo"; git clone -q "$REPO" "$EX" 2>/dev/null; cp "$T/extra.json" "$EX/known-hashes.extra.json"
chk "extra: место вне {claude}/{work}/{home} — сборка отказывает" "! python3 $REPO/tools/known_hashes.py --repo $EX --out $T/k2.json --tags $LAST >/dev/null 2>&1"
echo '{"files":[{"dst":"{claude}/../x","sha256":"'$(printf 'c%.0s' $(seq 64))'","from":"x"}]}' > "$EX/known-hashes.extra.json"
chk "extra: «..» в месте — сборка отказывает" "! python3 $REPO/tools/known_hashes.py --repo $EX --out $T/k4.json --tags $LAST >/dev/null 2>&1"
echo '{"files":[{"dst":"{claude}/hooks/send-guard.py","sha256":"'$(printf 'b%.0s' $(seq 64))'","from":"шаблон рождения на сервере"}]}' > "$EX/known-hashes.extra.json"
chk "extra: строка с dst, sha256 и «откуда» — в списке" "python3 $REPO/tools/known_hashes.py --repo $EX --out $T/k3.json --tags $LAST >/dev/null && grep -q bbbbbbbbbb $T/k3.json"
echo "итог $ok/$n"; [ $ok -eq $n ]
