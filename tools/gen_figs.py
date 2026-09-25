# -*- coding: utf-8 -*-
"""Live figures for numbers a generator computes in Python.

A generator that writes a count into prose as plain text leaves a number the
reader cannot expand. This gives each generator a namespace on the page:

    G = GenFigs("marolinta")
    html = f"... {G.fig('records', len(recs))} records ..."
    html += G.script()        # <script>GEN.marolinta = {...}</script>

Every value becomes <span data-fig="GEN.marolinta.records">13</span>, backed by
the object the region itself declares, so the figure is live on the page,
recomputed on every build, and resolves to its derivation through the rule for
its namespace in tools/render_derivations.py (DERIV_RULES).
"""
import html, json, re


def fmt(v):
    """The page's own fmt(): en-GB grouping, no forced decimals."""
    if v is None:
        return "—"
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    if isinstance(v, int):
        return f"{v:,}"
    s = f"{v:,.3f}".rstrip("0").rstrip(".")
    return s


class GenFigs:
    def __init__(self, ns):
        if not re.match(r"^[a-z][a-z0-9_]*$", ns):
            raise ValueError(ns)
        self.ns, self.vals = ns, {}

    def fig(self, key, value, text=None):
        if not re.match(r"^[a-z][a-z0-9_]*$", key):
            raise ValueError(key)
        if key in self.vals and self.vals[key] != value:
            raise ValueError(f"GEN.{self.ns}.{key} given two values")
        self.vals[key] = value
        t = fmt(value) if text is None else text
        return f'<span data-fig="GEN.{self.ns}.{key}">{html.escape(str(t), quote=False)}</span>'

    def script(self):
        return ("<script>(window.GEN=window.GEN||{})." + self.ns + "="
                + json.dumps(self.vals, ensure_ascii=False, separators=(",", ":")) + ";</script>")
