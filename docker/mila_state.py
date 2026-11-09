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
