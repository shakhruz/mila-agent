#!/usr/bin/env python3
"""doctor на языке владельца: в en те же ключи и те же %-подстановки, что в ru; язык — MILA_LANG → ~/work/owner.json → LANG → en;
на пустом временном канале en-вывод без кириллицы в тексте проверок, ru — по-русски, уровни и число строк одинаковые.
Запуск: python3 test_doctor_i18n.py"""
import json, os, re, shutil, subprocess, sys, tempfile
H = os.path.dirname(os.path.abspath(__file__)); T = tempfile.mkdtemp(prefix="doctor-i18n-"); ok = n = 0
def check(name, c, x=""):
    global ok, n; n += 1; ok += bool(c); print(("✅ " if c else "❌ ") + name + ("" if c else "  ← " + str(x)[:300]))
loc = {c: json.load(open(os.path.join(H, "locales", c + ".json"), encoding="utf-8")) for c in ("ru", "en")}
keys = {c: {k for k in d if not k.startswith("_")} for c, d in loc.items()}
check("en: те же ключи doctor.*, что ru", keys["en"] == keys["ru"] and len(keys["ru"]) > 100, keys["ru"] ^ keys["en"])
fmt = lambda s: sorted(re.findall(r"%[-0-9.]*[sdof]", s))
bad = [k for k in keys["ru"] & keys["en"] if fmt(loc["ru"][k]) != fmt(loc["en"][k])]
check("подстановки %s/%d/%o/%.0f совпадают", not bad, bad)
uz = json.load(open(os.path.join(H, "locales", "uz.json"), encoding="utf-8")); uzk = {k for k in uz if not k.startswith("_")}
check("uz: те же ключи, те же подстановки, латиница (без кириллицы)", uzk == keys["ru"] and not [k for k in uzk if fmt(uz[k]) != fmt(loc["ru"][k])]
      and not [k for k in uzk if re.search("[А-Яа-яЁё]", uz[k])], uzk ^ keys["ru"])
zh = json.load(open(os.path.join(H, "locales", "zh.json"), encoding="utf-8")); zhk = {k for k in zh if not k.startswith("_")}
check("zh: те же ключи и подстановки, без кириллицы", zhk == keys["ru"] and not [k for k in zhk if fmt(zh[k]) != fmt(loc["ru"][k])]
      and not [k for k in zhk if re.search("[А-Яа-яЁё]", zh[k])], zhk ^ keys["ru"])
check("в en.json нет кириллицы", not [k for k in keys["en"] if re.search("[А-Яа-яЁё]", loc["en"][k])])
src = open(os.path.join(H, "doctor.py"), encoding="utf-8").read()
used = set(re.findall(r'T\("(doctor\.[a-z_]+\.\d+)"\)', src))
check("каждый T(\"doctor.…\") в коде есть в словаре, лишних нет", used == keys["ru"], used ^ keys["ru"])
def run(env_extra):
    env = {k: v for k, v in os.environ.items() if k not in ("MILA_LANG", "LANG", "LC_ALL", "OWNER_JSON")}
    env.update(HOME=T, TELEGRAM_STATE_DIR=os.path.join(T, "state"), OWNER_JSON=os.path.join(T, "owner.json"), **env_extra)
    r = subprocess.run([sys.executable, os.path.join(H, "doctor.py"), "--json"], capture_output=True, text=True, env=env, timeout=60)
    return json.loads(r.stdout)
os.makedirs(os.path.join(T, "state"))
en, ru = run({"MILA_LANG": "en"}), run({"MILA_LANG": "ru"})
txt = lambda j: " ".join(r["name"] + " " + r["detail"] + " " + r.get("fix", "") for r in j["rows"])
check("MILA_LANG=en: тексты проверок без кириллицы", not re.search("[А-Яа-яЁё]", txt(en)), txt(en)[:300])
check("MILA_LANG=ru: по-русски («токен»)", "токен" in txt(ru))
check("те же уровни и число строк в ru и en", [r["level"] for r in en["rows"]] == [r["level"] for r in ru["rows"]] and en["bad"] == ru["bad"])
open(os.path.join(T, "owner.json"), "w").write('{"lang": "ru"}')
check("без MILA_LANG — язык владельца из owner.json (ru)", "токен" in txt(run({})))
os.remove(os.path.join(T, "owner.json"))
check("без MILA_LANG и owner.json — LANG=ru_RU.UTF-8 → ru", "токен" in txt(run({"LANG": "ru_RU.UTF-8"})))
check("LANG=C → en", "token" in txt(run({"LANG": "C"})) and "токен" not in txt(run({"LANG": "C"})))
open(os.path.join(T, "owner.json"), "w").write('{"lang": "uz"}')
check("owner.json uz → узбекские строки (maxfiylik / kirish)", "kirish" in txt(run({})) and "токен" not in txt(run({})), txt(run({}))[:200])
import importlib.util
spec = importlib.util.spec_from_file_location("doc", os.path.join(H, "doctor.py")); D = importlib.util.module_from_spec(spec); spec.loader.exec_module(D)
check("колонка ровная и для иероглифов: pad считает ширину на экране", D.pad("隐私", 6) == "隐私  " and D.pad("бот", 6) == "бот   ")
zh_line = "对「被提及时回复」模式来说这是正常的。若要「回复所有人」请关闭：@BotFather → /setprivacy → 选择机器人 → Disable"
w = D.wrap(zh_line, 60)
check("перенос по клеткам: китайская строка — ни одна строка не шире 60 клеток, текст цел", all(D.cells(x) <= 60 for x in w) and "".join(w).replace(" ", "") == zh_line.replace(" ", ""), w)
check("перенос не рвёт @BotFather внутри китайской строки", not any(x.endswith("@B") for x in w) and any("@BotFather" in x for x in w), w)
check("русский перенос как раньше", D.wrap("раз два три четыре", 9) == ["раз два", "три", "четыре"], D.wrap("раз два три четыре", 9))
shutil.rmtree(T, ignore_errors=True); print("итог %d/%d" % (ok, n)); sys.exit(0 if ok == n else 1)
