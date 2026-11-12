#!/usr/bin/env bash
# Mila — installs the assistant kit into an existing Claude Code setup.
#
# What it does, in order (README «What changes on your machine» lists the same):
#   1. copies the skills into ~/.claude/skills/ (a changed skill is backed up first)
#   2. installs the `mila` launcher into ~/.local/bin/
#   3. installs the hooks and registers them in ~/.claude/settings.json (backup first)
#   4. an hourly turns-collect job: launchd on macOS, a systemd user timer on Linux
#   4a. the Scheduler's pass every minute (jobs set with mila-cron fire only while it runs): launchd / systemd user timer
#   5. ~/.claude/channels/telegram/permissions.json from the example — only if there is none
#   6. the personal-data vault key ~/.config/mila/pd.key (600) — only if there is none
#
# It does NOT install the Telegram plugin (get.sh or you, inside Claude Code) and does not touch
# your bot token or your access list.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$HERE")"
CLAUDE_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
STATE_DIR="${TELEGRAM_STATE_DIR:-$CLAUDE_DIR/channels/telegram}"
BIN_DIR="$HOME/.local/bin"
DRY=0
VERBOSE=0
for _a in "$@"; do
  case "$_a" in
    --dry-run) DRY=1 ;;
    --verbose) VERBOSE=1 ;;
  esac
done
[[ "${MILA_INSTALL_VERBOSE:-}" == "1" ]] && VERBOSE=1
[[ $DRY -eq 1 ]] && VERBOSE=1   # a dry run exists to show every item
FROM_GET=0
[[ "${MILA_FROM_GET:-}" == "1" ]] && FROM_GET=1
LOG="$CLAUDE_DIR/mila-install.log"
LOG_READY=0
DONE=0

# Every backup this run actually made (or, in --dry-run, would make), for the
# summary printed at the end — the point of a backup nobody can find is the
# same as having none.
declare -a BACKUPS=()
declare -a PROBLEMS=()   # a step that did not work: always on the screen, never only in the log
declare -a NOTICES=()    # facts the owner must read: on the screen in plain words
SKILLS_N=0; GUARDS_N=0; TOOLS_N=0

# The screen shows a short summary; every per-file line goes to the log (mode 600, overwritten on each run),
# and to the screen too with --verbose / MILA_INSTALL_VERBOSE=1 (and in a dry run).
note() {
  if [[ $LOG_READY -eq 1 ]]; then printf '%s\n' "$*" >> "$LOG"; fi
  if [[ $VERBOSE -eq 1 ]]; then printf '%s\n' "$*"; fi
  return 0
}
say() { note "  $*"; }
run() { if [[ $DRY -eq 1 ]]; then say "would: $*"; else "$@"; fi; }
problem() { PROBLEMS+=("$*"); note "  ✗ $*"; return 0; }
# No ${1/#$HOME/~} here: newer bash expands the tilde in the replacement back to $HOME, bash 3.2 on macOS does not.
tilde() { case "$1" in "$HOME"/*) printf '~%s' "${1#"$HOME"}" ;; "$HOME") printf '~' ;; *) printf '%s' "$1" ;; esac; }
row() { if [[ -n "${3:-}" ]]; then printf '  %s %-19s %s\n' "$1" "$2" "$3"; else printf '  %s %s\n' "$1" "$2"; fi; }   # ✓ / ✗ / · , what , why it matters
cleanup() {
  local rc=$?
  if [[ -n "${SETTINGS_TMP:-}" ]]; then rm -f "$SETTINGS_TMP"; fi   # the script below fails → the installer stops here (set -e): the file must not stay behind
  if [[ $rc -ne 0 && $DONE -eq 0 ]]; then
    printf '\n  ✗ The install stopped before it finished (exit code %s) — her home is NOT complete.\n' "$rc"
    printf '    The message above says what failed; fix that and run the same command again.\n'
    if [[ $LOG_READY -eq 1 ]]; then printf '    Full log: %s\n' "$(tilde "$LOG")"; fi
  fi
}
trap cleanup EXIT

if [[ $DRY -eq 0 ]]; then
  mkdir -p "$CLAUDE_DIR"
  ( umask 077; : > "$LOG" ); chmod 600 "$LOG"; LOG_READY=1
  # steps get.sh did before this script (version, clone, update) — the first lines of the same log
  if [[ -n "${MILA_PRE_LOG:-}" && -f "${MILA_PRE_LOG:-}" ]]; then cat "$MILA_PRE_LOG" >> "$LOG"; rm -f "$MILA_PRE_LOG"; fi
fi

# Copies $1 (source) over $2 (destination), keeping a timestamped backup of
# whatever was already at the destination — unless it is byte-identical to
# what's about to replace it, in which case there is nothing worth keeping
# and nothing worth copying. Honours --dry-run: announces, writes nothing.
install_file() {
  local src="$1" dst="$2" label="${3:-$(basename "$2")}"
  if [[ -e "$dst" ]]; then
    if cmp -s "$src" "$dst" 2>/dev/null; then
      say "$label — unchanged, no copy needed"
      return
    fi
    local backup="$dst.bak-$(date +%Y%m%d-%H%M%S)"
    if [[ $DRY -eq 1 ]]; then
      say "would back up existing $label to $(basename "$backup")"
      BACKUPS+=("$backup")
    else
      cp -p "$dst" "$backup"
      BACKUPS+=("$backup")
      say "$label — exists, keeping a copy at $(basename "$backup")"
    fi
  fi
  run cp "$src" "$dst"
}

if [[ $FROM_GET -eq 0 ]]; then
  printf '\n  ✦  M I L A\n  hello · привет · salom · 你好\n\n  Preparing her home…\n'
fi
note "Mila installer"
note "  target: $CLAUDE_DIR"
[[ $DRY -eq 1 ]] && printf '  DRY RUN — nothing will be written\n'
note ""

# ── skills ────────────────────────────────────────────────────────────────
note "Skills"
run mkdir -p "$CLAUDE_DIR/skills"
for d in "$ROOT"/skills/*/; do
  name="$(basename "$d")"
  target="$CLAUDE_DIR/skills/$name"
  if [[ -e "$target" ]]; then
    # __pycache__ is not the owner's work: Python leaves it when a skill's script runs (mila-cron, the Scheduler's pass).
    # Counted as a change, every used skill was «customised» on the next install and got a backup copy.
    if diff -rq -x __pycache__ "$d" "$target" >/dev/null 2>&1; then
      say "$name — unchanged, no copy needed"
      SKILLS_N=$((SKILLS_N + 1))
      continue
    fi
    # Never overwrite silently: a customised skill is someone's work.
    backup="$target.bak-$(date +%Y%m%d-%H%M%S)"
    [[ -e "$backup" ]] && backup="$backup-$$"   # two installs within one second: never move a skill INTO an older backup
    if [[ $DRY -eq 1 ]]; then
      say "would back up existing $name to $(basename "$backup")"
      BACKUPS+=("$backup")
    else
      mv "$target" "$backup"
      BACKUPS+=("$backup")
      say "$name — exists, keeping a copy at $(basename "$backup")"
    fi
  fi
  run cp -R "$d" "$target"
  say "$name installed"
  if [[ $DRY -eq 1 || -d "$target" ]]; then SKILLS_N=$((SKILLS_N + 1)); else problem "skill $name was not copied"; fi
done
note ""

# ── launcher ──────────────────────────────────────────────────────────────
note "Launcher"
run mkdir -p "$BIN_DIR"
install_file "$HERE/mila" "$BIN_DIR/mila" "mila"
run chmod 755 "$BIN_DIR/mila"
say "mila → $BIN_DIR/mila"
case ":$PATH:" in
  *":$BIN_DIR:"*) say "$BIN_DIR is on PATH" ;;
  *) say "NOTE: $BIN_DIR is not on your PATH"
     NOTICES+=("PATH|$(tilde "$BIN_DIR") is not on your PATH yet. Add this line to ~/.zshrc or ~/.bashrc:|export PATH=\"\$HOME/.local/bin:\$PATH\"") ;;
esac
# Is the word `mila` already something else for this user? A function or an alias in an rc file is invisible to this
# non-interactive bash, so the rc files are read (never edited) and so is the PATH lookup.
SHADOW=""
if [[ $DRY -eq 0 ]]; then
  _found="$(command -v mila 2>/dev/null || true)"
  if [[ -n "$_found" && ! "$_found" -ef "$BIN_DIR/mila" ]]; then SHADOW="$_found"; fi
  if [[ -z "$SHADOW" ]]; then
    for _rc in .zshrc .zprofile .bashrc .bash_profile .profile; do
      [[ -f "$HOME/$_rc" ]] || continue
      _hit="$(grep -nE '^[[:space:]]*(function[[:space:]]+mila([[:space:]({]|$)|mila[[:space:]]*\(\)|alias[[:space:]]+mila=)' "$HOME/$_rc" 2>/dev/null | head -1 || true)"
      if [[ -n "$_hit" ]]; then SHADOW="~/$_rc:${_hit%%:*}"; break; fi
    done
  fi
  if [[ -n "$SHADOW" ]]; then
    say "NOTE: mila already means something else in the shell: $SHADOW"
    NOTICES+=("Heads up|\`mila\` already means something else in your shell ($(tilde "$SHADOW")). Until you rename or remove it, start her with the full path:|$(tilde "$BIN_DIR")/mila")
  fi
fi
note ""

# ── a newborn's home: who Mila is and how the first talk goes ───────────────
# Without ~/work/CLAUDE.md the session is a plain Claude: «How can I help?» instead of getting acquainted. Only what is missing
# is added — an owner's own CLAUDE.md, USER.md or canon are never overwritten.
note "Home"
WORK_DIR="${MILA_WORK:-$HOME/work}"
run mkdir -p "$WORK_DIR/canon"
for f in CLAUDE.md USER.md; do
  if [[ -e "$WORK_DIR/$f" ]]; then say "$f — yours, kept"; else run cp "$ROOT/templates/work/$f" "$WORK_DIR/$f"; say "$f — added"; fi
done
for f in CONSTITUTION.md CONSTITUTION.en.md; do
  [[ -e "$WORK_DIR/canon/$f" ]] || run cp "$ROOT/$f" "$WORK_DIR/canon/$f"
done
note ""

# ── inbox hook ────────────────────────────────────────────────────────────
note "Inbox hook"
HOOK_DIR="$CLAUDE_DIR/hooks"
run mkdir -p "$HOOK_DIR"
install_file "$HERE/envelope.py" "$HOOK_DIR/envelope.py" "envelope.py"   # the hook builds its envelope with it
install_file "$HERE/telegram-inbox-feed.py" "$HOOK_DIR/telegram-inbox-feed.py" "telegram-inbox-feed.py"
run chmod 755 "$HOOK_DIR/telegram-inbox-feed.py"
say "hook → $HOOK_DIR/telegram-inbox-feed.py"
GUARDS_N=$((GUARDS_N + 1))
# кроны переживают рестарт сессии — ~/work/state/crons.json, SessionStart просит поднять недостающее
install_file "$HERE/crons-keeper.py" "$HOOK_DIR/crons-keeper.py" "crons-keeper.py"
run chmod 755 "$HOOK_DIR/crons-keeper.py"
say "hook → $HOOK_DIR/crons-keeper.py"
GUARDS_N=$((GUARDS_N + 1))
# Хуки, которые установщик регистрирует в settings.json, обязаны лежать в $HOOK_DIR: Stop-хук без файла даёт код 2 = «не останавливаться»
for f in reply-required.py pd-mask.py; do
  install_file "$HERE/$f" "$HOOK_DIR/$f" "$f"
  run chmod 755 "$HOOK_DIR/$f"
  say "hook → $HOOK_DIR/$f"
  GUARDS_N=$((GUARDS_N + 1))
done
# сторож отправки и журнал обещаний — у self-host тоже из коробки
for f in send-guard.py done-guard.py secret-guard.py skill-hint.py hod-stream.py; do
  install_file "$ROOT/templates/home/.claude/hooks/$f" "$HOOK_DIR/$f" "$f"
  run chmod 755 "$HOOK_DIR/$f"
  say "hook → $HOOK_DIR/$f"
  GUARDS_N=$((GUARDS_N + 1))
done
note ""

# ── tools the launcher calls ──────────────────────────────────────────────
# The launcher looks for every one of these in $HOOK_DIR. Installing only the
# hook left six of the eight `mila` commands answering "reinstall the kit", and
# the promise watchdog silently returning an empty list — which reads exactly
# like "nothing is due".
note "Tools"
for f in usage_collect.py turns_collect.py records.py tasks.py chats_index.py \
         chat_note.py chat_locale.py doctor.py onboard.py birth.py birth_relay.py backup.py design_check.py mila_i18n.py tg_delivery.py \
         mila-run.py run-allow.py companion-feeder.py envelope.py limit_watch.py; do
  if [[ -f "$HERE/$f" ]]; then
    install_file "$HERE/$f" "$HOOK_DIR/$f" "$f"
    run chmod 755 "$HOOK_DIR/$f"
    say "$f"
    TOOLS_N=$((TOOLS_N + 1))
  else
    problem "the kit is missing $f — reinstall the kit (run the install command again)"
  fi
done
# What the background session may do with nobody at a screen to ask: its own short allow-list, beside the service.
if [[ -f "$HERE/mila-run-settings.json" ]]; then
  install_file "$HERE/mila-run-settings.json" "$HOOK_DIR/mila-run-settings.json" "mila-run-settings.json"
else
  problem "the kit is missing mila-run-settings.json — reinstall the kit (run the install command again)"
fi
# The sign-in from Telegram (a born Mila with no Claude login asks her owner in the chat): the same helper the container image
# uses, beside the background service that starts it.
if [[ -f "$HERE/../docker/claude_login.py" ]]; then
  install_file "$HERE/../docker/claude_login.py" "$HOOK_DIR/claude_login.py" "claude_login.py"
  run chmod 755 "$HOOK_DIR/claude_login.py"
else
  problem "the kit is missing docker/claude_login.py — reinstall the kit (run the install command again)"
fi
# the birth page: HTML and portrait next to birth.py
run mkdir -p "$HOOK_DIR/birth-assets"
for f in "$HERE"/birth-assets/*; do
  [[ -f "$f" ]] && install_file "$f" "$HOOK_DIR/birth-assets/$(basename "$f")" "birth-assets/$(basename "$f")"
done
# doctor speaks the owner's language: one strings file per language, next to the tools
run mkdir -p "$HOOK_DIR/locales"
for f in "$HERE"/locales/*.json; do
  [[ -f "$f" ]] && install_file "$f" "$HOOK_DIR/locales/$(basename "$f")" "locales/$(basename "$f")"
done

# ── hourly turn collection ────────────────────────────────────────────────
# The books are only worth keeping if they are kept as the day happens. Collected
# once a night, a turn has lost the conversation that produced it — and the point
# of the table is to be able to ask, by the evening, which question cost what.
#
# Not on the hour. Every other timer on these machines fires at :00, and a
# collector that runs in the same second as a cron job records a turn that is
# still in flight as a failure. The minute is derived from the hostname, so the
# fleet spreads itself across the hour instead of stampeding — override with
# MILA_TURNS_MINUTE if you need a specific one.
note "Hourly turn collection"
TURNS_MIN="${MILA_TURNS_MINUTE:-}"
if [[ -z "$TURNS_MIN" ]]; then
  # 10..49: the top and the bottom of the hour is where everyone else's crons
  # already sit, and :00 is where the daily briefs fire.
  TURNS_MIN=$(python3 -c 'import hashlib,socket;print(10+int(hashlib.sha1(socket.gethostname().encode()).hexdigest(),16)%40)')
fi
PY_BIN="$(command -v python3 || echo /usr/bin/python3)"
COLLECT="$HOOK_DIR/turns_collect.py"
LOG_FILE="$CLAUDE_DIR/turns-collect.log"

if [[ "$(uname -s)" == "Darwin" ]]; then
  LABEL="com.milagpt.turns-collect"
  PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
  if [[ $DRY -eq 1 ]]; then
    say "would: write $PLIST (every hour at :$(printf '%02d' "$TURNS_MIN"))"
  else
    mkdir -p "$HOME/Library/LaunchAgents"
    cat > "$PLIST" <<PLISTEOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>$PY_BIN</string>
    <string>$COLLECT</string>
    <string>--days</string><string>1</string>
    <string>--quiet</string>
  </array>
  <key>StartCalendarInterval</key>
  <dict><key>Minute</key><integer>$TURNS_MIN</integer></dict>
  <key>EnvironmentVariables</key>
  <dict><key>MILA_AGENT</key><string>${MILA_AGENT:-companion}</string></dict>
  <key>StandardOutPath</key><string>$LOG_FILE</string>
  <key>StandardErrorPath</key><string>$LOG_FILE</string>
  <key>RunAtLoad</key><false/>
</dict>
</plist>
PLISTEOF
    chmod 644 "$PLIST"
    # MILA_SKIP_TIMERS=1 (tests, images): the file is written and nothing is loaded. Without it a trial install with a temporary
    # HOME would take down the machine's own job of the same name and put one that looks into the temporary folder in its place.
    if [[ "${MILA_SKIP_TIMERS:-}" == "1" ]]; then
      say "$LABEL — written, not loaded (MILA_SKIP_TIMERS)"
    else
      launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
      launchctl bootstrap "gui/$(id -u)" "$PLIST" 2>/dev/null \
        || launchctl load -w "$PLIST" 2>/dev/null || true
      say "$LABEL — every hour at :$(printf '%02d' "$TURNS_MIN")"
    fi
  fi
elif command -v systemctl >/dev/null 2>&1; then
  UNITS="$HOME/.config/systemd/user"
  if [[ $DRY -eq 1 ]]; then
    say "would: write $UNITS/mila-turns-collect.{service,timer} (:$(printf '%02d' "$TURNS_MIN"))"
  else
    mkdir -p "$UNITS"
    cat > "$UNITS/mila-turns-collect.service" <<UNITEOF
[Unit]
Description=Mila — collect turns into conversations.db

[Service]
Type=oneshot
# Имя агента должно совпадать с тем, под которым ходы пишутся руками, иначе
# один и тот же Компаньон разъезжается в отчёте на две строки.
Environment=MILA_AGENT=${MILA_AGENT:-companion}
ExecStart=$PY_BIN $COLLECT --days 1 --quiet
UNITEOF
    cat > "$UNITS/mila-turns-collect.timer" <<UNITEOF
[Unit]
Description=Mila — hourly turn collection

[Timer]
OnCalendar=*:$(printf '%02d' "$TURNS_MIN")
# Persistent catches up after the machine was asleep: a missed hour is a hole
# in the books, and holes are noticed only when someone asks about that day.
Persistent=true

[Install]
WantedBy=timers.target
UNITEOF
    chmod 644 "$UNITS"/mila-turns-collect.*
    if [[ "${MILA_SKIP_TIMERS:-}" == "1" ]]; then
      say "mila-turns-collect.timer — written, not enabled (MILA_SKIP_TIMERS)"
    else
      systemctl --user daemon-reload 2>/dev/null || true
      systemctl --user enable --now mila-turns-collect.timer 2>/dev/null \
        && say "mila-turns-collect.timer — every hour at :$(printf '%02d' "$TURNS_MIN")" \
        || problem "could not enable the hourly timer — run: systemctl --user enable --now mila-turns-collect.timer"
    fi
  fi
else
  say "NOTE: neither launchd nor systemd found — run \`mila turns\` from your own scheduler"
  NOTICES+=("Timers|Neither launchd nor systemd was found, so no hourly job was set. Run  mila turns  from your own scheduler.|")
fi
note ""

# ── the Scheduler: one pass a minute ──────────────────────────────────────
# A job set with mila-cron fires only while something runs `baraban.py tick` for
# this home. The container has its own loop; on a laptop nothing did, so jobs
# were stored and never fired — and an answer «it stands in the Scheduler» was
# a promise that would not come true. The pass leaves a mark
# (~/.local/state/mila/baraban/<home>.beat): the send guard lets that answer
# through only while the mark is fresh, and `doctor` shows a Scheduler that
# stopped. The owner is the one paired with the bot (access.json).
# MILA_SKIP_TIMERS=1 writes the files and does not load them (tests, images).
# The pass runs with -B: a service that runs every minute must not leave __pycache__ inside the home's skills.
note "Scheduler (one pass a minute)"
install_file "$HERE/baraban.py" "$HOOK_DIR/baraban.py" "baraban.py"
SCHED="$HOOK_DIR/baraban.py"
SCHED_LOG="$CLAUDE_DIR/scheduler.log"
SLABEL="com.milagpt.scheduler"
SPLIST="$HOME/Library/LaunchAgents/$SLABEL.plist"
SUNIT="$HOME/.config/systemd/user/mila-scheduler.timer"
# Two Schedulers over one home would fire every job twice. If a pass mark for this home is fresh and the timer is not ours
# (a container's loop, a service of the server), leave it alone.
SCHED_ELSE=0
if [[ ! -e "$SPLIST" && ! -e "$SUNIT" ]] && "$PY_BIN" -B - "$HOME" "$CLAUDE_DIR/skills/raspisanie" <<'PYEOF' 2>/dev/null
import datetime, sys
sys.path.insert(0, sys.argv[2])
import cronspec
at = cronspec.last_beat(sys.argv[1])
sys.exit(0 if at and (datetime.datetime.now(datetime.timezone.utc) - at).total_seconds() <= cronspec.BEAT_FRESH else 1)
PYEOF
then SCHED_ELSE=1; fi
if [[ $SCHED_ELSE -eq 1 ]]; then
  say "the Scheduler is already passing for this home (a service of this machine) — no timer of ours is added"
elif [[ "$(uname -s)" == "Darwin" ]]; then
  if [[ $DRY -eq 1 ]]; then
    say "would: write $SPLIST (every minute)"
  else
    mkdir -p "$HOME/Library/LaunchAgents"
    cat > "$SPLIST" <<PLISTEOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$SLABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>$PY_BIN</string>
    <string>-B</string>
    <string>$SCHED</string>
    <string>tick</string>
    <string>--home</string><string>$HOME</string>
  </array>
  <key>StartInterval</key><integer>60</integer>
  <key>StandardOutPath</key><string>/dev/null</string>
  <key>StandardErrorPath</key><string>$SCHED_LOG</string>
  <key>RunAtLoad</key><true/>
</dict>
</plist>
PLISTEOF
    chmod 644 "$SPLIST"
    if [[ "${MILA_SKIP_TIMERS:-}" == "1" ]]; then
      say "$SLABEL — written, not loaded (MILA_SKIP_TIMERS)"
    else
      launchctl bootout "gui/$(id -u)/$SLABEL" 2>/dev/null || true
      launchctl bootstrap "gui/$(id -u)" "$SPLIST" 2>/dev/null \
        || launchctl load -w "$SPLIST" 2>/dev/null || true
      say "$SLABEL — every minute"
    fi
  fi
elif command -v systemctl >/dev/null 2>&1; then
  UNITS="$HOME/.config/systemd/user"
  if [[ $DRY -eq 1 ]]; then
    say "would: write $UNITS/mila-scheduler.{service,timer} (every minute)"
  else
    mkdir -p "$UNITS"
    cat > "$UNITS/mila-scheduler.service" <<UNITEOF
[Unit]
Description=Mila — the Scheduler: one pass over this home's jobs

[Service]
Type=oneshot
ExecStart=$PY_BIN -B $SCHED tick --home $HOME
StandardOutput=null
StandardError=append:$SCHED_LOG
UNITEOF
    cat > "$UNITS/mila-scheduler.timer" <<UNITEOF
[Unit]
Description=Mila — the Scheduler, every minute

[Timer]
OnCalendar=minutely
AccuracySec=5s

[Install]
WantedBy=timers.target
UNITEOF
    chmod 644 "$UNITS"/mila-scheduler.*
    if [[ "${MILA_SKIP_TIMERS:-}" == "1" ]]; then
      say "mila-scheduler.timer — written, not enabled (MILA_SKIP_TIMERS)"
    else
      systemctl --user daemon-reload 2>/dev/null || true
      systemctl --user enable --now mila-scheduler.timer 2>/dev/null \
        && say "mila-scheduler.timer — every minute" \
        || problem "could not enable the Scheduler timer — run: systemctl --user enable --now mila-scheduler.timer"
    fi
  fi
else
  say "NOTE: neither launchd nor systemd found — jobs set with mila-cron will not fire until your own scheduler runs every minute: $PY_BIN -B $SCHED tick --home $HOME"
  NOTICES+=("Scheduler|Neither launchd nor systemd was found: reminders and jobs fire only if something runs this every minute:|$PY_BIN -B $SCHED tick --home $HOME")
fi
note ""

# ── Mila in the background ────────────────────────────────────────────────
# A born Mila does not need a terminal: one service (install/mila-run.py) keeps her receiver, the feeder and the Claude Code
# session alive, in her own home folder, and brings her back after a reboot. Here the service file is only WRITTEN: she is not
# born yet. The birth page starts it (`mila start` does the same by hand; `mila stop` stops it).
# launchd and systemd start with a bare PATH, so the PATH of this install — where claude and bun were found — goes into the file.
echo "Background service (starts after birth)"
BG_RUN="$HOOK_DIR/mila-run.py"
BG_LABEL="com.milagpt.session"
BG_PLIST="$HOME/Library/LaunchAgents/$BG_LABEL.plist"
BG_STATE="${XDG_STATE_HOME:-$HOME/.local/state}/mila/run"
BG_PATH="$HOME/.local/bin:$HOME/.bun/bin:$PATH"
if [[ "$(uname -s)" == "Darwin" ]]; then
  if [[ $DRY -eq 1 ]]; then
    say "would: write $BG_PLIST (not loaded until birth)"
  else
    mkdir -p "$HOME/Library/LaunchAgents" "$BG_STATE"; chmod 700 "$BG_STATE"
    cat > "$BG_PLIST" <<PLISTEOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$BG_LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>$PY_BIN</string>
    <string>-B</string>
    <string>$BG_RUN</string>
    <string>run</string>
  </array>
  <key>WorkingDirectory</key><string>$HOME</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key><string>$BG_PATH</string>
    <key>MILA_RUN_SERVICE</key><string>1</string>
  </dict>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>ThrottleInterval</key><integer>10</integer>
  <key>ProcessType</key><string>Background</string>
  <key>StandardOutPath</key><string>$BG_STATE/service.log</string>
  <key>StandardErrorPath</key><string>$BG_STATE/service.log</string>
</dict>
</plist>
PLISTEOF
    chmod 644 "$BG_PLIST"
    say "$BG_LABEL — written; starts when Mila is born (mila start / mila stop)"
  fi
elif command -v systemctl >/dev/null 2>&1; then
  UNITS="$HOME/.config/systemd/user"
  if [[ $DRY -eq 1 ]]; then
    say "would: write $UNITS/mila-session.service (not enabled until birth)"
  else
    mkdir -p "$UNITS"
    cat > "$UNITS/mila-session.service" <<UNITEOF
[Unit]
Description=Mila in the background: receiver, feeder and the Claude Code session in her home folder
After=network-online.target

[Service]
ExecStart=$PY_BIN -B $BG_RUN run
WorkingDirectory=$HOME
Environment=PATH=$BG_PATH
Environment=MILA_RUN_SERVICE=1
Restart=always
RestartSec=10

[Install]
WantedBy=default.target
UNITEOF
    chmod 644 "$UNITS/mila-session.service"
    say "mila-session.service — written; starts when Mila is born (mila start / mila stop)"
    # without lingering, a systemd --user service stops when the person logs out of the machine
    if command -v loginctl >/dev/null 2>&1 && [[ "$(loginctl show-user "$(id -un)" -p Linger --value 2>/dev/null)" != "yes" ]]; then
      NOTICES+=("Background|On this Linux machine Mila stops when you log out. To keep her running:|loginctl enable-linger $(id -un)")
    fi
  fi
else
  say "NOTE: neither launchd nor systemd found — after birth  mila start  runs her as a plain background process (not restarted after a reboot)"
fi
note ""

# The permission policy decides what runs without waking anyone. With no file
# at all the code falls back to STRICT — every single tool call becomes a card
# in Telegram, and past twelve a minute they are auto-denied. A first evening
# like that reads as "the assistant is broken".
POLICY="$STATE_DIR/permissions.json"
if [[ -f "$POLICY" ]]; then
  say "permissions.json — exists, left alone"
elif [[ -f "$HERE/permissions.example.json" ]]; then
  # the channel's state folder holds the bot token and the access list: when the installer is the one who creates it, it is
  # closed to everyone else from the first second — a newborn must not start with a red line of the doctor
  if [[ ! -d "$STATE_DIR" ]]; then run mkdir -p "$STATE_DIR"; run chmod 700 "$STATE_DIR"; fi
  run cp "$HERE/permissions.example.json" "$POLICY"
  run chmod 600 "$POLICY"
  say "permissions.json installed from the example — READ IT before trusting it"
  say "  it decides what runs without asking you: $POLICY"
  NOTICES+=("Read first|permissions.json decides what runs without asking you. Read it before you trust it:|$(tilde "$POLICY")")
fi

if [[ $DRY -eq 1 ]]; then
  say "would check $CLAUDE_DIR/settings.json — register hooks (backup first if it changes):"
  say "  UserPromptSubmit: telegram-inbox-feed.py, skill-hint.py, hod-stream.py · PreToolUse + PostToolUse + Stop: hod-stream.py · SessionStart + PostToolUse(CronCreate|CronDelete): crons-keeper.py · Stop: reply-required.py · PostToolUse(Write|Edit): pd-mask.py"
  say "  PreToolUse(reply|edit_message): send-guard.py, done-guard.py · PostToolUseFailure: done-guard.py · PostToolUse(reply): task-sent.py · SessionStart: task-open.py · env OWNER_ID (MILA_OWNER_ID)"
  say "would create the personal data vault key ~/.config/mila/pd.key (600) if missing"
else
  # The script goes to python through a here-document that is NOT inside $( … ): bash 3.2 (the system shell of macOS) counts
  # apostrophes of a here-document inside a command substitution, and one comment with an unpaired apostrophe ends the whole
  # installer with «unexpected EOF while looking for matching». The output goes to a file and is read from it.
  SETTINGS_TMP="$(mktemp "${TMPDIR:-/tmp}/mila-settings.XXXXXX")"
  python3 - "$CLAUDE_DIR" > "$SETTINGS_TMP" << 'PY'
import json, os, sys, datetime
cfg_dir = sys.argv[1]
p = os.path.join(cfg_dir, 'settings.json')
hook_cmd = os.path.join(cfg_dir, 'hooks', 'telegram-inbox-feed.py')
try:
    with open(p, encoding='utf-8') as f:
        raw = f.read()
    cfg = json.loads(raw)
except FileNotFoundError:
    raw = None
    cfg = {}
except json.JSONDecodeError:
    print('FAIL:settings.json is not valid JSON, so the guardians are NOT registered. Fix the file (or move it aside) and run the install again.')
    raise SystemExit(0)

hooks = cfg.setdefault('hooks', {})
entries = hooks.setdefault('UserPromptSubmit', [])
already = any(hook_cmd in json.dumps(e) for e in entries)
# SessionStart и PostToolUse(CronCreate|CronDelete) — тот же сторож кронов
ck = 'python3 ' + os.path.join(cfg_dir, 'hooks', 'crons-keeper.py')
ck_want = [('SessionStart', {'hooks': [{'type': 'command', 'command': ck}]}),
           ('PostToolUse', {'matcher': 'CronCreate|CronDelete', 'hooks': [{'type': 'command', 'command': ck}]})]
ck_missing = [(ev, e) for ev, e in ck_want if not any('crons-keeper.py' in json.dumps(x) for x in hooks.get(ev, []))]
# Stop — reply-required: ход не кончается, пока на сообщение из Telegram не ушёл ответ инструментом reply (README/REFERENCE обещают его; план 17.10 п.3)
rr = 'python3 ' + os.path.join(cfg_dir, 'hooks', 'reply-required.py')
# PostToolUse(Write|Edit|MultiEdit) — pd-mask: личные данные в том, что Мила хранит, → ярлыки хранилища (слой 2а, по умолчанию; PD_MASK=0 — выкл.)
pm = 'python3 ' + os.path.join(cfg_dir, 'hooks', 'pd-mask.py')
if not any('pd-mask.py' in json.dumps(x) for x in hooks.get('PostToolUse', [])):
    ck_missing.append(('PostToolUse', {'matcher': 'Write|Edit|MultiEdit', 'hooks': [{'type': 'command', 'command': pm}]}))
if not any('reply-required.py' in json.dumps(x) for x in hooks.get('Stop', [])):
    ck_missing.append(('Stop', {'hooks': [{'type': 'command', 'command': rr}]}))
# PreToolUse(reply|edit_message) — send-guard блокирует отправку не туда, ключи, кухню; PostToolUse(reply) — task-sent
# пишет исходящие и обещания; SessionStart — task-open показывает сорванные и горящие обещания
SEND_RE = 'mcp__plugin_(mila-)?telegram_telegram__reply|mcp__plugin_(mila-)?telegram_telegram__edit_message|mcp__plugin_(mila-)?telegram_telegram__topic|mcp__plugin_(mila-)?telegram_telegram__widget|mcp__plugin_(mila-)?telegram_telegram__widget_data'   # a topic's name and a widget (its code, data, caption) leave the machine too — checked like a message
SEND_RE_TOPIC = 'mcp__plugin_(mila-)?telegram_telegram__reply|mcp__plugin_(mila-)?telegram_telegram__edit_message|mcp__plugin_(mila-)?telegram_telegram__topic'   # a home from before the widget tools
SEND_RE_OLD = 'mcp__plugin_(mila-)?telegram_telegram__reply|mcp__plugin_(mila-)?telegram_telegram__edit_message'
# "onFailure" у хука — с CC 2.1.295; на старой CC ключ не пишем (строгая CC могла бы отбросить весь хук сторожа)
import re as _re, subprocess as _sp
try: _v = _sp.run(['claude', '--version'], capture_output=True, text=True, timeout=10).stdout
except Exception: _v = ''
_v = os.environ.get('MILA_CC_VERSION') or _v
_m = _re.search(r'(\d+)\.(\d+)\.(\d+)', _v or '')
ONFAIL_OK = bool(_m) and tuple(int(x) for x in _m.groups()) >= (2, 1, 295)
if not ONFAIL_OK: print('WARN:send-guard: onFailure skipped - old or unknown Claude Code version (%s). Update Claude Code and run the install again, so a crashed guard blocks the message.' % ((_m and _m.group(0)) or '?'))
sg = 'python3 ' + os.path.join(cfg_dir, 'hooks', 'send-guard.py')
if not any('send-guard.py' in json.dumps(x) for x in hooks.get('PreToolUse', [])):
    ck_missing.append(('PreToolUse', {'matcher': SEND_RE, 'hooks': [dict({'type': 'command', 'command': sg}, **({'onFailure': 'block'} if ONFAIL_OK else {}))]}))
# done-guard: «сделала» не уходит в одном ходу с командой без результата; упала команда после ушедшего «сделала» — просьба о поправке.
# Отдельной записью и без onFailure (сам пропускает при сбое). PostToolUseFailure — только на CC, где есть onFailure (проверено на 2.1.310)
dg = 'python3 ' + os.path.join(cfg_dir, 'hooks', 'done-guard.py')
if not any('done-guard.py' in json.dumps(x) for x in hooks.get('PreToolUse', [])):
    ck_missing.append(('PreToolUse', {'matcher': SEND_RE, 'hooks': [{'type': 'command', 'command': dg}]}))
if ONFAIL_OK and not any('done-guard.py' in json.dumps(x) for x in hooks.get('PostToolUseFailure', [])):
    ck_missing.append(('PostToolUseFailure', {'hooks': [{'type': 'command', 'command': dg}]}))
# secret-guard: модель своими инструментами не трогает токен входа (~/.mila-auth) и сейф (~/work/secrets); плюс deny-правила Read/Edit
gg = 'python3 ' + os.path.join(cfg_dir, 'hooks', 'secret-guard.py')
if not any('secret-guard.py' in json.dumps(x) for x in hooks.get('PreToolUse', [])):
    ck_missing.append(('PreToolUse', {'matcher': 'Bash|Read|Grep|Glob|Edit|Write|MultiEdit', 'hooks': [{'type': 'command', 'command': gg}]}))
_deny = cfg.setdefault('permissions', {}).setdefault('deny', [])
for _r in ('Read(~/.mila-auth/**)', 'Edit(~/.mila-auth/**)', 'Read(~/work/secrets/**)', 'Edit(~/work/secrets/**)'):
    if _r not in _deny:
        _deny.append(_r)
        if ('_env', None) not in ck_missing: ck_missing.append(('_env', None))
# skill-hint: одно короткое слово в личке владельца («пульт») → подсказка навыка; отдельной записью UserPromptSubmit
sh = 'python3 ' + os.path.join(cfg_dir, 'hooks', 'skill-hint.py')
if not any('skill-hint.py' in json.dumps(x) for x in hooks.get('UserPromptSubmit', [])):
    ck_missing.append(('UserPromptSubmit', {'hooks': [{'type': 'command', 'command': sh}]}))
# hod-stream: the work progress stream (one message in the owner's private chat that updates while Mila works; /hod off switches it off).
# Four events, one entry each; it never blocks a tool (it always ends with code 0)
hs = 'python3 ' + os.path.join(cfg_dir, 'hooks', 'hod-stream.py')
for _ev in ('PreToolUse', 'PostToolUse', 'Stop', 'UserPromptSubmit'):
    if not any('hod-stream.py' in json.dumps(x) for x in hooks.get(_ev, [])):
        ck_missing.append((_ev, {'hooks': [{'type': 'command', 'command': hs}]}))
# сторож упал/завис → сообщение НЕ уходит. Уже записанный хук без onFailure — дописываем ключ
for e in hooks.get('PreToolUse', []):
    for hk in (e.get('hooks') or []) if isinstance(e, dict) else []:
        if isinstance(hk, dict) and 'send-guard.py' in str(hk.get('command', '')) and e.get('matcher') in (SEND_RE_OLD, SEND_RE_TOPIC):
            e['matcher'] = SEND_RE   # a home from before the topic or the widget tools: the guard checks those too
            if ('_env', None) not in ck_missing:
                ck_missing.append(('_env', None))
        if ONFAIL_OK and isinstance(hk, dict) and 'send-guard.py' in str(hk.get('command', '')) and hk.get('onFailure') != 'block':
            hk['onFailure'] = 'block'
            if ('_env', None) not in ck_missing:
                ck_missing.append(('_env', None))   # «есть что записать», без новой записи хука
tdir = os.path.join(cfg_dir, 'skills', 'mila-tasks', 'hooks')
if os.path.isfile(os.path.join(tdir, 'task-sent.py')):
    if not any('task-sent.py' in json.dumps(x) for x in hooks.get('PostToolUse', [])):
        ck_missing.append(('PostToolUse', {'matcher': 'mcp__plugin_(mila-)?telegram_telegram__reply',
                                           'hooks': [{'type': 'command', 'command': 'python3 ' + os.path.join(tdir, 'task-sent.py')}]}))
    if not any('task-open.py' in json.dumps(x) for x in hooks.get('SessionStart', [])):
        ck_missing.append(('SessionStart', {'hooks': [{'type': 'command', 'command': 'python3 ' + os.path.join(tdir, 'task-open.py')}]}))
# OWNER_ID — chat id хозяина: send-guard пускает ответы только ему и подключённым чатам (без него — по access.json)
own = (os.environ.get('MILA_OWNER_ID') or os.environ.get('OWNER_ID') or '').strip()
if own.lstrip('-').isdigit() and cfg.get('env', {}).get('OWNER_ID') != own:
    cfg.setdefault('env', {})['OWNER_ID'] = own
    ck_missing.append(('_env', None))
if already and not ck_missing:
    print('  already registered in settings.json')
else:
    if not already:
        entries.append({'hooks': [{'type': 'command', 'command': hook_cmd}]})
    for ev, e in ck_missing:
        if ev != '_env':
            hooks.setdefault(ev, []).append(e)
    new_raw = json.dumps(cfg, ensure_ascii=False, indent=2)
    if raw is not None and raw != new_raw:
        ts = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
        backup = p + f'.bak-{ts}'
        with open(backup, 'w', encoding='utf-8') as f:
            f.write(raw)
        print(f'BACKUP:{backup}')
        print(f'  registered in settings.json (previous version kept as {os.path.basename(backup)})')
    else:
        print('  registered in settings.json')
    with open(p, 'w', encoding='utf-8') as f:
        f.write(new_raw)
PY
  SETTINGS_OUT="$(cat "$SETTINGS_TMP")"; rm -f "$SETTINGS_TMP"; SETTINGS_TMP=""
  while IFS= read -r line; do
    case "$line" in
      BACKUP:*) BACKUPS+=("${line#BACKUP:}") ;;
      FAIL:*) problem "${line#FAIL:}" ;;
      WARN:*) say "${line#WARN:}"; NOTICES+=("Heads up|${line#WARN:}|") ;;
      "") ;;
      *) say "${line#  }" ;;
    esac
  done <<< "$SETTINGS_OUT"
fi
# Said plainly: the kit goes into this user's own Claude Code folder, so the hooks above work in every session of this user —
# not only in Mila's. Nothing here decides for the owner; it tells him before he meets a guard in his own coding session.
say "note: these hooks sit in $CLAUDE_DIR/settings.json and run in EVERY Claude Code session of this user, not only in Mila's."
say "      To keep Mila apart from your own sessions, install her under a separate user of this computer."
note ""
if [[ ${#BACKUPS[@]} -gt 0 ]]; then
  if [[ $DRY -eq 1 ]]; then note "Would back up (nothing written — dry run):"; else note "Existing files kept as backups:"; fi
  for b in "${BACKUPS[@]}"; do
    say "$b"
  done
  note ""
fi
# ключ хранилища личных данных — по умолчанию (слой 2а); уже есть — не трогаем
VAULT_OK=0
if [[ $DRY -eq 0 && -f "$CLAUDE_DIR/skills/pd-vault/pd_vault.py" ]]; then
  r="$(python3 "$CLAUDE_DIR/skills/pd-vault/pd_vault.py" init 2>/dev/null || true)"
  [[ "$r" == created ]] && say "personal data vault: key ~/.config/mila/pd.key created (600)" || say "personal data vault: key already there"
  [[ -f "${PD_KEY:-$HOME/.config/mila/pd.key}" ]] && VAULT_OK=1
fi

# ── what the screen says ──────────────────────────────────────────────────
DONE=1
if [[ $DRY -eq 1 ]]; then
  printf '\n  Dry run finished — nothing was written. Run the install without --dry-run to apply it.\n\n'
  exit 0
fi
CORE="${MILA_CORE_LABEL:-}"
if [[ -z "$CORE" ]]; then
  CORE_V="$(sed -n 's/.*"version": *"\([^"]*\)".*/\1/p' "$ROOT/release.json" 2>/dev/null | head -1)"
  CORE_SHA="$(git -C "$ROOT" rev-parse --short HEAD 2>/dev/null || true)"
  CORE="${CORE_V:+v$CORE_V}${CORE_SHA:+ ($CORE_SHA)}"
  CORE="${CORE:-kit}"
fi
BAD=0
printf '\n'
row "✓" "Core $CORE"
row "✓" "$SKILLS_N skills" "how she thinks, speaks and keeps her word"
row "✓" "$GUARDS_N guardians" "nothing leaves without your yes"
if [[ $VAULT_OK -eq 1 ]]; then row "✓" "A private vault" "the key stays with you"; else row "✗" "A private vault" "the key was not created — run  mila doctor  to see why"; BAD=$((BAD + 1)); fi
case "${MILA_TG_STATE:-}" in
  ok)      row "✓" "Telegram" "the place where you two will talk" ;;
  skipped) row "·" "Telegram" "skipped (MILA_SKIP_PLUGIN=1) — add it later in Claude Code: /plugin install mila-telegram@mila" ;;
  failed)  row "✗" "Telegram" "${MILA_TG_NOTE:-the plugin was not installed}"; BAD=$((BAD + 1)) ;;
  *)       row "·" "Telegram" "not installed yet — in Claude Code: /plugin marketplace add shakhruz/mila-telegram, then /plugin install mila-telegram@mila" ;;
esac
if [[ ${#PROBLEMS[@]} -gt 0 ]]; then
  for pr in "${PROBLEMS[@]}"; do printf '  ✗ %s\n' "$pr"; done
  BAD=$((BAD + ${#PROBLEMS[@]}))
fi
printf '\n'
if [[ ${#BACKUPS[@]} -gt 0 ]]; then
  KS_W="files"; [[ ${#BACKUPS[@]} -eq 1 ]] && KS_W="file"
  printf '  %-14s %s\n' "Kept safe" "${#BACKUPS[@]} earlier $KS_W → next to the originals, named <file>.bak-<date>-<time> (full list in the log)"
fi
if [[ ${#NOTICES[@]} -gt 0 ]]; then
  for nt in "${NOTICES[@]}"; do
    nlabel="${nt%%|*}"; nrest="${nt#*|}"; ntext="${nrest%%|*}"; ncode="${nrest#*|}"
    printf '  %-14s %s\n' "$nlabel" "$ntext"
    if [[ -n "$ncode" ]]; then printf '  %-14s %s\n' "" "$ncode"; fi
  done
fi
printf '  %-14s %s\n' "Good to know" "her guardians run in EVERY Claude Code session of this user, not only hers."
printf '  %-14s %s\n' "" "To keep Mila apart, install her under a separate user."
printf '\n'
M=mila
case ":$PATH:" in *":$BIN_DIR:"*) ;; *) M="$(tilde "$BIN_DIR")/mila" ;; esac
[[ -n "$SHADOW" ]] && M="$(tilde "$BIN_DIR")/mila"
if [[ $BAD -eq 0 ]]; then
  printf '  Her home is ready. One step left:\n'
else
  printf '  Her home is almost ready — fix the ✗ above first (details in the log), then one step:\n'
fi
printf '\n      %s\n\n' "$M"
printf '  Check her health any time:  %s doctor\n' "$M"
printf '  Full log: %s\n\n' "$(tilde "$LOG")"
