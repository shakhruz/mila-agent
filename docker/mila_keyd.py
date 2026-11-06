#!/usr/bin/env python3
"""mila_keyd.py — the key keeper. It runs as its own user (keys), holds the Claude token and the voice keys in files only
that user can read, and puts the right key into each request on the way out. The session and its tools talk to it at
127.0.0.1 and never see a key: they can use a key, not take it.

  /anthropic/…  → https://api.anthropic.com/…   subscription token: Authorization: Bearer + anthropic-beta oauth-2025-04-20;
                                                  an API key: x-api-key
  /deepgram/…   → https://api.deepgram.com/…    Authorization: Token <key>
  /groq/…       → https://api.groq.com/…        Authorization: Bearer <key>
  /status       → which keys are there (yes/no), never a value

Putting a key in: a unix socket (KEYD_SOCK), one JSON line {"kind": "anthropic|deepgram|groq", "value": "…"} → "ok" or
"bad". There is no way to read a key back. Whatever the caller sent as auth is dropped; request and response bodies and
headers are not logged — only method, route and status. Only stdlib.

Env: KEYS_DIR (default /home/agent/.keys), KEYD_PORT (8790), KEYD_BIND (127.0.0.1), KEYD_SOCK (/run/mila-keyd/put.sock),
KEYD_UPSTREAM_<KIND> (tests only: another upstream base)."""
import http.client, http.server, json, os, re, socket, socketserver, ssl, sys, threading, time, urllib.parse

KEYS = os.environ.get("KEYS_DIR") or "/home/agent/.keys"
ROUTES = {"anthropic": "https://api.anthropic.com", "deepgram": "https://api.deepgram.com", "groq": "https://api.groq.com",
          "telegram": "https://api.telegram.org",
          # strangers' lane: Claude on an Anthropic API key (never the owner's subscription), only for the lane's own OS user
          "guest": "https://api.anthropic.com"}
ANT = "sk-" + "ant-"; OAT = ANT + "oat"; GSK = "gs" + "k_"   # key prefixes glued: no key-shaped literal in the source
FORMAT = {"anthropic": r"^" + ANT + r"[A-Za-z0-9_-]{20,300}$", "deepgram": r"^[A-Za-z0-9]{32,64}$", "groq": r"^" + GSK + r"[A-Za-z0-9]{20,100}$",
          "telegram": r"^[0-9]{5,15}:[A-Za-z0-9_-]{30,60}$", "guest": r"^" + ANT + r"api[0-9]{2}-[A-Za-z0-9_-]{20,300}$"}
# Only what Mila's own work calls (Claude Code with non-essential traffic off: POST /v1/messages; the voice script: listen /
# transcriptions). Everything else — a service's account, keys, usage, billing — is 403 and never reaches the service:
# a key the session cannot read must not be usable to mint a new one.
ALLOW = {"anthropic": [("POST", r"/v1/messages"), ("POST", r"/v1/messages/count_tokens"), ("GET", r"/v1/models"), ("HEAD", r"/api/hello"), ("GET", r"/api/hello")],
         "deepgram": [("POST", r"/v1/listen")],
         "groq": [("POST", r"/openai/v1/audio/transcriptions"), ("GET", r"/openai/v1/models")],
         # the bot: a list of methods (Bot API method names are case-insensitive — compared in lower case), and file downloads
         "telegram": [],
         "guest": [("POST", r"/v1/messages"), ("POST", r"/v1/messages/count_tokens")]}
TG_METHODS = {m.lower() for m in """getMe getUpdates deleteWebhook getFile getChat getChatMember getStickerSet getMyCommands
    sendMessage sendPhoto sendDocument sendVideo sendAudio sendVoice sendAnimation sendVideoNote sendMediaGroup sendSticker sendPoll
    sendRichMessage sendChatAction copyMessage forwardMessage editMessageText editMessageCaption editMessageMedia
    editMessageReplyMarkup deleteMessage deleteMessages answerCallbackQuery setMessageReaction setMyCommands pinChatMessage
    unpinChatMessage unpinAllChatMessages createForumTopic editForumTopic closeForumTopic reopenForumTopic
    closeGeneralForumTopic reopenGeneralForumTopic unpinAllForumTopicMessages leaveChat""".split()}   # not setWebhook, logOut, close


IO_ONLY = {"getupdates", "deletewebhook"}   # reading the bot's updates: the receiver's alone once it runs
IO_UID = int(os.environ.get("MILA_IO_UID") or 1003)
GUEST_UID = int(os.environ.get("MILA_GUEST_UID") or 1004)   # the strangers' lane: its own OS user, only the «guest» route
RECEIVER_UP = os.environ.get("MILA_RECEIVER_UP") or "/run/mila-io/receiver.up"


def tg_allowed(method, rest, peer="tcp"):
    m = re.fullmatch(r"/bot[^/]+/([A-Za-z]+)", rest)
    if m and m.group(1).lower() in IO_ONLY:
        # the receiver (its own OS user, over the unix socket) — always; anyone else — only while the receiver is not up
        # (the sign-in helper before the first start). Otherwise the session could read every update, strangers' too.
        return method in ("GET", "POST") and (peer == "io" or not os.path.exists(RECEIVER_UP))
    if m: return method in ("GET", "POST") and m.group(1).lower() in TG_METHODS
    m = re.fullmatch(r"/file/bot[^/]+/([A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*)", rest)
    return bool(m) and method == "GET" and ".." not in m.group(1).split("/")


# Outgoing messages for the archive (Mila Agent): what Telegram answered to a send — the method, the chat, the message id, the text —
# goes to a spool folder, a file per send, only the receiver's user reads (MILA_ARCHIVE_SPOOL, set by the root step). The receiver
# deletes each file once it is in the archive; the keeper keeps nothing itself. /run is memory, so the folder has a ceiling.
OUT_METHODS = {m.lower() for m in """sendMessage sendPhoto sendDocument sendVideo sendAudio sendVoice sendAnimation sendVideoNote
    sendSticker sendPoll copyMessage forwardMessage editMessageText editMessageCaption""".split()}
OUT_SPOOL = os.environ.get("MILA_ARCHIVE_SPOOL") or ""
OUT_MAX = int(os.environ.get("MILA_ARCHIVE_SPOOL_MAX") or 2000)   # files waiting; over it a send is not copied (one log line)
_out_n = 0


def spool_out(method, body):
    try:
        res = json.loads(body.decode("utf-8")).get("result")
    except (ValueError, UnicodeDecodeError, AttributeError):
        return
    if not isinstance(res, dict): return
    chat = (res.get("chat") or {}).get("id")
    row = {"ts": int(time.time() * 1000), "method": method, "chat_id": str(chat) if chat is not None else "", "message_id": res.get("message_id"),
           "text": str(res.get("text") or res.get("caption") or "")[:4096]}
    for k in ("photo", "document", "video", "audio", "voice", "animation", "video_note", "sticker"):
        if res.get(k):
            f = res[k][-1] if isinstance(res[k], list) else res[k]
            row["kind"], row["file_id"] = k, (f or {}).get("file_id"); break
    global _out_n
    try:
        with os.scandir(OUT_SPOOL) as it:
            if sum(1 for _ in zip(range(OUT_MAX), it)) >= OUT_MAX:
                log("spool: full, not copied"); return
        _out_n += 1
        name = "%013d-%d-%d.json" % (row["ts"], os.getpid(), _out_n)
        tmp = os.path.join(OUT_SPOOL, "." + name)   # written whole, then renamed: the receiver never reads half a file
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o640)
        with os.fdopen(fd, "w", encoding="utf-8") as f: f.write(json.dumps(row, ensure_ascii=False))
        os.rename(tmp, os.path.join(OUT_SPOOL, name))
    except OSError as e:
        log("spool: %s" % type(e).__name__)


CHECK = {"guest": "/v1/models", "anthropic": "/v1/models", "deepgram": "/v1/projects", "groq": "/openai/v1/models", "telegram": "/bot{key}/getMe"}   # «is this key alive» — the keeper's own call
HOP = {"host", "connection", "keep-alive", "proxy-authorization", "proxy-connection", "te", "trailer", "transfer-encoding", "upgrade",
       "authorization", "x-api-key", "content-length", "accept-encoding", "cookie"}
OAUTH_BETA = "oauth-2025-04-20"


def log(m):
    sys.stderr.write("keyd: %s\n" % m); sys.stderr.flush()


def key(kind):
    try:
        with open(os.path.join(KEYS, kind), encoding="utf-8") as f: return f.read().strip()
    except OSError:
        return ""


def alive(kind, k):
    """the provider still takes this key (the keeper's own GET, not a path from the session)."""
    hd = {"anthropic-version": "2023-06-01"}; auth_headers(kind, k, hd)
    up = urllib.parse.urlsplit(os.environ.get("KEYD_UPSTREAM_" + kind.upper()) or ROUTES[kind])
    try:
        c = (http.client.HTTPSConnection(up.hostname, up.port or 443, context=ssl.create_default_context(), timeout=20) if up.scheme == "https"
             else http.client.HTTPConnection(up.hostname, up.port or 80, timeout=20))
        c.request("GET", up.path.rstrip("/") + CHECK[kind].replace("{key}", k), headers=hd); st = c.getresponse().status; c.close()
        return st not in (401, 403)   # a network hiccup is not «dead»: the owner's key stays
    except Exception:
        return True


def put(kind, value, replace=False):
    """a key of this kind already here and still alive → refused (the session must not swap the owner's key for its own);
    the old one is dead (401/403) → replaced. The root step (a platform variable the owner set) passes replace=True."""
    value = (value or "").strip()
    if kind not in FORMAT or not re.match(FORMAT[kind], value): return False
    old = key(kind)
    if old and old != value and not replace and alive(kind, old):
        log("put %s refused: a live key is already here" % kind); return False
    os.makedirs(KEYS, mode=0o700, exist_ok=True); os.chmod(KEYS, 0o700)
    p = os.path.join(KEYS, kind); tmp = "%s.%d.tmp" % (p, os.getpid())
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w") as f: f.write(value + "\n")
    os.replace(tmp, p)
    log("put %s" % kind)
    return True


def auth_headers(kind, k, hd):
    if kind == "anthropic":
        if k.startswith(OAT):
            hd["Authorization"] = "Bearer " + k
            name = next((h for h in hd if h.lower() == "anthropic-beta"), "anthropic-beta")
            beta = [b.strip() for b in hd.pop(name, "").split(",") if b.strip()]
            if OAUTH_BETA not in beta: beta.append(OAUTH_BETA)
            hd["anthropic-beta"] = ",".join(beta)
        else:
            hd["x-api-key"] = k
    elif kind == "guest":
        hd["x-api-key"] = k
    elif kind == "telegram":
        pass   # the token goes into the path (rewrite), not into a header
    elif kind == "deepgram":
        hd["Authorization"] = "Token " + k
    else:
        hd["Authorization"] = "Bearer " + k


def put_remote(kind, value, sock=None):
    """for the login helper and the key page: hand a key to the keeper. True — kept; False — refused or no keeper."""
    sock = sock or os.environ.get("KEYD_SOCK") or "/run/mila-keyd/put.sock"
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.settimeout(10); s.connect(sock)
            s.sendall((json.dumps({"kind": kind, "value": value}) + "\n").encode())
            return s.recv(16).strip() == b"ok"
    except OSError:
        return False


def present(kind, base=None):
    """is a key of this kind with the keeper (yes/no only)."""
    import urllib.request
    try:
        with urllib.request.urlopen((base or os.environ.get("MILA_KEYD") or "http://127.0.0.1:8790") + "/status", timeout=5) as r:
            return bool(json.loads(r.read()).get(kind))
    except Exception:
        return False


def guest_user_exists():
    try:
        import pwd; pwd.getpwuid(GUEST_UID); return True
    except (KeyError, ImportError):
        return False


def tcp_peer(client, server, tables=("/proc/net/tcp", "/proc/net/tcp6")):
    """who opened this TCP connection to the keeper: the uid column of the kernel's socket table (as identd does). The lane's
    user on TCP is the lane — it gets only its own route there too. Not found while the lane's user exists → «unknown», refused."""
    cport, sport = "%04X" % client[1], "%04X" % server[1]
    for t in tables:
        try: rows = open(t).read().splitlines()[1:]
        except OSError: continue
        for row in rows:
            f = row.split()
            if len(f) > 7 and f[1].endswith(":" + cport) and f[2].endswith(":" + sport):
                return "guest" if f[7] == str(GUEST_UID) else "tcp"
    return "unknown" if guest_user_exists() else "tcp"


class Proxy(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "mila-keyd"

    def log_message(self, *a): pass

    def setup(self):
        super().setup()
        if isinstance(self.client_address, tuple) and len(self.client_address) >= 2 and self.client_address[0] != "unix":
            self.peer = tcp_peer(self.client_address, self.server.server_address)

    def plain(self, code, obj):
        b = json.dumps(obj).encode()
        self.send_response(code); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(b)))
        self.end_headers(); self.wfile.write(b)

    def handle_any(self):
        path = self.path
        if path == "/status":
            a = key("anthropic")
            return self.plain(200, dict({k: bool(key(k)) for k in ROUTES}, anthropic_kind=("sub" if a.startswith(OAT) else "key") if a else "",
                                        telegram_bot_id=key("telegram").split(":")[0]))   # the bot's id is public; the token after «:» is not
        m = re.match(r"^/(anthropic|deepgram|groq|telegram|guest)(/[^#]*)$", path)
        if not m: return self.plain(404, {"error": "unknown route"})
        kind, rest = m.group(1), m.group(2)
        shown = re.sub(r"bot[^/]+/", "bot…/", rest.split("?")[0])[:80]   # the journal never shows a token, real or placeholder
        peer = getattr(self, "peer", "tcp")
        if peer == "unknown":
            log("%s %s → 403 (caller not known)" % (self.command, kind))
            return self.plain(403, {"error": "not allowed through the key keeper"})
        if (kind == "guest") != (peer == "guest"):   # the lane reaches only its own key; nobody else reaches that key
            log("%s %s%s → 403 (route not for this caller)" % (self.command, kind, shown))
            return self.plain(403, {"error": "not allowed through the key keeper"})
        if not (tg_allowed(self.command, rest.split("?")[0], peer) if kind == "telegram"
                else any(self.command == meth and re.fullmatch(pat, rest.split("?")[0]) for meth, pat in ALLOW[kind])):
            log("%s %s%s → 403 (not on the list)" % (self.command, kind, shown))
            return self.plain(403, {"error": "not allowed through the key keeper"})
        k = key(kind)
        if not k: return self.plain(503, {"error": "no %s key here yet" % kind})
        n = int(self.headers.get("Content-Length") or 0)
        if n > 64 * 1024 * 1024: return self.plain(413, {"error": "too large"})
        body = self.rfile.read(n) if n else None
        if kind == "telegram":   # the placeholder in /bot<…>/ and /file/bot<…>/ becomes the real token
            rest = re.sub(r"^(/(?:file/)?bot)[^/]+/", lambda mm: mm.group(1) + k + "/", rest, count=1)
        hd = {a: b for a, b in self.headers.items() if a.lower() not in HOP}
        auth_headers(kind, k, hd)
        if body is not None: hd["Content-Length"] = str(len(body))
        up = urllib.parse.urlsplit(os.environ.get("KEYD_UPSTREAM_" + kind.upper()) or ROUTES[kind])
        try:
            c = (http.client.HTTPSConnection(up.hostname, up.port or 443, context=ssl.create_default_context(), timeout=600) if up.scheme == "https"
                 else http.client.HTTPConnection(up.hostname, up.port or 80, timeout=600))
            c.request(self.command, (up.path.rstrip("/") + rest) or "/", body=body, headers=hd)
            r = c.getresponse()
        except Exception as e:
            log("%s %s%s → upstream error %s" % (self.command, kind, shown, type(e).__name__))
            return self.plain(502, {"error": "upstream unreachable"})
        log("%s %s%s → %d" % (self.command, kind, shown, r.status))
        self.send_response(r.status)
        for a, b in r.getheaders():
            if a.lower() not in ("transfer-encoding", "connection", "content-length", "keep-alive"): self.send_header(a, b)
        if self.command == "HEAD":
            self.send_header("Content-Length", "0"); self.end_headers(); return
        self.send_header("Transfer-Encoding", "chunked"); self.send_header("Connection", "close"); self.end_headers()
        om = re.fullmatch(r"/bot[^/]+/([A-Za-z]+)", rest.split("?")[0]) if kind == "telegram" else None
        keep = bool(om and r.status == 200 and om.group(1).lower() in OUT_METHODS and OUT_SPOOL)
        got = []
        try:
            while True:
                ch = r.read1(65536)
                if not ch: break
                if keep and sum(map(len, got)) < 1 << 20: got.append(ch)
                self.wfile.write(b"%x\r\n%s\r\n" % (len(ch), ch)); self.wfile.flush()   # stream as it comes (SSE)
            # the spool line before the end of the response: whoever sent it reads the archive after its own send
            if keep: spool_out(om.group(1), b"".join(got)); keep = False
            self.wfile.write(b"0\r\n\r\n"); self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            if keep:   # the caller hung up, the message is still sent: read Telegram's answer to the end and keep it
                try:
                    got.append(r.read(1 << 20)); spool_out(om.group(1), b"".join(got))
                except OSError:
                    pass
        finally:
            c.close()

    do_GET = do_POST = do_PUT = do_DELETE = do_PATCH = do_HEAD = handle_any


class ProxyUnix(Proxy):
    """the same routes over a unix socket, where the calling OS user is known (SO_PEERCRED): the receiver's user is «io»."""
    def setup(self):
        super().setup()
        import struct
        try: uid = struct.unpack("3i", self.request.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i")))[1]
        except OSError: uid = -1
        self.peer = "io" if uid == IO_UID else "guest" if uid == GUEST_UID else "local"
        self.client_address = ("unix", 0)


class Put(socketserver.StreamRequestHandler):
    def handle(self):
        try:
            d = json.loads(self.rfile.readline(4096).decode("utf-8"))
            ok = put(str(d.get("kind")), str(d.get("value")))
        except Exception:
            ok = False
        self.wfile.write(b"ok\n" if ok else b"bad\n")


OLD_FILES = (("anthropic", ".mila-auth/oauth_token", None), ("telegram", ".mila-auth/bot_token", None), ("deepgram", "work/secrets/deepgram.env", "DEEPGRAM_API_KEY"),
             ("groq", "work/secrets/groq.env", "GROQ_API_KEY"))
ENV_KEYS = (("telegram", "TELEGRAM_BOT_TOKEN"), ("anthropic", "CLAUDE_CODE_OAUTH_TOKEN"), ("anthropic", "ANTHROPIC_API_KEY"), ("deepgram", "DEEPGRAM_API_KEY"), ("groq", "GROQ_API_KEY"), ("guest", "ANTHROPIC_GUEST_API_KEY"))


def _old_value(path, field):
    try: txt = open(path, encoding="utf-8").read()
    except OSError: return ""
    if not field: return txt.strip().splitlines()[0].strip() if txt.strip() else ""
    m = re.search(r"^\s*%s\s*=\s*['\"]?([^'\"\s]+)" % field, txt, re.M)
    return m.group(1) if m else ""


def migrate(home):
    """keys the session could read — variables and files of earlier starts — move here; the old files are wiped."""
    moved = []
    for kind, rel, field in OLD_FILES:
        p = os.path.join(home, rel); v = _old_value(p, field)
        if v and put(kind, v): moved.append(kind)
        if v and os.path.isfile(p) and not os.path.islink(p):
            with open(p, "r+b") as f: f.write(b"\0" * os.path.getsize(p))
            os.unlink(p)
    for kind, var in ENV_KEYS:   # a platform variable wins over an old file (the owner changed it in the panel)
        if os.environ.get(var) and put(kind, os.environ[var], replace=True): moved.append(kind)
    return sorted(set(moved))


def detach_stdio(logpath, uid=None, gid=None):
    """the keeper's stdin from /dev/null, its stdout and stderr to its own log (no keys are written there). Without this the
    forked keeper held the entrypoint's pipe open, and the start waited on it forever — an empty container log."""
    fd = os.open(logpath, os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW, 0o640)
    if uid is not None and os.geteuid() == 0: os.fchown(fd, uid, gid)
    dn = os.open(os.devnull, os.O_RDONLY)
    os.dup2(dn, 0); os.dup2(fd, 1); os.dup2(fd, 2)
    os.close(dn); os.close(fd)


def boot(home, agent_uid, keys_uid, port):
    """root, once per start: keys into ~/.keys of their own user, the put socket for agent, the keeper as that user."""
    if os.geteuid() != 0: sys.exit("keyd boot: needs root (the entrypoint's first step)")
    global KEYS
    KEYS = os.path.join(home, ".keys")
    if os.path.islink(KEYS): os.unlink(KEYS)
    os.makedirs(KEYS, mode=0o700, exist_ok=True)
    moved = migrate(home)
    for root_, dirs, files in os.walk(KEYS):
        for x in [root_] + [os.path.join(root_, f) for f in files]: os.lchown(x, keys_uid, keys_uid)
    os.chmod(KEYS, 0o700)
    run = os.path.dirname(os.environ.get("KEYD_SOCK") or "/run/mila-keyd/put.sock")
    os.makedirs(run, exist_ok=True); os.chown(run, keys_uid, agent_uid); os.chmod(run, 0o2751)   # o+x: the receiver's user reaches api.sock
    global OUT_SPOOL
    try:   # Mila Agent: a spool for outgoing messages the receiver's user reads and empties (group mila-io), the session's user does not
        import pwd; io_gid = pwd.getpwnam("mila-io").pw_gid
        od = os.path.join(run, "out"); os.makedirs(od, exist_ok=True); os.chown(od, keys_uid, io_gid); os.chmod(od, 0o2770)
        OUT_SPOOL = od
    except (KeyError, ImportError, OSError):
        pass
    if os.fork():
        for _ in range(50):
            try: socket.create_connection(("127.0.0.1", port), 0.2).close(); log("up as uid %d; moved in: %s" % (keys_uid, ", ".join(moved) or "nothing")); return 0
            except OSError: time.sleep(0.1)
        log("did not start"); return 1
    os.setsid()
    detach_stdio(os.path.join(run, "keyd.log"), keys_uid, agent_uid)   # let go of the entrypoint's pipe: it must not wait for the keeper
    os.setgroups([]); os.setgid(keys_uid); os.setuid(keys_uid)
    for v in [v for v in os.environ if v not in ("PATH", "KEYD_PORT", "KEYD_BIND", "KEYD_SOCK", "LANG")]: del os.environ[v]
    os.environ["KEYS_DIR"] = KEYS
    try: main()
    finally: os._exit(1)


def main():
    os.umask(0o077)
    sock = os.environ.get("KEYD_SOCK") or "/run/mila-keyd/put.sock"
    if os.path.exists(sock): os.unlink(sock)
    class PutServer(socketserver.ThreadingUnixStreamServer):
        def handle_error(self, request, client_address):
            log("put error: %s" % (sys.exc_info()[0].__name__ if sys.exc_info()[0] else "?"))
    us = PutServer(sock, Put)
    os.chmod(sock, 0o620)   # the group (agent) may put a key in; nobody reads one out
    threading.Thread(target=us.serve_forever, daemon=True).start()
    class Server(http.server.ThreadingHTTPServer):
        def handle_error(self, request, client_address):   # only the error's type in the log — never a traceback with values
            log("request error: %s" % (sys.exc_info()[0].__name__ if sys.exc_info()[0] else "?"))
    api_sock = os.environ.get("KEYD_API_SOCK") or os.path.join(os.path.dirname(sock), "api.sock")
    if os.path.exists(api_sock): os.unlink(api_sock)
    class UnixServer(socketserver.ThreadingUnixStreamServer):
        daemon_threads = True
        def handle_error(self, request, client_address):
            log("request error: %s" % (sys.exc_info()[0].__name__ if sys.exc_info()[0] else "?"))
    ux = UnixServer(api_sock, ProxyUnix)
    os.chmod(api_sock, 0o666)   # anyone local may connect; what they may do depends on who they are (SO_PEERCRED)
    threading.Thread(target=ux.serve_forever, daemon=True).start()
    srv = Server((os.environ.get("KEYD_BIND") or "127.0.0.1", int(os.environ.get("KEYD_PORT") or 8790)), Proxy)
    log("listening on %s:%d, keys in %s" % (srv.server_address[0], srv.server_address[1], KEYS))
    srv.serve_forever()


if __name__ == "__main__":
    if sys.argv[1:2] == ["boot"]:
        import argparse
        ap = argparse.ArgumentParser(); ap.add_argument("cmd"); ap.add_argument("--home", required=True)
        ap.add_argument("--agent-uid", type=int, default=1001); ap.add_argument("--keys-uid", type=int, default=1002)
        a = ap.parse_args()
        sys.exit(boot(a.home, a.agent_uid, a.keys_uid, int(os.environ.get("KEYD_PORT") or 8790)))
    main()
