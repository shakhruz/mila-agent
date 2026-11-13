#!/usr/bin/env python3
"""Does the install command in the READMEs work right now? Run before pushing a README change and after a release.

  python3 tools/check_install_link.py            # exit 0 — every releases/…/download/<file> link answers 200; 1 — list of broken
The READMEs point at `releases/latest/download/get.sh`; until the latest release carries get.sh and SHA256SUMS that link is a
404 for everyone who opens the repository. So: push a README that points at a release only together with that release.
A link that answers is not enough: `latest` may be an old release (it once stayed six versions behind while every link was
green). So the get.sh behind `releases/latest` is read too: its PIN_REF must not be older than the tag in release.json here.
Only stdlib. CHECK_INSTALL_BASE replaces https://github.com in tests."""
import glob, json, os, re, sys, urllib.error, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LINK = re.compile(r"https://github\.com/[\w.-]+/[\w.-]+/releases/(?:latest/download|download/v[\w.-]+)/[\w.-]+")


def links(root=ROOT):
    out = {}
    for p in sorted(glob.glob(os.path.join(root, "README*.md"))):
        for m in LINK.findall(open(p, encoding="utf-8").read()):
            out.setdefault(m, []).append(os.path.basename(p))
    return out


def status(url, timeout=15):
    base = os.environ.get("CHECK_INSTALL_BASE")
    if base:
        url = url.replace("https://github.com", base.rstrip("/"))
    rq = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "mila-check-install-link"})
    try:
        with urllib.request.urlopen(rq, timeout=timeout) as r:   # follows the redirect to the release asset
            return r.status
    except urllib.error.HTTPError as e:
        return e.code
    except (urllib.error.URLError, OSError):
        return 0


def body(url, timeout=15, cap=400000):
    base = os.environ.get("CHECK_INSTALL_BASE")
    if base:
        url = url.replace("https://github.com", base.rstrip("/"))
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "mila-check-install-link"}), timeout=timeout) as r:
            return r.read(cap).decode("utf-8", "replace")
    except (urllib.error.URLError, OSError):
        return None


def ver(tag):
    m = re.fullmatch(r"v(\d+)\.(\d+)\.(\d+)", tag or "")
    return tuple(int(x) for x in m.groups()) if m else None


def repo_tag(root=ROOT):
    try:
        return json.load(open(os.path.join(root, "release.json"), encoding="utf-8")).get("tag") or ""
    except (OSError, ValueError, AttributeError):
        return ""


def stale(ls, root=ROOT):
    """Lines about a `latest` get.sh that installs something older than this repository's release (or is not pinned at all)."""
    want = repo_tag(root)
    if not ver(want):
        return []   # no release.json with a vX.Y.Z tag here: nothing to compare with
    out = []
    for u in sorted(x for x in ls if x.endswith("/releases/latest/download/get.sh")):
        text = body(u)
        if text is None:
            out.append("✗ %s → could not be read, so its version is unknown" % u); continue
        m = re.search(r'^PIN_REF="([^"\n]*)"', text, re.M)
        pin = m.group(1) if m else ""
        if not ver(pin):
            out.append("✗ %s is not pinned to a release (PIN_REF=%r): it was not made by the release tooling" % (u, pin))
        elif ver(pin) < ver(want):
            out.append("✗ %s installs %s, but this repository is at %s: the latest release is behind — publish %s with get.sh and SHA256SUMS" % (u, pin, want, want))
    return out


def main(argv=None):
    ls = links()
    if not ls:
        print("no release download links in README*.md"); return 0
    bad = [(u, f, s) for u, f in ls.items() for s in [status(u)] if s != 200]
    for u, f, s in bad:
        print("✗ %s → %s  (in %s)" % (u, s or "no answer", ", ".join(sorted(set(f)))))
    if bad:
        print("The install command is broken for readers: publish the release with these files, or do not push the README yet.")
        return 1
    old = stale(ls)
    for line in old:
        print(line)
    if old:
        print("Readers who paste the install command get an old Mila: the links answer, the release behind them is stale.")
        return 1
    print("✓ %d install link(s) answer 200%s" % (len(ls), ", latest get.sh is not behind %s" % repo_tag() if ver(repo_tag()) else "")); return 0


if __name__ == "__main__":
    sys.exit(main())
