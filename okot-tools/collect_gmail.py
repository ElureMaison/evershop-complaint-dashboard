#!/usr/bin/env python3
"""
collect_gmail.py — pull recent OKOT inbox activity into data/gmail.json.

Reads connect@outdoorkidsot.com with the gmail.readonly token minted by
okot_gmail_auth.py. Everything here is stdlib; the access token is refreshed
on every run rather than cached.

What lands in the digest, per message: who it is from, when, the subject, a
snippet, and two judgements a VA would make by eye —
  * needs_reply: the newest message in the thread came from outside and we
    have not written back since.
  * category: a coarse bucket (volunteer / student / therapist / finance /
    scheduling / newsletter / admin) inferred from subject + sender.
"""
import base64
import json
import os
import re
import sys
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import okot_lib as L

TOKEN = os.path.join(L.HERE, "token_gmail_okot.json")
API = "https://gmail.googleapis.com/gmail/v1/users/me"
MAILBOX = "connect@outdoorkidsot.com"

# Subject/sender keywords -> the section of the report an email belongs in.
CATEGORIES = [
    ("volunteer", r"\bvolunteer|\bapplicant|\bapplication\b|\bonboard|orientation|"
                  r"background check|\bclearance\b|\bmentorship\b"),
    ("student",   r"\bstudent|\benrol|\bregistration\b|attendance|\bparent|guardian|"
                  r"\bcamp\b|\bcamps\b|session plan|\bcapstone\b"),
    ("therapist", r"therapist|\bOT\b|\bOTR\b|occupational therap|clinician|caseload|"
                  r"supervision|evaluation|\bIEP\b"),
    ("finance",   r"invoice|receipt|payment|payroll|billing|reimburse|\bquote\b|deposit|"
                  r"refund|stripe|paypal"),
    ("schedule",  r"schedul|calendar|booking|appointment|\bcancel|availability|\bshift\b|"
                  r"time-?off|\bPTO\b"),
]
# Senders that are machines, not people — never flagged as needing a reply.
NOREPLY = re.compile(r"no-?reply|do-?not-?reply|notification|notifications@|mailer-daemon|"
                     r"calendar-notification|@.*\.mailchimp|@sendgrid|@mailgun", re.I)
# Gmail's own tab classification. Promotions/Social/Forums are never a thread
# that OKOT owes someone an answer on.
BULK_LABELS = {"CATEGORY_PROMOTIONS", "CATEGORY_SOCIAL", "CATEGORY_FORUMS"}
# Vendor newsletters often carry no List-Unsubscribe and land in the Updates
# tab, so neither signal above catches them. What they do share is a generic
# role address: a real first-time enquiry comes from a person, not hello@.
ROLE_SENDER = re.compile(r"^(hello|hi|info|news|newsletter|updates?|team|marketing|"
                         r"community|digest|mail|email|contact|announce\w*|billing|"
                         r"members?|learn|blog|events?)@", re.I)


def access_token():
    if not os.path.exists(TOKEN):
        raise SystemExit("No %s — run: python3 -u okot_gmail_auth.py" % TOKEN)
    tok = json.load(open(TOKEN))
    body = urllib.parse.urlencode({
        "client_id": tok["client_id"], "client_secret": tok["client_secret"],
        "refresh_token": tok["refresh_token"], "grant_type": "refresh_token"}).encode()
    req = urllib.request.Request(tok["token_uri"], data=body,
                                 headers={"Content-Type": "application/x-www-form-urlencoded"})
    return json.loads(urllib.request.urlopen(req).read())["access_token"]


def api(path, tok):
    req = urllib.request.Request(API + path, headers={"Authorization": "Bearer " + tok})
    return json.loads(urllib.request.urlopen(req).read())


def header(msg, name):
    for h in msg.get("payload", {}).get("headers", []):
        if h["name"].lower() == name.lower():
            return h["value"]
    return ""


def pretty_from(raw):
    """'Jane Doe <jane@x.com>' -> ('Jane Doe', 'jane@x.com')"""
    match = re.match(r'\s*"?([^"<]*?)"?\s*<([^>]+)>', raw or "")
    if match:
        return match.group(1).strip() or match.group(2), match.group(2).lower()
    return (raw or "").strip(), (raw or "").strip().lower()


def categorise(subject, sender, bulk):
    """Bulk mail is 'marketing' whatever it says; the rest goes by keyword."""
    if bulk:
        return "marketing"
    blob = "%s %s" % (subject, sender)
    for name, pattern in CATEGORIES:
        if re.search(pattern, blob, re.I):
            return name
    return "admin"


def collect():
    tok = access_token()
    query = "newer_than:%dd -in:chats" % L.LOOKBACK_DAYS
    listed, page = [], None
    while True:
        path = "/messages?q=%s&maxResults=200" % urllib.parse.quote(query)
        if page:
            path += "&pageToken=" + page
        batch = api(path, tok)
        listed.extend(batch.get("messages", []))
        page = batch.get("nextPageToken")
        if not page or len(listed) >= 600:
            break

    print("gmail: %d messages in the last %dd" % (len(listed), L.LOOKBACK_DAYS))

    # Thread-level state: who spoke last, and how many messages deep it is.
    threads, items = {}, []
    for n, ref in enumerate(listed, 1):
        msg = api("/messages/%s?format=metadata"
                  "&metadataHeaders=From&metadataHeaders=Subject"
                  "&metadataHeaders=To&metadataHeaders=Date"
                  "&metadataHeaders=List-Unsubscribe" % ref["id"], tok)
        when = L.parse_iso_ms(msg.get("internalDate"))
        week = L.bucket(when)
        if week is None:
            continue
        name, addr = pretty_from(header(msg, "From"))
        labels = msg.get("labelIds", [])
        outbound = "SENT" in labels or addr.endswith("@outdoorkidsot.com")
        # A mailing list, a Promotions/Social/Forums tab, or a machine sender.
        bulk = bool(header(msg, "List-Unsubscribe")
                    or (BULK_LABELS & set(labels))
                    or NOREPLY.search(addr))
        # Deferred until thread sizes are known: a role address that has only
        # ever sent us one-off messages is a mailing list, not a correspondent.
        role = bool(ROLE_SENDER.match(addr)) and not outbound
        tid = msg.get("threadId")
        slot = threads.setdefault(tid, {"count": 0, "last": None, "last_out": None})
        slot["count"] += 1
        if slot["last"] is None or when > slot["last"]["when"]:
            slot["last"] = {"when": when, "outbound": outbound}

        items.append({
            "id": msg["id"], "thread_id": tid, "week": week,
            "when": L.iso(when), "from_name": name, "from_addr": addr,
            "subject": header(msg, "Subject") or "(no subject)",
            "snippet": (msg.get("snippet") or "").strip()[:320],
            "outbound": outbound, "unread": "UNREAD" in labels,
            "starred": "STARRED" in labels, "important": "IMPORTANT" in labels,
            "thread_size": 0, "needs_reply": False, "bulk": bulk, "role": role,
            "category": categorise(header(msg, "Subject"), addr, bulk),
        })
        if n % 50 == 0:
            print("  ...%d" % n)

    for item in items:
        slot = threads[item["thread_id"]]
        item["thread_size"] = slot["count"]
        last = slot["last"]
        # A role address that never drew a reply and never became a
        # conversation is a newsletter; treat it as bulk.
        if item["role"] and slot["count"] == 1:
            item["bulk"] = True
            item["category"] = "marketing"
        item["needs_reply"] = bool(
            not last["outbound"]
            and not item["outbound"]
            and not item["bulk"]
        )

    items.sort(key=lambda i: i["when"], reverse=True)
    return {"source": "gmail", "mailbox": MAILBOX, "status": "ok",
            "collected_at": L.iso(L.now()), "items": items}


if __name__ == "__main__":
    try:
        payload = collect()
    except SystemExit:
        raise
    except Exception as exc:
        payload = {"source": "gmail", "mailbox": MAILBOX, "status": "error",
                   "error": str(exc)[:500], "collected_at": L.iso(L.now()), "items": []}
        print("gmail FAILED: %s" % exc, file=sys.stderr)
    L.save("gmail.json", payload)
