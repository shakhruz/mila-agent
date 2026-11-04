#!/usr/bin/env bash
# No «Surprise me» button or branch anywhere — core, templates, image, packs; no step-list / reserve leftovers in onboarding.
set -u; cd "$(dirname "$0")/.." || exit 1; ok=0; n=0
chk() { n=$((n+1)); if eval "$2"; then ok=$((ok+1)); echo "✅ $1"; else echo "❌ $1"; fi; }
W='Удиви|Surprise me|surprise me|"wow"|`wow`|🎁|Hayratlan|Ajablantir|惊喜|驚喜'
chk "нет «Удиви меня» / «Surprise me» / choice wow / 🎁 в навыках, шаблонах, docker, install и паках" "! git grep -n -E '$W' -- skills templates docker install packs >/dev/null"
chk "знакомство без строки ⛽, fuel.sh и «Мы здесь»" "! grep -qE '⛽|fuel\.sh|We are here|Мы здесь' skills/onboarding/SKILL.md"
echo "итог $ok/$n"; [ $ok -eq $n ]
