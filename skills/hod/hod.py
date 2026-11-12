#!/usr/bin/env python3
"""hod.py on|off|status: the switch of the work progress stream. The flag file `hod.off` lives in the channel state
folder (TELEGRAM_STATE_DIR, default ~/.claude/channels/telegram): present = off, absent = on (the default, from birth).
Prints the word on or off. Standard library only."""
import os
import sys

CLAUDE = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.expanduser("~/.claude")
STATE = os.environ.get("TELEGRAM_STATE_DIR") or os.path.join(CLAUDE, "channels", "telegram")
FLAG = os.path.join(STATE, "hod.off")


def inside(path, base):
    try:
        a, b = os.path.realpath(path), os.path.realpath(base)
        return os.path.commonpath([a, b]) == b
    except ValueError:
        return False


def main(argv):
    if not inside(STATE, CLAUDE):   # the same rule as the hook: only this Mila's own channel folder
        print("the channel folder is outside this Mila's home - not touching it")
        return 2
    act = (argv[1] if len(argv) > 1 else "status").lower()
    if act == "off":
        os.makedirs(STATE, exist_ok=True)
        with open(FLAG, "w") as f:
            f.write("off\n")
    elif act == "on":
        try:
            os.unlink(FLAG)
        except FileNotFoundError:
            pass
    elif act != "status":
        print("usage: hod.py on|off|status")
        return 2
    print("off" if os.path.exists(FLAG) else "on")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
