#!/usr/bin/env bash
# Mila Agent files without Docker: compose parses and has no secrets or ports; Dockerfile copies paths that exist;
# entrypoint waits with a clear line (not a crash loop) when a variable is missing or wrong.
cd "$(dirname "$0")/.." || exit 1
ok=0; n=0
chk() { n=$((n+1)); if eval "$2"; then ok=$((ok+1)); echo "✅ $1"; else echo "❌ $1"; fi; }
chk "помощник входа: тест поддельного Telegram и setup-token" "python3 docker/test_claude_login.py >/dev/null 2>&1"
chk "код рождения: тест поддельного relay и entrypoint" "python3 docker/test_birth_claim.py >/dev/null 2>&1"
chk "compose: один сервис mila, том mila-home, портов нет" "python3 -c \"import yaml;d=yaml.safe_load(open('docker-compose.yml'));s=d['services']['mila'];assert 'ports' not in s and 'mila-home:/home/agent' in s['volumes'][0]\""
chk "compose: переменные — только подстановкой \${…}, значений нет" "! grep -E '(TOKEN|KEY): [^\$ ]' docker-compose.yml"
chk "Dockerfile: install.sh и onboard.py, на которые опирается entrypoint, есть в репозитории" "[ -f install/install.sh ] && [ -f install/onboard.py ] && grep -q 'COPY docker/entrypoint.sh docker/healthcheck.sh' docker/Dockerfile"
chk "entrypoint и healthcheck — синтаксис bash" "bash -n docker/entrypoint.sh && bash -n docker/healthcheck.sh"
H=$(mktemp -d); PYDIR=$(dirname "$(command -v python3)"); run_ep() { env -i HOME="$H" PATH="$PYDIR:/usr/bin:/bin" MILA_KIT="$PWD" "$@" timeout 3 bash docker/entrypoint.sh 2>&1; }
o=$(run_ep); chk "нет TELEGRAM_BOT_TOKEN → ждёт со строкой про @BotFather (не падает)" "printf '%s' \"\$o\" | grep -q 'BotFather' && printf '%s' \"\$o\" | grep -q 'restart the container'"
o=$(run_ep TELEGRAM_BOT_TOKEN=abc); chk "токен не похож → строка «does not look like»" "printf '%s' \"\$o\" | grep -q 'does not look like'"
T="1234567"":""AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
o=$(run_ep TELEGRAM_BOT_TOKEN="$T" LOGIN_HELPER="$PWD/docker/claude_login.py" TG_API=http://127.0.0.1:9); chk "нет входа Claude → помощник входа ждёт /start в Telegram (не «ждёт вечно»)" "printf '%s' \"\$o\" | grep -q 'write /start to your bot' && printf '%s' \"\$o\" | grep -q 'waiting for /start'"
chk "…и до входа ничего не установлено и не записано (.env нет)" "[ ! -e \"$H/.claude/channels/telegram/.env\" ]"
o=$(run_ep TELEGRAM_BOT_TOKEN="$T" ANTHROPIC_API_KEY=x OWNER_ID=abc); chk "OWNER_ID не число → строка про numeric Telegram id" "printf '%s' \"\$o\" | grep -q 'numeric Telegram id'"
HC=$(mktemp -d); mkdir -p "$HC/state" "$HC/.claude/channels/telegram"; echo 0 > "$HC/state/session.pid"; echo 0 > "$HC/.claude/channels/telegram/receiver.pid"
chk "healthcheck: pid 0 — не «жив» (kill -0 0 бьёт по группе)" "! HOME=$HC bash docker/healthcheck.sh >/dev/null 2>&1"
rm -rf "$HC"
rm -rf "$H"
echo "итог $ok/$n"; [ $ok -eq $n ]
