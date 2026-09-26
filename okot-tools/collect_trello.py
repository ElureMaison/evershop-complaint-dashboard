#!/usr/bin/env python3
"""
collect_trello.py — pull recent Trello activity across the OKOT workspaces.

Needs "trello_key" and "trello_token" in okot_config.json
(key: trello.com/power-ups/admin -> your integration -> API key;
 token: the "Token" link beside it, granting read access).

Trello's `actions` feed is the closest thing any of these three tools has to
a plain-English changelog, so it carries the narrative; cards are collected
alongside it to answer "what is due and what is stuck".
"""
import datetime as dt
import os
import sys
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import okot_lib as L

API = "https://api.trello.com/1"

# Action types worth reporting. Trello emits dozens; most are chatter.
WANTED = ["createCard", "updateCard", "commentCard", "addMemberToCard",
          "removeMemberFromCard", "createList", "updateCheckItemStateOnCard",
          "addAttachmentToCard", "moveCardToBoard", "copyCard", "createBoard"]

# Plain-English rendering of each action type, for the digest line.
def describe(action):
    kind = action.get("type")
    data = action.get("data") or {}
    card = (data.get("card") or {}).get("name") or "a card"
    who = ((action.get("memberCreator") or {}).get("fullName")
           or (action.get("memberCreator") or {}).get("username") or "someone")

    if kind == "createCard":
        return "%s added %s to %s" % (who, card, (data.get("list") or {}).get("name", "a list"))
    if kind == "commentCard":
        return "%s commented on %s" % (who, card)
    if kind == "updateCard":
        old = data.get("old") or {}
        if "idList" in old:
            return "%s moved %s from %s to %s" % (
                who, card, (data.get("listBefore") or {}).get("name", "?"),
                (data.get("listAfter") or {}).get("name", "?"))
        if "due" in old:
            due = (data.get("card") or {}).get("due")
            return "%s %s the due date on %s" % (
                who, "set" if due else "cleared", card)
        if old.get("closed") is False:
            return "%s archived %s" % (who, card)
        if old.get("closed") is True:
            return "%s restored %s" % (who, card)
        if "name" in old:
            return "%s renamed a card to %s" % (who, card)
        if "desc" in old:
            return "%s edited the description on %s" % (who, card)
        return "%s updated %s" % (who, card)
    if kind == "addMemberToCard":
        return "%s assigned %s to %s" % (
            who, (data.get("member") or {}).get("name", "someone"), card)
    if kind == "removeMemberFromCard":
        return "%s unassigned someone from %s" % (who, card)
    if kind == "updateCheckItemStateOnCard":
        state = (data.get("checkItem") or {}).get("state")
        return "%s %s a checklist item on %s" % (
            who, "ticked" if state == "complete" else "un-ticked", card)
    if kind == "addAttachmentToCard":
        return "%s attached a file to %s" % (who, card)
    if kind == "createList":
        return "%s created the list %s" % (who, (data.get("list") or {}).get("name", "?"))
    if kind == "createBoard":
        return "%s created the board %s" % (who, (data.get("board") or {}).get("name", "?"))
    return "%s: %s" % (who, kind)


def call(path, key, token, **params):
    params.update({"key": key, "token": token})
    return L.http("%s%s?%s" % (API, path, urllib.parse.urlencode(params, doseq=True)))


def collect(key, token):
    since = (L.now() - dt.timedelta(days=L.LOOKBACK_DAYS)).astimezone(dt.timezone.utc)
    since_iso = since.strftime("%Y-%m-%dT%H:%M:%SZ")

    orgs = call("/members/me/organizations", key, token,
                fields="name,displayName") or []
    org_names = {o["id"]: o.get("displayName") or o.get("name") for o in orgs}

    boards = call("/members/me/boards", key, token, filter="open",
                  fields="name,url,shortUrl,idOrganization,dateLastActivity") or []
    print("trello: %d open boards across %d workspaces" % (len(boards), len(orgs)))

    items, cards_out = [], []
    for board in boards:
        workspace = org_names.get(board.get("idOrganization"), "Personal")

        actions = call("/boards/%s/actions" % board["id"], key, token,
                       limit=200, since=since_iso, filter=",".join(WANTED)) or []
        for action in actions:
            when = L.parse_iso(action.get("date"))
            week = L.bucket(when)
            if week is None:
                continue
            data = action.get("data") or {}
            card = data.get("card") or {}
            items.append({
                "kind": "action", "id": action["id"], "week": week,
                "when": L.iso(when), "type": action.get("type"),
                "text": describe(action),
                "comment": (data.get("text") or "").strip()[:400] or None,
                "card": card.get("name"),
                "url": "https://trello.com/c/%s" % card["shortLink"] if card.get("shortLink") else board.get("shortUrl"),
                "board": board["name"], "board_id": board["id"],
                "board_url": board.get("shortUrl"), "workspace": workspace,
                "who": ((action.get("memberCreator") or {}).get("fullName")
                        or (action.get("memberCreator") or {}).get("username")),
            })

        # Cards with a due date, so the digest can flag what is landing soon.
        cards = call("/boards/%s/cards" % board["id"], key, token,
                     fields="name,due,dueComplete,shortUrl,dateLastActivity,idList",
                     limit=1000) or []
        lists = {l["id"]: l["name"] for l in
                 (call("/boards/%s/lists" % board["id"], key, token, fields="name") or [])}
        for card in cards:
            due = L.parse_iso(card.get("due"))
            if not due:
                continue
            cards_out.append({
                "name": card.get("name"), "due": L.iso(due),
                "done": bool(card.get("dueComplete")),
                "list": lists.get(card.get("idList")),
                "url": card.get("shortUrl"), "board": board["name"],
                "workspace": workspace,
            })
        print("  %-42s %d actions" % (board["name"][:42],
              sum(1 for i in items if i["board_id"] == board["id"])))

    items.sort(key=lambda i: i["when"], reverse=True)
    cards_out.sort(key=lambda c: c["due"])
    return {"source": "trello", "status": "ok", "collected_at": L.iso(L.now()),
            "workspaces": sorted(set(org_names.values())),
            "boards": [{"name": b["name"], "url": b.get("shortUrl"),
                        "workspace": org_names.get(b.get("idOrganization"), "Personal")}
                       for b in boards],
            "due_cards": cards_out, "items": items}


if __name__ == "__main__":
    cfg = L.config()
    key, tok = cfg.get("trello_key"), cfg.get("trello_token")
    if not (key and tok):
        payload = {"source": "trello", "status": "no_token", "items": [],
                   "boards": [], "due_cards": [], "workspaces": [],
                   "collected_at": L.iso(L.now()),
                   "error": "Add trello_key and trello_token to okot_config.json"}
        print("trello: no key/token yet — skipping", file=sys.stderr)
    else:
        try:
            payload = collect(key, tok)
        except Exception as exc:
            payload = {"source": "trello", "status": "error", "items": [],
                       "boards": [], "due_cards": [], "workspaces": [],
                       "collected_at": L.iso(L.now()), "error": str(exc)[:500]}
            print("trello FAILED: %s" % exc, file=sys.stderr)
    L.save("trello.json", payload)
