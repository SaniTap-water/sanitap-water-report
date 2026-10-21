#!/usr/bin/env python3
"""Decide a publish from every gate's result (20 Oct 2026).

publish.sh runs every gate to the end and records each one in
logs/gates_run.tsv (id, exit status, message, file holding its output). This
reads that file and data/gate_classes.json and:

  * prints one report of every gate, PASS or FAIL, with its class, and appends
    it to logs/gates.log;
  * writes data/provisional.json: the REVIEW gates that failed, with the lines
    of output that say why, for tools/provisional.py (the page) and
    tools/asana_setup.py --approval (the week's approval task);
  * exits 1 if any BLOCKING gate failed (nothing is published), else 0.

A gate missing from data/gate_classes.json counts as BLOCKING. A generator is
looked up as "generator" (its id is generator:<path>).

    python3 tools/gate_decide.py
"""
import datetime, json, os, re, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUN = os.path.join(REPO, "logs", "gates_run.tsv")
LOG = os.path.join(REPO, "logs", "gates.log")
CLASSES = os.path.join(REPO, "data", "gate_classes.json")
PROV = os.path.join(REPO, "data", "provisional.json")


def classes():
    return json.load(open(CLASSES, encoding="utf8"))


def class_of(gid, cl=None):
    cl = cl or classes()
    g = cl["gates"].get(gid) or cl["gates"].get(gid.split(":", 1)[0])
    return (g or {}).get("class", cl.get("default", "BLOCKING")), (g or {}).get("why", "not in data/gate_classes.json")


def detail(path, n=6):
    """The lines of a gate's output that say what failed."""
    if not path or not os.path.isfile(path):
        return []
    lines = [l.rstrip() for l in open(path, encoding="utf8", errors="replace")]
    keep = [l.strip() for l in lines
            if re.search(r"FAIL|TIMEOUT|clipped|overlapped|fewer|unread|not found|differs|missing|DRIFTED|!", l)
            and "GATE PASS" not in l and not l.strip().startswith(("ABORT", "20"))]
    return [re.sub(r"\s+", " ", l)[:240] for l in keep[:n]]


def main():
    cl = classes()
    rows = []
    for line in open(RUN, encoding="utf8"):
        p = line.rstrip("\n").split("\t")
        if len(p) >= 2 and p[0]:
            rows.append({"id": p[0], "rc": int(p[1]), "message": p[2] if len(p) > 2 else "",
                         "out": p[3] if len(p) > 3 else ""})
    blocking, review = [], []
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    out = [f"{now}  ==== gate report: {len(rows)} gate(s)"]
    for r in rows:
        k, why = class_of(r["id"], cl)
        r.update(cls=k, why=why)
        ok = r["rc"] == 0
        out.append(f"{now}  {'PASS' if ok else 'FAIL'}  {k:8s}  {r['id']}"
                   + ("" if ok else f"  - {r['message']}"))
        if not ok:
            (blocking if k == "BLOCKING" else review).append(r)
    verdict = ("NOT PUBLISHABLE: " + ", ".join(r["id"] for r in blocking) if blocking
               else "PUBLISHABLE" + (f", {len(review)} REVIEW item(s) published PROVISIONAL" if review else ""))
    out.append(f"{now}  ==== {verdict}")
    print("\n".join("  " + l.split("  ", 1)[1] for l in out))
    with open(LOG, "a", encoding="utf8") as fh:
        fh.write("\n".join(out) + "\n")
    items = [{"gate": r["id"], "why": r["why"], "message": r["message"],
              "detail": detail(r["out"])} for r in review]
    json.dump({"note": "REVIEW gates that failed in the run that built this edition "
                       "(tools/gate_decide.py); shown PROVISIONAL on the page and listed on "
                       "the week's approval task. Cleared at the start of every build.",
               "run": now, "items": items,
               "blocking": [r["id"] for r in blocking]},
              open(PROV, "w", encoding="utf8"), indent=1, ensure_ascii=False)
    for r in blocking:
        print(f"  ABORT: {r['message'] or r['id']}")
    return 1 if blocking else 0


if __name__ == "__main__":
    sys.exit(main())
