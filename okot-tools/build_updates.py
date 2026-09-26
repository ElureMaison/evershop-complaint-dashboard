#!/usr/bin/env python3
"""
build_updates.py — turn the three raw feeds into the OKOT Updates digest.

Reads data/{gmail,monday,trello}.json, buckets everything into Wednesday
weeks, works out the things a VA would actually flag, and writes
data/updates.json — the single file the published page fetches.

Run with --full to keep email addresses unmasked. The default masks them,
because the published page sits on a public domain behind a client-side
gate only, and that gate does not stop anyone who knows the URL from
downloading this JSON.
"""
import collections
import datetime as dt
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import okot_lib as L

FULL = "--full" in sys.argv


def mask(addr):
    """jane.doe@example.org -> j****e@example.org"""
    if FULL or not addr or "@" not in addr:
        return addr
    user, _, domain = addr.partition("@")
    if len(user) <= 2:
        head = user[:1] + "*"
    else:
        head = user[0] + "*" * max(1, len(user) - 2) + user[-1]
    return "%s@%s" % (head, domain)


def soonest(cards, days=14):
    edge = L.now() + dt.timedelta(days=days)
    out = []
    for card in cards:
        due = L.parse_iso(card["due"])
        if due and not card["done"] and due <= edge:
            card = dict(card)
            card["overdue"] = due < L.now()
            card["days"] = (due.date() - L.now().date()).days
            out.append(card)
    return out



# Status values worth calling out by name in the summary, mapped to the tone
# they should carry. Anything else stays in the detail panels.
NOTABLE = {
    "accepted": "good", "approved": "good", "cleared": "good", "done": "good",
    "hired": "good", "completed": "good", "invited to interview": "good",
    "stuck": "bad", "stuck/waiting": "bad", "waiting": "bad", "blocked": "bad",
    "not started": "warn", "in progress": "warn", "pending": "warn",
    "needs screening": "warn", "declined": "bad", "rejected": "bad",
}
# Email subjects that signal a person leaving or missing a session.
LEAVING = re.compile(r"discontinu|resign|stepping down|withdraw|last day|quit", re.I)
ABSENT = re.compile(r"\bsick\b|unwell|under the weather|can'?t make it|absent|"
                    r"out today|time.?off|leave request", re.I)



# --- what an email thread is actually about -------------------------------
# Subject plus the first readable sentence carries the topic; a handful of
# phrases say who the ball is with. Coarse on purpose — the point is to spare
# the owner opening ten threads to find the two that need them.
TOPICS = [
    ("Leaving OKOT", r"discontinu|resign|withdraw|step(ping)? down|last day"),
    ("Absence", r"\bsick\b|under the weather|can'?t make it|won'?t be able|absent|time.?off"),
    ("Hours approval", r"observation hours?|volunteer hours?|hours? (approv|verif|sign)|sign off"),
    ("Contract / agreement", r"contract|agreement|\bMOU\b|affiliation|memorandum"),
    ("Capstone / fieldwork placement", r"capstone|fieldwork|\bFW\b|placement|rotation|practicum"),
    ("Interview / scheduling", r"interview|schedul|availability|confirm the time|booking|appointment"),
    ("Camp / programme dates", r"\bcamp\b|date request|school year|session dates"),
    ("Volunteer application", r"volunteer|applicant|application|apply|onboard|mentorship"),
    ("Invoice / payment", r"invoice|payment|billing|reimburse|deposit"),
]

# They have taken the next step and OKOT is waiting on them.
THEIRS = re.compile(
    r"will be in contact|will reach out|reaching out soon|will contact you|"
    r"have forward|has been forwarded|will get back|will send|once (we|they|i) (have|review)|"
    r"i('ll| will) (let you know|follow up)|is reviewing|in review|initiate a contract",
    re.I)
# They have asked OKOT for something.
OURS = re.compile(
    r"\bcould you\b|\bcan you\b|\bplease (send|fill|complete|confirm|provide|re-?attach|resend|sign)|"
    r"would love to|let me know|need (you|your)|awaiting your|requires? (a |an )?(signature|confirmation|approval)|"
    r"send over|i did not receive|looking for|want(ed)? to confirm|need to (ensure|confirm|know)|"
    r"checking in|following up|any update|is (it|this) possible|would it be",
    re.I)

QUOTED = re.compile(r"\s(From:|On .{0,60}wrote:|Sent:)\s", re.I)


def key_sentence(snippet):
    """The one line that says what they want, minus the quoted reply tail."""
    if not snippet:
        return ""
    body = QUOTED.split(snippet)[0]
    body = re.sub(r"&#39;", "'", body)
    body = re.sub(r"&(amp|lt|gt|nbsp);", " ", body)
    parts = [p.strip() for p in re.split(r"(?<=[.?!])\s+", body) if len(p.strip()) > 18]
    if not parts:
        return body.strip()[:180]
    # Prefer the sentence that carries a request or a hand-off.
    for pattern in (OURS, THEIRS):
        for part in parts:
            if pattern.search(part):
                return part[:200]
    # Otherwise skip the greeting.
    for part in parts:
        if re.match(r"^(hi|hello|hey|good (morning|afternoon)|dear|thank|thanks|"
                    r"that('s| is) (amazing|great|wonderful)|i hope)\b", part, re.I):
            continue
        if True:
            return part[:200]
    return parts[0][:200]


def conversations(gmail):
    """One row per email thread: topic, the ask, and who it is waiting on."""
    threads = {}
    for msg in gmail:
        if msg["category"] == "marketing":
            continue
        slot = threads.setdefault(msg["thread_id"], {"msgs": []})
        slot["msgs"].append(msg)

    rows = []
    for tid, slot in threads.items():
        msgs = sorted(slot["msgs"], key=lambda m: m["when"])
        inbound = [m for m in msgs if not m["outbound"]]
        if not inbound:
            continue
        newest = msgs[-1]
        newest_in = inbound[-1]
        blob = "%s %s" % (newest_in["subject"], newest_in["snippet"])

        topic = next((name for name, pat in TOPICS if re.search(pat, blob, re.I)), "General")
        line = key_sentence(newest_in["snippet"])

        if topic == "Leaving OKOT":
            waiting, state = "fyi", "Notice given — cover the sessions"
        elif topic == "Absence":
            waiting, state = "fyi", "Absence logged"
        elif not newest["outbound"]:
            if THEIRS.search(blob) and not OURS.search(blob):
                waiting, state = "them", "They are actioning it — nothing needed from OKOT yet"
            else:
                waiting, state = "okot", "Waiting on OKOT to reply"
        else:
            waiting, state = "them", "OKOT replied — waiting on them"

        rows.append({
            "thread_id": tid,
            "subject": newest_in["subject"],
            "who": newest_in["from_name"] or newest_in["from_addr"],
            "addr": newest_in["from_addr"],
            "topic": topic,
            "ask": line,
            "waiting": waiting,
            "state": state,
            "messages": len(msgs),
            "when": newest["when"],
            "last_in": newest_in["when"],
        })

    order = {"okot": 0, "fyi": 1, "them": 2}
    rows.sort(key=lambda r: r["when"], reverse=True)
    rows.sort(key=lambda r: order.get(r["waiting"], 3))
    return rows


def tidy(text):
    """Monday item names arrive with raw markdown and list bullets in them."""
    if not text:
        return text
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)      # **bold**
    text = re.sub(r"(?<!\w)[*_](.+?)[*_](?!\w)", r"\1", text)  # *italic*
    text = re.sub(r"^\s*[-*\u2022]\s+", "", text)       # leading list bullet
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def highlights(gmail, monday, trello):
    """The bullets a VA would put at the top: who did what, and what is stuck.

    Everything here is derived, not hand-written — status columns, Trello
    comments and email subjects carry most of the signal already.
    """
    out = []

    # Trello comments are the most quotable "what happened" line there is.
    for act in trello:
        if act.get("comment"):
            out.append({"kind": "trello", "tone": "good"
                        if re.search(r"clear|approv|done|complete", act["comment"], re.I)
                        else "info",
                        "who": act.get("who"), "what": tidy(act["comment"])[:180],
                        "where": act.get("card") or act.get("board"),
                        "when": act["when"]})

    # Monday status columns: the state changes that matter.
    for item in monday:
        if item.get("kind") != "item":
            continue
        for value in (item.get("columns") or {}).values():
            tone = NOTABLE.get(value.strip().lower())
            if not tone:
                continue
            out.append({"kind": "monday", "tone": tone, "who": None,
                        "what": "%s — %s" % (tidy(item["name"]), value.strip()),
                        "where": item["board"], "when": item["when"]})
            break

    # People leaving or calling in, straight from the subject line.
    for msg in gmail:
        if msg["outbound"] or msg["category"] == "marketing":
            continue
        subject = msg["subject"]
        if LEAVING.search(subject):
            out.append({"kind": "gmail", "tone": "bad",
                        "who": msg["from_name"] or msg["from_addr"],
                        "what": subject, "where": "email", "when": msg["when"]})
        elif ABSENT.search(subject):
            out.append({"kind": "gmail", "tone": "warn",
                        "who": msg["from_name"] or msg["from_addr"],
                        "what": subject, "where": "email", "when": msg["when"]})

    seen, deduped = set(), []
    for item in out:
        key = (item["what"].strip().lower(), (item["where"] or "").lower())
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)

    tone_rank = {"bad": 0, "warn": 1, "good": 2, "info": 3}
    deduped.sort(key=lambda h: (tone_rank.get(h["tone"], 4), h["when"]))
    # Problems first and in full; routine "Done" ticks are capped so they do
    # not bury them.
    urgent = [h for h in deduped if h["tone"] in ("bad", "warn")]
    rest = [h for h in deduped if h["tone"] not in ("bad", "warn")]
    return urgent + rest[:10]


def week_insights(week, gmail, monday, trello, due_cards):
    """The 'so what' layer — what a VA would put at the top of the email."""
    inbound = [m for m in gmail if not m["outbound"]]
    replies_due = [m for m in gmail if m["needs_reply"]]
    # Collapse to one entry per thread; the digest wants conversations, not messages.
    seen, threads = set(), []
    for msg in replies_due:
        if msg["thread_id"] in seen:
            continue
        seen.add(msg["thread_id"])
        threads.append(msg)

    by_cat = collections.Counter(m["category"] for m in inbound)
    senders = collections.Counter(
        (m["from_name"] or m["from_addr"]) for m in inbound)
    new_items = [i for i in monday if i.get("kind") == "item" and i.get("is_new")]
    comments = [i for i in monday if i.get("kind") == "update"]
    moves = [a for a in trello if a.get("type") == "updateCard"
             and " moved " in (a.get("text") or "")]
    new_cards = [a for a in trello if a.get("type") == "createCard"]
    card_comments = [a for a in trello if a.get("type") == "commentCard"]
    people = collections.Counter(
        a["who"] for a in trello if a.get("who"))
    people.update(i["author"] for i in comments if i.get("author"))

    headline = []
    if inbound:
        headline.append("%d email%s in" % (len(inbound), "" if len(inbound) == 1 else "s"))
    if threads:
        headline.append("%d awaiting a reply" % len(threads))
    if new_items:
        headline.append("%d new Monday item%s" % (len(new_items), "" if len(new_items) == 1 else "s"))
    if new_cards:
        headline.append("%d new Trello card%s" % (len(new_cards), "" if len(new_cards) == 1 else "s"))
    if moves:
        headline.append("%d card%s moved" % (len(moves), "" if len(moves) == 1 else "s"))

    return {
        "headline": " · ".join(headline) or "No activity recorded this week",
        "counts": {
            "email_in": len(inbound),
            "email_out": len(gmail) - len(inbound),
            "needs_reply": len(threads),
            "monday_items": len([i for i in monday if i.get("kind") == "item"]),
            "monday_new": len(new_items),
            "monday_comments": len(comments),
            "trello_actions": len(trello),
            "trello_new_cards": len(new_cards),
            "trello_moves": len(moves),
            "trello_comments": len(card_comments),
        },
        "needs_reply": [{
            "subject": m["subject"], "from": m["from_name"] or mask(m["from_addr"]),
            "addr": mask(m["from_addr"]), "when": m["when"],
            "snippet": m["snippet"], "category": m["category"],
            "thread_size": m["thread_size"],
        } for m in threads[:12]],
        "by_category": by_cat.most_common(),
        "top_senders": [{"name": n, "count": c} for n, c in senders.most_common(6)],
        "active_people": [{"name": n, "count": c} for n, c in people.most_common(8)],
        "due_soon": soonest(due_cards),
        "highlights": highlights(gmail, monday, trello),
        "conversations": conversations(gmail),
    }


def main():
    gmail = L.load("gmail.json")
    monday = L.load("monday.json")
    trello = L.load("trello.json")

    for row in monday.get("items", []):
        if row.get("name"):
            row["name"] = tidy(row["name"])

    weeks = [w.date().isoformat() for w in L.week_starts()]
    per_week = {}
    for week in weeks:
        g = [m for m in gmail.get("items", []) if m["week"] == week]
        m_ = [i for i in monday.get("items", []) if i["week"] == week]
        t = [a for a in trello.get("items", []) if a["week"] == week]
        # Due-card look-ahead only belongs on the current week.
        cards = trello.get("due_cards", []) if week == weeks[0] else []
        for row in g:
            row = row
            row["from_addr"] = mask(row["from_addr"])
        per_week[week] = {
            "gmail": g, "monday": m_, "trello": t,
            "insights": week_insights(week, g, m_, t, cards),
        }

    payload = {
        "generated_at": L.iso(L.now()),
        "current_week": weeks[0],
        "weeks": [{
            "start": w,
            "label": dt.date.fromisoformat(w).strftime("%b %-d"),
            "end_label": (dt.date.fromisoformat(w) + dt.timedelta(days=6)).strftime("%b %-d, %Y"),
            "is_current": w == weeks[0],
        } for w in weeks],
        "redacted": not FULL,
        "sources": {
            "gmail": {"status": gmail.get("status"), "error": gmail.get("error"),
                      "collected_at": gmail.get("collected_at"),
                      "mailbox": gmail.get("mailbox"),
                      "total": len(gmail.get("items", []))},
            "monday": {"status": monday.get("status"), "error": monday.get("error"),
                       "collected_at": monday.get("collected_at"),
                       "boards": monday.get("boards", []),
                       "skipped": len(monday.get("skipped", []) or []),
                       "total": len(monday.get("items", []))},
            "trello": {"status": trello.get("status"), "error": trello.get("error"),
                       "collected_at": trello.get("collected_at"),
                       "boards": trello.get("boards", []),
                       "workspaces": trello.get("workspaces", []),
                       "total": len(trello.get("items", []))},
        },
        "data": per_week,
    }
    L.save("updates.json", {"items": [], **payload})
    top = per_week[weeks[0]]["insights"]
    print("\ncurrent week %s — %s" % (weeks[0], top["headline"]))
    for source, meta in payload["sources"].items():
        print("  %-7s %-10s %d items" % (source, meta["status"], meta["total"]))


if __name__ == "__main__":
    main()
