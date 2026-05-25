"""Scan .binaryclass.xml schemas that back lib/obj files in a target folder
for the misclassified pair pattern:

    <field name="text_X" type="BinHex"/>
    <field name="X" type="BinHex"/>

text_X is the text representation of an asset reference (almost always
a null-terminated string), so when its type is declared as BinHex
alongside the matching X (the 8-byte FNV64 hash), the schema is wrong
about text_X — should be String.

Scoped via the lib/obj contents of LIBS_DIR: only schemas whose
basename matches a file in that folder are scanned. This is the most
efficient form of the audit — only the schemas you actually use for a
given asset set.

READ-ONLY — only reads files, prints findings. Never writes.

Usage:
  python find_misclassified_text_pairs.py <subfolder>

<subfolder> is the name of a folder under bin/ containing .lib/.obj
files to scope the scan to. Examples:
  python find_misclassified_text_pairs.py common_libs
  python find_misclassified_text_pairs.py patch_libs_missing
"""
import re, sys
from collections import Counter
from pathlib import Path

BIN = Path(r"C:\Users\qstli\Downloads\Gibbed.Disrupt-wasdennnoch\bin")
CLASSES_DIR = BIN / "projects" / "WDL" / "binary objects" / "classes"

if len(sys.argv) < 2:
    print("Usage: python find_misclassified_text_pairs.py <subfolder>")
    print("       (subfolder is a name under bin/, e.g. common_libs)")
    sys.exit(1)
LIBS_DIR = BIN / sys.argv[1]
if not LIBS_DIR.is_dir():
    print(f"Not a directory: {LIBS_DIR}")
    sys.exit(1)

# Pair pattern: text_X with BinHex immediately followed by X with BinHex
PAT = re.compile(
    r'<field\s+name="text_([^"]+)"\s+type="BinHex"\s*/?>\s*[\r\n]+\s*<field\s+name="\1"\s+type="BinHex"'
)

# Build the set of schema basenames (PascalCase) corresponding to lib/obj files
# in LIBS_DIR. Lib basenames are the bare filename; obj basenames include the
# _HHHHHHHH discriminator suffix.
asset_basenames = set()
for ext in ("*.lib", "*.obj"):
    for f in LIBS_DIR.glob(ext):
        # Schema files are PascalCase: first char uppercased, rest unchanged
        asset_basenames.add(f.stem[0].upper() + f.stem[1:])
print(f"Lib/obj files in LIBS_DIR: {len(asset_basenames)}", flush=True)

# Filter schemas to just the ones backing those assets.
# Use replace() instead of .stem because .binaryclass.xml has two extensions
# and Path.stem only strips the last one.
schemas = sorted(s for s in CLASSES_DIR.glob("*.binaryclass.xml")
                 if s.name.replace(".binaryclass.xml", "") in asset_basenames)
total = len(schemas)
print(f"Matching schemas: {total} (of {sum(1 for _ in CLASSES_DIR.glob('*.binaryclass.xml'))} total in CLASSES_DIR)", flush=True)
print(f"Starting scan...\n", flush=True)

hits = []  # (file_path, stem_X)
for i, f in enumerate(schemas, 1):
    try:
        text = f.read_text(encoding="utf-8", errors="ignore")
    except Exception as ex:
        print(f"  [{i}/{total}] (read error) {f.name}: {ex}", flush=True)
        continue
    file_hits = list(PAT.finditer(text))
    if file_hits:
        for m in file_hits:
            hits.append((f, m.group(1)))
        print(f"  [{i}/{total}] MATCH x{len(file_hits)}  {f.name}  (e.g. text_{file_hits[0].group(1)})", flush=True)
    else:
        print(f"  [{i}/{total}] {f.name}", flush=True)

print(f"\n=== Done ===", flush=True)
print(f"Schemas scanned: {total}", flush=True)
print(f"Pattern matches: {len(hits)}", flush=True)

if hits:
    by_stem = Counter(stem for _, stem in hits)
    print(f"\nDistinct stems found ({len(by_stem)}):", flush=True)
    for stem, c in by_stem.most_common(20):
        print(f"  text_{stem} / {stem}: x{c}", flush=True)
else:
    print("No misclassified text_X/X (BinHex/BinHex) pairs found — clean.", flush=True)
