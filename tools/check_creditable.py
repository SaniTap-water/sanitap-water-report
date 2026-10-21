# -*- coding: utf-8 -*-
"""No point that failed its SDWS 3 commissioning test is counted in the carbon portfolio.

Decision: James Walker, Head of Carbon, 20 Oct 2026 (comment on the SDWS 3
SOP): a water point that did not pass SDWS 3 is not creditable, is not part of
the carbon portfolio, and is excluded from survey frames. The rule is
data/sdws3_rule.json; tools/sdws3_creditable.py applies it.

Called from tools/check_consistency.py. It fails when:

  1. data/sdws3_creditable.json was written under another rule file (SHA-256),
     or its list differs from the rule re-applied to the SDWS 3 extract now;
  2. a not-creditable point is in the carbon fleet population
     (populations.carbon_fleet), or the carbon fleet is not the managed fleet
     less Marolinta and less those points;
  3. CARBON (data/carbon_denominator.json) counts one: carbon_points or
     carbon_by_site differ from the managed fleet less Marolinta less the
     not-creditable points;
  4. the page's carbon portfolio is not built without them: CPUMPS must leave
     out NOCREDIT.wps, the annual-cap check must multiply CARBON.carbon_by_site
     (never the managed S.by_site), and no carbon sum over the managed fleet
     less Marolinta may stand outside the Marolinta section;
  5. the collapsed list "Not creditable: failed SDWS 3" is missing, open, or
     does not list exactly the not-creditable points;
  6. the rule file or its test cases differ from the sanitap-sampler copies
     (checked when that repository is present beside this one).

    python3 tools/check_creditable.py        # prints every check, exit 1 on a failure
"""
import hashlib, json, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAMPLER = os.environ.get("SANITAP_SAMPLER", os.path.expanduser("~/sanitap-sampler"))
WHY = "James Walker, 20 Oct 2026: a point that did not pass SDWS 3 is not creditable"


def _const(idx, name):
    i = idx.index(f"\nconst {name}=")
    return json.JSONDecoder().raw_decode(idx[i + len(f"\nconst {name}="):])[0]


def run(page=os.path.join(REPO, "index.html")):
    """-> list of (name, ok, expected, actual, note), as check_consistency's check()."""
    import sdws3_creditable as SC
    import populations as P
    res = []
    idx = open(page, encoding="utf8").read()
    rule, sha = SC.load_rule()
    doc = json.load(open(SC.OUT, encoding="utf8"))
    res.append(("SDWS 3 creditable list written under the current rule file",
                doc["rule"]["sha256"] == sha, sha[:16], doc["rule"]["sha256"][:16],
                "tools/sdws3_creditable.py --write"))
    now = sorted(wp for wp, v in SC.evaluate(P._wq_results(), rule).items() if not v["creditable"])
    res.append(("SDWS 3 creditable list = the rule re-applied to the SDWS 3 extract",
                now == doc["wps"], ", ".join(now) or "none", ", ".join(doc["wps"]) or "none",
                "tools/sdws3_creditable.py --write"))
    nc = set(now)
    pumps = _const(idx, "PUMPS")
    want = {p["wp"] for p in pumps if p["site"] != "Marolinta" and p["wp"] not in nc}
    carbon = P.carbon_fleet()
    leak = sorted(carbon & nc)
    res.append(("no not-creditable point in the carbon fleet population",
                not leak, "none", ", ".join(leak) or "none", WHY))
    res.append(("carbon fleet = managed fleet less Marolinta less not creditable",
                carbon == want, len(want), len(carbon), "tools/populations.py carbon_fleet"))
    cd = json.load(open(os.path.join(REPO, "data", "carbon_denominator.json"), encoding="utf8"))
    by = {}
    for p in pumps:
        if p["wp"] in want:
            by[p["site"]] = by.get(p["site"], 0) + 1
    res.append(("CARBON counts no not-creditable point (carbon_points, carbon_by_site)",
                cd.get("carbon_points") == len(want) and cd.get("carbon_by_site") == by,
                f"{len(want)} {by}", f"{cd.get('carbon_points')} {cd.get('carbon_by_site')}",
                "tools/carbon_denominator.py --write"))
    page_cd = _const(idx, "CARBON")
    page_nc = _const(idx, "NOCREDIT")
    res.append(("the page inlines the current CARBON and NOCREDIT",
                page_cd.get("carbon_by_site") == by and page_nc.get("wps") == now,
                "current", "current" if page_cd.get("carbon_by_site") == by and page_nc.get("wps") == now else "stale",
                "tools/render_datasets.py --write"))
    cp = "const CPUMPS=PUMPS.filter(p=>p.site!=='Marolinta'&&!NOCREDIT.wps.includes(p.wp));"
    res.append(("the page's carbon portfolio (CPUMPS) leaves out NOCREDIT.wps",
                idx.count(cp) == 1, "defined once", f"{idx.count(cp)} definition(s)", WHY))
    # tonnes: the cap check multiplies carbon points, never the managed site counts
    bad_er = re.findall(r"S\.by_site\['(?:Fort-Dauphin|Maroantsetra)'\]\s*\*\s*PARAMS\.er_", idx)
    capn = "const capN={anosy:(CARBON.carbon_by_site||{})['Fort-Dauphin']||0, maro:(CARBON.carbon_by_site||{})['Maroantsetra']||0};"
    res.append(("the annual-cap tonnes multiply CARBON.carbon_by_site, not the managed S.by_site",
                not bad_er and capn in idx, "carbon counts", f"{len(bad_er)} managed product(s), capN "
                + ("on CARBON" if capn in idx else "NOT on CARBON"), WHY))
    # people: a sum over the managed fleet less Marolinta is a carbon figure only by
    # accident; outside the Marolinta section (two-district wording) it must be CPUMPS
    mb = idx.find("<!-- BEGIN GENERATED marolinta-table"); me = idx.find("<!-- END GENERATED marolinta-table")
    dv = idx.find("\nconst DERIV="); de = idx.find("\n", dv + 1)
    stray = [m.start() for m in re.finditer(r"PUMPS\.filter\(p=>p\.site!=='Marolinta'\)\.reduce\(", idx)
             if not (mb <= m.start() <= me or dv <= m.start() <= de) and idx[m.start() - 1] != "C"]
    res.append(("no carbon people sum over the managed fleet less Marolinta outside the Marolinta section",
                not stray, "0", str(len(stray)), "use CPUMPS"))
    # the collapsed list
    rb = idx.find("<!-- BEGIN GENERATED sdws3-not-creditable"); re_ = idx.find("<!-- END GENERATED sdws3-not-creditable")
    region = idx[rb:re_] if rb >= 0 and re_ > rb else ""
    listed = re.findall(r'<tr data-rid="[^"]*"><td class="mono">(\d+)</td>', region)
    res.append(("the collapsed list 'Not creditable: failed SDWS 3' lists exactly the not-creditable points",
                bool(region) and "<details " in region and " open" not in region.split(">", 2)[1]
                and sorted(listed) == now and "Not creditable: failed SDWS 3" in region,
                ", ".join(now) or "none", ", ".join(sorted(listed)) or ("MISSING" if not region else "none"),
                "tools/sdws3_creditable.py --write"))
    # the sampler carries the same rule
    for f in ("sdws3_rule.json", "sdws3_rule_cases.json"):
        ours = os.path.join(REPO, "data", f)
        theirs = os.path.join(SAMPLER, "data", f)
        if os.path.isfile(theirs):
            a = hashlib.sha256(open(ours, "rb").read()).hexdigest()
            b = hashlib.sha256(open(theirs, "rb").read()).hexdigest()
            res.append((f"data/{f} is byte-identical in sanitap-sampler", a == b, a[:16], b[:16],
                        "one rule in two repositories: change both in the same pass"))
        else:
            res.append((f"data/{f} is byte-identical in sanitap-sampler", True, "checked when present",
                        "sanitap-sampler not present here", ""))
    return res


def main():
    bad = 0
    for name, ok, exp, act, note in run():
        bad += not ok
        print(("PASS  " if ok else "FAIL  ") + name + ("" if ok else f"\n      expected {exp}, got {act}. {note}"))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
