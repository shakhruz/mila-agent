#!/usr/bin/env python3
"""The files of a release: get.sh with the tag and the commit of that tag written in (a moved tag will not install), and
SHA256SUMS for it. One builder for the release script on a laptop and for the release workflow — the two give the same bytes.

  python3 tools/release_files.py <tag> <commit sha> <out dir> [--src install/get.sh]
Only stdlib."""
import hashlib, os, re, sys


def build(tag, sha, out, src="install/get.sh"):
    if not re.fullmatch(r"v\d+\.\d+\.\d+", tag): raise SystemExit("tag: vX.Y.Z is needed, not %r" % tag[:40])
    if not re.fullmatch(r"[0-9a-f]{40}", sha): raise SystemExit("sha: a full commit id (40 hex characters) is needed")
    s = open(src, encoding="utf-8").read()
    if s.count('\nPIN_REF=""\n') != 1 or s.count('\nPIN_SHA=""\n') != 1: raise SystemExit("%s: no empty PIN_REF / PIN_SHA lines" % src)
    s = s.replace('\nPIN_REF=""\n', '\nPIN_REF="%s"\n' % tag).replace('\nPIN_SHA=""\n', '\nPIN_SHA="%s"\n' % sha)
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "get.sh"), "w", encoding="utf-8") as f: f.write(s)
    h = hashlib.sha256(s.encode("utf-8")).hexdigest()
    with open(os.path.join(out, "SHA256SUMS"), "w") as f: f.write(h + "  get.sh\n")   # the name of the release file: sha256sum -c --ignore-missing
    return h


if __name__ == "__main__":
    a = sys.argv[1:]
    src = "install/get.sh"
    if "--src" in a: i = a.index("--src"); src = a[i + 1]; del a[i:i + 2]
    if len(a) != 3: raise SystemExit(__doc__)
    print("%s  get.sh  (tag %s, commit %s)" % (build(a[0], a[1], a[2], src), a[0], a[1]))
