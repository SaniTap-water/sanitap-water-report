# -*- coding: utf-8 -*-
"""Refresh data/mwater_form_snapshot.json from the live mWater form designs.

THE ONLY PLACE THE SNAPSHOT IS EDITED. The snapshot is what
tools/check_consistency.py block 7ai asserts against, because the checker
cannot call mWater on every build: publish.sh has to work without network or
credentials. So the guarantee is two-part and it is worth being precise about
which half is which.

  * The checker guarantees, on every build, that the structure the SOPs and
    the report describe is the structure recorded in the snapshot - that the
    calendar presence question exists, that the absence-reason question is
    conditional on it, that the photograph is required when a calendar is
    present, and that no question code is duplicated within a form.
  * The snapshot guarantees only what was true when it was last fetched.

So a form edit made in the mWater designer is caught the next time this is
run, not the moment it happens. Run it whenever a form is changed, and the
failing check names what moved.

    python3 tools/refresh_form_snapshot.py               # rewrite the snapshot
    python3 tools/refresh_form_snapshot.py --check       # exit 1 if it differs
    python3 tools/refresh_form_snapshot.py --if-possible # refresh, or say why not

--if-possible is what publish.sh runs. It NEVER fails the build for being
offline - a machine with no network or no credentials still publishes, using
the snapshot it has. What it does not do is fail quietly: it prints the reason
and the age of the snapshot it is falling back on, and the consistency
checker fails the build outright once that age passes MAX_AGE_DAYS. Being
offline is allowed; publishing a week-old claim about a live form is not.

It shells out to the mwater-mcp server rather than talking to the API itself,
so there is one implementation of authentication and one of the form contract.
"""
import json, os, subprocess, sys, datetime

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "data", "mwater_form_snapshot.json")
MCP = os.path.expanduser("~/mwater-mcp")
CALLER = os.path.join(MCP, "cli_call.mjs")

FORMS = {
    "preventive-maintenance":       "de26d89a5c8a4452b42158c622be20d0",
    "repair-after-breakdown":       "958b4763788348d699e7d8c5821f92ee",
    "old-combined-works":           "86cf66efdd3749dd8a121314bab3675a",
    "point-of-use-survey":          "db0bcbf2e7ea44b280aed653a715553e",
    "water-quality-result-sdws3":   "7b33c5d7e5074808a94915939a5a0783",
    "water-quality-sampling-sdws3": "43c96af4bc4240c0b5c4402383b9c539",
    "stroke-meter":                 "8be8e0384709433795d2d0197e98275f",
    "call-centre":                  "c08b3fe26d0f42c084074701f29eb75e",
    "hygiene-promotion":            "283c5670de82489d833e986cb76a67d8",
    "beneficiary-roof-count":       "8aa2dd78eb1f460f8f43db7935955846",
    "marolinta-borehole-progress":  "8764843c94484f5b984078c68f13b2ca",
    "premiere-rehabilitation":      "63747997e70e478fbb2ebf71581ceeb0",
}


sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_config as _bc  # noqa: E402
# from data/build_config.json, which the page renders
MAX_AGE_DAYS = _bc.load()["form_snapshot"]["max_age_days"]


class Unavailable(Exception):
    """mWater cannot be reached from here - not a build failure by itself."""


def snapshot_age():
    if not os.path.exists(OUT):
        return None
    try:
        f = json.load(open(OUT, encoding="utf8")).get("fetched")
        return (datetime.date.today() - datetime.date.fromisoformat(f)).days
    except Exception:
        return None


def fetch(form_id):
    if not os.path.isfile(CALLER):
        raise Unavailable(f"{CALLER} is not present")
    r = subprocess.run(["node", CALLER, "mwater_get_form_design",
                        json.dumps({"form_id": form_id})],
                       capture_output=True, text=True, cwd=MCP)
    err = (r.stderr or "") + (r.stdout or "")
    if r.returncode != 0 or "{" not in r.stdout:
        low = err.lower()
        if any(k in low for k in ("enotfound", "econnrefused", "etimedout", "network",
                                  "getaddrinfo", "unauthorized", "401", "credentials",
                                  "no such file", "cannot find module", "econnreset")):
            raise Unavailable(err.strip()[:200] or "mWater unreachable")
        sys.exit(f"mwater call failed for {form_id}: {err.strip()[:300]}")
    s = r.stdout[r.stdout.index("{"):]
    return json.loads(s)


def questions(design):
    out = []

    def walk(n, group=None):
        if isinstance(n, dict):
            if n.get("_type") in ("Group", "RosterGroup", "RosterMatrix"):
                nm = n.get("name")
                group = (nm.get("en") or nm.get("fr")) if isinstance(nm, dict) else group
            t = n.get("_type")
            if isinstance(t, str) and t.endswith("Question"):
                out.append({"code": n.get("code"), "id": n["_id"], "type": t,
                            "required": bool(n.get("required")),
                            "conditions": n.get("conditions") or [],
                            "group": group,
                            "en": (n.get("text") or {}).get("en", ""),
                            "fr": (n.get("text") or {}).get("fr", "")})
            for v in n.values():
                walk(v, group)
        elif isinstance(n, list):
            for v in n:
                walk(v, group)

    walk(design)
    return out


def build():
    snap = {"fetched": datetime.date.today().isoformat(), "forms": {}}
    for name, fid in FORMS.items():
        d = fetch(fid)
        snap["forms"][name] = {
            "id": d["_id"], "rev": d.get("_rev"), "state": d.get("state"),
            "locales": d.get("locales"),
            "deployments": [{"name": x.get("name"), "active": bool(x.get("active"))}
                            for x in d.get("deployments", [])],
            "questions": questions(d["design"]),
        }
    return snap


def main():
    if "--if-possible" in sys.argv[1:]:
        age = snapshot_age()
        try:
            snap = build()
        except Unavailable as e:
            have = "no snapshot at all" if age is None else f"{age} day(s) old"
            print(f"  mWater not reachable from here: {e}")
            print(f"  falling back on the committed snapshot ({have}).")
            if age is not None and age > MAX_AGE_DAYS:
                print(f"  NOTE: that is past the {MAX_AGE_DAYS}-day limit; "
                      f"the consistency checker will fail this build.")
            return 0
        new = json.dumps(snap, ensure_ascii=False, indent=1, sort_keys=True)
        old = open(OUT, encoding="utf8").read() if os.path.exists(OUT) else ""
        open(OUT, "w", encoding="utf8").write(new)
        a = json.loads(old or "{}"); a.pop("fetched", None)
        b = json.loads(new); b.pop("fetched", None)
        print(f"  mWater form snapshot refreshed ({len(snap['forms'])} forms)"
              + ("; the designs have not changed." if a == b
                 else "; A FORM HAS CHANGED since the last build."))
        if a != b:
            for f in sorted(set(a.get("forms", {})) | set(b.get("forms", {}))):
                if a.get("forms", {}).get(f) != b.get("forms", {}).get(f):
                    print(f"    {f}: rev {(a.get('forms', {}).get(f) or {}).get('rev')}"
                          f" -> {(b.get('forms', {}).get(f) or {}).get('rev')}")
        return 0
    check = "--check" in sys.argv[1:]
    snap = build()
    new = json.dumps(snap, ensure_ascii=False, indent=1, sort_keys=True)
    old = open(OUT, encoding="utf8").read() if os.path.exists(OUT) else ""
    if check:
        # the fetch date always moves; compare everything else
        a = json.loads(old or "{}"); a.pop("fetched", None)
        b = json.loads(new); b.pop("fetched", None)
        if a == b:
            print("snapshot matches the live forms")
            return 0
        print("the live forms differ from data/mwater_form_snapshot.json")
        for f in sorted(set(a.get("forms", {})) | set(b.get("forms", {}))):
            if a.get("forms", {}).get(f) != b.get("forms", {}).get(f):
                ra = (a.get("forms", {}).get(f) or {}).get("rev")
                rb = (b.get("forms", {}).get(f) or {}).get("rev")
                print(f"  {f}: snapshot rev {ra} -> live rev {rb}")
        print("run: python3 tools/refresh_form_snapshot.py")
        return 1
    open(OUT, "w", encoding="utf8").write(new)
    print(f"wrote {OUT} ({len(new):,} bytes, {len(snap['forms'])} forms, "
          f"{sum(len(v['questions']) for v in snap['forms'].values())} questions)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
