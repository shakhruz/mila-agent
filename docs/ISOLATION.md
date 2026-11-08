# Isolation — what is separated from what

One page for the question «if the session is talked into something, what can it not reach?». The details of every layer are in
[THREAT-MODEL.md](THREAT-MODEL.md) and [RECEIVER-AND-JOURNALS.md](RECEIVER-AND-JOURNALS.md); this page is the map.

## Mila Agent (the container image)

The image runs one Mila in one container. Inside it, four OS users split the work so that the Claude Code session — the part that
reads untrusted text — holds no keys and cannot forge what the owner said.

| User | Runs | Holds | The session (`agent`) can |
|---|---|---|---|
| `agent` (1001) | Claude Code session, feeder, sign-in helpers, the Scheduler | no keys: a placeholder token everywhere | — |
| `mila-keys` (1002) | key keeper (`docker/mila_keyd.py`) at 127.0.0.1 | Claude sign-in, bot token, service keys (`~/.keys`, 700) | use a key through a route, never read it; put a new key through the socket, not take it back |
| `mila-io` (1003) | receiver of Telegram updates, consent proxy | the updates stream, journals of what came in and what the owner pressed | read the journals; not write them; not read updates past the receiver (403) |
| `mila-guest` (1004) | strangers' lane: answers people who are not paired, without tools | its own knowledge folder | nothing: its socket refuses the session (PermissionError) |

Other walls of the image:
- Claude Code never runs as root: the entrypoint drops to `agent` before anything else starts.
- The only port is 8080, for two one-time pages (sign-in and key entry); the rest listens on 127.0.0.1 or on sockets.
- Outgoing texts on their way to the archive lie in memory (`/run`), a file per send, readable by the keeper and the receiver, not by the session.

## What is checked automatically

`docker/wall_probe.sh` runs in CI inside the built image as root, boots the keeper with fake keys and then, **as the session's
user**, tries every way out we know of: the key files, the keeper's `/proc` (environ, cmdline, mem), `ps`, the environment, a
search of the home and `/tmp`, the sockets, the status page, path tricks on the routes, `getUpdates` past the receiver, writing
into the receiver's journals, the strangers' lane and the consent proxy sockets. A fake key found anywhere, or a write that
succeeds, fails the build.

## In front of the walls — layers, not walls

The hooks in `templates/home/.claude/hooks/` stop the model's mistakes before they happen, under the same user, by pattern:
`secret-guard.py` (no reading of key places, no environment dumps), `send-guard.py` (no key
in a reply, no reply to a chat that was not connected), `done-guard.py`. A determined command can be phrased so that no
pattern sees it; that is why the keys live behind the users above.

## Hosted Milas (one container each)

A hosted setup runs each Mila in its own container: its own home, its own files, its own bot. One Mila cannot see another one's
files or chats — the container is the boundary. Mount nothing into a container you would not hand to that Mila.

## What isolation does not give

- **A laptop install is one OS user.** The session can read every key in its home; the hooks are the only layer. Use the image
  if the keys matter.
- **Text is not isolated.** Whatever an allowed person writes reaches the session; behaviour, not walls, decides what Mila does
  with it.
- **Entering a key.** The sign-in helper and the key page run as the session's user at the moment a key is typed.
- **Everything the session is allowed to do, it can do wrong.** A wall stops reading a key, not a wrong reply in a connected chat.
