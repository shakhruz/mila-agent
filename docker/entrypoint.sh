#!/usr/bin/env bash
# Mila Agent entrypoint — the MILAGPT fleet's companion-run.sh, adapted for a stranger's server:
# receiver daemon (keeps the bot online, writes the journal) · feeder (journal → session stdin) ·
# Claude Code session in tmux «mila» (`claude -p --input-format stream-json`, stdin = FIFO, the plugin's channel).
# Needs: TELEGRAM_BOT_TOKEN; the owner's own Claude login — CLAUDE_CODE_OAUTH_TOKEN (`claude setup-token` on your computer,
# your subscription) or ANTHROPIC_API_KEY. OWNER_ID (your Telegram id) is optional: without it a pairing code goes to the log.
# Nothing secret is printed.
set -u
# Root only for one step: the home volume to agent (Railway mounts volumes as root), then the same script as agent.
if [ "$(id -u)" = 0 ]; then
  AU="${MILA_AGENT_UID:-1001}"
  # Layout B (docker/mila_state.py, audit 09.11): one volume at /var/lib/mila — home/ for the session, keys/ and io/ beside it,
  # the volume's root to root. First start after the update: an old volume that WAS the home moves into home/ (one rename at a
  # time, resumes after a crash; a clash refuses the start). Owners by descriptor — no chown -R over the home any more.
  ST_CMD="${MILA_STATE_CMD:-python3 -I /usr/local/bin/mila_state.py}"   # tests put a stub here, as KEYD_BIN for the keeper
  mkdir -p /run 2>/dev/null; SJ="${MILA_STATE_JSON:-/run/mila-state.json}"
  ( cd / && $ST_CMD prepare --agent-uid "$AU" ) > "$SJ" 2> >(sed 's/^/mila-agent: /' >&2) \
    || { echo "mila-agent: the state folders are not safe to use — see the line above; not starting"; exit 1; }
  grep -q '"persistent": true' "$SJ" || echo "mila-agent: keys and io are NOT on a volume (mount it at /var/lib/mila) — the sign-in will be lost at the next redeploy" >&2
  # The key keeper (mila_keyd.py): the Claude token and the voice keys move to its own user (/var/lib/mila/keys, 700 — outside the home the session owns) — variables and
  # files of earlier starts included; the session gets only the keeper's address and can use a key, not read it.
  # MILA_KEYD=off keeps the old way (keys readable by the session, see SECURITY.md).
  if [ "${MILA_KEYD:-on}" != off ] && python3 "${KEYD_BIN:-/usr/local/bin/mila_keyd.py}" boot --home "$HOME" --agent-uid "$AU" 2>&1 | sed 's/^/mila-agent: /'; [ "${PIPESTATUS[0]}" = 0 ]; then
    export MILA_KEYD=http://127.0.0.1:8790 KEYD_SOCK=/run/mila-keyd/put.sock
    unset CLAUDE_CODE_OAUTH_TOKEN ANTHROPIC_API_KEY DEEPGRAM_API_KEY GROQ_API_KEY ANTHROPIC_GUEST_API_KEY
    curl -s --max-time 5 http://127.0.0.1:8790/status | grep -q '"telegram": true' && unset TELEGRAM_BOT_TOKEN
  else
    unset MILA_KEYD KEYD_SOCK
  fi
  # The receiver as its own OS user (mila-io, a member of the session's group): it writes the journals into io/ — inbound,
  # presses, authorizations — which the session reads and cannot write; the rest of the Telegram state is shared by group.
  # It starts when the session's side says go (after the token page, pairing and the Claude sign-in, which read updates
  # themselves); from then on the key keeper gives updates to mila-io only. Needs the keeper; MILA_IO=off — the old way.
  if [ -n "${MILA_KEYD:-}" ] && [ "${MILA_IO:-on}" != off ] && id -u mila-io >/dev/null 2>&1; then
    TGd="$HOME/.claude/channels/telegram"; IOD="$TGd/io"
    # root changes owners and rights here at every start: none of these may be a link the session put between starts
    for d in "$HOME/.claude" "$HOME/.claude/channels" "$TGd" "$TGd/inbound" "$IOD" "$IOD/consent"; do
      [ -L "$d" ] && { echo "mila-agent: $d is a link — refusing to start (root would follow it out of the home)"; exit 1; }
    done
    mkdir -p "$TGd/inbound" "$IOD" /run/mila-io
    chown "$AU:$AU" "$HOME/.claude" "$HOME/.claude/channels" "$TGd" "$TGd/inbound"
    chmod 2770 "$TGd" "$TGd/inbound"; rm -f "$TGd/receiver.go"   # group rights for the shared state — io_perms.py below, not chmod -R
    chmod 750 "$HOME" "$HOME/.claude" "$HOME/.claude/channels"
    chown mila-io:"$AU" "$IOD" /run/mila-io; chmod 2750 "$IOD"; chmod 2755 /run/mila-io   # setgid: sockets there belong to the session's group
    UPGRADED=; [ -s "$TGd/inbound/events.jsonl" ] && [ ! -L "$TGd/inbound/events.jsonl" ] && UPGRADED=1   # a home from before mila-io
    # …or any home where a session has already run (its transcripts), even if the receiver never kept a journal there
    [ -n "$(find "$HOME/.claude/projects" -name '*.jsonl' -print -quit 2>/dev/null)" ] && UPGRADED=1
    for p in inbound/events.jsonl taps.jsonl auth-log.jsonl suspicious.jsonl; do   # journals of earlier starts move in once
      b="${p##*/}"
      if [ -f "$TGd/$p" ] && [ ! -L "$TGd/$p" ]; then cat "$TGd/$p" >> "$IOD/$b"; rm -f "$TGd/$p"; fi
      touch "$IOD/$b"; chown mila-io:"$AU" "$IOD/$b"; chmod 640 "$IOD/$b"
      ln -sfn "$IOD/$b" "$TGd/$p"
    done
    touch "$TGd/cards.jsonl"; chown "$AU:$AU" "$TGd/cards.jsonl"; chmod 660 "$TGd/cards.jsonl"
    # Who is an owner: the receiver's own list. From the platform's OWNER_ID / OWNERS (the owner set it; the session cannot),
    # otherwise written once by the receiver at the first «go» (before the session ever ran). Never from access.json.
    if [ -n "${OWNERS:-}${OWNER_ID:-}" ]; then
      python3 -c 'import json, re, sys; json.dump({"owners": [x for x in re.split(r"[ ,;]+", sys.argv[1]) if x.isdigit()]}, open(sys.argv[2], "w"))' \
        "${OWNERS:-$OWNER_ID}" "$IOD/owners.json" && chown mila-io:"$AU" "$IOD/owners.json" && chmod 640 "$IOD/owners.json"
      rm -f "$IOD/owners.pending"
    elif [ ! -s "$IOD/owners.json" ] && [ -n "$UPGRADED" ]; then
      # An updated home: the session has run here before and could have changed the files the sign-in left. The owner is
      # taken only from the platform then — until OWNER_ID is set, nobody counts as the owner for presses and group decisions.
      touch "$IOD/owners.pending"; chown mila-io:"$AU" "$IOD/owners.pending"
      echo "mila-agent: set OWNER_ID (your Telegram id) in the platform's variables and restart — until then owner-only buttons do not work"
    fi
    # The strangers' lane (mila-guest): answers strangers who address the bot, with no tools, on the strangers' key (an
    # Anthropic API key with the keeper). No such key — no lane, and strangers in groups get no answer. What it may tell
    # people: the files the owner put in ~/work/knowledge-for-people (regular .md/.txt, copied here; empty by default).
    LANE=; IOG="$AU"
    if id -u mila-guest >/dev/null 2>&1 && curl -s --max-time 5 http://127.0.0.1:8790/status | grep -q '"guest": true'; then
      LD=/run/mila-lane; rm -rf "${LD:?}/knowledge"; mkdir -p "$LD/knowledge"
      KD="$HOME/work/knowledge-for-people"
      if [ -d "$KD" ] && [ ! -L "$KD" ]; then   # root reads the owner's home: regular files only, no links, no hard links, small
        find "$KD" -maxdepth 1 -type f -links 1 \( -name '*.md' -o -name '*.txt' \) -size -64k -exec cp --no-dereference -t "$LD/knowledge" {} + 2>/dev/null
      fi
      chown mila-guest:mila-guest "$LD"; chmod 2750 "$LD"; chown -R root:mila-guest "$LD/knowledge"; chmod -R u=rwX,g=rX,o= "$LD/knowledge"
      setpriv --reuid=mila-guest --regid=mila-guest --clear-groups -- env -i PATH="$PATH" HOME="$LD" MILA_KEYD=http://127.0.0.1:8790 \
        bash -c 'while :; do python3 /usr/local/bin/mila_lane.py serve --sock /run/mila-lane/lane.sock --knowledge /run/mila-lane/knowledge >> /run/mila-lane/lane.log 2>&1; sleep 5; done' >/dev/null 2>&1 &
      LANE="$LD/lane.sock"; IOG="$AU,$(id -g mila-guest)"
      echo "mila-agent: the strangers' lane is on — strangers who address the bot in a group get short answers with no tools"
    else
      echo "mila-agent: no strangers' key (ANTHROPIC_GUEST_API_KEY) — strangers in groups get no answer"
    fi
    # The consent proxy (mila-io): an outside action — post, spend, send as the owner — runs only after the owner's press on a
    # card the proxy draws itself; the owner's decisions go to io/consent/decisions.jsonl (a hash chain the session reads).
    # Its categories come from the image, never from the session's files: the session only asks over consent.sock.
    mkdir -p "$IOD/consent"; chown mila-io:"$AU" "$IOD/consent"; chmod 2750 "$IOD/consent"
    # the session's own shared files get group rights; io/ (journals, consent, hmac key, owners) loses every write but its own
    ( cd / && python3 -I /usr/local/bin/io_perms.py "$TGd" "$IOD" "$AU" | sed 's/^/mila-agent: /' )
    python3 - "$HOME" "$IOD/consent" "${MILA_KIT:-/opt/mila/kit}/consent/categories.json" "$TGd/langs.json" > /run/mila-io/consent.json <<'PYC'
import json, sys
home, state, cats, langs = sys.argv[1:5]
try: categories = json.load(open(cats))
except (OSError, ValueError): categories = {}
json.dump({"owner_id_env": "MILA_OWNER_ID", "bot_token_env": "BOT_TOKEN", "home": home, "state_dir": state,
           "session_socket": "/run/mila-io/consent.sock", "session_socket_mode": "660", "io_socket": "/run/mila-io/consent.io.sock",
           "ttl_min": 15, "max_attachment_mb": 20, "langs_file": langs, "default_lang": "en", "categories": categories,
           "tz": __import__("os").environ.get("MILA_TZ") or __import__("os").environ.get("TZ") or None, "quiet": [22, 8]}, sys.stdout)
PYC
    chown root:mila-io /run/mila-io/consent.json; chmod 640 /run/mila-io/consent.json
    setpriv --reuid=mila-io --regid=mila-io --groups="$IOG" -- env -i PATH="$PATH" HOME=/run/mila-io MILA_KIT="${MILA_KIT:-/opt/mila/kit}" \
      TGd="$TGd" IOD="$IOD" PLUG=/opt/mila/plugin/mila-telegram LANE="$LANE" bash -c '
        until [ -e "$TGd/receiver.go" ]; do sleep 2; done
        if [ ! -s "$IOD/owners.json" ] && [ ! -e "$IOD/owners.pending" ]; then   # first start: the owner the sign-in paired, before any session
          O="$(head -c 32 "$TGd/receiver.go" | tr -cd 0-9)"; [ -n "$O" ] && printf "{\"owners\": [\"%s\"]}\n" "$O" > "$IOD/owners.json" && chmod 640 "$IOD/owners.json"
        fi
        say() { echo "mila-agent: $*"; echo "$(date +%FT%T) $*" >> /run/mila-io/receiver.log; }   # the platform log (Railway) and the receiver log
        say "go — starting the receiver"
        W=   # no bot token in the key keeper yet: wait for it (said once in the log), never leave silently
        while :; do
          BID="$(curl -s --max-time 5 http://127.0.0.1:8790/status | python3 -c "import json,sys; print(json.load(sys.stdin).get(\"telegram_bot_id\") or \"\")" 2>/dev/null)"
          [[ "$BID" =~ ^[0-9]{5,15}$ ]] && break
          [ -n "$W" ] || say "receiver waits for the bot token in the key keeper"; W=1; sleep 5
        done
        touch /run/mila-io/receiver.up
        OWN="$(python3 -c "import json,sys; o=json.load(open(sys.argv[1])).get(\"owners\") or [\"\"]; print(o[0])" "$IOD/owners.json" 2>/dev/null)"
        if [[ "$OWN" =~ ^[0-9]{3,15}$ ]]; then   # no owner yet (owners.pending) — no proxy: nobody to ask
          ( umask 027; while :; do MILA_OWNER_ID="$OWN" BOT_TOKEN="$BID:mila-keyd-placeholder-not-a-token" TELEGRAM_API_ROOT=http://127.0.0.1:8790/telegram \
              python3 "$MILA_KIT/consent/consent_proxy.py" serve --config /run/mila-io/consent.json >> /run/mila-io/consent.log 2>&1; sleep 5; done ) &
          CIO=/run/mila-io/consent.io.sock
        else
          CIO=; say "no owner yet — the consent proxy waits (set OWNER_ID)"
        fi
        while :; do
          RECEIVER_DAEMON=1 TELEGRAM_STATE_DIR="$TGd" TELEGRAM_JOURNAL_DIR="$IOD" TELEGRAM_SHARED_GROUP=1 \
          TELEGRAM_BOT_TOKEN="$BID:mila-keyd-placeholder-not-a-token" TELEGRAM_API_ROOT=http://keeper/telegram \
          TELEGRAM_API_UNIX=/run/mila-keyd/api.sock MILA_KEYD=http://127.0.0.1:8790 \
          TELEGRAM_GUEST_LANE="$LANE" TELEGRAM_CONSENT_IO="$CIO" TELEGRAM_OUT_SPOOL=/run/mila-keyd/out TELEGRAM_VOICE_TRANSCRIBE_CMD="$MILA_KIT/install/transcribe-voice.sh" bun "$PLUG/receiver.ts" >> /run/mila-io/receiver.log 2>&1
          sleep 5
        done' 2>/dev/null &
    export MILA_IO=1 MILA_CONSENT_SOCKET=/run/mila-io/consent.sock
  else
    unset MILA_IO
  fi
  exec setpriv --reuid="$AU" --regid="$AU" --init-groups -- bash "$0" "$@"
fi
H="$HOME"; ST=$H/state; CL=$H/.claude
TG=$CL/channels/telegram            # the plugin's real state: .env, access.json, receiver journal
TGS=$CL/channels/telegram-session   # the session's bridge: same token, EMPTY journal (the feeder delivers)
PLUG=/opt/mila/plugin/mila-telegram; MK=mila-local; FIFO=$ST/session.in
log() { printf '%s mila-agent: %s\n' "$(date +%FT%T)" "$*"; }
wait_forever() { log "$1"; log "Fix the variable in your Docker settings and restart the container."; exec sleep infinity; }

AUTH="$H/.mila-auth"
# The bot token with the key keeper: a token saved on this start (token page, birth code) goes to it and the file is wiped;
# from then on everything here — receiver, session, helpers — holds only «<bot id>:placeholder» and calls Telegram through
# the keeper, which puts the real token into the path.
keyd_bot() {
  [ -n "${MILA_KEYD:-}" ] || return 0
  if [ -s "$AUTH/bot_token" ] && python3 -c 'import sys; sys.path.insert(0, sys.argv[2]); import mila_keyd; sys.exit(0 if mila_keyd.put_remote("telegram", open(sys.argv[1]).read().strip()) else 1)' "$AUTH/bot_token" "${KEYD_LIB:-/usr/local/bin}"; then
    rm -f "$AUTH/bot_token"
  fi
  local BID; BID="$(curl -s --max-time 5 "$MILA_KEYD/status" | python3 -c 'import json, sys; print(json.load(sys.stdin).get("telegram_bot_id") or "")' 2>/dev/null)"
  if [[ "$BID" =~ ^[0-9]{5,15}$ ]]; then
    export TELEGRAM_BOT_TOKEN="$BID:mila-keyd-placeholder-not-a-token" TELEGRAM_API_ROOT="$MILA_KEYD/telegram"
    export TG_API="$TELEGRAM_API_ROOT" MILA_TG_API="$TELEGRAM_API_ROOT" TELEGRAM_API="$TELEGRAM_API_ROOT"
  fi
}
keyd_bot
# No token anywhere and the platform gave a port (Railway, panels with a public address): one-field page, once.
if [ -z "${TELEGRAM_BOT_TOKEN:-}" ] && [ ! -s "$AUTH/bot_token" ] && [ -z "${BIRTH_CODE:-}" ] && [ -n "${PORT:-}" ] && [ ! -e "$AUTH/token_page.done" ]; then
  MILA_AUTH_DIR="$AUTH" python3 "${TOKEN_PAGE:-/usr/local/bin/token_page.py}" | while IFS= read -r l; do log "$l"; done
  [ -s "$AUTH/bot_token" ] || wait_forever "The token page closed without a token (time or attempts ran out) — restart the service to open it again."
fi
# Bot token: the variable, or the one fetched earlier by a birth code (volume, 600), or now by BIRTH_CODE — once, from our relay.
if [ -z "${TELEGRAM_BOT_TOKEN:-}" ] && [ ! -s "$AUTH/bot_token" ] && [ -n "${BIRTH_CODE:-}" ]; then
  MILA_AUTH_DIR="$AUTH" python3 "${BIRTH_HELPER:-/usr/local/bin/birth_claim.py}" | while IFS= read -r l; do log "$l"; done
fi
[ -z "${TELEGRAM_BOT_TOKEN:-}" ] && keyd_bot
if [ -z "${TELEGRAM_BOT_TOKEN:-}" ] && [ -s "$AUTH/bot_token" ]; then TELEGRAM_BOT_TOKEN="$(head -n1 "$AUTH/bot_token")"; export TELEGRAM_BOT_TOKEN; fi
[ -n "${TELEGRAM_BOT_TOKEN:-}" ] || wait_forever "No bot yet: set BIRTH_CODE (a one-time code from the MILAGPT bot) or TELEGRAM_BOT_TOKEN (from @BotFather)."
[[ "${TELEGRAM_BOT_TOKEN}" =~ ^[0-9]{5,}:[A-Za-z0-9_-]{30,}$ ]] || wait_forever "TELEGRAM_BOT_TOKEN does not look like a bot token (digits:letters)."
# Claude login: a variable, or the one saved by an earlier sign-in from Telegram (volume, 600). None — sign in from the chat:
# the helper answers /start with Anthropic's own sign-in link and takes the code back in the chat (no ports, no page).
load_auth() {
  if [ -n "${MILA_KEYD:-}" ]; then   # the keeper holds the key: Claude Code talks to it, with a placeholder instead of a token
    if curl -s --max-time 5 "$MILA_KEYD/status" | grep -q '"anthropic": true'; then
      export ANTHROPIC_BASE_URL="$MILA_KEYD/anthropic" ANTHROPIC_AUTH_TOKEN=mila-keyd
    fi
  elif [ -z "${CLAUDE_CODE_OAUTH_TOKEN:-}${ANTHROPIC_API_KEY:-}" ] && [ -s "$AUTH/oauth_token" ]; then
    CLAUDE_CODE_OAUTH_TOKEN="$(head -n1 "$AUTH/oauth_token")"; export CLAUDE_CODE_OAUTH_TOKEN
  fi
  if [ -z "${OWNER_ID:-}" ] && [ -s "$AUTH/owner_id" ]; then OWNER_ID="$(head -n1 "$AUTH/owner_id")"; export OWNER_ID; fi
}
load_auth
if [ -z "${CLAUDE_CODE_OAUTH_TOKEN:-}${ANTHROPIC_API_KEY:-}${ANTHROPIC_AUTH_TOKEN:-}" ]; then
  log "no Claude login yet — write /start to your bot in Telegram: it sends the sign-in button (your own Claude account)"
  until MILA_AUTH_DIR="$AUTH" python3 "${LOGIN_HELPER:-/usr/local/bin/claude_login.py}"; do log "sign-in helper stopped — restarting in 10 s"; sleep 10; done
  load_auth
fi
[ -n "${CLAUDE_CODE_OAUTH_TOKEN:-}${ANTHROPIC_API_KEY:-}${ANTHROPIC_AUTH_TOKEN:-}" ] || wait_forever "No Claude login after sign-in — write /login to the bot and try again."
[ -z "${OWNER_ID:-}" ] || [[ "$OWNER_ID" =~ ^[0-9]{3,15}$ ]] || wait_forever "OWNER_ID must be your numeric Telegram id (or leave it empty for a pairing code)."

umask 077
[ "${MILA_IO:-}" = 1 ] && umask 007   # the receiver's user is in the session's group: what we share in the Telegram state, it reads
mkdir -p "$ST" "$CL" "$TG/inbound" "$TGS/inbound" "$H/work" "$H/.local/bin"
for d in "$CL" "$TGS" "$TGS/inbound"; do chmod 700 "$d"; done   # not 700 → the plugin silently does not poll
[ "${MILA_IO:-}" = 1 ] && chmod 750 "$CL" || { chmod 700 "$TG" "$TG/inbound"; }   # with mila-io: its group passes to telegram/
export PATH="$H/.local/bin:$PATH"

# The kit (skills, hooks, launcher) into the home volume — on the first start and again whenever the image brings a changed kit:
# core skills are replaced (an edited one is backed up first), the owner's own skills stay. Before, only the first start did it,
# and a redeployed image never reached an existing home.
KIT_SUM="$(cd "$MILA_KIT" && find skills templates install -type f ! -name '*.pyc' -print0 | sort -z | xargs -0 sha256sum | sha256sum | cut -c1-16)"
if [ "$(cat "$CL/.mila-agent-installed" 2>/dev/null)" != "$KIT_SUM" ]; then
  log "installing the Mila kit ($KIT_SUM)"
  bash "$MILA_KIT/install/install.sh" >> "$ST/install.log" 2>&1 || wait_forever "kit install failed — see $ST/install.log"
  echo "$KIT_SUM" > "$CL/.mila-agent-installed"
fi
# Our CLAUDE.md and constitution in ~/work: added when missing, replaced when the owner has not edited them (a version we shipped),
# otherwise the new one goes beside as *.new. USER.md is the owner's: only added when missing.
python3 "$MILA_KIT/install/home_template.py" "$MILA_KIT" "$H/work" | while read -r l; do log "$l"; done
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
# Cards with buttons: the session registers them, the receiver checks a press against them — one file for both. Before, the
# session wrote telegram-session/cards.jsonl and the receiver read telegram/cards.jsonl: a press on Mila's own card was
# «not found». Cards of earlier starts move into the shared file once.
if [ -f "$TGS/cards.jsonl" ] && [ ! -L "$TGS/cards.jsonl" ]; then cat "$TGS/cards.jsonl" >> "$TG/cards.jsonl"; rm -f "$TGS/cards.jsonl"; fi
ln -sfn ../telegram/cards.jsonl "$TGS/cards.jsonl"
# Forum topics: one registry for the session's tools and the receiver (the plugin writes through the link)
if [ -f "$TGS/topics.json" ] && [ ! -L "$TGS/topics.json" ] && [ ! -e "$TG/topics.json" ]; then mv "$TGS/topics.json" "$TG/topics.json"; fi
ln -sfn ../telegram/topics.json "$TGS/topics.json"
# Scripts in the session that check the owner's press or file (packs, spend) read the receiver's journals, not the session's
# empty bridge journal.
export MILA_TG_STATE="$TG"

PIDS=()
cleanup() { log "stop"; tmux kill-server 2>/dev/null; kill "${PIDS[@]}" 2>/dev/null; exit 0; }
trap cleanup TERM INT
# 1. receiver daemon
# voice: the receiver runs our script for every voice note (Groq key: GROQ_API_KEY or ~/work/secrets/groq.env, see key_page.py)
if [ "${MILA_IO:-}" = 1 ]; then   # the receiver runs as mila-io (root step); here only «go» — after sign-in, so it does not take /start
  chmod -R g+rwX "$TG" 2>/dev/null
  O="${OWNER_ID:-$(head -n1 "$AUTH/owner_id" 2>/dev/null | tr -cd 0-9)}"
  [ -n "$O" ] || O="$(python3 -c 'import json,sys; print((json.load(open(sys.argv[1])).get("allowFrom") or [""])[0])' "$TG/access.json" 2>/dev/null | tr -cd 0-9)"
  printf '%s\n' "$O" > "$TG/receiver.go"   # «go», with the owner the sign-in paired (the receiver keeps it only on the first start)
else
  ( while :; do RECEIVER_DAEMON=1 TELEGRAM_STATE_DIR="$TG" TELEGRAM_VOICE_TRANSCRIBE_CMD="${TELEGRAM_VOICE_TRANSCRIBE_CMD:-$MILA_KIT/install/transcribe-voice.sh}" bun "$PLUG/receiver.ts" >> "$ST/receiver.log" 2>&1; sleep 5; done ) & PIDS+=($!)
fi
# schedule outside the session (Baraban): mila-cron jobs of this home become events once a minute — «remind me in an hour»,
# the morning summary — even while the session restarts. State in ~/state/baraban (one owner, one home in the container).
# The owner is read on every tick: paired by a code in the log after start (no OWNER_ID), the schedule starts without a restart.
# Errors keep only the last 64 KB.
( while :; do O="${OWNER_ID:-}"; [ -n "$O" ] || O="$(head -n1 "$AUTH/owner_id" 2>/dev/null | tr -cd 0-9)"
  [ -n "$O" ] || O="$(python3 -c 'import json,sys; print((json.load(open(sys.argv[1])).get("allowFrom") or [""])[0])' "$TG/access.json" 2>/dev/null | tr -cd 0-9)"
  [ -n "$O" ] && python3 "$MILA_KIT/install/baraban.py" tick --home "$H" --owner "$O" --state "$ST/baraban" >/dev/null 2>>"$ST/baraban.err"
  [ "$(stat -c %s "$ST/baraban.err" 2>/dev/null || echo 0)" -gt 65536 ] && { tail -c 32768 "$ST/baraban.err" > "$ST/baraban.err.t" && mv -f "$ST/baraban.err.t" "$ST/baraban.err"; }
  sleep 60; done ) & PIDS+=($!)
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
  # the conversation goes on after a restart (--continue): she remembers what was said and does not greet again.
  # A continued session that dies within 30 s starts fresh next time (a broken conversation must not loop).
  CONT=--continue; [ -e "$ST/session.fresh" ] && CONT=; T0=\$(date +%s)
  TELEGRAM_STATE_DIR="$TGS" claude -p \$CONT --input-format stream-json --output-format stream-json --verbose \\
    --dangerously-load-development-channels "plugin:mila-telegram@$MK" --dangerously-skip-permissions <&3 >> "$ST/session.jsonl" 2>> "$ST/session.err" &
  echo \$! > "$ST/session.pid"; wait \$!; exec 3>&-; rm -f "$ST/session.pid"
  if [ -n "\$CONT" ] && [ \$(( \$(date +%s) - T0 )) -lt 30 ]; then touch "$ST/session.fresh"; else rm -f "$ST/session.fresh"; fi
  echo "\$(date +%FT%T) session ended — restarting in 10 s" >> "$ST/session.log"; sleep 10
done
LOOP
chmod 700 "$ST/session-loop.sh"
tmux new-session -d -s mila "bash $ST/session-loop.sh" || log "tmux did not start"
log "running: receiver + feeder + Claude Code session (tmux «mila»). Logs: $ST/"
while :; do sleep 30 & wait $!; done
