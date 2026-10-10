# -*- coding: utf-8 -*-
"""Negative test: the mWater backup must refuse every write before it is sent.

tools/mwater_backup.py may GET anything and POST only the login, /v3/clients.
This replaces urlopen with a recorder - nothing reaches the network - and
asserts that POST, PUT, PATCH and DELETE anywhere else raise RefusedWrite and
never reach urlopen, while GET and the login do.

    python3 tools/test_mwater_backup.py
"""
import os, sys, urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mwater_backup as mb  # noqa: E402

API = mb.API


def main():
    sent = []
    real = urllib.request.urlopen
    urllib.request.urlopen = lambda req, timeout=None: sent.append(
        (req.get_method(), req.full_url))
    fails = []
    try:
        allowed = [
            urllib.request.Request(f"{API}/responses?client=x"),
            urllib.request.Request(f"{API}/images/{'a' * 32}"),
            urllib.request.Request(f"{API}/clients", data=b"{}", method="POST"),
            urllib.request.Request(f"{API}/clients/", data=b"{}", method="POST"),
        ]
        refused = [urllib.request.Request(f"{API}/{p}", data=b"{}", method=m)
                   for m in ("POST", "PUT", "PATCH", "DELETE")
                   for p in ("responses", "entities/water_point", "forms/x", "clients/x")]
        refused += [urllib.request.Request(f"{API}/clients", method=m)
                    for m in ("PUT", "PATCH", "DELETE")]
        # data= without method= makes urllib send a POST
        refused.append(urllib.request.Request(f"{API}/responses", data=b"{}"))
        for req in allowed:
            n = len(sent)
            try:
                mb._send(req)
            except mb.RefusedWrite as e:
                fails.append(f"refused an allowed request: {e}")
            if len(sent) != n + 1:
                fails.append(f"allowed request not sent: {req.get_method()} {req.full_url}")
        for req in refused:
            n = len(sent)
            try:
                mb._send(req)
                fails.append(f"NOT refused: {req.get_method()} {req.full_url}")
            except mb.RefusedWrite:
                pass
            if len(sent) != n:
                fails.append(f"refused request reached urlopen: {req.get_method()} {req.full_url}")
    finally:
        urllib.request.urlopen = real
    for f in fails:
        print("  FAIL", f)
    print(f"mwater_backup guard: {len(allowed)} allowed, {len(refused)} refused, "
          f"{len(fails)} failure(s)")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
