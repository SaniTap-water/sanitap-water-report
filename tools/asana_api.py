# -*- coding: utf-8 -*-
"""Minimal Asana REST client for the water report (2 Oct 2026).

The token is read from ~/.config/sanitap/asana_token (outside the repository)
and is never printed, logged or written anywhere. Builds use only get();
tools/asana_setup.py is the one script that writes to Asana.
"""
import json, os, time, urllib.error, urllib.parse, urllib.request

TOKEN_FILE = os.path.expanduser("~/.config/sanitap/asana_token")
BASE = "https://app.asana.com/api/1.0"
WORKSPACE = "1200141858542667"
PROJECT = "1209455787942089"
SECTION_NAME = "Weekly report actions"
REPORT_URL = "https://sanitap-water.github.io/sanitap-water-report/"


def _token():
    if not os.path.isfile(TOKEN_FILE):
        raise SystemExit(f"Asana token missing: {TOKEN_FILE} - stop.")
    return open(TOKEN_FILE).read().strip()


def _call(method, path, params=None, body=None):
    url = BASE + path + ("?" + urllib.parse.urlencode(params) if params else "")
    data = json.dumps({"data": body}).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": "Bearer " + _token(), "Accept": "application/json",
        **({"Content-Type": "application/json"} if data else {})})
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            if e.code == 429 or e.code >= 500:
                time.sleep(int(e.headers.get("Retry-After", "5")))
                continue
            raise SystemExit(f"Asana {method} {path}: HTTP {e.code} {e.read().decode()[:300]}")
    raise SystemExit(f"Asana {method} {path}: gave up after retries")


def get(path, params=None):
    """GET, following pagination; returns the list (or the object)."""
    params = dict(params or {})
    out = _call("GET", path, params)
    if not isinstance(out.get("data"), list):
        return out["data"]
    items = list(out["data"])
    while out.get("next_page"):
        params["offset"] = out["next_page"]["offset"]
        out = _call("GET", path, params)
        items += out["data"]
    return items


def post(path, body):
    return _call("POST", path, body=body)["data"]


def put(path, body):
    return _call("PUT", path, body=body)["data"]
