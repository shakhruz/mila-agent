#!/bin/bash
# Mila in the background, end to end on a fresh home: install.sh writes the service file and does not start it; a home that is
# not born is not started; after birth `mila start` runs her (launchd / systemd --user / a plain process), plain `mila` shows how
# she is instead of opening a session in the current folder, `mila stop` stops her. Claude Code, bun, launchctl and systemctl
# are stand-ins; nothing leaves the temp folder. bash install/test_mila_bg.sh
set -u; R="$(cd "$(dirname "$0")/.." && pwd)"; T="$(mktemp -d)"; T="$(cd "$T" && pwd -P)"
# cleanup stops only what this test started: by the pid files of its own homes, never by a pattern of a command line
stopall() { for f in "$T"/*/state/run.pid; do [ -f "$f" ] || continue; p="$(cat "$f")"; case "$p" in ''|*[!0-9]*) continue;; esac; kill "$p" 2>/dev/null; done; }
trap 'stopall; sleep 1; rm -rf "$T"' EXIT
svc_pid() { cat "$T/$1/state/run.pid" 2>/dev/null; }   # the service of a home, if it runs
ok=0; n=0; chk(){ n=$((n+1)); if eval "$2" >/dev/null 2>&1; then ok=$((ok+1)); echo "✅ $1"; else echo "❌ $1  ← $(eval "${3:-true}" 2>&1 | head -c 300)"; fi; }
BIN="$T/bin"; mkdir -p "$BIN"
cat > "$BIN/claude" <<'C'
#!/bin/bash
if [ "$1" = auth ]; then echo '{"loggedIn": true}'; exit 0; fi
if [ "$1" = plugin ]; then exit 0; fi
printf '%s|%s\n' "$PWD" "$*" >> "$FAKE_LOG.claude"
case " $* " in *" -p "*) while IFS= read -r l; do echo '{"type":"result"}'; done ;; esac
C
cat > "$BIN/bun" <<'C'
#!/bin/bash
echo $$ > "$TELEGRAM_STATE_DIR/receiver.pid"; exec sleep 600
C
chmod +x "$BIN/claude" "$BIN/bun"
home() {   # home <name> [Darwin] → a fresh installed home; prints nothing
  local H="$T/$1"; mkdir -p "$H" "$T/$1-bin"; cp "$BIN/claude" "$BIN/bun" "$T/$1-bin/"
  if [ "${2:-}" != Darwin ]; then   # a Linux machine whatever this test runs on (also on a Mac in CI): uname says Linux, and systemd --user
    # «is not running» — so she is started as a plain process and nothing of the real machine's service manager is touched
    printf '#!/bin/bash\n[ "${1:-}" = -s ] || [ -z "${1:-}" ] && echo Linux || /usr/bin/uname "$@"\n' > "$T/$1-bin/uname"
    printf '#!/bin/bash\nprintf "%%s\\n" "$*" >> "$FAKE_LOG.systemctl"\ncase "$*" in *"--user cat"*|*"--user enable"*) exit 1;; esac\nexit 0\n' > "$T/$1-bin/systemctl"
    printf '#!/bin/bash\nexit 1\n' > "$T/$1-bin/loginctl"
    chmod +x "$T/$1-bin/uname" "$T/$1-bin/systemctl" "$T/$1-bin/loginctl"
  fi
  if [ "${2:-}" = Darwin ]; then
    printf '#!/bin/bash\n[ "${1:-}" = -s ] || [ -z "${1:-}" ] && echo Darwin || /usr/bin/uname "$@"\n' > "$T/$1-bin/uname"
    printf '#!/bin/bash\nprintf "%%s\\n" "$*" >> "$FAKE_LOG.launchctl"\ncase "$1" in bootstrap|load) ( cd "$HOME" || exit 1; MILA_TG_API="http://127.0.0.1:9" MILA_RUN_SERVICE=1 exec nohup python3 -B "$HOME/.claude/hooks/mila-run.py" run >/dev/null 2>&1 </dev/null ) >/dev/null 2>&1 & ;; esac\nexit 0\n' > "$T/$1-bin/launchctl"
    chmod +x "$T/$1-bin/uname" "$T/$1-bin/launchctl"
  fi
  ( export HOME="$H" PATH="$T/$1-bin:$PATH" MILA_SKIP_TIMERS=1 FAKE_LOG="$T/$1.fake" MILA_RUN_STATE="$H/state" MILA_RUN_PAUSE=0.5; unset TELEGRAM_STATE_DIR CLAUDE_CONFIG_DIR XDG_STATE_HOME MILA_WORK
    bash "$R/install/install.sh" > "$T/$1.install.log" 2>&1; echo $? > "$T/$1.install.rc" )
}
# Telegram is a dead local port here: her first words must not leave this machine
in_home() { local name="$1"; shift; ( export HOME="$T/$name" PATH="$T/$name-bin:$PATH" FAKE_LOG="$T/$name.fake" MILA_RUN_STATE="$T/$name/state" MILA_RUN_PAUSE=0.5 MILA_TG_API="http://127.0.0.1:9"; unset TELEGRAM_STATE_DIR CLAUDE_CONFIG_DIR XDG_STATE_HOME MILA_WORK; cd "$T"; "$@" ); }
up() { local i; for i in $(seq 1 40); do in_home "$1" python3 -B "$T/$1/.claude/hooks/mila-run.py" status --json | grep -q '"session": true' && return 0; sleep 0.5; done; return 1; }   # the session of a home is up (waits up to 20 s)
born() {   # what birth leaves on the machine: a token file, an owner, the record, the plugin
  local H="$T/$1"; mkdir -p "$H/.claude/channels/telegram" "$H/.claude/plugins/cache/mila/mila-telegram/1.0"
  printf 'TELEGRAM_BOT_TOKEN=%s\n' "5550""0111:$(printf 'K%.0s' $(seq 1 35))" > "$H/.claude/channels/telegram/.env"; chmod 600 "$H/.claude/channels/telegram/.env"
  printf '{"dmPolicy":"allowlist","allowFrom":["555000"]}\n' > "$H/.claude/channels/telegram/access.json"
  printf '{"bot_username":"ivan_mila_bot","born_at":"2026-01-01T00:00:00Z"}\n' > "$H/.claude/mila-birth.json"
  : > "$H/.claude/plugins/cache/mila/mila-telegram/1.0/receiver.ts"; : > "$H/.claude/plugins/cache/mila/mila-telegram/1.0/server.ts"
}

# ── Linux here: systemd --user if this machine has it, else a plain process ──
home lin
chk "установка прошла, служба фона установлена: mila-run.py, feeder с модулями, помощник входа" '[ "$(cat "$T/lin.install.rc")" = 0 ] && for f in mila-run.py companion-feeder.py envelope.py limit_watch.py claude_login.py; do [ -f "$T/lin/.claude/hooks/$f" ] || exit 1; done' 'tail -n 5 "$T/lin.install.log"'
chk "установка службу НЕ запускает: Мила ещё не рождена" '! in_home lin python3 -B "$T/lin/.claude/hooks/mila-run.py" status --json | grep -q "\"running\": true"'
chk "Linux: файл службы systemd --user написан — путь к claude и bun, перезапуск, рабочая папка дома" 'U="$T/lin/.config/systemd/user/mila-session.service"; grep -q "mila-run.py run" "$U" && grep -q "Restart=always" "$U" && grep -q "Environment=PATH=.*$T/lin-bin" "$U" && grep -q "MILA_RUN_SERVICE=1" "$U" && grep -q "^UMask=0077$" "$U"' 'cat "$T/lin/.config/systemd/user/mila-session.service"'
o="$(in_home lin "$T/lin/.local/bin/mila" start 2>&1)"
chk "mila start до рождения — отказ со словами «mila birth», ничего не запущено" 'echo "$o" | grep -q "mila birth" && [ ! -e "$T/lin/state/run.pid" ]' 'echo "$o"'
born lin
o="$(in_home lin "$T/lin/.local/bin/mila" start 2>&1)"
chk "после рождения mila start поднимает её фоном" 'echo "$o" | grep -q "running in the background" && up lin' 'echo "$o"; cat "$T/lin/state/run.log" "$T/lin/state/service.log" 2>/dev/null | tail -n 5'
chk "сеанс открыт в доме Милы, а не в папке, где набрали команду" 'grep -q "^$T/lin/work|-p " "$T/lin.fake.claude" && ! grep " -p " "$T/lin.fake.claude" | grep -qv "^$T/lin/work|"' 'cat "$T/lin.fake.claude"'
chk "…без отключения разрешений" '! grep -q "skip-permissions" "$T/lin.fake.claude"' 'cat "$T/lin.fake.claude"'
chk "дом Милы помечен доверенным в настройках Claude Code (для mila open)" 'python3 -c "import json,sys;d=json.load(open(sys.argv[1]));sys.exit(0 if d[\"projects\"][sys.argv[2]][\"hasTrustDialogAccepted\"] is True else 1)" "$T/lin/.claude.json" "$T/lin/work"' 'cat "$T/lin/.claude.json"'
PID1="$(svc_pid lin)"; before="$(wc -l < "$T/lin.fake.claude")"; o="$(in_home lin "$T/lin/.local/bin/mila" 2>&1)"
chk "простое mila у рождённой: статус и ссылка на бота, новый сеанс в текущей папке НЕ открывается" 'echo "$o" | grep -q "session   up" && echo "$o" | grep -q "https://t.me/ivan_mila_bot" && [ "$(wc -l < "$T/lin.fake.claude")" = "$before" ]' 'echo "$o"'
o="$(in_home lin "$T/lin/.local/bin/mila" start 2>&1)"
chk "второй mila start — «уже работает», второй службы нет" 'echo "$o" | grep -q "already running" && [ "$(svc_pid lin)" = "$PID1" ] && kill -0 "$PID1"' 'echo "$o"; svc_pid lin'
chk "mila logs показывает журнал службы" 'in_home lin "$T/lin/.local/bin/mila" logs | grep -q "run.log"'
o="$(in_home lin "$T/lin/.local/bin/mila" stop 2>&1)"
chk "mila stop останавливает: служба, сеанс и приёмник не работают" 'echo "$o" | grep -q "stopped" && ! kill -0 "$PID1" 2>/dev/null && ! kill -0 "$(cat "$T/lin/.claude/channels/telegram/receiver.pid")" 2>/dev/null' 'echo "$o"; svc_pid lin'
# ── mila uninstall: off this machine with one command, nothing deleted ──
in_home lin "$T/lin/.local/bin/mila" start >/dev/null 2>&1; up lin; PID2="$(svc_pid lin)"
o="$(in_home lin "$T/lin/.local/bin/mila" uninstall 2>&1)"; RM="$(ls -d "$T/lin/.mila-removed"/* 2>/dev/null | head -n 1)"
chk "mila uninstall у работающей: сама останавливает её и убирает с машины" 'echo "$o" | grep -q "taken off this machine" && ! kill -0 "$PID2" 2>/dev/null' 'echo "$o"'
chk "…ключ бота, список доступа и запись о рождении не удалены, а перенесены в ~/.mila-removed/<дата>/ (700)" '[ -f "$RM/telegram/.env" ] && [ -f "$RM/telegram/access.json" ] && [ -f "$RM/mila-birth.json" ] && [ ! -e "$T/lin/.claude/channels/telegram" ] && [ ! -e "$T/lin/.claude/mila-birth.json" ] && [ "$(python3 -c "import os,sys;print(oct(os.stat(sys.argv[1]).st_mode & 0o777))" "$RM")" = 0o700 ]' 'ls -la "$RM" "$T/lin/.claude"'
chk "…её дом (память) оставлен, файл службы убран" '[ -d "$T/lin/work" ] && [ ! -e "$T/lin/.config/systemd/user/mila-session.service" ] && [ ! -e "$T/lin/Library/LaunchAgents/com.milagpt.session.plist" ]' 'ls "$T/lin"'
o="$(in_home lin "$T/lin/.local/bin/mila" start 2>&1)"
chk "после uninstall она не рождена: mila start отказывает со словами «mila birth»" 'echo "$o" | grep -q "mila birth"' 'echo "$o"'
o="$(in_home lin "$T/lin/.local/bin/mila" uninstall 2>&1)"
chk "второй uninstall — «нечего убирать», без ошибок" 'echo "$o" | grep -q "Nothing to remove"' 'echo "$o"'
born lin; mkdir -p "$T/lin/.claude/projects/$(printf %s "$T/lin/work" | sed "s/[^A-Za-z0-9]/-/g")"; sleep 1.1
o="$(in_home lin "$T/lin/.local/bin/mila" uninstall --all 2>&1)"; RM2="$(ls -d "$T/lin/.mila-removed"/* | tail -n 1)"
chk "mila uninstall --all переносит и её дом, и её разговор — следующее рождение с чистого листа" '[ -d "$RM2/work" ] && [ -d "$RM2/conversation" ] && [ ! -e "$T/lin/work" ] && [ "$RM2" != "$RM" ]' 'echo "$o"; ls "$RM2"'

# ── macOS: a stand-in uname and launchctl ──
home mac Darwin
P="$T/mac/Library/LaunchAgents/com.milagpt.session.plist"
chk "Мак: plist службы написан — RunAtLoad, KeepAlive, PATH установки, не загружен при установке" 'grep -q "<key>RunAtLoad</key><true/>" "$P" && grep -q "<key>KeepAlive</key><true/>" "$P" && grep -q "$T/mac-bin" "$P" && grep -q "mila-run.py" "$P" && ! grep -q "com.milagpt.session" "$T/mac.fake.launchctl" 2>/dev/null' 'cat "$P"; cat "$T/mac.fake.launchctl"'
chk "Мак: службе записаны точные пути к claude и bun, найденные при установке (PATH другого терминала может их не знать)" 'python3 -c "import plistlib,sys;e=plistlib.load(open(sys.argv[1],\"rb\"))[\"EnvironmentVariables\"];assert e[\"MILA_CLAUDE\"]==sys.argv[2]+\"/claude\" and e[\"MILA_BUN\"]==sys.argv[2]+\"/bun\"" "$P" "$T/mac-bin"' 'grep -A1 MILA_ "$P"'
chk "…plist разбирается как XML; Umask 077 — её журналы только её" 'python3 -c "import plistlib,sys;d=plistlib.load(open(sys.argv[1],\"rb\"));assert d[\"ProgramArguments\"][-1]==\"run\" and d[\"EnvironmentVariables\"][\"MILA_RUN_SERVICE\"]==\"1\" and d[\"Umask\"]==0o077" "$P"'
born mac
o="$(in_home mac "$T/mac/.local/bin/mila" start 2>&1)"
chk "Мак: mila start загружает службу через launchctl bootstrap, она поднимает сеанс" 'grep -q "^bootstrap gui/.* $P" "$T/mac.fake.launchctl" && echo "$o" | grep -q "running in the background" && up mac' 'echo "$o"; cat "$T/mac.fake.launchctl"'
o="$(in_home mac "$T/mac/.local/bin/mila" stop 2>&1)"
chk "Мак: mila stop выгружает службу (bootout) и она остановлена" 'grep -q "^bootout gui/.*/com.milagpt.session" "$T/mac.fake.launchctl" && echo "$o" | grep -q "stopped"' 'echo "$o"; cat "$T/mac.fake.launchctl"'
# ── a trial install into a temporary HOME must not touch the services of the user who runs it ──
mkdir -p "$T/trial" "$T/trial-bin"; cp "$BIN/claude" "$BIN/bun" "$T/trial-bin/"
printf '#!/bin/bash\n[ "${1:-}" = -s ] || [ -z "${1:-}" ] && echo Darwin || /usr/bin/uname "$@"\n' > "$T/trial-bin/uname"
printf '#!/bin/bash\nprintf "%%s\\n" "$*" >> "%s"\nexit 0\n' "$T/trial.launchctl" > "$T/trial-bin/launchctl"; chmod +x "$T/trial-bin/uname" "$T/trial-bin/launchctl"
( export HOME="$T/trial" PATH="$T/trial-bin:$PATH" FAKE_LOG="$T/trial.fake"; unset MILA_SKIP_TIMERS TELEGRAM_STATE_DIR CLAUDE_CONFIG_DIR XDG_STATE_HOME MILA_WORK; bash "$R/install/install.sh" > "$T/trial.install.log" 2>&1 )
chk "пробная установка во временный HOME без MILA_SKIP_TIMERS: службы пользователя не трогает — launchctl не вызван ни разу, файлы служб написаны" '[ ! -s "$T/trial.launchctl" ] && [ -f "$T/trial/Library/LaunchAgents/com.milagpt.session.plist" ] && grep -q "not this user.s own home" "$T/trial.install.log" "$T/trial/.claude/mila-install.log"' 'cat "$T/trial.launchctl"; tail -n 5 "$T/trial.install.log"'
echo "итог $ok/$n"; [ "$ok" = "$n" ]
