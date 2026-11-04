#!/usr/bin/env bash
# Дом новорождённой: install.sh кладёт ~/work/CLAUDE.md (знакомство, а не «Чем могу помочь?»), USER.md и конституцию в canon/,
# только если их нет; своё у хозяина не перезаписывает. Песочница: свой HOME.
set -u; REPO="$(cd "$(dirname "$0")/.." && pwd)"; T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT; mkdir -p "$T/home"
ok=0; n=0; chk() { n=$((n+1)); if eval "$2"; then ok=$((ok+1)); echo "✅ $1"; else echo "❌ $1"; fi; }
inst() { HOME="$T/home" CLAUDE_CONFIG_DIR="$T/home/.claude" MILA_CC_VERSION=2.1.310 PATH=/usr/bin:/bin:/usr/local/bin bash "$REPO/install/install.sh" >/dev/null 2>&1; }
inst; W="$T/home/work"
chk "CLAUDE.md в ~/work есть" "[ -f $W/CLAUDE.md ]"
chk "в нём знакомство через onboarding, не «How can I help»: правило и запрет" "grep -q 'onboarding' $W/CLAUDE.md && grep -q 'знакомство: пройдено' $W/CLAUDE.md && grep -q 'Never a bare' $W/CLAUDE.md"
chk "конституция подключена (@canon/CONSTITUTION.en.md) и лежит рядом" "grep -q '@canon/CONSTITUTION.en.md' $W/CLAUDE.md && [ -f $W/canon/CONSTITUTION.en.md ] && [ -f $W/canon/CONSTITUTION.md ]"
chk "USER.md — паспорт хозяина" "grep -q 'Name:' $W/USER.md"
echo "мой собственный" > "$W/CLAUDE.md"; echo "Имя: Иван" > "$W/USER.md"; inst
chk "повторная установка не трогает CLAUDE.md и USER.md хозяина" "grep -q 'мой собственный' $W/CLAUDE.md && grep -q 'Иван' $W/USER.md"
echo "итог $ok/$n"; [ $ok -eq $n ]
