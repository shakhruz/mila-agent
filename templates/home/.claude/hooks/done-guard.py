#!/usr/bin/env python3
"""done-guard.py — «done» only after the result: a message that says the work is done must not leave in the same model turn as
the command that does the work. A rule in the prompt does not hold this: the text is written before the result exists.

Two events, one file:
  PreToolUse on reply / edit_message, the text claims «done»:
    a) the same assistant message has a work call (Bash, Write, an MCP tool…) whose result is not in the transcript yet → deny:
       «wait for the result, then write». Works when the work call comes first in the message (Claude Code writes it to the
       transcript before the reply runs);
    b) the last work call of this turn came back with an error and nothing worked after it → deny: «write the fact». The same
       text sent a second time passes: the model looked and the error is not about this deed (grep with no match is an error too).
    The deny reason says the answer is still owed in this turn; the Stop hook reply-required keeps the turn open until it leaves.
  PostToolUseFailure on any tool — the call failed and the same assistant message already sent a «done» reply → a note to the
    model: send a correction now. Covers the other order (reply first, work second), which the first check cannot see.
Fail open: no transcript, a format it cannot read, any error → exit 0 and nothing said. This guard catches the model's mistakes;
it never stops a message on a guess about the transcript. Claim words are a short list, not a language model."""
import json, os, re, sys

CLAIM = re.compile(r"(?<![\w-])(сделал[аи]?|сделан[оа]?|готово|готова|выложил[аи]?|выложен[оа]?|отправил[аи]?|отправлен[оа]?|"
                   r"поставил[аи]?|поставлен[оа]?|исправил[аи]?|исправлен[оа]?|починил[аи]?|починен[оа]?|запустил[аи]?|запущен[оа]?|"
                   r"done|deployed|fixed|shipped|sent)(?![\w-])|✅", re.I)
NEGATED = re.compile(r"(?:^|[\s«(—-])(не|ещё не|еще не|пока не|not|not yet)\s+$", re.I)   # «ещё не готово», «не отправила»
WAITING = "⏳"   # the waiting card (step 2 of 3 ✅ build) is sent while the work runs — its ✅ marks a step, not the deed
ASKED = re.compile(r"\s*(ли(?![\w-])|\?)", re.I)   # «готово ли», «готово?» — a question, not a claim
# a plan is not a claim: «будет готово», «как будет готово», «пришлю, когда сделаю»
PLAN = re.compile(r"(будет|будут|как|когда|если)\s+(\w+\s+)?(готов|сделан|выложен|отправлен)", re.I)
SENT_WORD = re.compile(r"^(отправил[аи]?|отправлено|sent)$", re.I)
SEND = ("__reply", "__edit_message")
QUIET = ("__react", "__download_attachment")   # messaging tools that do no work
READ_ONLY = {"Read", "Glob", "Grep", "LS", "ToolSearch", "TodoWrite", "WebFetch", "WebSearch"}
TAIL = 4 << 20   # read at most the last 4 MB of the transcript
DENY_MARK = "Не отправляю «сделано»"


def claims(text, files=False):
    """True when a line says the work is done. With files attached, «sent» is about the attachment itself — the reply tool
    fails if the file is not there — so it does not count."""
    text = str(text or "")
    for line in text.splitlines():
        if PLAN.search(line):
            continue
        for m in CLAIM.finditer(line):
            if ASKED.match(line, m.end()) or NEGATED.search(line[:m.start()]) or (files and SENT_WORD.match(m.group(0))):
                continue
            if m.group(0) == "✅" and (WAITING in text or line[:m.start()].strip()):
                continue   # ✅ is a claim only at the start of a line and outside a waiting card
            return True
    return False


def work_tool(name):
    return bool(name) and name not in READ_ONLY and not name.endswith(SEND) and not name.endswith(QUIET)


def read_turn(path):
    """The current turn (since the last prompt of a person): tool_use blocks in order as (message id, block),
    and {tool_use_id: (result is not an error, result text)}."""
    with open(path, "rb") as f:
        f.seek(0, 2); size = f.tell(); f.seek(max(0, size - TAIL))
        raw = f.read().decode("utf-8", "replace").splitlines()
    uses, done = [], {}
    for line in raw:
        try:
            o = json.loads(line)
        except ValueError:
            continue
        m = o.get("message") or {}
        c = m.get("content")
        if o.get("type") == "user" and (isinstance(c, str) or (isinstance(c, list) and c and not any(
                isinstance(b, dict) and b.get("type") == "tool_result" for b in c))):
            uses = []   # a new prompt from a person starts a new turn
            continue
        if not isinstance(c, list):
            continue
        if o.get("type") == "assistant":
            uses += [(m.get("id"), b) for b in c if isinstance(b, dict) and b.get("type") == "tool_use"]
        for b in c:
            if isinstance(b, dict) and b.get("type") == "tool_result":
                done[b.get("tool_use_id")] = (not b.get("is_error"), json.dumps(b.get("content"), ensure_ascii=False))
    return uses, done


def last_message(uses):
    return [b for mid, b in uses if mid == uses[-1][0]] if uses else []


def journal(kind, tools):
    """One line per refusal or correction request in ~/.claude/mila-guard/done-guard.jsonl (600): time, kind, the tools' names —
    never the message text. So the guard's work can be counted after a rollout. A journal that cannot be written changes nothing."""
    try:
        import time
        d = os.path.join(os.environ.get("CLAUDE_CONFIG_DIR") or os.path.expanduser("~/.claude"), "mila-guard")
        os.makedirs(d, mode=0o700, exist_ok=True)
        fd = os.open(os.path.join(d, "done-guard.jsonl"), os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "kind": kind, "tools": [str(t)[:60] for t in tools][:3]},
                               ensure_ascii=False) + "\n")
    except Exception:
        pass


def deny(reason, kind="", tools=()):
    journal(kind or "deny", tools)
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                             "permissionDecisionReason": DENY_MARK + ": " + reason}}, ensure_ascii=False))


def pre(p):
    args = p.get("tool_input") or {}
    text = args.get("text")
    if not claims(text, bool(args.get("files"))):
        return
    uses, done = read_turn(p["transcript_path"])
    open_work = [b.get("name") for b in last_message(uses) if work_tool(b.get("name")) and b.get("id") not in done]
    if open_work:
        return deny("в этом же ходу ещё не вернулся результат (%s). Дождись результата, проверь его и напиши ответ — "
                    "человек ждёт его в этом же ходу." % ", ".join(open_work[:3]), "open_work", open_work)
    # the last work call of this turn that has come back failed, and nothing worked after it
    back = [b for _, b in uses if work_tool(b.get("name")) and b.get("id") in done]
    if back and not done[back[-1]["id"]][0]:
        again = any((b.get("name") or "").endswith(SEND) and (b.get("input") or {}).get("text") == text and b.get("id") in done
                    and DENY_MARK in done[b["id"]][1] for _, b in uses)
        if not again:   # the same text a second time = the model checked and the failure is not about this deed
            deny("последний вызов этого хода (%s) вернулся с ошибкой. Если дело не сделано — напиши факт и следующий шаг; "
                 "если ошибка не про это дело — отправь тот же текст ещё раз." % back[-1].get("name"), "last_failed", [back[-1].get("name")])


def post_failure(p):
    if not work_tool(p.get("tool_name")):
        return
    uses, done = read_turn(p["transcript_path"])
    uses = last_message(uses)
    # only a reply that really left: its result is in and is not an error (a reply the first check denied did not leave)
    sent = [u for u in uses if (u.get("name") or "").endswith(SEND) and done.get(u.get("id"), (False,))[0]
            and claims((u.get("input") or {}).get("text"), bool((u.get("input") or {}).get("files")))]
    if sent and any(u.get("id") == p.get("tool_use_id") for u in uses):
        chat = (sent[-1].get("input") or {}).get("chat_id")
        journal("correction", [p.get("tool_name")])
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUseFailure",
              "additionalContext": "В этом же ходу в чат %s ушло «сделано», а %s не прошёл. Это сообщение неверно: следующим "
                                   "ходом пришли туда поправку — факт и что делаешь дальше." % (chat, p.get("tool_name"))}},
              ensure_ascii=False))


if __name__ == "__main__":
    try:
        p = json.loads(sys.stdin.read())
        if isinstance(p, dict) and p.get("transcript_path") and os.path.isfile(p["transcript_path"]):
            ev, tool = p.get("hook_event_name"), p.get("tool_name") or ""
            if ev == "PreToolUse" and tool.endswith(SEND):
                pre(p)
            elif ev == "PostToolUseFailure":
                post_failure(p)
    except Exception:
        pass
    sys.exit(0)
