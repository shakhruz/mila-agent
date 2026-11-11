#!/bin/bash
# mila on a fresh install: no conversation for this folder yet → a new one, not --continue (Claude Code quits on --continue
# with nothing to resume); once a conversation exists → --continue as before. bash install/test_mila_first_run.sh
set -u; H="$(cd "$(dirname "$0")" && pwd)"; T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
ok=0; n=0; chk(){ n=$((n+1)); if eval "$2" >/dev/null 2>&1; then ok=$((ok+1)); echo "✅ $1"; else echo "❌ $1"; fi; }
mkdir -p "$T/bin" "$T/home" "$T/proj"
printf '#!/bin/sh\necho "ARGS: $*"\n' > "$T/bin/claude"; printf '#!/bin/sh\nexit 0\n' > "$T/bin/pgrep"; chmod +x "$T/bin/claude" "$T/bin/pgrep"
# onboarding is complete in these checks (stub of the `onboard.py --check` the launcher asks); the birth page has its own checks below
mkdir -p "$T/home/.claude/hooks"; printf 'import sys\nsys.exit(0)\n' > "$T/home/.claude/hooks/onboard.py"
P="$(cd "$T/proj" && pwd -P)"; SLUG="$(printf '%s' "$P" | sed 's/[^A-Za-z0-9]/-/g')"
run(){ (cd "$T/proj" && env -u CLAUDE_CONFIG_DIR HOME="$T/home" PATH="$T/bin:$PATH" "$@" bash "$H/mila" 2>&1); }
O1="$(run)"
chk "свежий дом: без --continue, строка «first start»" "printf '%s' \"\$O1\" | grep -q 'first start' && printf '%s' \"\$O1\" | grep 'ARGS:' | grep -vq -- '--continue'"
mkdir -p "$T/home/.claude/projects/$SLUG"; echo '{}' > "$T/home/.claude/projects/$SLUG/s1.jsonl"
O2="$(run)"
chk "есть разговор этой папки — --continue, как раньше" "printf '%s' \"\$O2\" | grep 'ARGS:' | grep -q -- '--continue' && ! printf '%s' \"\$O2\" | grep -q 'first start'"
mkdir -p "$T/cfg/projects"; O3="$(cd "$T/proj" && HOME="$T/home" CLAUDE_CONFIG_DIR="$T/cfg" PATH="$T/bin:$PATH" bash "$H/mila" 2>&1)"
chk "CLAUDE_CONFIG_DIR учитывается: там пусто — новый разговор" "printf '%s' \"\$O3\" | grep 'ARGS:' | grep -vq -- '--continue'"
O4="$(cd "$T/proj" && env -u CLAUDE_CONFIG_DIR HOME="$T/home" PATH="$T/bin:$PATH" bash "$H/mila" new 2>&1)"
chk "mila new — всегда без --continue" "printf '%s' \"\$O4\" | grep 'ARGS:' | grep -vq -- '--continue'"
printf 'import sys\nsys.exit(1)\n' > "$T/home/.claude/hooks/onboard.py"; printf 'print("BIRTH PAGE STARTED")\n' > "$T/home/.claude/hooks/birth.py"
O5="$(run)"
chk "не рождена (onboard --check ≠ 0): простое mila запускает страницу рождения, а не сессию" "printf '%s' \"\$O5\" | grep -q 'BIRTH PAGE STARTED' && ! printf '%s' \"\$O5\" | grep -q 'ARGS:'"
O6="$(cd "$T/proj" && env -u CLAUDE_CONFIG_DIR HOME="$T/home" PATH="$T/bin:$PATH" bash "$H/mila" birth 2>&1)"
chk "mila birth — страница рождения" "printf '%s' \"\$O6\" | grep -q 'BIRTH PAGE STARTED'"
O7="$(cd "$T/proj" && env -u CLAUDE_CONFIG_DIR HOME="$T/home" PATH="$T/bin:$PATH" bash "$H/mila" new 2>&1)"
chk "mila new не трогает страницу рождения" "printf '%s' \"\$O7\" | grep -q 'ARGS:' && ! printf '%s' \"\$O7\" | grep -q 'BIRTH'"
echo "итог $ok/$n"; [ $ok -eq $n ]
