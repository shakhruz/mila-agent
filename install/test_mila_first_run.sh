#!/bin/bash
# A born Mila lives in the background: plain `mila` shows how she is and opens no session in the folder it was typed in.
# `mila open` is the session in a terminal, in HER home folder: no conversation there yet → a new one, not --continue (Claude
# Code quits on --continue with nothing to resume); once a conversation exists → --continue. Not born → the birth page.
# bash install/test_mila_first_run.sh
set -u; unset TELEGRAM_STATE_DIR; H="$(cd "$(dirname "$0")" && pwd)"; T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
ok=0; n=0; chk(){ n=$((n+1)); if eval "$2" >/dev/null 2>&1; then ok=$((ok+1)); echo "✅ $1"; else echo "❌ $1"; fi; }
mkdir -p "$T/bin" "$T/home/work" "$T/proj"
printf '#!/bin/sh\necho "ARGS: $*"; echo "CWD: $PWD"\n' > "$T/bin/claude"; printf '#!/bin/sh\nexit 0\n' > "$T/bin/pgrep"; chmod +x "$T/bin/claude" "$T/bin/pgrep"
# Mila is born in these checks: the launcher decides it from files on the machine (a saved bot token together with access.json,
# or a birth record), never from the network; the birth page has its own checks below
ST="$T/home/.claude/channels/telegram"; mkdir -p "$T/home/.claude/hooks" "$ST" "$T/cfg"; : > "$ST/.env"; echo '{}' > "$ST/access.json"
echo '{"env":{"OWNER_ID":"1"}}' > "$T/home/.claude/settings.json"; cp "$T/home/.claude/settings.json" "$T/cfg/settings.json"
P="$(cd "$T/home/work" && pwd -P)"; SLUG="$(printf '%s' "$P" | sed 's/[^A-Za-z0-9]/-/g')"
run(){ (cd "$T/proj" && env -u CLAUDE_CONFIG_DIR HOME="$T/home" PATH="$T/bin:$PATH" "$@" bash "$H/mila" 2>&1); }
open_(){ (cd "$T/proj" && env -u CLAUDE_CONFIG_DIR HOME="$T/home" PATH="$T/bin:$PATH" "$@" bash "$H/mila" open 2>&1); }
O1="$(open_)"
chk "mila open, свежий дом: сеанс без --continue и в доме Милы, а не в папке, где набрали команду" "printf '%s' \"\$O1\" | grep 'ARGS:' | grep -vq -- '--continue' && printf '%s' \"\$O1\" | grep -q \"CWD: $P\$\""
mkdir -p "$T/home/.claude/projects/$SLUG"; echo '{}' > "$T/home/.claude/projects/$SLUG/s1.jsonl"
O2="$(open_)"
chk "mila open: в доме Милы уже есть разговор — --continue" "printf '%s' \"\$O2\" | grep 'ARGS:' | grep -q -- '--continue'"
mkdir -p "$T/cfg/projects"; O3="$(cd "$T/proj" && HOME="$T/home" CLAUDE_CONFIG_DIR="$T/cfg" PATH="$T/bin:$PATH" bash "$H/mila" open 2>&1)"
chk "CLAUDE_CONFIG_DIR учитывается: там пусто — новый разговор" "printf '%s' \"\$O3\" | grep 'ARGS:' | grep -vq -- '--continue'"
O4="$(cd "$T/proj" && env -u CLAUDE_CONFIG_DIR HOME="$T/home" PATH="$T/bin:$PATH" bash "$H/mila" new 2>&1)"
chk "mila new — всегда без --continue" "printf '%s' \"\$O4\" | grep 'ARGS:' | grep -vq -- '--continue'"
# a failing online check (no network, expired sign-in) must not matter: the stub of onboard.py fails from here on
printf 'import sys\nsys.exit(1)\n' > "$T/home/.claude/hooks/onboard.py"; printf 'print("BIRTH PAGE STARTED")\n' > "$T/home/.claude/hooks/birth.py"
O8="$(run)"
chk "рождена (ключ бота и access.json на месте), проверка в сети падает — простое mila показывает, как она: не страница рождения и не сеанс в текущей папке" "printf '%s' \"\$O8\" | grep -q 'Mila in the background' && ! printf '%s' \"\$O8\" | grep -q 'BIRTH' && ! printf '%s' \"\$O8\" | grep -q 'ARGS:'"
echo '{}' > "$T/home/.claude/settings.json"
O11="$(run)"
chk "ключ бота и access.json есть, а хозяина в settings.json нет (чужой канал Telegram в Claude Code) — страница рождения" "printf '%s' \"\$O11\" | grep -q 'BIRTH PAGE STARTED' && ! printf '%s' \"\$O11\" | grep -q 'ARGS:'"
echo '{"env":{"OWNER_ID":"1"}}' > "$T/home/.claude/settings.json"; mkdir -p "$T/other"; cp "$ST/.env" "$ST/access.json" "$T/other/"; mv "$ST/.env" "$ST/.env.off"
O12="$(run TELEGRAM_STATE_DIR="$T/other")"
chk "папка канала другой Милы в окружении (TELEGRAM_STATE_DIR вне своего дома) — страница рождения, не сессия" "printf '%s' \"\$O12\" | grep -q 'BIRTH PAGE STARTED' && ! printf '%s' \"\$O12\" | grep -q 'ARGS:'"
mv "$ST/.env.off" "$ST/.env"; echo '{}' > "$T/home/.claude/settings.json"
rm -f "$ST/.env" "$ST/access.json"; echo '{"born_at":"2026-01-01T00:00:00+00:00"}' > "$T/home/.claude/mila-birth.json"
O9="$(run)"
chk "рождена по записи о рождении — простое mila показывает, как она: не страница и не сеанс" "printf '%s' \"\$O9\" | grep -q 'Mila in the background' && ! printf '%s' \"\$O9\" | grep -q 'BIRTH' && ! printf '%s' \"\$O9\" | grep -q 'ARGS:'"
rm -f "$T/home/.claude/mila-birth.json"
O5="$(run)"
chk "не рождена (нет записи о рождении, нет ключа бота): простое mila запускает страницу рождения, а не сессию" "printf '%s' \"\$O5\" | grep -q 'BIRTH PAGE STARTED' && ! printf '%s' \"\$O5\" | grep -q 'ARGS:'"
: > "$ST/.env"
O10="$(run)"
chk "ключ сохранён, но пара не пройдена (нет access.json) — снова страница рождения" "printf '%s' \"\$O10\" | grep -q 'BIRTH PAGE STARTED'"
O6="$(cd "$T/proj" && env -u CLAUDE_CONFIG_DIR HOME="$T/home" PATH="$T/bin:$PATH" bash "$H/mila" birth 2>&1)"
chk "mila birth — страница рождения" "printf '%s' \"\$O6\" | grep -q 'BIRTH PAGE STARTED'"
O7="$(cd "$T/proj" && env -u CLAUDE_CONFIG_DIR HOME="$T/home" PATH="$T/bin:$PATH" bash "$H/mila" new 2>&1)"
chk "mila new не трогает страницу рождения" "printf '%s' \"\$O7\" | grep -q 'ARGS:' && ! printf '%s' \"\$O7\" | grep -q 'BIRTH'"
echo "итог $ok/$n"; [ $ok -eq $n ]
