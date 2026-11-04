#!/usr/bin/env bash
# Знакомство без кнопки и сценария «Удиви меня» — ни на одном языке, ни в навыках, ни в шаблонах, ни в образе.
# Разбор д2 (одна находка, один шаг) остаётся — без Instagram (Мила его не открывает).
set -u; cd "$(dirname "$0")/../.." || exit 1; ok=0; n=0
chk() { n=$((n+1)); if eval "$2"; then ok=$((ok+1)); echo "✅ $1"; else echo "❌ $1"; fi; }
W='Удиви|Surprise me|surprise me|"wow"|`wow`|🎁|Hayratlan|Ajablantir|惊喜|驚喜'
chk "нет «Удиви меня» / «Surprise me» / choice wow / 🎁 в навыках, шаблонах, docker и install" "! git grep -n -E '$W' -- skills templates docker install packs ':(exclude)skills/onboarding/test_no_surprise.sh' >/dev/null"
chk "разбор д2 на месте (en, ru) и без Instagram" "grep -q 'д2 · The analysis' skills/onboarding/SKILL.md && grep -q 'д2 · Разбор' skills/onboarding/SKILL.ru.md && ! grep -n 'д2 ·' -A1 skills/onboarding/SKILL.md skills/onboarding/SKILL.ru.md | grep -q Instagram"
echo "итог $ok/$n"; [ $ok -eq $n ]
