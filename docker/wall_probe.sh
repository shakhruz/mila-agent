#!/usr/bin/env bash
# Wall probe — run as root inside the image (CI: docker run --rm --entrypoint bash mila-agent:ci /opt/mila/kit/docker/wall_probe.sh).
# The key keeper boots with fake keys the way the entrypoint does it; then, as the session's user (agent), every way out we know
# of is tried: the files, the keeper's /proc (environ, cmdline, mem), ps, the session's environment, a search of the home,
# the put socket, the status page. A fake key found anywhere — the wall is down. Prints «итог ok/n».
set -u
[ "$(id -u)" = 0 ] || { echo "run as root inside the image"; echo "итог 0/1"; exit 1; }
HOME=/home/agent; export HOME
OAT="sk-""ant-""oat01-""WALLPROBE""$(head -c 12 /dev/urandom | od -An -tx1 | tr -d ' \n')"; BOT="1234""5678:""WALLPROBE""$(head -c 12 /dev/urandom | od -An -tx1 | tr -d ' \n')"; GQ="gs""k_""WALLPROBE""$(head -c 12 /dev/urandom | od -An -tx1 | tr -d ' \n')"
mkdir -p "$HOME/.mila-auth" "$HOME/work/secrets" "$HOME/state"; echo "$OAT" > "$HOME/.mila-auth/oauth_token"; printf "GROQ_API_KEY='%s'\n" "$GQ" > "$HOME/work/secrets/groq.env"
chown -R agent:agent "$HOME"
ok=0; n=0; chk() { n=$((n+1)); if eval "$2" >/dev/null 2>&1; then ok=$((ok+1)); echo "✅ $1"; else echo "❌ $1"; fi; }
TELEGRAM_BOT_TOKEN="$BOT" CLAUDE_CODE_OAUTH_TOKEN="$OAT" python3 /usr/local/bin/mila_keyd.py boot --home "$HOME" --agent-uid 1001 >/dev/null 2>&1
chk "хранитель поднялся: токен Claude и бота у него (status отвечает)" "curl -s --max-time 5 http://127.0.0.1:8790/status | grep -q '\"anthropic\": true' && curl -s --max-time 5 http://127.0.0.1:8790/status | grep -q '\"telegram\": true'"
chk "старые файлы с ключами стёрты" "[ ! -e $HOME/.mila-auth/oauth_token ] && [ ! -e $HOME/work/secrets/groq.env ]"
AS() { setpriv --reuid=1001 --regid=1001 --init-groups -- env -i HOME="$HOME" PATH=/usr/local/bin:/usr/bin:/bin MILA_KEYD=http://127.0.0.1:8790 KEYD_SOCK=/run/mila-keyd/put.sock bash -c "$1" 2>&1; }
KP=$(pgrep -f 'mila_keyd.py' | head -1)
OUT=$(AS "cat ~/.keys/* ~/.keys/anthropic; ls -la ~/.keys; cat /proc/$KP/environ /proc/$KP/cmdline; dd if=/proc/$KP/mem bs=1 count=1 2>&1; \
  ps eww -u mila-keys; env; grep -rI 'WALLPROBE' ~ /tmp /run 2>/dev/null; cat /run/mila-keyd/put.sock; \
  curl -s http://127.0.0.1:8790/status; curl -s http://127.0.0.1:8790/../.keys/anthropic; curl -s 'http://127.0.0.1:8790/anthropic/../../etc/passwd'; \
  python3 -c 'import os; print(os.listdir(\"/proc/$KP/fd\"))'; cat /proc/1/environ; su -s /bin/sh mila-keys -c id </dev/null")
chk "под agent: ни файлы, ни /proc хранителя, ни ps, ни env, ни поиск по дому, ни status не дают ключа" "! printf '%s' \"\$OUT\" | grep -q WALLPROBE"
chk "под agent: ~/.keys не читается (Permission denied)" "printf '%s' \"\$OUT\" | grep -q 'Permission denied'"
chk "под agent: класть ключ в сокет можно (запись), прочесть — нечем" "AS \"python3 -c 'import sys; sys.path.insert(0,\\\"/usr/local/bin\\\"); import mila_keyd; sys.exit(0 if mila_keyd.put_remote(\\\"deepgram\\\", \\\"a1b2c3d4\\\"*5) else 1)'\""
chk "в журнале хранителя ключей нет" "! grep -rq WALLPROBE $HOME/state 2>/dev/null"
# the receiver's updates: once it is up, the session's user cannot read the bot's updates through the keeper
mkdir -p /run/mila-io; touch /run/mila-io/receiver.up
chk "под agent: getUpdates через хранителя при поднятом приёмнике — 403" "[ \"\$(AS 'curl -s -o /dev/null -w %{http_code} -X POST http://127.0.0.1:8790/telegram/bot1:x/getUpdates')\" = 403 ]"
# the receiver's journals: owned by mila-io in io/, the session's user reads and cannot write
IOD=/tmp/wall-io; mkdir -p "$IOD"; touch "$IOD/taps.jsonl"; chown mila-io:agent "$IOD" "$IOD/taps.jsonl"; chmod 2750 "$IOD"; chmod 640 "$IOD/taps.jsonl"
chk "под agent: журнал нажатий приёмника — читается, не пишется, папку не подменить" "AS 'cat $IOD/taps.jsonl' >/dev/null && ! AS 'echo x >> $IOD/taps.jsonl' && ! AS 'touch $IOD/new'"
# the strangers' lane: its user reaches only its own route (socket and TCP); the session's own calls are not cut by that wall
GS() { setpriv --reuid=mila-guest --regid=mila-guest --clear-groups -- env -i PATH=/usr/local/bin:/usr/bin:/bin bash -c "$1" 2>&1; }
chk "пользователь полосы по TCP: подписка владельца и бот — 403" "[ \"\$(GS 'curl -s -o /dev/null -w %{http_code} -X POST http://127.0.0.1:8790/anthropic/v1/messages')\" = 403 ] && [ \"\$(GS 'curl -s -o /dev/null -w %{http_code} -X POST http://127.0.0.1:8790/telegram/bot1:x/sendMessage')\" = 403 ]"
chk "сессия по TCP при существующем пользователе полосы — свои маршруты не 403 (стена не режет своих)" "[ \"\$(AS 'curl -s -o /dev/null -w %{http_code} --max-time 20 -X POST http://127.0.0.1:8790/telegram/bot1:x/getMe')\" != 403 ] && [ \"\$(AS 'curl -s -o /dev/null -w %{http_code} --max-time 20 -X POST http://127.0.0.1:8790/anthropic/v1/messages')\" != 403 ]"
mkdir -p /run/mila-lane/knowledge; chown mila-guest:mila-guest /run/mila-lane; chmod 2750 /run/mila-lane
setpriv --reuid=mila-guest --regid=mila-guest --clear-groups -- python3 /usr/local/bin/mila_lane.py serve --sock /run/mila-lane/lane.sock --knowledge /run/mila-lane/knowledge >/dev/null 2>&1 &
LP=$!; for _ in $(seq 1 30); do [ -S /run/mila-lane/lane.sock ] && break; sleep 0.2; done
# the socket checks: the connecting code is a file (an inline string inside chk's eval and AS's bash -c never reached python —
# both lines checked nothing). The session must get PermissionError; the receiver's user — an answer (the positive control).
cat > /tmp/sock_try.py <<'PY'
import socket, sys
try:
    s = socket.socket(socket.AF_UNIX); s.settimeout(5); s.connect(sys.argv[1]); s.sendall(sys.argv[2].encode() + b"\n"); print(s.recv(300).decode())
except OSError as e:
    print(type(e).__name__)
PY
chmod 644 /tmp/sock_try.py
as_agent() { AS "python3 /tmp/sock_try.py $1 '$2'"; }
as_io() { setpriv --reuid=mila-io --regid=mila-io --init-groups -- python3 /tmp/sock_try.py "$1" "$2" 2>&1; }
chk "сокет полосы: сессия (agent) — PermissionError" "as_agent /run/mila-lane/lane.sock '{}' | grep -q PermissionError"
chk "сокет полосы: приёмник (mila-io) подключается и получает ответ" "as_io /run/mila-lane/lane.sock '{}' | grep -q empty"
kill $LP 2>/dev/null
# the consent proxy: the session asks on consent.sock, only the receiver's user reaches consent.io.sock (the owner's presses)
CS=/tmp/wall-consent; mkdir -p "$CS/state"; chown -R mila-io:agent "$CS"; chmod 2750 "$CS"
printf '{"owner_id_env":"MILA_OWNER_ID","home":"/home/agent","state_dir":"%s/state","session_socket":"%s/c.sock","session_socket_mode":"660","io_socket":"%s/io.sock","categories":{}}' "$CS" "$CS" "$CS" > "$CS/cfg.json"
setpriv --reuid=mila-io --regid=mila-io --groups=agent -- env MILA_OWNER_ID=1 python3 /opt/mila/kit/consent/consent_proxy.py serve --config "$CS/cfg.json" >/dev/null 2>&1 &
CP=$!; for _ in $(seq 1 30); do [ -S "$CS/io.sock" ] && [ -S "$CS/c.sock" ] && break; sleep 0.2; done
chk "посредник согласий: сессия просит через consent.sock" "as_agent $CS/c.sock '{\"op\": \"x\"}' | grep -q status"
chk "посредник согласий: io-сокет — сессии PermissionError, приёмнику ответ" "as_agent $CS/io.sock '{}' | grep -q PermissionError && as_io $CS/io.sock '{}' | grep -q status"
kill $CP 2>/dev/null
# outgoing messages for the archive: the keeper's spool folder — the receiver's user reads it, the session's does not
chk "спул исходящих: папка хранителя для архива — приёмнику читается, сессии нет" "[ -d /run/mila-keyd/out ] && setpriv --reuid=mila-io --regid=mila-io --init-groups -- ls /run/mila-keyd/out >/dev/null && AS 'ls /run/mila-keyd/out' 2>&1 | grep -q 'Permission denied'"
echo "итог $ok/$n"; [ $ok -eq $n ]
