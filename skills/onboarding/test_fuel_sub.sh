#!/bin/bash
# fuel.sh: подписка Mila Agent (токен setup-token в env или ~/.mila-auth) — «sub», не «пробный запас»; API-ключ Anthropic — «key».
set -u; H="$(cd "$(dirname "$0")" && pwd)"; T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
ok=0; n=0; chk(){ n=$((n+1)); if eval "$2"; then ok=$((ok+1)); echo "✅ $1"; else echo "❌ $1  ← $o"; fi; }
run(){ env -i HOME="$T" PATH="/usr/bin:/bin" CLAUDE_CONFIG_DIR="$T/.claude" "$@" sh "$H/fuel.sh" 2>&1; }
o=$(run CLAUDE_CODE_OAUTH_TOKEN=x); chk "токен подписки в env → FUEL sub" 'echo "$o" | grep -q "^FUEL sub"'
mkdir -p "$T/.mila-auth"; echo t > "$T/.mila-auth/oauth_token"; o=$(run); chk "токен в ~/.mila-auth/oauth_token → FUEL sub" 'echo "$o" | grep -q "^FUEL sub"'
rm -rf "$T/.mila-auth"; o=$(run ANTHROPIC_API_KEY=x); chk "API-ключ Anthropic → FUEL key" 'echo "$o" | grep -q "^FUEL key"'
o=$(run CLAUDE_CODE_OAUTH_TOKEN=x ANTHROPIC_BASE_URL=https://openrouter.ai/api); chk "через OpenRouter (BASE_URL) — не sub" '! echo "$o" | grep -q "^FUEL sub"'
o=$(run); chk "ничего нет → FUEL unknown" 'echo "$o" | grep -q "^FUEL unknown"'
echo "итог $ok/$n"; [ $ok -eq $n ]
