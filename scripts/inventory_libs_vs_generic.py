"""Cross-tabulate three sets: Generic XMLs, unpacked asset files (.lib + .obj),
and our binary class schemas. Reports what's covered, what's missing, and
where the gaps overlap.

Generic XML  = Dare editor's exported attribute schemas (authoritative naming)
.lib / .obj  = Unpacked FCB asset files from common + patch
.binaryclass = Our schema definitions for the binary object reader

Useful for answering:
  - How many Generic classes are there that we don't have schemas for?
  - How many .lib files are there that have no Generic reference?
  - How many of our schemas have no backing data anywhere?
  - Which orphans are stubs vs substantive?
"""
import re
import xml.etree.ElementTree as ET
from _paths import CLASSES, GENERIC, LIBS_COMMON, LIBS_PATCH

def bare(stem):
    """Strip trailing _HHHHHHHH discriminator suffix; lowercase."""
    return re.sub(r'_[0-9a-fA-F]{8}$', '', stem).lower()

# Build name sets
# Generic classes can be either a single <Name>.xml file OR a <Name>/ directory of per-entry XMLs.
generic_names = {f.stem.lower() for f in GENERIC.glob("*.xml")}
generic_names |= {d.name.lower() for d in GENERIC.iterdir() if d.is_dir()}
asset_names = set()
for d in (LIBS_COMMON, LIBS_PATCH):
    for ext in ("*.lib", "*.obj"):
        for f in d.glob(ext):
            asset_names.add(bare(f.stem))
schema_names = {bare(f.stem.replace(".binaryclass","")) for f in CLASSES.glob("*.binaryclass.xml")}

print(f"Generic XMLs:     {len(generic_names)}")
print(f"Asset files:      {len(asset_names)}  (.lib + .obj, suffix-stripped)")
print(f"Schemas:          {len(schema_names)}")
print()

# Cross-tab
g_a   = generic_names & asset_names
g_s   = generic_names & schema_names
a_s   = asset_names & schema_names
g_a_s = generic_names & asset_names & schema_names

g_only      = generic_names - asset_names - schema_names
a_only      = asset_names - generic_names - schema_names
s_only      = schema_names - generic_names - asset_names
g_a_no_s    = (generic_names & asset_names) - schema_names
g_s_no_a    = (generic_names & schema_names) - asset_names
a_s_no_g    = (asset_names & schema_names) - generic_names

print("Triple-set crosstab:")
print(f"  in ALL three (G & A & S):                 {len(g_a_s)}  <- complete coverage")
print(f"  Generic+Asset, no schema  (gap = define): {len(g_a_no_s)}")
print(f"  Generic+Schema, no asset  (orphan schema):{len(g_s_no_a)}")
print(f"  Asset+Schema, not in Generic:             {len(a_s_no_g)}")
print(f"  Generic only:                             {len(g_only)}")
print(f"  Asset only:                               {len(a_only)}")
print(f"  Schema only:                              {len(s_only)}")
print()

# Detail on the "Generic+Asset, no schema" set — these would warn at runtime
print(f"=== Generic+Asset but NO schema (would warn — {len(g_a_no_s)}) ===")
for n in sorted(g_a_no_s):
    print(f"  {n}")

# Detail on substantive orphan Generic XMLs (likely embedded-in-parent classes)
print(f"\n=== Generic-only Generic XMLs (no asset, no schema), classified by size ===")
stub = small = big = 0
sample_big = []
for f in GENERIC.glob("*.xml"):
    if f.stem.lower() not in g_only: continue
    try: root = ET.parse(f).getroot()
    except Exception: continue
    n = len(list(root))
    if n == 0: stub += 1
    elif n <= 2: small += 1
    else:
        big += 1
        sample_big.append((f.stem, n))
print(f"  empty stub:          {stub}")
print(f"  small (1-2 entries): {small}")
print(f"  larger (3+):         {big}  <- likely classes embedded in parent libs")
for name, n in sorted(sample_big, key=lambda x: -x[1])[:15]:
    print(f"    {n:5d} entries  {name}")
