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
echo "итог $ok/$n"; [ $ok -eq $n ]
