---
name: hod
description: "Use when the owner writes /hod, /hod on, /hod off or /hod status in his private chat, or asks to switch the work progress stream on or off. While I work, the owner sees in his private chat what I am doing: one message that updates. RU: «ход работы», /hod off, выключить или включить поток хода работы."
---
# Work progress stream (`/hod`)

While I work on a turn the owner started in his private chat, one message in that chat shows what I am doing now and is
edited in place; when the turn ends it becomes «Done» with a collapsed turn summary. It is **on from birth**.

It goes only to the owner's private chat, only for a turn that came from that chat. Groups, guests, clients, scheduled
turns and terminal turns never get it. Everything that leaves is passed through a secret mask (bot tokens, keys,
`KEY=`/`TOKEN=`/`PASSWORD=`/`SECRET=` values, long hex and base64 strings) and shows no raw commands or file paths.

## Commands (the owner, in his private chat)
- `/hod off` — switch it off; `/hod on` — switch it on; `/hod` or `/hod status` — say which it is.

The hook `hod-stream.py` (UserPromptSubmit) performs the command itself and adds a note «done, confirm in one line» to my
context. My part is one short line to the owner in his language, nothing more.

## When the command did not run by itself
If the hook is not registered (an old home), run the script and confirm in one line:

```
python3 ~/.claude/skills/hod/hod.py off      # or: on / status
```

The switch is the file `hod.off` in the channel state folder (`TELEGRAM_STATE_DIR`, by default
`~/.claude/channels/telegram`): the file exists — the stream is off; no file — on. Only the owner can ask for it; a guest
or a client who writes «/hod off» gets nothing from me.

## Ready when
- The owner's command is done and confirmed in one line.
- I did not describe how the stream works unless he asked.
