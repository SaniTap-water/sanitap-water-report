# -*- coding: utf-8 -*-
"""Live figures TYPED into prose, rather than interpolated from the data.

figure_census.py reads the rendered page and asks whether each number has a
source. This reads the SOURCE and asks a different question: was this number
typed by hand? A typed 736 and an interpolated ${fmt(S.n)} render identically
and the census cannot tell them apart - but only one of them is still correct
after the register moves.

It scans index.html outside the data blocks, and the generator scripts that
write the generated regions, since a literal typed into a generator reaches
the page just the same.

    python3 tools/typed_figures.py            # the worklist, by value
    python3 tools/typed_figures.py --list     # every occurrence with its line
"""
import json, os, re, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Lines that ARE the data. A literal here is the source of truth, not a copy.
DATA_DECL = re.compile(r"^\s*(const|let|var)\s+(S|PUMPS|ROUTES|TTR|DOWN|OPENREP|"
                       r"PARTIAL|COAST|CORR|PHOTOS|WPOP|WPOPMETA|RESP|REG|"
                       r"ENDURO|TRACE|CALLS|ACTS|PARAMS|SCOPES)\b")


def live_values():
    """value -> the expression that yields it, from the page's own data."""
    src = open(os.path.join(REPO, "index.html"), encoding="utf8").read()

    def obj(name):
        """Brace-match the literal. The data consts are concatenated onto
        shared physical lines (`...};const REG={...`), so a line-anchored
        regex finds nothing - which is how REG.succ, REG.register_total and
        the whole register chain came to be missing from the first worklist."""
        m = re.search(r"\bconst %s\s*=\s*([\{\[])" % name, src)
        if not m:
            return None
        i = m.start(1)
        open_c, close_c = m.group(1), {"{": "}", "[": "]"}[m.group(1)]
        depth, j, instr, esc = 0, i, False, False
        while j < len(src):
            ch = src[j]
            if instr:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    instr = False
            elif ch == '"':
                instr = True
            elif ch == open_c:
                depth += 1
            elif ch == close_c:
                depth -= 1
                if depth == 0:
                    break
            j += 1
        raw = src[i:j + 1]
        try:
            return json.loads(raw)
        except Exception:                                      # noqa: BLE001
            pass
        # ENDURO is a JS object literal with bare keys, not JSON
        try:
            return json.loads(re.sub(r"([{,])\s*([A-Za-z_]\w*)\s*:",
                                     r'\1"\2":', raw).replace("'", '"'))
        except Exception:                                      # noqa: BLE001
            return None

    out = {}

    def add(v, expr):
        # Below this, a bare integer in prose collides with everything -
        # page sizes, day counts, CSS. The audit's own smallest live figure
        # is 84, and a floor makes the worklist honest rather than long.
        if isinstance(v, (int, float)) and not isinstance(v, bool) and v >= 84:
            out.setdefault(int(v) if float(v).is_integer() else v, expr)

    S, REG, TTR = obj("S"), obj("REG"), obj("TTR")
    E = obj("ENDURO")
    if E:
        for k, v in E.items():
            if isinstance(v, dict):
                for k2, v2 in v.items():
                    add(v2, f"ENDURO.reg.{k2}  [TIER 3 - manual file]")
            else:
                add(v, f"ENDURO.{k}  [TIER 3 - manual file]")
    for name, o in (("S", S), ("REG", REG), ("TTR", TTR)):
        if not o:
            continue
        for k, v in o.items():
            if isinstance(v, dict):
                for k2, v2 in v.items():
                    add(v2, f"{name}.{k}['{k2}']")
            else:
                add(v, f"{name}.{k}")
    if S and REG:
        add(S["n"] + 131, "S.n + ENDURO.systems")
        add(REG["total_first_rehab"] - REG["succ"],
            "REG.total_first_rehab - REG.succ")
    # figures the page computes rather than stores
    for extra, expr in ((732, "SUCC_CORRECTED (to be computed from CORR)"),
                        (136683, "WPOP_IM500 (to be computed from WPOP)"),
                        (115074, "WPOP_C250 (to be computed from WPOP)"),
                        (727, "actively managed, computed"),
                        (731, "PUMPS excluding Marolinta"),
                        (3130, "marBasis().people"),
                        (126780, "madx scope wpop"),
                        (128221, "mad scope wpop"),
                        (867, "S.n + ENDURO.systems")):
        out.setdefault(extra, expr)
    return out


def scan():
    live = live_values()
    hits = {}
    idx = open(os.path.join(REPO, "index.html"), encoding="utf8").read()
    # The stylesheet is not prose. Blank it rather than drop it, so line
    # numbers still point at the file.
    idx = re.sub(r"<style>.*?</style>",
                 lambda m: "\n" * m.group(0).count("\n"), idx, flags=re.S)
    files = [("index.html", idx.splitlines())]
    for f in sorted(os.listdir(os.path.join(REPO, "tools"))):
        if f.startswith("render_") and f.endswith(".py"):
            files.append((f"tools/{f}",
                          open(os.path.join(REPO, "tools", f),
                               encoding="utf8").read().splitlines()))
    vals = sorted(live, key=lambda v: -v)
    pats = {v: re.compile(r"(?<![\d.,])" + f"{v:,}".replace(",", r"[,  ]?")
                          + r"(?![\d.,])") for v in vals}
    for fname, lines in files:
        for ln, line in enumerate(lines, 1):
            if DATA_DECL.match(line):
                continue
            for v in vals:
                for m in pats[v].finditer(line):
                    ctx = line[max(0, m.start() - 60):m.end() + 60]
                    if re.search(r'"[a-f0-9]{8,}"', ctx):
                        continue
                    # code, not prose: a CSS length, an array index, a
                    # colour, a coordinate
                    if re.search(r"(px|pt|rem|em|vh|vw|ms|%)\s*[;,)}]", ctx) \
                            or re.search(r"[\[\(]\s*$", line[:m.start()]) \
                            or re.search(r"^\s*[-\d.,\[\] ]+$", line):
                        continue
                    hits.setdefault(v, []).append(
                        {"file": fname, "line": ln,
                         "ctx": re.sub(r"\s+", " ", ctx).strip()[:120]})
    return live, hits


def main():
    live, hits = scan()
    n = sum(len(v) for v in hits.values())
    print()
    print(f"  LIVE FIGURES TYPED INTO PROSE - {n} occurrence(s), "
          f"{len(hits)} distinct value(s)")
    print("  " + "-" * 92)
    print(f"  {'value':>10} {'count':>6}  expression that should replace it")
    for v, hs in sorted(hits.items(), key=lambda kv: -len(kv[1])):
        byf = {}
        for h in hs:
            byf[h["file"]] = byf.get(h["file"], 0) + 1
        where = ", ".join(f"{k} x{c}" for k, c in sorted(byf.items(),
                                                        key=lambda kv: -kv[1]))
        print(f"  {v:>10,} {len(hs):>6}  {live[v]}")
        print(f"             {'':>6}  in {where}")
    if "--list" in sys.argv:
        print()
        for v, hs in sorted(hits.items(), key=lambda kv: -len(kv[1])):
            for h in hs:
                print(f"  {v:>10,}  {h['file']}:{h['line']}  {h['ctx']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
