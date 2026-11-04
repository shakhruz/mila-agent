#!/usr/bin/env bash
# Healthy = receiver daemon, feeder and the Claude Code session all run. (pid ≤ 1 = none: «kill -0 0» would hit the whole group)
ST="$HOME/state"
alive() { [ "${1:-0}" -gt 1 ] 2>/dev/null && kill -0 "$1" 2>/dev/null; }
alive "$(cat "$HOME/.claude/channels/telegram/receiver.pid" 2>/dev/null)" || { echo "receiver is down"; exit 1; }
pgrep -f companion-feeder.py >/dev/null 2>&1 || { echo "feeder is down"; exit 1; }
alive "$(cat "$ST/session.pid" 2>/dev/null)" || { echo "no Claude session"; exit 1; }
exit 0
