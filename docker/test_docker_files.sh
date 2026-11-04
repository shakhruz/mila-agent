#!/usr/bin/env bash
# Mila Agent files without Docker: compose parses and has no secrets or ports; Dockerfile copies paths that exist;
# entrypoint waits with a clear line (not a crash loop) when a variable is missing or wrong.
cd "$(dirname "$0")/.." || exit 1
ok=0; n=0
chk() { n=$((n+1)); if eval "$2"; then ok=$((ok+1)); echo "✅ $1"; else echo "❌ $1"; fi; }
chk "помощник входа: тест поддельного Telegram и setup-token" "python3 docker/test_claude_login.py >/dev/null 2>&1"
chk "страница токена: тест поддельного Telegram" "python3 docker/test_token_page.py >/dev/null 2>&1"
chk "код рождения: тест поддельного relay и entrypoint" "python3 docker/test_birth_claim.py >/dev/null 2>&1"
chk "compose: один сервис mila, том mila-home, портов нет" "python3 -c \"import yaml;d=yaml.safe_load(open('docker-compose.yml'));s=d['services']['mila'];assert 'ports' not in s and 'mila-home:/home/agent' in s['volumes'][0]\""
chk "compose: переменные — только подстановкой \${…}, значений нет" "! grep -E '(TOKEN|KEY): [^\$ ]' docker-compose.yml"
chk "Dockerfile: install.sh и onboard.py, на которые опирается entrypoint, есть в репозитории" "[ -f install/install.sh ] && [ -f install/onboard.py ] && grep -q 'COPY docker/entrypoint.sh docker/healthcheck.sh' docker/Dockerfile"
chk "Dockerfile в корне = docker/Dockerfile (Railway и панели «из GitHub» ищут ./Dockerfile)" "cmp -s Dockerfile docker/Dockerfile"
chk "в Dockerfile нет VOLUME (Railway такой не собирает) и нет USER (entrypoint сам переходит в agent)" "! grep -qE '^(VOLUME|USER)' docker/Dockerfile"
chk "railway.json: сборка по Dockerfile, перезапуск при сбое" "python3 -c \"import json;d=json.load(open('railway.json'));assert d['build']['builder']=='DOCKERFILE' and d['deploy']['restartPolicyType']=='ON_FAILURE'\""
chk "entrypoint и healthcheck — синтаксис bash" "bash -n docker/entrypoint.sh && bash -n docker/healthcheck.sh"
H=$(mktemp -d); PYDIR=$(dirname "$(command -v python3)"); run_ep() { env -i HOME="$H" PATH="$PYDIR:/usr/bin:/bin" MILA_KIT="$PWD" "$@" timeout 3 bash docker/entrypoint.sh 2>&1; }
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
chmod +x "$SB"/*; env -i HOME="$HR" PATH="$SB:/usr/bin:/bin" timeout 3 bash docker/entrypoint.sh >/dev/null 2>&1
chk "запуск от root: дом отдаётся agent (chown -R -h 1001), затем тот же скрипт под 1001 через setpriv" "grep -q 'chown -R -h 1001:1001 $HR' $SB/log && grep -q 'setpriv --reuid=1001 --regid=1001 --init-groups -- bash docker/entrypoint.sh' $SB/log"
printf '#!/bin/sh\necho 1001\n' > "$SB/stat"; : > "$SB/log"; env -i HOME="$HR" PATH="$SB:/usr/bin:/bin" timeout 3 bash docker/entrypoint.sh >/dev/null 2>&1
chk "дом уже agent — chown не нужен, только setpriv" "! grep -q chown $SB/log && grep -q setpriv $SB/log"
rm -rf "$SB" "$HR"
HC=$(mktemp -d); mkdir -p "$HC/state" "$HC/.claude/channels/telegram"; echo 0 > "$HC/state/session.pid"; echo 0 > "$HC/.claude/channels/telegram/receiver.pid"
chk "healthcheck: pid 0 — не «жив» (kill -0 0 бьёт по группе)" "! HOME=$HC bash docker/healthcheck.sh >/dev/null 2>&1"
rm -rf "$HC"
rm -rf "$H"
echo "итог $ok/$n"; [ $ok -eq $n ]
