#!/usr/bin/env python3
"""mila_state.py — where Mila Agent keeps what the session must not change (audit 09.11, №1 + №9; docs: STATE-LAYOUT).

Decision 09.11 (variant B, everywhere): ONE volume at /var/lib/mila — <root>/home, <root>/keys, <root>/io on it; <root> itself
belongs to root, so the session (which owns home) can neither rename keys/io nor put its own there.
  MILA_STATE=data:<root> (default data:/var/lib/mila); MILA_STATE=volumes — the old split (home on /home/agent), kept for a
  self-host that has not moved its mount yet: it runs, and the owner gets a card about the mount.
Root's step at each start, all by descriptor (no link followed, no -R over the home):
  1. data layout, first start after the update: the old volume WAS the home (its root has .claude/work and belongs to agent).
     Move every name of it into <root>/home one rename at a time; a crash in the middle is finished by the next start
     (marker .moving); an old home that already has home/, keys/ or io/ of its own — refuse, never merge.
  2. the root of the layout → root:root 755 (fchown through its descriptor).
  3. home, keys, io — real folders, not links, owned by root or by their user, else refuse; then fchown/fchmod to their user.
  4. persistent(): keys on the same device as «/» — the container's layer, the sign-in would vanish at the next redeploy.
  python3 mila_state.py prepare --agent-uid U --keys-uid K --io-uid I   → prints the layout as JSON, exit 1 with a reason
"""
import json, os, stat, sys

HOME_SIGNS = (".claude", "work")
OWN_NAMES = ("home", "keys", "io")
MARK = ".moving"


class Refuse(Exception):
    pass


def layout(env=None):
    env = os.environ if env is None else env
    v = env.get("MILA_STATE") or "data:/var/lib/mila"
    if v.startswith("data:"):
        root = v[5:] or "/data"
        return {"kind": "data", "root": root, "home": os.path.join(root, "home"), "keys": os.path.join(root, "keys"),
                "io": os.path.join(root, "io")}
    root = env.get("MILA_STATE_ROOT") or "/var/lib/mila"
    return {"kind": "volumes", "root": root, "home": env.get("MILA_HOME") or "/home/agent",
            "keys": os.path.join(root, "keys"), "io": os.path.join(root, "io")}


def open_dir(path, dir_fd=None):
    try:
        return os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=dir_fd)
    except OSError as e:
        raise Refuse("%s: not a folder of its own (%s)" % (path, e.strerror))


def _exists(name, dfd):
    try:
        os.stat(name, dir_fd=dfd, follow_symlinks=False); return True
    except FileNotFoundError:
        return False


def move_old_home(root, agent_uid):
    """data layout: the volume's root used to be the home itself → move it into root/home. Returns the names moved."""
    rfd = open_dir(root)
    try:
        names = set(os.listdir(rfd))
        moving = MARK in names
        if not moving:
            if "home" in names or not any(n in names for n in HOME_SIGNS):
                return []   # already laid out, or a fresh volume
            clash = [n for n in OWN_NAMES if n in names]
            if clash:
                raise Refuse("%s: the old home already has %s of its own — not merging; move them away by hand" % (root, ", ".join(clash)))
            fd = os.open(MARK, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=rfd); os.close(fd)
        if not _exists("home", rfd):
            os.mkdir("home", 0o750, dir_fd=rfd)
        hfd = open_dir("home", rfd)
        moved = []
        try:
            for n in sorted(os.listdir(rfd)):
                if n in OWN_NAMES or n in (MARK, "lost+found"):
                    continue
                if _exists(n, hfd):
                    raise Refuse("%s/home/%s already there — a half-moved home with a clash; look by hand" % (root, n))
                os.rename(n, n, src_dir_fd=rfd, dst_dir_fd=hfd)   # same volume: one rename, nothing copied
                moved.append(n)
            os.fchown(hfd, agent_uid, agent_uid)
        finally:
            os.close(hfd)
        os.unlink(MARK, dir_fd=rfd)
        return moved
    finally:
        os.close(rfd)


def slug(path):
    """the name Claude Code gives a project folder: the path with «/» and «.» as «-»."""
    return path.replace("/", "-").replace(".", "-")


def rename_projects(home, old_home="/home/agent"):
    """memory and transcripts are found by the folder named after the path: home moved → rename -home-agent… to the new
    prefix, or Mila wakes up with no memory and nobody notices. By descriptor; a clash is left as it is (both kept)."""
    old, new = slug(old_home), slug(home)
    if old == new:
        return []
    try: hfd = open_dir(home)
    except Refuse: return []
    done = []
    try:
        try: cfd = open_dir(".claude", hfd)
        except Refuse: return []
        try:
            try: pfd = open_dir("projects", cfd)
            except Refuse: return []
            try:
                for n in sorted(os.listdir(pfd)):
                    if n == old or n.startswith(old + "-"):
                        to = new + n[len(old):]
                        if _exists(to, pfd): continue
                        st = os.stat(n, dir_fd=pfd, follow_symlinks=False)
                        if not stat.S_ISDIR(st.st_mode): continue
                        os.rename(n, to, src_dir_fd=pfd, dst_dir_fd=pfd); done.append(to)
            finally: os.close(pfd)
        finally: os.close(cfd)
    finally: os.close(hfd)
    return done


def own(path, uid, gid, mode):
    """a real folder (made if missing), owned by root or by uid already — else refuse; then uid:gid and mode by fd."""
    parent, name = os.path.split(path.rstrip("/"))
    pfd = open_dir(parent)
    try:
        if not _exists(name, pfd):
            os.mkdir(name, 0o700, dir_fd=pfd)
        fd = open_dir(name, pfd)
    finally:
        os.close(pfd)
    try:
        st = os.fstat(fd)
        if st.st_uid not in (0, uid):
            raise Refuse("%s belongs to uid %d, not %d — refusing" % (path, st.st_uid, uid))
        os.fchown(fd, uid, gid); os.fchmod(fd, mode)
    finally:
        os.close(fd)


JOURNALS = ("events.jsonl", "taps.jsonl", "auth-log.jsonl", "suspicious.jsonl")
OLD_IO = ".claude/channels/telegram/io"


def _read_plain(dfd, name, maxlen=64 << 20):
    """a regular file of one name, opened without following a link — its bytes, or None."""
    try: fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=dfd)
    except OSError: return None
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1 or st.st_size > maxlen: return None
        out = b""
        while True:
            b = os.read(fd, 1 << 20)
            if not b: return out
            out += b
    finally:
        os.close(fd)


def _write_new(dfd, name, data, uid, gid, mode=0o640):
    fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode, dir_fd=dfd)
    try:
        os.write(fd, data); os.fchown(fd, uid, gid); os.fchmod(fd, mode)
    finally:
        os.close(fd)


def migrate_io(home, io, io_uid, agent_gid, verify=None):
    """the old io/ lived in the session's home and could have been changed by it — its contents are evidence, not truth.
    Carried: the journals (history). The owner's decisions go to io/quarantine as evidence only — the hash chain has no secret,
    a session that could write there could recompute it, so «intact» proves nothing; the owner gives consents again (card). NOT carried: owners.json (the owner comes from the platform again), hmac.key and consents.json
    (a fresh key; pending consents fail closed). Every step by descriptor, no link followed. Once: io/.migrated."""
    ifd = open_dir(io)
    try:
        if _exists(".migrated", ifd):
            return {"skipped": True}
        out = {"journals": [], "decisions": None}
        fds = []
        try:
            fds.append(open_dir(home))
            for part in OLD_IO.split("/"):
                fds.append(open_dir(part, fds[-1]))
        except Refuse:
            fds_ok = False
        else:
            fds_ok = True
        try:
            if fds_ok:
                ofd = fds[-1]
                for j in JOURNALS:
                    data = _read_plain(ofd, j)
                    if data is not None and not _exists(j, ifd):
                        _write_new(ifd, j, data, io_uid, agent_gid); out["journals"].append(j)
                try: cfd = open_dir("consent", ofd)
                except Refuse: cfd = None
                if cfd is not None:
                    try:
                        data = _read_plain(cfd, "decisions.jsonl")
                    finally:
                        os.close(cfd)
                    if data:
                        # the chain has no secret: a session that could write here could also recompute it — old decisions are
                        # evidence only, never the working journal; the owner gives consents again (card)
                        if not _exists("quarantine", ifd): os.mkdir("quarantine", 0o2750, dir_fd=ifd)
                        qfd = open_dir("quarantine", ifd)
                        try:
                            os.fchown(qfd, io_uid, agent_gid)
                            if not _exists("decisions.jsonl", qfd):
                                _write_new(qfd, "decisions.jsonl", data, io_uid, agent_gid)
                            ok = bool(verify and verify("/proc/self/fd/%d/decisions.jsonl" % qfd))
                        finally:
                            os.close(qfd)
                        out["decisions"] = "quarantine (chain %s)" % ("intact" if ok else "broken")
        finally:
            for x in fds: os.close(x)
        _write_new(ifd, ".migrated", json.dumps(out).encode(), io_uid, agent_gid, 0o640)
        return out
    finally:
        os.close(ifd)


def persistent(path, rootdir="/"):
    """False when path sits on the same device as the container's own «/» — no volume under it."""
    return os.stat(path).st_dev != os.stat(rootdir).st_dev


def prepare(env, agent_uid, keys_uid, io_uid):
    L = layout(env)
    if L["kind"] == "data":
        L["moved"] = len(move_old_home(L["root"], agent_uid))
        L["projects_renamed"] = len(rename_projects(L["home"]))
        rfd = open_dir(L["root"])
        try: os.fchown(rfd, 0, 0); os.fchmod(rfd, 0o755)
        finally: os.close(rfd)
    else:
        os.makedirs(L["root"], mode=0o755, exist_ok=True)
        rfd = open_dir(L["root"])
        try:
            st = os.fstat(rfd)
            if st.st_uid != 0 and os.geteuid() == 0:
                raise Refuse("%s belongs to uid %d, not root" % (L["root"], st.st_uid))
        finally:
            os.close(rfd)
    own(L["home"], agent_uid, agent_uid, 0o750)
    own(L["keys"], keys_uid, keys_uid, 0o700)
    own(L["io"], io_uid, agent_uid, 0o2750)
    if L["kind"] == "data":   # the old io/ inside the home: journals carried, decisions to quarantine (see migrate_io)
        verify = None
        try:
            sys.path.insert(0, os.path.join(env.get("MILA_KIT") or "/opt/mila/kit", "consent")); import decisions
            verify = lambda p: decisions.verify(p)[0]
        except ImportError:
            pass
        L["io_migrated"] = migrate_io(L["home"], L["io"], io_uid, agent_uid, verify)
    L["persistent"] = persistent(L["keys"])
    return L


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(); ap.add_argument("cmd", choices=["prepare", "layout"])
    ap.add_argument("--agent-uid", type=int, default=1001); ap.add_argument("--keys-uid", type=int, default=1002)
    ap.add_argument("--io-uid", type=int, default=1003)
    a = ap.parse_args()
    if a.cmd == "layout":
        print(json.dumps(layout())); sys.exit(0)
    try:
        print(json.dumps(prepare(os.environ, a.agent_uid, a.keys_uid, a.io_uid)))
    except Refuse as e:
        print("mila-state: %s" % e, file=sys.stderr); sys.exit(1)
