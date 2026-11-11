#!/usr/bin/env python3
"""The gate of a release: a tag becomes a release with files only if every line below holds. Run by the release workflow
before anything is published; can be run by hand in a clone.

  python3 tools/release_gate.py <tag> [--main origin/main] [--tests owner/repo] [--wait MINUTES]

  1. the tag is vX.Y.Z (a pre-release vX.Y.Z-rcN is never a release with files);
  2. the tag is an annotated tag object, not a bare name on a commit;
  3. its commit is on the main branch (an ancestor of --main): a tag put on a commit that is in no branch, or in a side
     branch, is refused — that commit never went through review and the main branch's tests;
  4. release.json in that commit says this version and this tag;
  5. CHANGELOG.md in that commit has the section «## vX.Y.Z» with the block for the owner;
  6. the tag is not in yanked.json of the main branch;
  7. the signature: if the main branch has .github/allowed_signers, the tag must carry a valid signature of one of them
     (the list is read from the main branch, never from the tag's own commit); no such file — the line says «not checked»;
  8. --tests: the workflow «tests» has a successful run for exactly this commit. With --wait the gate waits for a run in
     progress; a finished run that is not a success, with no newer one, is a refusal.
Exit 0 — every line holds; 1 — the reasons, one per line. Only stdlib and git."""
import argparse, json, os, re, subprocess, sys, tempfile, time, urllib.error, urllib.request

TAG = re.compile(r"^v(\d+\.\d+\.\d+)$")


def git(*a, check=True):
    r = subprocess.run(["git", *a], capture_output=True, text=True)
    if check and r.returncode != 0: raise RuntimeError("git %s: %s" % (" ".join(a[:3]), (r.stderr or r.stdout).strip()[:200]))
    return r.returncode, r.stdout.strip()


def show(ref, path):
    rc, out = git("show", "%s:%s" % (ref, path), check=False)
    return out if rc == 0 else None


def local_checks(tag, main="origin/main"):
    """→ (reasons, notes, commit sha or None). Everything that needs only the clone."""
    why, notes = [], []
    m = TAG.match(tag or "")
    if not m: return ["%r is not a release tag: vX.Y.Z is needed" % str(tag)[:40]], notes, None
    ver = m.group(1)
    rc, kind = git("cat-file", "-t", "refs/tags/" + tag, check=False)
    if rc != 0: return ["there is no tag %s in this clone" % tag], notes, None
    if kind != "tag": why.append("%s is a bare name on a commit, not an annotated tag (git tag -a / -s)" % tag)
    rc, sha = git("rev-parse", "refs/tags/%s^{commit}" % tag, check=False)
    if rc != 0: return why + ["%s does not point at a commit" % tag], notes, None
    rc, _ = git("rev-parse", "--verify", "-q", main + "^{commit}", check=False)
    if rc != 0: return why + ["there is no %s in this clone (fetch the main branch first)" % main], notes, sha
    if git("merge-base", "--is-ancestor", sha, main, check=False)[0] != 0:
        why.append("the commit of %s (%s) is not on %s: a release is cut only from the main branch" % (tag, sha[:12], main))
    try:
        rj = json.loads(show(sha, "release.json") or "")
    except ValueError:
        rj = None
    if not isinstance(rj, dict) or rj.get("version") != ver or rj.get("tag") != tag:
        why.append("release.json in that commit does not say version %s and tag %s" % (ver, tag))
    sec = re.search(r"^## v%s(?:[ \t][^\n]*)?\n(.*?)(?=^## |\Z)" % re.escape(ver), show(sha, "CHANGELOG.md") or "", re.S | re.M)
    if not sec: why.append("CHANGELOG.md in that commit has no section «## v%s»" % ver)
    elif not re.search(r"Для хозяина|For the owner", sec.group(1), re.I): why.append("the section v%s has no block for the owner" % ver)
    try:
        yanked = json.loads(show(main, "yanked.json") or "[]")
    except ValueError:
        yanked = None
    if not isinstance(yanked, list): why.append("yanked.json on %s is unreadable" % main)
    elif any(tag == (y.get("tag") if isinstance(y, dict) else y) for y in yanked): why.append("%s is withdrawn (yanked.json)" % tag)
    signers = show(main, ".github/allowed_signers")
    if signers is None:
        notes.append("signature of the tag: not checked — the main branch has no .github/allowed_signers")
    else:
        with tempfile.NamedTemporaryFile("w", suffix=".signers", delete=False) as f: f.write(signers + "\n")
        try:
            rc, _ = git("-c", "gpg.format=ssh", "-c", "gpg.ssh.allowedSignersFile=" + f.name, "verify-tag", tag, check=False)
        finally:
            os.unlink(f.name)
        if rc != 0: why.append("%s has no valid signature of a signer from .github/allowed_signers of the main branch" % tag)
        else: notes.append("signature of the tag: valid, signer from .github/allowed_signers")
    return why, notes, sha


def api_runs(repo, sha):
    """Runs of the workflow «tests» for this commit, newest first: [(status, conclusion)]."""
    url = "%s/repos/%s/actions/workflows/tests.yml/runs?head_sha=%s&per_page=30" % (os.environ.get("GITHUB_API_URL", "https://api.github.com"), repo, sha)
    rq = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": "mila-release-gate"})
    tok = os.environ.get("GH_TOKEN")
    if tok: rq.add_header("Authorization", "Bearer " + tok)
    with urllib.request.urlopen(rq, timeout=30) as r: d = json.load(r)
    runs = sorted((x for x in d.get("workflow_runs", []) if x.get("head_sha") == sha), key=lambda x: x.get("run_number", 0), reverse=True)
    return [(x.get("status"), x.get("conclusion")) for x in runs]


def tests_green(sha, runs_of, wait_minutes=0, sleep=time.sleep, clock=time.time, every=60):
    """→ (ok, line). A success among the runs of this commit — yes. Otherwise wait while the newest run is still going."""
    deadline = clock() + wait_minutes * 60
    while True:
        try:
            runs = runs_of(sha)
        except (OSError, ValueError, urllib.error.URLError) as e:
            runs = None; err = str(e)[:120]
        if runs is not None:
            if any(s == "completed" and c == "success" for s, c in runs): return True, "tests: a successful run for %s" % sha[:12]
            if runs and runs[0][0] == "completed":
                return False, "tests: the newest run for %s ended «%s» — no release; rerun the tests, then rerun this job" % (sha[:12], runs[0][1])
        if clock() >= deadline:
            if runs is None: return False, "tests: the list of runs was not read (%s)" % err
            return False, ("tests: no run for %s — the commit was not pushed to a branch, or the run has not started" % sha[:12]) if not runs \
                else "tests: the run for %s is still going after %d minutes" % (sha[:12], wait_minutes)
        sleep(every)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("tag"); ap.add_argument("--main", default="origin/main"); ap.add_argument("--tests"); ap.add_argument("--wait", type=int, default=0)
    a = ap.parse_args(argv)
    why, notes, sha = local_checks(a.tag, a.main)
    for x in notes: print("· " + x)
    if not why and a.tests:
        ok, line = tests_green(sha, lambda s: api_runs(a.tests, s), a.wait)
        if ok: print("· " + line)
        else: why.append(line)
    if why:
        for x in why: print("✗ " + x)
        print("No release for %s." % a.tag); return 1
    print("✓ %s → commit %s: on the main branch, release.json and CHANGELOG agree%s" % (a.tag, sha, ", tests green" if a.tests else "")); return 0


if __name__ == "__main__":
    sys.exit(main())
