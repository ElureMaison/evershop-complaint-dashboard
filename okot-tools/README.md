# OKOT Updates

Weekly digest of what happened across **Outdoor Kids OT**'s three systems —
the `connect@outdoorkidsot.com` Gmail inbox, `outdoorkidsot.monday.com`, and
the OKOT Trello workspaces — written the way a VA would report it: what
happened, when, who did it, and what is still waiting on us.

This project is self-contained. It shares nothing with the Evershop tooling.

## The reporting week

Weeks run **Wednesday to Wednesday**, because that is when OKOT wants its
update. The page keeps the last five of them; the newest is "This week".

## Layout

```
okot-tools/
  okot_lib.py           shared plumbing: week buckets, HTTP, config, io
  okot_gmail_auth.py    one-time OAuth, writes token_gmail_okot.json
  collect_gmail.py      inbox -> data/gmail.json
  collect_monday.py     boards + comments -> data/monday.json
  collect_trello.py     actions + due cards -> data/trello.json
  build_updates.py      merges the three -> data/updates.json
  refresh.sh            runs all four, publishes into ../site
  okot_config.json      API tokens (gitignored, not in the repo)
site/OKOT-Update/
  index.html            the page
  data.json             what the page fetches
```

Everything is Python standard library only — this Mac has no pip, no node
packages, no brew, so each collector speaks HTTP by hand.

## Setup

**1. Gmail** (one time):

```bash
python3 -u okot_gmail_auth.py      # -u matters, or the consent URL never prints
```

Approve as `connect@outdoorkidsot.com`. Writes `token_gmail_okot.json`.

**2. Monday and Trello** — copy the example config and fill it in:

```bash
cp okot_config.example.json okot_config.json
```

- `monday_token` — monday.com → avatar → **Developers** → My Access Tokens
- `trello_key` — trello.com/power-ups/admin → your integration → **API key**
- `trello_token` — the **Token** link beside that key (read access is enough)

A missing token is not an error: that collector is skipped and the page shows
the source as "Not connected yet".

## Refreshing

```bash
./refresh.sh            # what gets published — email addresses masked
./refresh.sh --full     # unmasked, for reading locally only
```

Then publish `site/OKOT-Update/` wherever the page is hosted.

## The Refresh button

The button on the page re-fetches `data.json` with a cache-buster and
re-renders. It shows whatever the **last `refresh.sh` run** published — a
static page cannot pull Gmail, Monday and Trello itself. To get genuinely new
data, run `refresh.sh` and publish, then press Refresh.

## What the page shows

Headline, four stat cards, then:

- **Summary** — bullets, problems first, each led by an absolute date. Derived
  from Trello comments, monday status columns that landed on a notable value,
  and email subjects signalling a departure or an absence.
- **Email conversations** — per thread: the topic, the sentence carrying the
  actual ask, and who the ball is with (waiting on OKOT / with them / FYI).
- Waiting on us, Monday, Trello, Inbox, and a Connections strip showing each
  source's state.

Both derived sections are heuristics in `build_updates.py`, not hand-written.
The quoted ask comes from Gmail's 320-character snippet, so a request buried
deep in a long email can be clipped.

## Masking

`build_updates.py` masks email addresses by default (`j****e@example.org`).

More importantly, **what gets published is ciphertext, not the digest**. The
page is served from a public repo, and the report carries volunteer, student
and therapist names beside real message text — a client-side gate would not
protect a file anyone can fetch directly. So the password *is* the decryption
key: `encrypt_data.js` derives it with PBKDF2-SHA256 (310k rounds) and encrypts
with AES-256-GCM; the page decrypts in the browser with Web Crypto in ~80ms. A
wrong password fails to decrypt rather than failing a comparison.

The password lives in `okot_config.json` as `page_password`. **Rotating it
means re-encrypting**, and `refresh.sh` re-encrypts on every run — so never
rotate while a collector is running, or the background job will overwrite the
file with the previous password. To confirm a rotation actually shipped,
compare the `salt` field of the live `data.json` against the local one.
