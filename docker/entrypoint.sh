#!/usr/bin/env bash
# Mila Agent entrypoint — the MILAGPT fleet's companion-run.sh, adapted for a stranger's server:
# receiver daemon (keeps the bot online, writes the journal) · feeder (journal → session stdin) ·
# Claude Code session in tmux «mila» (`claude -p --input-format stream-json`, stdin = FIFO, the plugin's channel).
# Needs: TELEGRAM_BOT_TOKEN; the owner's own Claude login — CLAUDE_CODE_OAUTH_TOKEN (`claude setup-token` on your computer,
# your subscription) or ANTHROPIC_API_KEY. OWNER_ID (your Telegram id) is optional: without it a pairing code goes to the log.
# OPENROUTER_API_KEY — optional, cheap tasks on open models. Nothing secret is printed.
set -u
# Root only for one step: the home volume to agent (Railway mounts volumes as root), then the same script as agent.
if [ "$(id -u)" = 0 ]; then
  AU="${MILA_AGENT_UID:-1001}"
  [ "$(stat -c %u "$HOME" 2>/dev/null)" = "$AU" ] || chown -R -h "$AU:$AU" "$HOME"
  exec setpriv --reuid="$AU" --regid="$AU" --init-groups -- bash "$0" "$@"
fi
H="$HOME"; ST=$H/state; CL=$H/.claude
TG=$CL/channels/telegram            # the plugin's real state: .env, access.json, receiver journal
TGS=$CL/channels/telegram-session   # the session's bridge: same token, EMPTY journal (the feeder delivers)
PLUG=/opt/mila/plugin/mila-telegram; MK=mila-local; FIFO=$ST/session.in
log() { printf '%s mila-agent: %s\n' "$(date +%FT%T)" "$*"; }
wait_forever() { log "$1"; log "Fix the variable in your Docker settings and restart the container."; exec sleep infinity; }

AUTH="$H/.mila-auth"
# No token anywhere and the platform gave a port (Railway, panels with a public address): one-field page, once.
if [ -z "${TELEGRAM_BOT_TOKEN:-}" ] && [ ! -s "$AUTH/bot_token" ] && [ -z "${BIRTH_CODE:-}" ] && [ -n "${PORT:-}" ] && [ ! -e "$AUTH/token_page.done" ]; then
  MILA_AUTH_DIR="$AUTH" python3 "${TOKEN_PAGE:-/usr/local/bin/token_page.py}" | while IFS= read -r l; do log "$l"; done
  [ -s "$AUTH/bot_token" ] || wait_forever "The token page closed without a token (time or attempts ran out) — restart the service to open it again."
fi
# Bot token: the variable, or the one fetched earlier by a birth code (volume, 600), or now by BIRTH_CODE — once, from our relay.
if [ -z "${TELEGRAM_BOT_TOKEN:-}" ] && [ ! -s "$AUTH/bot_token" ] && [ -n "${BIRTH_CODE:-}" ]; then
  MILA_AUTH_DIR="$AUTH" python3 "${BIRTH_HELPER:-/usr/local/bin/birth_claim.py}" | while IFS= read -r l; do log "$l"; done
fi
if [ -z "${TELEGRAM_BOT_TOKEN:-}" ] && [ -s "$AUTH/bot_token" ]; then TELEGRAM_BOT_TOKEN="$(head -n1 "$AUTH/bot_token")"; export TELEGRAM_BOT_TOKEN; fi
[ -n "${TELEGRAM_BOT_TOKEN:-}" ] || wait_forever "No bot yet: set BIRTH_CODE (a one-time code from the MILAGPT bot) or TELEGRAM_BOT_TOKEN (from @BotFather)."
[[ "${TELEGRAM_BOT_TOKEN}" =~ ^[0-9]{5,}:[A-Za-z0-9_-]{30,}$ ]] || wait_forever "TELEGRAM_BOT_TOKEN does not look like a bot token (digits:letters)."
# Claude login: a variable, or the one saved by an earlier sign-in from Telegram (volume, 600). None — sign in from the chat:
# the helper answers /start with Anthropic's own sign-in link and takes the code back in the chat (no ports, no page).
load_auth() {
  if [ -z "${CLAUDE_CODE_OAUTH_TOKEN:-}${ANTHROPIC_API_KEY:-}" ] && [ -s "$AUTH/oauth_token" ]; then
    CLAUDE_CODE_OAUTH_TOKEN="$(head -n1 "$AUTH/oauth_token")"; export CLAUDE_CODE_OAUTH_TOKEN
  fi
  if [ -z "${OWNER_ID:-}" ] && [ -s "$AUTH/owner_id" ]; then OWNER_ID="$(head -n1 "$AUTH/owner_id")"; export OWNER_ID; fi
}
load_auth
if [ -z "${CLAUDE_CODE_OAUTH_TOKEN:-}${ANTHROPIC_API_KEY:-}" ]; then
  log "no Claude login yet — write /start to your bot in Telegram: it sends the sign-in button (your own Claude account)"
  until MILA_AUTH_DIR="$AUTH" python3 "${LOGIN_HELPER:-/usr/local/bin/claude_login.py}"; do log "sign-in helper stopped — restarting in 10 s"; sleep 10; done
  load_auth
fi
[ -n "${CLAUDE_CODE_OAUTH_TOKEN:-}${ANTHROPIC_API_KEY:-}" ] || wait_forever "No Claude login after sign-in — write /login to the bot and try again."
[ -z "${OWNER_ID:-}" ] || [[ "$OWNER_ID" =~ ^[0-9]{3,15}$ ]] || wait_forever "OWNER_ID must be your numeric Telegram id (or leave it empty for a pairing code)."

umask 077
mkdir -p "$ST" "$CL" "$TG/inbound" "$TGS/inbound" "$H/work" "$H/.local/bin"
for d in "$CL" "$TG" "$TG/inbound" "$TGS" "$TGS/inbound"; do chmod 700 "$d"; done   # not 700 → the plugin silently does not poll
export PATH="$H/.local/bin:$PATH"

# First start: the kit (skills, hooks, launcher) into the home volume; Claude Code onboarding answered once.
if [ ! -e "$CL/.mila-agent-installed" ]; then
  log "first start: installing the Mila kit"
  bash "$MILA_KIT/install/install.sh" >> "$ST/install.log" 2>&1 || wait_forever "kit install failed — see $ST/install.log"
  touch "$CL/.mila-agent-installed"
fi
# A home born before the newborn's CLAUDE.md existed gets it on the next start (add-only: the owner's own files stay)
mkdir -p "$H/work/canon"
for f in CLAUDE.md USER.md; do [ -e "$H/work/$f" ] || cp "$MILA_KIT/templates/work/$f" "$H/work/$f"; done
for f in CONSTITUTION.md CONSTITUTION.en.md; do [ -e "$H/work/canon/$f" ] || cp "$MILA_KIT/$f" "$H/work/canon/$f"; done
[ -s "$H/.claude.json" ] || printf '{"hasCompletedOnboarding":true}\n' > "$H/.claude.json"
[ -s "$CL/.claude.json" ] || printf '{"hasCompletedOnboarding":true}\n' > "$CL/.claude.json"
[ -s "$CL/settings.json" ] || printf '{"skipDangerousModePermissionPrompt":true}\n' > "$CL/settings.json"

# Token — in the plugin's .env on every start (changing the variable is enough).
printf 'TELEGRAM_BOT_TOKEN=%s\n' "$TELEGRAM_BOT_TOKEN" > "$TG/.env"; cp "$TG/.env" "$TGS/.env"

# Owner: OWNER_ID → access.json directly; otherwise a pairing code in the log (mila onboard, step 3).
if [ ! -s "$TG/access.json" ] && [ -n "${OWNER_ID:-}" ]; then
  printf '{"dmPolicy":"allowlist","allowFrom":["%s"],"groups":{},"ackReaction":"👀","replyToMode":"first","textChunkLimit":4096,"chunkMode":"newline"}\n' "$OWNER_ID" > "$TG/access.json"
fi
if [ ! -s "$TG/access.json" ]; then
  log "pairing: send the 6-character code below to your bot in Telegram (5 minutes)"
  MILA_CLAUDE=true python3 "$MILA_KIT/install/onboard.py" </dev/null || log "pairing not finished — restart the container to get a new code"
fi
ln -sfn ../telegram/access.json "$TGS/access.json"; ln -sfn ../telegram/receiver.pid "$TGS/receiver.pid"

PIDS=()
cleanup() { log "stop"; tmux kill-server 2>/dev/null; kill "${PIDS[@]}" 2>/dev/null; exit 0; }
trap cleanup TERM INT
# 1. receiver daemon
# voice: the receiver runs our script for every voice note (Groq key: GROQ_API_KEY or ~/work/secrets/groq.env, see key_page.py)
( while :; do RECEIVER_DAEMON=1 TELEGRAM_STATE_DIR="$TG" TELEGRAM_VOICE_TRANSCRIBE_CMD="${TELEGRAM_VOICE_TRANSCRIBE_CMD:-$MILA_KIT/install/transcribe-voice.sh}" bun "$PLUG/receiver.ts" >> "$ST/receiver.log" 2>&1; sleep 5; done ) & PIDS+=($!)
# 2. feeder: journal → session stdin
( while :; do TELEGRAM_STATE_DIR="$TG" COMPANION_STATE="$ST" COMPANION_FIFO="$FIFO" python3 "$MILA_KIT/install/companion-feeder.py" >> "$ST/feeder.err" 2>&1; sleep 3; done ) & PIDS+=($!)
# 3. the session in tmux «mila». The plugin is not on Anthropic's channel list yet, so it loads with the development-channels flag,
#    like the `mila` launcher. Permissions are NOT asked in the container: the boundary is the container itself (docs/THREAT-MODEL.md).
cat > "$ST/session-loop.sh" <<LOOP
#!/usr/bin/env bash
cd "$H/work" || exit 1
while :; do
  rm -f "$FIFO"; mkfifo -m 600 "$FIFO"; exec 3<>"$FIFO"
  if ! claude plugin list 2>/dev/null | grep -q "mila-telegram@$MK"; then
    claude plugin marketplace add /opt/mila/marketplace >> "$ST/session.log" 2>&1
    claude plugin install "mila-telegram@$MK" >> "$ST/session.log" 2>&1
  fi
  TELEGRAM_STATE_DIR="$TGS" claude -p --input-format stream-json --output-format stream-json --verbose \\
    --dangerously-load-development-channels "plugin:mila-telegram@$MK" --dangerously-skip-permissions <&3 >> "$ST/session.jsonl" 2>> "$ST/session.err" &
  echo \$! > "$ST/session.pid"; wait \$!; exec 3>&-; rm -f "$ST/session.pid"
  echo "\$(date +%FT%T) session ended — restarting in 10 s" >> "$ST/session.log"; sleep 10
done
LOOP
chmod 700 "$ST/session-loop.sh"
tmux new-session -d -s mila "bash $ST/session-loop.sh" || log "tmux did not start"
log "running: receiver + feeder + Claude Code session (tmux «mila»). Logs: $ST/"
while :; do sleep 30 & wait $!; done
