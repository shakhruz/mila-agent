#!/usr/bin/env python3
"""pack_mila.py on temp dirs: every role in packs/ builds; the zip is byte-for-byte the same on a rebuild; manifest sha256 = files;
a planted key stops the build; install.sh on a fake home: --dry-run writes nothing, install puts ROLE/WHAT and skills, backs up a
different ROLE.md, adds the CLAUDE.md line once, refuses without the core (2) or without a core skill (3). Run: python3 test_pack_mila.py"""
import hashlib, json, os, shutil, subprocess, sys, tempfile, zipfile
H = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(H); T = tempfile.mkdtemp(prefix="pack-mila-"); ok = n = 0
def check(name, c, x=""):
    global ok, n; n += 1; ok += bool(c); print(("✅ " if c else "❌ ") + name + ("" if c else "  ← " + str(x)[:300]))
sys.path.insert(0, H); import pack_mila as pm
roles = [r for r in sorted(os.listdir(os.path.join(ROOT, "packs"))) if os.path.isfile(os.path.join(ROOT, "packs", r, "pack.json"))]
check("три роли: business-assistant, content-expert, travel-agency", {"business-assistant", "content-expert", "travel-agency"} <= set(roles), roles)
for r in roles:
    p1, m = pm.build(r, os.path.join(T, "a")); p2, _ = pm.build(r, os.path.join(T, "b"))
    z = zipfile.ZipFile(p1); names = z.namelist(); base = names[0].split("/")[0]
    files = {nm[len(base) + 1:]: z.read(nm) for nm in names}
    good = all(hashlib.sha256(files[k]).hexdigest() == v for k, v in m["files"].items())
    check("%s: собирается; повторная сборка — те же байты; manifest sha256 = файлы; ROLE, WHAT, install.sh, INSTALL.md внутри" % r,
          open(p1, "rb").read() == open(p2, "rb").read() and good and {"ROLE.md", "WHAT.md", "install.sh", "INSTALL.md", "manifest.json"} <= set(files), sorted(files))
pm_, mm = pm.build("manager", os.path.join(T, "m"))
check("manager: курс установки COURSE.md в пакете и в манифесте", "COURSE.md" in mm["files"])
bad = os.path.join(T, "badrepo"); shutil.copytree(ROOT, bad, ignore=shutil.ignore_patterns(".git", "__pycache__", "dist", "node_modules"))
j = json.load(open(os.path.join(bad, "packs", "manager", "pack.json"))); j["docs"] = ["../../etc/passwd"]; json.dump(j, open(os.path.join(bad, "packs", "manager", "pack.json"), "w"))
r = subprocess.run([sys.executable, os.path.join(bad, "tools", "pack_mila.py"), "manager", "--out", os.path.join(T, "bad")], capture_output=True, text=True)
check("docs с путём (../) — отказ сборки", r.returncode != 0 and "plain .md" in (r.stderr + r.stdout), r.stderr[-200:])
od = os.path.join(T, "OFFER.md"); open(od, "w").write("# Offer\nHosting option.\n")
_, mo = pm.build("manager", os.path.join(T, "o"), extra_docs=[od])
check("--doc: документ продавца в пакете и манифесте", "OFFER.md" in mo["files"])
open(od, "a").write("OPENROUTER_API_KEY=" + "sk" + "-o" + "r-v1-" + "a1b2c3d4e5f6" * 4 + "\n")
r = subprocess.run([sys.executable, os.path.join(H, "pack_mila.py"), "manager", "--out", os.path.join(T, "o2"), "--doc", od], capture_output=True, text=True)
check("--doc с ключом — сканер останавливает сборку", r.returncode != 0 and "secret scanner" in (r.stderr + r.stdout))
# planted key stops the build
fake = os.path.join(T, "repo"); shutil.copytree(ROOT, fake, ignore=shutil.ignore_patterns(".git", "__pycache__", "dist", "node_modules"))
open(os.path.join(fake, "packs", "business-assistant", "ROLE.md"), "a").write("\nOPENROUTER_API_KEY=" + "sk" + "-o" + "r-v1-" + "a1b2c3d4e5f6" * 4 + "\n")
r = subprocess.run([sys.executable, os.path.join(fake, "tools", "pack_mila.py"), "business-assistant", "--out", os.path.join(T, "c")], capture_output=True, text=True)
check("ключ в ROLE.md — сборка падает, архива нет", r.returncode != 0 and "secret scanner" in (r.stderr + r.stdout) and not os.path.exists(os.path.join(T, "c")), r.stderr[-200:])
# install.sh on a fake home
path, m = pm.build("travel-agency", os.path.join(T, "d")); ex = os.path.join(T, "x"); zipfile.ZipFile(path).extractall(ex)
pk = os.path.join(ex, os.listdir(ex)[0]); sh = os.path.join(pk, "install.sh")
home = os.path.join(T, "home"); claude = os.path.join(home, ".claude"); work = os.path.join(home, "work")
os.makedirs(os.path.join(claude, "skills", "mila-update")); os.makedirs(work)
for s in m["core_skills"]:
    os.makedirs(os.path.join(claude, "skills", s), exist_ok=True)
open(os.path.join(work, "CLAUDE.md"), "w").write("# my Mila\n"); open(os.path.join(work, "ROLE.md"), "w").write("old role\n")
env = dict(os.environ, HOME=home, CLAUDE_CONFIG_DIR=claude, MILA_WORK=work, PATH=os.path.dirname(shutil.which("python3")) + ":/usr/bin:/bin")
r = subprocess.run(["bash", sh, "--dry-run"], capture_output=True, text=True, env=env)
check("--dry-run: ничего не записано", r.returncode == 0 and open(os.path.join(work, "ROLE.md")).read() == "old role\n" and "would:" in r.stdout, r.stdout + r.stderr)
r = subprocess.run(["bash", sh], capture_output=True, text=True, env=env)
role = open(os.path.join(work, "ROLE.md"), encoding="utf-8").read(); baks = [f for f in os.listdir(work) if f.startswith("ROLE.md.bak-")]
check("установка: ROLE и WHAT на месте, прежний ROLE.md — в .bak", r.returncode == 0 and "турагентства" in role and os.path.exists(os.path.join(work, "WHAT.md")) and len(baks) == 1, r.stdout + r.stderr)
subprocess.run(["bash", sh], capture_output=True, text=True, env=env)
check("строка в CLAUDE.md — одна, и после повторной установки", open(os.path.join(work, "CLAUDE.md")).read().count("ROLE.md right after the constitution") == 1)
shutil.rmtree(os.path.join(claude, "skills", m["core_skills"][0]))
r = subprocess.run(["bash", sh], capture_output=True, text=True, env=env)
check("нет навыка ядра — отказ (3), «mila update»", r.returncode == 3 and "mila update" in r.stdout, r.stdout)
shutil.rmtree(os.path.join(claude, "skills", "mila-update"))
r = subprocess.run(["bash", sh], capture_output=True, text=True, env=env)
check("нет ядра — отказ (2), команда установки ядра", r.returncode == 2 and "get.sh" in r.stdout, r.stdout)
r = subprocess.run([shutil.which("bash"), sh], capture_output=True, text=True, env=dict(env, PATH="/nonexistent"))
check("нет python3 — отказ (4), а не тихий пропуск проверки ядра", r.returncode in (4, 127), r.returncode)
shutil.rmtree(T, ignore_errors=True); print("итог %d/%d" % (ok, n)); sys.exit(0 if ok == n else 1)
