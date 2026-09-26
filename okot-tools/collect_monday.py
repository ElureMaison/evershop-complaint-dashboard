#!/usr/bin/env python3
"""
collect_monday.py — pull recent outdoorkidsot.monday.com activity.

Needs a personal API token in okot_config.json as "monday_token"
(monday.com -> avatar -> Developers -> My Access Tokens).

Two complementary feeds, because neither alone tells the whole story:
  * items    — every board item touched inside the lookback window, with its
               group, status-ish columns, and who it is assigned to.
  * updates  — the comment stream, which is where people actually say what
               happened and what they need.
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import okot_lib as L

ENDPOINT = "https://api.monday.com/v2"
API_VERSION = "2024-10"

# Column types worth showing in a digest; the rest are noise in a summary.
INTERESTING = {"status", "color", "people", "person", "multiple-person",
               "date", "timeline", "dropdown", "email", "phone", "text"}


def gql(token, query, variables=None, tries=4):
    """monday throws transient 500s and rate-limit waits; ride both out."""
    payload = {"query": query, "variables": variables or {}}
    last = None
    for attempt in range(tries):
        try:
            out = L.http(ENDPOINT, data=payload, headers={
                "Authorization": token, "API-Version": API_VERSION})
            if out.get("errors"):
                raise RuntimeError("monday GraphQL: %s" % out["errors"])
            return out["data"]
        except Exception as exc:
            last = exc
            text = str(exc)
            transient = ("INTERNAL_SERVER_ERROR" in text or "500" in text
                         or "429" in text or "Rate Limit" in text
                         or "ComplexityException" in text)
            if not transient or attempt == tries - 1:
                raise
            time.sleep(2 ** attempt * 4)
    raise last


BOARDS_Q = """
query ($page: Int!) {
  boards (limit: 50, page: $page, state: active, order_by: used_at) {
    id name url state
    workspace { id name }
    groups { id title }
  }
}"""

ITEM_FIELDS = """
        id name url created_at updated_at
        group { title }
        creator { name }
        column_values { id type text }
"""

# Server-side filter: only items touched recently. These accounts carry
# hundreds of archived onboarding boards, and pulling every item of every one
# is both slow and pointless.
# `between` is NOT a valid operator for __last_updated__ — monday answers
# `no_operator_config` and the whole query fails. greater_than is.
ITEMS_RECENT_Q = """
query ($board: ID!, $cursor: String) {
  boards (ids: [$board]) {
    items_page (limit: 100, cursor: $cursor, query_params: {
        rules: [{column_id: "__last_updated__",
                 compare_value: ["ONE_MONTH_AGO"],
                 operator: greater_than}]}) {
      cursor
      items {%s}
    }
  }
}""" % ITEM_FIELDS

# Fallback for boards that reject the filter.
# Fallback for boards that reject the filter. A smaller page: the 500s come
# from monday straining on wide boards, and 25 rows at a time survives where
# 100 does not.
ITEMS_ALL_Q = """
query ($board: ID!, $cursor: String) {
  boards (ids: [$board]) {
    items_page (limit: 25, cursor: $cursor) {
      cursor
      items {%s}
    }
  }
}""" % ITEM_FIELDS

UPDATES_Q = """
query ($page: Int!) {
  updates (limit: 100, page: $page) {
    id body text_body created_at
    creator { name email }
    item { id name url board { id name } }
  }
}"""


def strip_columns(columns):
    """Keep the handful of columns a human would read in a status report."""
    out = {}
    for col in columns or []:
        if col.get("type") in INTERESTING and (col.get("text") or "").strip():
            out[col["id"]] = col["text"].strip()[:120]
    return out


def board_items(token, board, cap=400):
    """Recent items for one board: filtered first, unfiltered as a fallback."""
    for query in (ITEMS_RECENT_Q, ITEMS_ALL_Q):
        try:
            rows, cursor = [], None
            while True:
                data = gql(token, query, {"board": board["id"], "cursor": cursor})
                page = (data.get("boards") or [{}])[0].get("items_page") or {}
                rows.extend(page.get("items") or [])
                cursor = page.get("cursor")
                if not cursor or len(rows) >= cap:
                    break
            return rows
        except Exception:
            if query is ITEMS_ALL_Q:
                raise
    return []


def collect(token):
    boards, page = [], 1
    while page <= 6:
        batch = gql(token, BOARDS_Q, {"page": page}).get("boards") or []
        boards.extend(batch)
        if len(batch) < 50:
            break
        page += 1
    print("monday: %d active boards" % len(boards))

    items, failed, scanned = [], [], 0
    for board in boards:
        scanned += 1
        if scanned % 25 == 0:
            print("  ...scanned %d/%d boards, %d items so far"
                  % (scanned, len(boards), len(items)))
        before = len(items)
        try:
            rows_all = board_items(token, board)
        except Exception as exc:
            failed.append({"board": board["name"], "error": str(exc)[:200]})
            print("  !! %s — skipped (%s)" % (board["name"][:40], str(exc)[:90]))
            continue
        for row in rows_all:
            when = L.parse_iso(row.get("updated_at") or row.get("created_at"))
            week = L.bucket(when)
            if week is None:
                continue
            created = L.parse_iso(row.get("created_at"))
            items.append({
                "kind": "item", "id": row["id"], "week": week,
                "when": L.iso(when), "created_at": L.iso(created),
                "is_new": bool(created and L.bucket(created) == week),
                "name": row.get("name") or "(untitled)",
                "url": row.get("url"),
                "board": board["name"], "board_id": board["id"],
                "board_url": board.get("url"),
                "workspace": (board.get("workspace") or {}).get("name") or "Main",
                "group": (row.get("group") or {}).get("title"),
                "creator": (row.get("creator") or {}).get("name"),
                "columns": strip_columns(row.get("column_values")),
            })
        if len(items) > before:
            print("  %-42s %d item(s) in window"
                  % (board["name"][:42], len(items) - before))

    updates, page = [], 1
    while page <= 5:
        try:
            batch = gql(token, UPDATES_Q, {"page": page}).get("updates") or []
        except Exception as exc:
            failed.append({"board": "(comment stream)", "error": str(exc)[:200]})
            print("  !! comment stream unavailable (%s)" % str(exc)[:90])
            break
        stop = False
        for row in batch:
            when = L.parse_iso(row.get("created_at"))
            week = L.bucket(when)
            if week is None:
                stop = True
                continue
            item = row.get("item") or {}
            board = item.get("board") or {}
            updates.append({
                "kind": "update", "id": row["id"], "week": week,
                "when": L.iso(when),
                "name": item.get("name") or "(deleted item)",
                "url": item.get("url"),
                "board": board.get("name") or "—", "board_id": board.get("id"),
                "author": (row.get("creator") or {}).get("name") or "someone",
                "text": (row.get("text_body") or "").strip()[:400],
            })
        if len(batch) < 100 or stop:
            break
        page += 1
    print("monday: %d comments in window" % len(updates))

    everything = items + updates
    everything.sort(key=lambda i: i["when"], reverse=True)
    # Those 500s are monday straining under a 300-board sweep, not broken
    # boards — the same queries succeed in isolation. Give the stragglers one
    # unhurried pass once the sweep is over.
    if failed:
        print("monday: retrying %d straggler board(s) after a pause" % len(failed))
        time.sleep(20)
        still = []
        for entry in failed:
            board = next((b for b in boards if b["name"] == entry["board"]), None)
            if board is None:
                still.append(entry)
                continue
            try:
                rows = board_items(token, board)
            except Exception as exc:
                still.append({"board": entry["board"], "error": str(exc)[:200]})
                print("  !! %s — still unreadable" % entry["board"][:44])
                continue
            added = 0
            for row in rows:
                when = L.parse_iso(row.get("updated_at") or row.get("created_at"))
                week = L.bucket(when)
                if week is None:
                    continue
                created = L.parse_iso(row.get("created_at"))
                items.append({
                    "kind": "item", "id": row["id"], "week": week,
                    "when": L.iso(when), "created_at": L.iso(created),
                    "is_new": bool(created and L.bucket(created) == week),
                    "name": row.get("name") or "(untitled)",
                    "url": row.get("url"),
                    "board": board["name"], "board_id": board["id"],
                    "board_url": board.get("url"),
                    "workspace": (board.get("workspace") or {}).get("name") or "Main",
                    "group": (row.get("group") or {}).get("title"),
                    "creator": (row.get("creator") or {}).get("name"),
                    "columns": strip_columns(row.get("column_values")),
                })
                added += 1
            print("  ok %s — recovered, %d item(s) in window" % (board["name"][:44], added))
        failed = still

    if failed:
        print("monday: %d board(s) could not be read" % len(failed))
    return {"source": "monday", "account": "outdoorkidsot.monday.com",
            "status": "partial" if failed else "ok",
            "skipped": failed, "collected_at": L.iso(L.now()),
            "boards": [{"id": b["id"], "name": b["name"], "url": b.get("url"),
                        "workspace": (b.get("workspace") or {}).get("name") or "Main"}
                       for b in boards],
            "items": everything}


if __name__ == "__main__":
    tok = L.config().get("monday_token")
    if not tok:
        payload = {"source": "monday", "status": "no_token", "items": [], "boards": [],
                   "collected_at": L.iso(L.now()),
                   "error": "Add monday_token to okot_config.json"}
        print("monday: no token yet — skipping", file=sys.stderr)
    else:
        try:
            payload = collect(tok)
        except Exception as exc:
            payload = {"source": "monday", "status": "error", "items": [], "boards": [],
                       "collected_at": L.iso(L.now()), "error": str(exc)[:500]}
            print("monday FAILED: %s" % exc, file=sys.stderr)
    L.save("monday.json", payload)
