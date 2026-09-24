# -*- coding: utf-8 -*-
"""The build's rules, read from data/build_config.json.

One file holds the values the build applies - the pump models a joining pump
must carry, the E. coli pass threshold, the WorldPop release and checksum, the
service and neighbourhood radii, the capacity caps, the roof-count factors.
The tools read them from here and the page's "How this is worked out"
footnotes render them from the same file, so a footnote cannot say one thing
while the build does another. tools/check_consistency.py asserts that the
values here are the ones actually applied, including inside the SDWS1
pipeline, which lives outside this repository.
"""
import json, os

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(REPO, "data", "build_config.json")


def load():
    return json.load(open(PATH, encoding="utf8"))
