#!/usr/bin/env bash
# Mila Agent files without Docker: compose parses and has no secrets or ports; Dockerfile copies paths that exist;
# entrypoint waits with a clear line (not a crash loop) when a variable is missing or wrong.
cd "$(dirname "$0")/.." || exit 1
ok=0; n=0
# portable «timeout N cmd»: macOS has no GNU timeout; perl is on both runners
PERL=$(command -v perl)
# perl as «timeout N cmd»: the command in its own process group, the whole group killed after N s (like GNU timeout,
# which macOS lacks) — a waiting child (the sign-in helper) must not keep the output pipe open
TMO='$t=shift; $p=fork; if(!$p){setpgrp(0,0); exec @ARGV; exit 127} $SIG{ALRM}=sub{kill "KILL", -$p}; alarm $t; waitpid($p,0); exit($?>>8)'
chk() { n=$((n+1)); if eval "$2"; then ok=$((ok+1)); echo "✅ $1"; else echo "❌ $1"; fi; }
chk "помощник входа: тест поддельного Telegram и setup-token" "python3 docker/test_claude_login.py >/dev/null 2>&1"
chk "страница токена: тест поддельного Telegram" "python3 docker/test_token_page.py >/dev/null 2>&1"
chk "код рождения: тест поддельного relay и entrypoint" "python3 docker/test_birth_claim.py >/dev/null 2>&1"
chk "compose: один сервис mila, том mila-home, портов нет" "python3 -c \"import yaml;d=yaml.safe_load(open('docker-compose.yml'));s=d['services']['mila'];assert 'ports' not in s and 'mila-home:/home/agent' in s['volumes'][0]\""
chk "compose: переменные — только подстановкой \${…}, значений нет" "! grep -E '(TOKEN|KEY): [^\$ ]' docker-compose.yml"
chk "Dockerfile: install.sh и onboard.py, на которые опирается entrypoint, есть в репозитории" "[ -f install/install.sh ] && [ -f install/onboard.py ] && grep -q 'COPY docker/entrypoint.sh docker/healthcheck.sh' docker/Dockerfile"
chk "плагин в образе закреплён коммитом (40 знаков), не веткой main" "grep -qE '^ARG PLUGIN_REF=[0-9a-f]{40}$' docker/Dockerfile && grep -q 'checkout -q \"\${PLUGIN_REF}\"' docker/Dockerfile"
chk "Dockerfile в корне = docker/Dockerfile (Railway и панели «из GitHub» ищут ./Dockerfile)" "cmp -s Dockerfile docker/Dockerfile"
chk "в Dockerfile нет VOLUME (Railway такой не собирает) и нет USER (entrypoint сам переходит в agent)" "! grep -qE '^(VOLUME|USER)' docker/Dockerfile"
chk "страница токена: PORT=8080 и EXPOSE 8080 в образе (подсказка Railway совпадает), compose отключает страницу" "grep -q '^ENV PORT=8080' docker/Dockerfile && grep -q '^EXPOSE 8080' docker/Dockerfile && python3 -c \"import yaml;assert yaml.safe_load(open('docker-compose.yml'))['services']['mila']['environment']['PORT']==''\""
chk "railway.json: сборка по Dockerfile, перезапуск при сбое" "python3 -c \"import json;d=json.load(open('railway.json'));assert d['build']['builder']=='DOCKERFILE' and d['deploy']['restartPolicyType']=='ON_FAILURE'\""
chk "каждый старт: наши CLAUDE.md и конституция — home_template.py (недостающее, наше прежнее — замена, правка хозяина — .new)" "grep -q 'install/home_template.py\" \"\$MILA_KIT\" \"\$H/work\"' docker/entrypoint.sh && python3 install/test_home_template.py >/dev/null 2>&1"
chk "сессия продолжает разговор после рестарта (--continue), сломанный разговор — заново через session.fresh" "grep -q 'claude -p \\\\\$CONT' docker/entrypoint.sh && grep -q 'session.fresh' docker/entrypoint.sh"
chk "голос: приёмник запускается с TELEGRAM_VOICE_TRANSCRIBE_CMD = скрипт Groq; key_page в образе" "grep -q 'TELEGRAM_VOICE_TRANSCRIBE_CMD=.*transcribe-voice.sh' docker/entrypoint.sh && grep -q 'docker/key_page.py' docker/Dockerfile"
chk "CLAUDE.md новорождённой: ключ Deepgram (Groq — для узбекского) — страницей key_page, не в чат; без ключа — честно и просьба текстом, не угадывать" "grep -q 'key_page.py deepgram' templates/work/CLAUDE.md && grep -q 'Deepgram does not know Uzbek' templates/work/CLAUDE.md && grep -q 'not here in the chat' templates/work/CLAUDE.md && grep -q 'please write this one in text' templates/work/CLAUDE.md && grep -q 'never guess what a voice note said' templates/work/CLAUDE.md"
chk "Барабан в контейнере: цикл tick раз в минуту для своего дома, состояние в ~/state/baraban" "grep -q 'install/baraban.py\" tick --home \"\$H\" --owner \"\$O\" --state \"\$ST/baraban\"' docker/entrypoint.sh && grep -q 'sleep 60' docker/entrypoint.sh"
chk "entrypoint и healthcheck — синтаксис bash" "bash -n docker/entrypoint.sh && bash -n docker/healthcheck.sh"
H=$(mktemp -d); PYDIR=$(dirname "$(command -v python3)"); run_ep() { env -i HOME="$H" PATH="$PYDIR:/usr/bin:/bin" MILA_KIT="$PWD" "$@" "$PERL" -e "$TMO" 3 bash docker/entrypoint.sh 2>&1; }
o=$(run_ep); chk "нет TELEGRAM_BOT_TOKEN → ждёт со строкой про @BotFather (не падает)" "printf '%s' \"\$o\" | grep -q 'BotFather' && printf '%s' \"\$o\" | grep -q 'restart the container'"
TP=$(mktemp -d); printf '#!/bin/sh\necho "token-page: open this service public address"\nexit 3\n' > "$TP/tp"; chmod +x "$TP/tp"
o=$(run_ep PORT=8080 TOKEN_PAGE="$TP/tp"); chk "нет токена, есть PORT → страница токена; закрылась пустой — ждёт со строкой «restart the service»" "printf '%s' \"\$o\" | grep -q 'token-page: open' && printf '%s' \"\$o\" | grep -q 'restart the service'"
mkdir -p "$H/.mila-auth"; touch "$H/.mila-auth/token_page.done"; o=$(run_ep PORT=8080 TOKEN_PAGE="$TP/tp"); rm -f "$H/.mila-auth/token_page.done"
chk "страница уже была (метка) — второй раз не открывается" "! printf '%s' \"\$o\" | grep -q 'token-page'"
rm -rf "$TP"
o=$(run_ep TELEGRAM_BOT_TOKEN=abc); chk "токен не похож → строка «does not look like»" "printf '%s' \"\$o\" | grep -q 'does not look like'"
T="1234567"":""AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
o=$(run_ep TELEGRAM_BOT_TOKEN="$T" LOGIN_HELPER="$PWD/docker/claude_login.py" TG_API=http://127.0.0.1:9); chk "нет входа Claude → помощник входа ждёт /start в Telegram (не «ждёт вечно»)" "printf '%s' \"\$o\" | grep -q 'write /start to your bot' && printf '%s' \"\$o\" | grep -q 'waiting for /start'"
chk "…и до входа ничего не установлено и не записано (.env нет)" "[ ! -e \"$H/.claude/channels/telegram/.env\" ]"
o=$(run_ep TELEGRAM_BOT_TOKEN="$T" ANTHROPIC_API_KEY=x OWNER_ID=abc); chk "OWNER_ID не число → строка про numeric Telegram id" "printf '%s' \"\$o\" | grep -q 'numeric Telegram id'"
# root → agent: подменённые id/stat/chown/setpriv пишут, что их звали; сам entrypoint дальше не идёт (setpriv-заглушка выходит)
SB=$(mktemp -d); HR=$(mktemp -d)
printf '#!/bin/sh\necho 0\n' > "$SB/id"; printf '#!/bin/sh\necho 0\n' > "$SB/stat"
printf '#!/bin/sh\necho "chown $*" >> "%s/log"\n' "$SB" > "$SB/chown"; printf '#!/bin/sh\necho "setpriv $*" >> "%s/log"\nexit 0\n' "$SB" > "$SB/setpriv"
chmod +x "$SB"/*; env -i HOME="$HR" PATH="$SB:/usr/bin:/bin" "$PERL" -e "$TMO" 3 bash docker/entrypoint.sh >/dev/null 2>&1
chk "запуск от root: дом отдаётся agent (chown -R -h 1001), затем тот же скрипт под 1001 через setpriv" "grep -q 'chown -R -h 1001:1001 $HR' $SB/log && grep -q 'setpriv --reuid=1001 --regid=1001 --init-groups -- bash docker/entrypoint.sh' $SB/log"
printf '#!/bin/sh\necho 1001\n' > "$SB/stat"; : > "$SB/log"; env -i HOME="$HR" PATH="$SB:/usr/bin:/bin" "$PERL" -e "$TMO" 3 bash docker/entrypoint.sh >/dev/null 2>&1
chk "дом уже agent — chown не нужен, только setpriv" "! grep -q chown $SB/log && grep -q setpriv $SB/log"
PYD="$(dirname "$(command -v python3)")"
# root → the key keeper first: on success the session gets only its address, the token variables are gone
printf '#!/bin/sh\necho "setpriv $*" >> "%s/log"; env | grep -E "^(MILA_KEYD|KEYD_SOCK|CLAUDE_CODE_OAUTH_TOKEN|GROQ_API_KEY|MILA_IO|MILA_TG_JOURNAL)=" | sed "s/=.*//" >> "%s/log"\nexit 0\n' "$SB" "$SB" > "$SB/setpriv"
printf 'import os, sys\nopen("%s/log", "a").write("keyd " + " ".join(sys.argv[1:]) + "\\n")\nsys.exit(int(os.environ.get("KEYD_RC", "0")))\n' "$SB" > "$SB/keyd"; chmod +x "$SB"/*
: > "$SB/log"; env -i HOME="$HR" PATH="$SB:$PYD:/usr/bin:/bin" KEYD_BIN="$SB/keyd" CLAUDE_CODE_OAUTH_TOKEN=x GROQ_API_KEY=y "$PERL" -e "$TMO" 3 bash docker/entrypoint.sh >/dev/null 2>&1
chk "root: хранитель ключей запущен (boot --home --agent-uid 1001), сессии — только его адрес, переменных с токеном нет" "grep -q 'keyd boot --home $HR --agent-uid 1001' $SB/log && grep -qx MILA_KEYD $SB/log && grep -qx KEYD_SOCK $SB/log && ! grep -qx CLAUDE_CODE_OAUTH_TOKEN $SB/log && ! grep -qx GROQ_API_KEY $SB/log"
chk "приёмник — своим пользователем mila-io (фоном, ждёт «go»), сессии — MILA_IO" "grep -q 'setpriv --reuid=mila-io --regid=mila-io --groups=1001' $SB/log && grep -qx MILA_IO $SB/log"
: > "$SB/log"; env -i HOME="$HR" PATH="$SB:$PYD:/usr/bin:/bin" KEYD_BIN="$SB/keyd" KEYD_RC=1 CLAUDE_CODE_OAUTH_TOKEN=x "$PERL" -e "$TMO" 3 bash docker/entrypoint.sh >/dev/null 2>&1
chk "хранитель не поднялся — без его адреса, токен как раньше (старт не ломается)" "! grep -qx MILA_KEYD $SB/log && grep -qx CLAUDE_CODE_OAUTH_TOKEN $SB/log && grep -q setpriv $SB/log"
: > "$SB/log"; env -i HOME="$HR" PATH="$SB:$PYD:/usr/bin:/bin" KEYD_BIN="$SB/keyd" MILA_KEYD=off "$PERL" -e "$TMO" 3 bash docker/entrypoint.sh >/dev/null 2>&1
chk "MILA_KEYD=off — хранитель не запускается" "! grep -q 'keyd boot' $SB/log && grep -q setpriv $SB/log"
# an updated home (journals from before mila-io) and no OWNER_ID: owners only from the platform — a «pending» mark, a log line
rm -rf "${HR:?}"; HR=$(mktemp -d); mkdir -p "$HR/.claude/channels/telegram/inbound"; echo '{"x":1}' > "$HR/.claude/channels/telegram/inbound/events.jsonl"
OUT_UP=$(env -i HOME="$HR" PATH="$SB:$PYD:/usr/bin:/bin" KEYD_BIN="$SB/keyd" CLAUDE_CODE_OAUTH_TOKEN=x "$PERL" -e "$TMO" 3 bash docker/entrypoint.sh 2>&1)
chk "обновлённый дом без OWNER_ID: владелец только с платформы (owners.pending), строка «set OWNER_ID»" "[ -e $HR/.claude/channels/telegram/io/owners.pending ] && [ ! -e $HR/.claude/channels/telegram/io/owners.json ] && printf '%s' \"\$OUT_UP\" | grep -q 'set OWNER_ID'"
OUT_UP2=$(env -i HOME="$HR" PATH="$SB:$PYD:/usr/bin:/bin" KEYD_BIN="$SB/keyd" CLAUDE_CODE_OAUTH_TOKEN=x OWNER_ID="555"'000111' "$PERL" -e "$TMO" 3 bash docker/entrypoint.sh 2>&1)
chk "с OWNER_ID платформы — owners.json из него, pending снят" "grep -q '555''000111' $HR/.claude/channels/telegram/io/owners.json && [ ! -e $HR/.claude/channels/telegram/io/owners.pending ]"
# a home where a session ran but the receiver kept no journal (no inbound/events.jsonl) — updated too, by the session's transcripts
rm -rf "${HR:?}"; HR=$(mktemp -d); mkdir -p "$HR/.claude/projects/-home-x"; echo '{}' > "$HR/.claude/projects/-home-x/s.jsonl"
env -i HOME="$HR" PATH="$SB:$PYD:/usr/bin:/bin" KEYD_BIN="$SB/keyd" CLAUDE_CODE_OAUTH_TOKEN=x "$PERL" -e "$TMO" 3 bash docker/entrypoint.sh >/dev/null 2>&1
chk "дом со следами сессии (projects/*.jsonl), без журнала приёмника — тоже обновлённый: owners.pending" "[ -e $HR/.claude/channels/telegram/io/owners.pending ] && [ ! -e $HR/.claude/channels/telegram/io/owners.json ]"
rm -rf "${HR:?}"; HR=$(mktemp -d)
env -i HOME="$HR" PATH="$SB:$PYD:/usr/bin:/bin" KEYD_BIN="$SB/keyd" CLAUDE_CODE_OAUTH_TOKEN=x "$PERL" -e "$TMO" 3 bash docker/entrypoint.sh >/dev/null 2>&1
chk "новый дом (ни журнала, ни сессии) — без pending: владельца запишет первый «go»" "[ ! -e $HR/.claude/channels/telegram/io/owners.pending ]"
rm -rf "$SB" "$HR"
HC=$(mktemp -d); mkdir -p "$HC/state" "$HC/.claude/channels/telegram"; echo 0 > "$HC/state/session.pid"; echo 0 > "$HC/.claude/channels/telegram/receiver.pid"
chk "healthcheck: pid 0 — не «жив» (kill -0 0 бьёт по группе)" "! HOME=$HC bash docker/healthcheck.sh >/dev/null 2>&1"
rm -rf "$HC"
# Kit sync: install.sh runs on the first start and again only when the image's kit changed
KS=$(mktemp -d); mkdir -p "$KS/kit/install" "$KS/kit/skills/a" "$KS/kit/templates" "$KS/cl" "$KS/st"; echo a > "$KS/kit/skills/a/SKILL.md"
printf 'echo run >> "%s/runs"\n' "$KS" > "$KS/kit/install/install.sh"
sed -n '/^KIT_SUM=/,/^fi$/p' docker/entrypoint.sh > "$KS/sync.sh"
sync_() { env -i PATH="$PATH" MILA_KIT="$KS/kit" CL="$KS/cl" ST="$KS/st" bash -c 'log(){ :; }; wait_forever(){ exit 9; }; . "$0"' "$KS/sync.sh"; }
sync_; sync_
chk "набор: первый старт ставит, второй с тем же набором — нет" "[ \$(wc -l < $KS/runs) = 1 ]"
echo b > "$KS/kit/skills/a/SKILL.md"; sync_
chk "набор в образе изменился — install.sh снова (обновление доходит до живого дома)" "[ \$(wc -l < $KS/runs) = 2 ]"
rm -rf "$KS"
# The bot token with the key keeper: a token file of this start goes to the keeper and is wiped; then a placeholder and the API root
KB=$(mktemp -d); mkdir -p "$KB/auth" "$KB/bin" "$KB/lib"; BID="555"'000111'; BT="$BID:$(printf 'T%.0s' $(seq 35))"
printf '%s\n' "$BT" > "$KB/auth/bot_token"
printf 'import json, sys\ndef put_remote(kind, value, sock=None):\n    open(%s, "a").write(kind + "\\n"); return True\n' "'$KB/put.log'" > "$KB/lib/mila_keyd.py"
cat > "$KB/bin/curl" <<CURL
#!/bin/sh
echo '{"telegram": true, "telegram_bot_id": "$BID"}'
CURL
chmod +x "$KB/bin/curl"
sed -n '/^keyd_bot() {/,/^}/p' docker/entrypoint.sh > "$KB/fn.sh"
OUT=$(env -i PATH="$KB/bin:$PATH" MILA_KEYD=http://keyd AUTH="$KB/auth" KEYD_LIB="$KB/lib" bash -c '. "$1"; keyd_bot; echo "T=$TELEGRAM_BOT_TOKEN"; echo "R=$TELEGRAM_API_ROOT"; echo "G=$TG_API"' x "$KB/fn.sh")
chk "токен бота этого старта — хранителю, файл стёрт" "grep -qx telegram $KB/put.log && [ ! -e $KB/auth/bot_token ]"
chk "дальше везде заглушка «<id бота>:…» и адрес хранителя, настоящего токена в окружении нет" "printf '%s' \"\$OUT\" | grep -qx \"T=\$BID:mila-keyd-placeholder-not-a-token\" && printf '%s' \"\$OUT\" | grep -qx 'R=http://keyd/telegram' && printf '%s' \"\$OUT\" | grep -qx 'G=http://keyd/telegram' && ! printf '%s' \"\$OUT\" | grep -q TTTTTTTT"
OUT2=$(env -i PATH="$PATH" AUTH="$KB/auth" bash -c '. "$1"; keyd_bot; echo "T=${TELEGRAM_BOT_TOKEN:-}"' x "$KB/fn.sh")
chk "без хранителя keyd_bot ничего не трогает" "[ \"\$OUT2\" = 'T=' ]"
rm -rf "$KB"
# Cards: the session's registry and the receiver's presses are one file (before: two, a press on Mila's card was «not found»)
CK=$(mktemp -d); mkdir -p "$CK/telegram" "$CK/telegram-session"; echo '{"card_id":"old1"}' > "$CK/telegram-session/cards.jsonl"; echo '{"card_id":"r1"}' > "$CK/telegram/cards.jsonl"
sed -n '/^if \[ -f "\$TGS\/cards.jsonl" \]/,/^ln -sfn ..\/telegram\/cards.jsonl/p' docker/entrypoint.sh > "$CK/c.sh"
(cd "$CK" && TG="$CK/telegram" TGS="$CK/telegram-session" bash c.sh)
chk "карточки: файл сессии — ссылка на файл приёмника, старые карточки сессии перенесены" "[ -L $CK/telegram-session/cards.jsonl ] && grep -q old1 $CK/telegram/cards.jsonl && grep -q r1 $CK/telegram/cards.jsonl && echo '{\"card_id\":\"s2\"}' >> $CK/telegram-session/cards.jsonl && grep -q s2 $CK/telegram/cards.jsonl"
chk "сессия знает, где журналы приёмника (MILA_TG_STATE)" "grep -q '^export MILA_TG_STATE=\"\$TG\"' docker/entrypoint.sh"
rm -rf "$CK"
# Baraban loop, one turn: the owner from the file / access.json when OWNER_ID is empty; the error log is cut
O1="555"'000111'; O2="555"'000222'; O3="555"'000333'
BB=$(mktemp -d); mkdir -p "$BB/kit/install" "$BB/st" "$BB/auth" "$BB/tg"
printf 'import sys\nopen(sys.argv[0]+".args","a").write(" ".join(sys.argv[1:])+"\\n")\nsys.stderr.write("e"*100)\n' > "$BB/kit/install/baraban.py"
sed -n '/^( while :; do O=/,/sleep 60; done ) & PIDS/p' docker/entrypoint.sh | sed -e 's/^( while :; do //' -e 's/  sleep 60; done ) & PIDS+=(\$!)$/:/' > "$BB/turn.sh"
turn() { env -i PATH="$PATH" OWNER_ID="${1:-}" MILA_KIT="$BB/kit" H="$BB/h" ST="$BB/st" AUTH="$BB/auth" TG="$BB/tg" bash "$BB/turn.sh"; }
rm -f "$BB/kit/install/baraban.py.args"; turn
chk "Барабан: нет владельца нигде — виток молчит" "[ ! -e $BB/kit/install/baraban.py.args ]"
echo '{"allowFrom":["'"$O1"'"]}' > "$BB/tg/access.json"; turn
chk "Барабан: OWNER_ID пуст, пара по коду (access.json) — тик идёт без рестарта" "grep -q -- \"--owner $O1 \" $BB/kit/install/baraban.py.args"
echo "$O2" > "$BB/auth/owner_id"; : > "$BB/kit/install/baraban.py.args"; turn
chk "Барабан: файл owner_id важнее access.json" "grep -q -- \"--owner $O2 \" $BB/kit/install/baraban.py.args"
: > "$BB/kit/install/baraban.py.args"; turn "$O3"
chk "Барабан: OWNER_ID из переменной — первым" "grep -q -- \"--owner $O3 \" $BB/kit/install/baraban.py.args"
head -c 70000 /dev/zero > "$BB/st/baraban.err"; turn
chk "Барабан: журнал ошибок больше 64 КБ обрезан до 32 КБ" "[ \$(stat -c %s $BB/st/baraban.err) -le 32768 ]"
rm -rf "$BB"
rm -rf "$H"
# the receiver's supervisor after «go»: no bot token in the keeper yet → waits and says so once, does not leave; token comes → receiver starts
SV=$(mktemp -d); mkdir -p "$SV/run" "$SV/tg" "$SV/io" "$SV/bin"; printf '{}' > "$SV/status"
PORT=$(python3 -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1",0)); print(s.getsockname()[1])')
python3 -c 'import http.server,sys
class H(http.server.BaseHTTPRequestHandler):
    def do_GET(s): b=open(sys.argv[2],"rb").read(); s.send_response(200); s.end_headers(); s.wfile.write(b)
    def log_message(s,*a): pass
http.server.HTTPServer(("127.0.0.1",int(sys.argv[1])),H).serve_forever()' "$PORT" "$SV/status" & SVP=$!
printf '#!/bin/sh\necho started >> "%s/receiver.started"; sleep 30\n' "$SV" > "$SV/bin/bun"; chmod +x "$SV/bin/bun"
BODY=$(awk "/bash -c '\$/{f=1;next} f&&/^        done' >/{exit} f" docker/entrypoint.sh | sed "s#/run/mila-io#$SV/run#g; s#127.0.0.1:8790#127.0.0.1:$PORT#g"; echo done)
echo '555' > "$SV/tg/receiver.go"
(TGd="$SV/tg" IOD="$SV/io" PLUG=/x MILA_KIT=/x PATH="$SV/bin:$PATH" "$PERL" -e "$TMO" 14 bash -c "$BODY" > "$SV/stdout" 2>/dev/null &)
sleep 4
chk "надзор приёмника: «go» есть, токена бота нет — ждёт, строка в журнале и в выводе платформы (mila-agent:), не выходит и не стартует" "grep -q 'waits for the bot token' $SV/run/receiver.log && [ \$(grep -c 'waits for the bot token' $SV/run/receiver.log) -eq 1 ] && grep -q '^mila-agent: receiver waits for the bot token' $SV/stdout && [ ! -e $SV/run/receiver.up ] && [ ! -e $SV/receiver.started ]"
printf '{"telegram_bot_id": "12345678"}' > "$SV/status"; sleep 7
chk "надзор приёмника: токен появился — receiver.up и приёмник запущен" "[ -e $SV/run/receiver.up ] && [ -e $SV/receiver.started ]"
kill $SVP 2>/dev/null; sleep 8; rm -rf "${SV:?}"
# the strangers' lane: without the strangers' key it is off and the start log says so; the knowledge copy takes only small regular
# .md/.txt files from the owner's folder — no links, no hard links (root reads the owner's home)
chk "без ключа для чужих — полоса не запускается, строка в журнале старта" "printf '%s' \"\$OUT_UP\" | grep -q \"no strangers' key\""
KQ=$(mktemp -d); mkdir -p "$KQ/src" "$KQ/dst"; echo price > "$KQ/src/prices.md"; echo faq > "$KQ/src/faq.txt"; echo x > "$KQ/src/run.sh"
echo secret > "$KQ/secret"; ln -s "$KQ/secret" "$KQ/src/link.md"; ln "$KQ/src/faq.txt" "$KQ/hard.txt"; head -c 70000 /dev/zero > "$KQ/src/big.md"
CP=$(grep -o "find \"\$KD\" -maxdepth 1 .*2>/dev/null" docker/entrypoint.sh | sed "s#\"\$KD\"#$KQ/src#; s#\"\$LD/knowledge\"#$KQ/dst#; s#\\\\\\\\#\\\\#g")
eval "$CP"
chk "знания для людей: копируются только обычные небольшие .md/.txt — не ссылка, не жёсткая ссылка, не большой, не .sh" "[ \"\$(ls $KQ/dst | tr '\n' ' ')\" = 'prices.md ' ]"
rm -rf "${KQ:?}"
echo "итог $ok/$n"; [ $ok -eq $n ]
