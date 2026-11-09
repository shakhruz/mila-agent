#!/usr/bin/env python3
"""io_perms.py — root's permission step over the Telegram state at each start (audit 09.11, №9).

Was: chmod -R g+rwX over the whole folder, io/ included — the consent journal, its hmac key and the owners' list became
writable by the session's group, and a restart made a forged decision legal. Now two separate passes, each by descriptor:
  share — the session's own shared files get group read/write: only regular files and folders the session's uid owns,
          one name only (a hard link to a system file is not «shared state»), never through a link, never inside io/;
  lock  — inside io/: group write and every right of others are taken away, so the session reads io/ and never writes.
  python3 io_perms.py <telegram dir> <io dir> <session uid>"""
import os, stat, sys


def _fd(path):
    return os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)


def _walk(top, skip=None):
    """every real entry under top, links not followed and not yielded; skip — a folder not entered."""
    for root, dirs, files in os.walk(top, followlinks=False):
        dirs[:] = [d for d in dirs if os.path.join(root, d) != skip]
        for n in dirs + files:
            yield os.path.join(root, n)
    yield top


def share(tgd, iod, uid):
    n = 0
    for p in _walk(tgd, skip=iod):
        try: fd = _fd(p)
        except OSError: continue   # a link (ELOOP) or gone
        try:
            st = os.fstat(fd)
            if st.st_uid != uid: continue
            if stat.S_ISDIR(st.st_mode): os.fchmod(fd, (st.st_mode & 0o7777) | 0o070); n += 1
            elif stat.S_ISREG(st.st_mode) and st.st_nlink == 1: os.fchmod(fd, (st.st_mode & 0o7777) | 0o060); n += 1
        finally:
            os.close(fd)
    return n


def lock(iod):
    n = 0
    for p in _walk(iod):
        try: fd = _fd(p)
        except OSError: continue
        try:
            st = os.fstat(fd)
            if stat.S_ISDIR(st.st_mode) or (stat.S_ISREG(st.st_mode) and st.st_nlink == 1):
                os.fchmod(fd, st.st_mode & 0o7777 & ~0o027); n += 1   # group keeps read, others keep nothing
        finally:
            os.close(fd)
    return n


if __name__ == "__main__":
    tgd, iod, uid = sys.argv[1], sys.argv[2], int(sys.argv[3])
    print("io_perms: shared %d, locked %d" % (share(tgd, iod, uid), lock(iod)))
