"""Build a flat, sorted list of every attribute and element name found across
all Generic XMLs (including subdirectories). Output is one name per line —
algorithm-agnostic, callers can compute CRC32/FNV/etc. on the fly as needed.

Used as the dictionary source for hash resolution in .binaryclass.xml schemas
and as a brute-force corpus for unknown path resolution.
"""
import xml.etree.ElementTree as ET
from pathlib import Path

GENERIC = Path(r"C:\Users\qstli\data\Databases\Generic")
OUT = Path(r"C:\Users\qstli\Downloads\WDL\disrupt-24-04-19\bin\generic_names.txt")

names = set()
files_parsed = 0
for f in GENERIC.rglob("*.xml"):
    try: root = ET.parse(f).getroot()
    except Exception: continue
    files_parsed += 1
    stack = [root]
    while stack:
        el = stack.pop()
        names.add(el.tag)
        for k in el.attrib: names.add(k)
        stack.extend(list(el))

with OUT.open("w", encoding="utf-8") as fp:
    for n in sorted(names, key=str.lower):
        fp.write(f"{n}\n")
print(f"Parsed {files_parsed} Generic XMLs (including subdirs)")
print(f"Wrote {len(names)} names to {OUT}")
print(f"  ({OUT.stat().st_size} bytes)")
