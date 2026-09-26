#!/usr/bin/env python3
"""
okot_lib.py — shared plumbing for the OKOT Updates digest.

Standard library only: this Mac has no pip, no node, no brew, so every
collector talks HTTP by hand (same constraint the evershop-tools scripts
were written under).

The reporting week runs Wednesday -> Wednesday, because that is when OKOT
wants its update. `week_starts()` hands back those anchors newest-first so
collectors can bucket anything they find into the right week.
"""
import datetime as dt
import json
import os
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
CONFIG = os.path.join(HERE, "okot_config.json")

WEEKS_KEPT = 3              # how many Wednesday weeks the digest reports
LOOKBACK_DAYS = 24          # covers WEEKS_KEPT anchors from any weekday, plus slack
WEEK_ANCHOR = 2             # Monday=0 ... Wednesday=2


def config():
    """Tokens live outside git. Missing file is not fatal — collectors skip."""
    if not os.path.exists(CONFIG):
        return {}
    with open(CONFIG) as fh:
        return json.load(fh)


def now():
    return dt.datetime.now().astimezone()


def last_anchor(when=None):
    """The most recent Wednesday 00:00 at or before `when`."""
    when = when or now()
    midnight = when.replace(hour=0, minute=0, second=0, microsecond=0)
    back = (midnight.weekday() - WEEK_ANCHOR) % 7
    return midnight - dt.timedelta(days=back)


def week_starts(count=WEEKS_KEPT):
    """Wednesday anchors, newest first."""
    top = last_anchor()
    return [top - dt.timedelta(days=7 * i) for i in range(count)]


def bucket(when):
    """Label the Wednesday-week an event belongs to, or None if too old."""
    if when is None:
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=now().tzinfo)
    for start in week_starts():
        if when >= start:
            return start.date().isoformat()
    return None


def iso(when):
    return when.isoformat() if when else None


def parse_iso(text):
    """Tolerant ISO-8601 parse — the three APIs each spell it differently."""
    if not text:
        return None
    text = text.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        stamp = dt.datetime.fromisoformat(text)
    except ValueError:
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                stamp = dt.datetime.strptime(text, fmt)
                break
            except ValueError:
                continue
        else:
            return None
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=dt.timezone.utc)
    return stamp.astimezone()


def parse_iso_ms(millis):
    """Gmail hands back internalDate as epoch milliseconds, as a string."""
    if not millis:
        return None
    return dt.datetime.fromtimestamp(int(millis) / 1000).astimezone()


def http(url, data=None, headers=None, method=None):
    headers = dict(headers or {})
    if isinstance(data, (dict, list)):
        data = json.dumps(data).encode()
        headers.setdefault("Content-Type", "application/json")
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read() or b"null")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")[:600]
        raise RuntimeError("HTTP %s %s\n%s" % (exc.code, url.split("?")[0], body))


def save(name, payload):
    os.makedirs(DATA, exist_ok=True)
    path = os.path.join(DATA, name)
    with open(path, "w") as fh:
        json.dump(payload, fh, indent=1, ensure_ascii=False)
    print("wrote %s (%d items)" % (path, len(payload.get("items", []))))
    return path


def load(name):
    path = os.path.join(DATA, name)
    if not os.path.exists(path):
        return {"items": [], "collected_at": None, "status": "missing"}
    with open(path) as fh:
        return json.load(fh)
