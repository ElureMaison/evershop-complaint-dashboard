#!/usr/bin/env python3
"""
gmail_auth.py — mint a Gmail read-only token from the existing `evershop`
Google Cloud OAuth client, using nothing but the standard library.

The Mac has no pip packages, so the usual google-auth flow is unavailable.
This does the loopback OAuth dance by hand: spin up a one-shot HTTP server on
a free localhost port, send the user to Google's consent page, catch the
redirect, and swap the code for a refresh token.

Prerequisites (one-time, in console.cloud.google.com, signed in as the OKOT
admin, in a Cloud project owned by the outdoorkidsot.com organisation):
  1. APIs & Services -> Library -> Gmail API -> Enable
  2. Google Auth Platform -> Audience -> Internal  (outdoorkidsot.com is a
     Workspace domain, so Internal needs no verification and no test users)
  3. Credentials -> OAuth client ID -> Desktop app -> download the JSON and
     save it here as credentials.json

Usage:  python3 gmail_auth.py
Writes: token_gmail.json  (gitignored, same as the other secrets here)
"""
import http.server
import json
import os
import socket
import threading
import urllib.parse
import urllib.request
import webbrowser

HERE = os.path.dirname(os.path.abspath(__file__))
CLIENT = os.path.join(HERE, "credentials.json")
TOKEN = os.path.join(HERE, "token_gmail_okot.json")
SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
LOGIN_HINT = "connect@outdoorkidsot.com"

_code = {}


class Catch(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        _code.update({k: v[0] for k, v in q.items()})
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        ok = "code" in _code
        self.wfile.write(
            ("<h2>%s</h2><p>You can close this tab and go back to the terminal.</p>"
             % ("Gmail access granted." if ok else "Something went wrong: "
                + _code.get("error", "no code returned"))).encode())

    def log_message(self, *a):
        pass


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def main():
    if not os.path.exists(CLIENT):
        raise SystemExit(
            "No credentials.json in this folder.\n"
            "Download the OAuth client JSON (Desktop app) from the OKOT Cloud "
            "project and save it here as credentials.json.")
    cfg = json.load(open(CLIENT))
    c = cfg.get("installed") or cfg.get("web")
    port = free_port()
    redirect = "http://localhost:%d" % port

    srv = http.server.HTTPServer(("127.0.0.1", port), Catch)
    threading.Thread(target=srv.handle_request, daemon=True).start()

    auth_url = c["auth_uri"] + "?" + urllib.parse.urlencode({
        "client_id": c["client_id"],
        "redirect_uri": redirect,
        "response_type": "code",
        "scope": SCOPE,
        "access_type": "offline",
        "prompt": "consent",
        "login_hint": LOGIN_HINT,
    })

    print("\nOpen this URL and approve access as %s:\n" % LOGIN_HINT)
    print(auth_url + "\n")
    try:
        webbrowser.open(auth_url)
    except Exception:
        pass
    print("Waiting for the redirect...")

    for _ in range(6000):
        if _code:
            break
        import time
        time.sleep(0.1)

    if "code" not in _code:
        raise SystemExit("No authorisation code received: " + json.dumps(_code))

    body = urllib.parse.urlencode({
        "code": _code["code"],
        "client_id": c["client_id"],
        "client_secret": c["client_secret"],
        "redirect_uri": redirect,
        "grant_type": "authorization_code",
    }).encode()
    req = urllib.request.Request(c["token_uri"], data=body,
                                 headers={"Content-Type": "application/x-www-form-urlencoded"})
    tok = json.loads(urllib.request.urlopen(req).read())
    tok["client_id"] = c["client_id"]
    tok["client_secret"] = c["client_secret"]
    tok["token_uri"] = c["token_uri"]
    json.dump(tok, open(TOKEN, "w"), indent=1)
    os.chmod(TOKEN, 0o600)
    print("\nSaved %s  (refresh_token: %s)" %
          (TOKEN, "yes" if tok.get("refresh_token") else "NO - re-run with prompt=consent"))


if __name__ == "__main__":
    main()
