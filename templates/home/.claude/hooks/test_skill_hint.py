#!/usr/bin/env python3
"""skill-hint.py: одно слово из карты → подсказка навыка; фраза, чужой навык, нет навыка — молчание. Песочница: свой CLAUDE_CONFIG_DIR."""
import json, os, subprocess, sys, tempfile
H = os.path.dirname(os.path.abspath(__file__)); G = os.path.join(H, "skill-hint.py"); ok = n = 0
C = tempfile.mkdtemp(); os.makedirs(os.path.join(C, "skills", "pult-dnya")); open(os.path.join(C, "skills", "pult-dnya", "SKILL.md"), "w").write("x")
OWN = "555" + "000111"
def run(prompt, env_extra=None):
    r = subprocess.run([sys.executable, G], input=json.dumps({"prompt": prompt}), capture_output=True, text=True, env={**os.environ, "CLAUDE_CONFIG_DIR": C, "OWNER_ID": OWN, "TELEGRAM_STATE_DIR": "", **(env_extra or {})}, timeout=20)
    return r.returncode, (json.loads(r.stdout)["hookSpecificOutput"]["additionalContext"] if r.stdout.strip() else "")
def chk(name, c, x=""):
    global ok, n
    n += 1; ok += bool(c); print(("✅ " if c else "❌ ") + name + ("" if c else "  ← " + str(x)[:200]))
code, h = run("пульт"); chk("«пульт» → навык pult-dnya", code == 0 and 'skill: "pult-dnya"' in h, h)
chk("«Пульт!» и «/пульт» — тоже", 'pult-dnya' in run("Пульт!")[1] and 'pult-dnya' in run("/пульт")[1])
env = '<channel source="telegram" chat_id="%s" message_id="2" user="Иван" ts="x">пульт</channel>' % OWN
chk("слово в личке владельца (конверт Telegram) — подсказка", 'pult-dnya' in run(env)[1])
grp = '<channel source="telegram" chat_id="-1009" message_id="2" user="Гость" ts="x">пульт</channel>'
chk("то же слово от гостя в группе — молчание", run(grp)[1] == "")
chk("в группе от имени «Иван» (имя можно подделать) — тоже молчание", run(grp.replace("Гость", "Иван"))[1] == "")
chk("чужая личка — молчание", run(env.replace(OWN, "555" + "000222"))[1] == "")
chk("нет OWNER_ID и в access.json не один allowFrom — молчание (не знаю владельца)", run(env, {"OWNER_ID": ""})[1] == "")
os.makedirs(os.path.join(C, "channels", "telegram")); json.dump({"allowFrom": [OWN]}, open(os.path.join(C, "channels", "telegram", "access.json"), "w"))
json.dump({"allowFrom": [OWN, "555" + "000333"]}, open(os.path.join(C, "channels", "telegram", "access.json"), "w"))
chk("нет OWNER_ID, в allowFrom двое — не знаю, кто владелец: молчание", run(env, {"OWNER_ID": ""})[1] == "")
json.dump({"allowFrom": [OWN]}, open(os.path.join(C, "channels", "telegram", "access.json"), "w"))
chk("нет OWNER_ID, но allowFrom один — он владелец", 'pult-dnya' in run(env, {"OWNER_ID": ""})[1])
chk("фраза «покажи пульт и календарь на неделю» — молчание (подсказка только на одно слово)", run("покажи пульт и календарь на неделю")[1] == "")
chk("слово есть в карте, а навыка у этой Милы нет («входящие» → inbox) — молчание", run("входящие")[1] == "")
json.dump({"календарь": "kalendar-dnya"}, open(os.path.join(C, "skill-hints.json"), "w"))
os.makedirs(os.path.join(C, "skills", "kalendar-dnya")); open(os.path.join(C, "skills", "kalendar-dnya", "SKILL.md"), "w").write("x")
chk("своя карта Милы: «календарь» → её навык", 'kalendar-dnya' in run("календарь")[1])
chk("своя карта не стирает общую: «пульт» по-прежнему работает", 'pult-dnya' in run("пульт")[1])
os.makedirs(os.path.join(C, "etc")); open(os.path.join(C, "etc", "SKILL.md"), "w").write("x")
long = "покажи пульт и календарь на неделю пожалуйста"
json.dump({"пульт": "../etc", long: "pult-dnya", "a\nb": "pult-dnya"}, open(os.path.join(C, "skill-hints.json"), "w"))
chk("имя навыка с ../ в карте — молчание (даже если файл по пути есть)", run("пульт")[1] == "")
chk("длинная фраза из карты (больше 30 знаков) — молчание", run(long)[1] == "")
chk("битый вход — код 0, молчание", subprocess.run([sys.executable, G], input="{oops", capture_output=True, text=True).returncode == 0)
print("итог %d/%d" % (ok, n)); sys.exit(0 if ok == n else 1)
