"""Parse a ConvertBinaryObject batch run output for 'could not find binary
object file definition' warnings, then categorize each warning by whether:

  - a matching schema exists (under classes/)
  - a matching binary object file def exists (under files/)
  - a Generic XML reference exists (which means the schema could be scaffolded)
  - a matching .lib/.obj asset exists

Usage:
    python categorize_warnings.py < run_log.txt
    python categorize_warnings.py run_log.txt

If no input is given, reads stdin. Lines look like:
    Warning: could not find binary object file definition 'X'
"""
import re, sys
from pathlib import Path
from _paths import CLASSES, GENERIC, LIBS_COMMON, LIBS_PATCH

# Read warnings from stdin or file arg
text = sys.stdin.read() if len(sys.argv) < 2 else Path(sys.argv[1]).read_text(encoding="utf-8", errors="ignore")
WARN_RE = re.compile(r"could not find binary object file definition '([^']+)'")
warnings = sorted(set(WARN_RE.findall(text)))
print(f"Distinct warnings: {len(warnings)}\n")

# Build reference sets
def bare(s): return re.sub(r'_[0-9a-fA-F]{8}$', '', s).lower()

generic_names = {f.stem.lower() for f in GENERIC.glob("*.xml")}
class_names = {bare(f.stem.replace(".binaryclass","")) for f in CLASSES.glob("*.binaryclass.xml")}
files_dir = CLASSES.parent / "files"
file_def_names = {bare(f.stem.replace(".binaryobjectfile","")) for f in files_dir.glob("*.binaryobjectfile.xml")} if files_dir.exists() else set()
lib_names = ({bare(f.stem) for d in (LIBS_COMMON, LIBS_PATCH) for f in d.glob("*.lib")} |
             {bare(f.stem) for d in (LIBS_COMMON, LIBS_PATCH) for f in d.glob("*.obj")})

# Categorize
rows = []
for w in warnings:
    key = w.lower()
    rows.append({
        "name": w,
        "schema":  key in class_names,
        "filedef": key in file_def_names,
        "generic": key in generic_names,
        "asset":   key in lib_names,
    })

def fmt(row):
    return f"  S={'Y' if row['schema'] else '.'} F={'Y' if row['filedef'] else '.'} G={'Y' if row['generic'] else '.'} L={'Y' if row['asset'] else '.'}  {row['name']}"

# Bucket by status pattern
from collections import defaultdict
buckets = defaultdict(list)
for r in rows:
    key = (r["schema"], r["filedef"], r["generic"], r["asset"])
    buckets[key].append(r)

print("Legend: S=schema  F=filedef  G=Generic  L=asset(.lib/.obj)")
for (S,F,G,L), rs in sorted(buckets.items(), key=lambda kv: -len(kv[1])):
    label = ("def-able from Generic" if not S and not F and G else
             "missing entirely"     if not S and not F and not G else
             "weird (S without F)"  if S and not F else
             "everything present"   if all((S,F,G,L)) else
             "")
    print(f"\n[{len(rs)}] S={'Y' if S else '.'} F={'Y' if F else '.'} G={'Y' if G else '.'} L={'Y' if L else '.'}  {label}")
    for r in rs[:20]:
        print(f"    {r['name']}")
    if len(rs) > 20:
        print(f"    ... ({len(rs)-20} more)")
