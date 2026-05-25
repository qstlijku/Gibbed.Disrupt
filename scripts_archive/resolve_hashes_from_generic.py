"""Build a CRC32 hash->name dictionary from all Generic XMLs and apply it to
.binaryclass.xml schemas: replace `hash="HHHHHHHH"` with `name="..."` wherever
the hash matches an attribute or element name from the Generic dump.

Disrupt FCB field-name hashes are standard CRC32 of the attribute name
(case-sensitive, no normalization). The Dare editor's Generic XML export uses
the resolved names directly, so its attribute/element name set is a clean
source for resolving hashes in our schemas.

Usage:
    python resolve_hashes_from_generic.py          # apply in place
    python resolve_hashes_from_generic.py --dry    # report only
"""
import re, sys, zlib
import xml.etree.ElementTree as ET
from collections import defaultdict
from _paths import CLASSES, GENERIC

DRY = "--dry" in sys.argv

# Build hash -> name dictionary from Generic XMLs
attr_names = set()
tag_names = set()
for f in GENERIC.glob("*.xml"):
    try: root = ET.parse(f).getroot()
    except Exception: continue
    stack = [root]
    while stack:
        el = stack.pop()
        tag_names.add(el.tag)
        for k in el.attrib: attr_names.add(k)
        stack.extend(list(el))

hash_to_name = {}
collisions = defaultdict(set)
for n in attr_names | tag_names:
    h = f"{zlib.crc32(n.encode()) & 0xffffffff:08x}"
    if h in hash_to_name and hash_to_name[h] != n:
        collisions[h].add(hash_to_name[h])
        collisions[h].add(n)
    hash_to_name[h] = n

print(f"Generic XMLs: {sum(1 for _ in GENERIC.glob('*.xml'))}")
print(f"Distinct names: {len(attr_names | tag_names)}")
print(f"Hash entries: {len(hash_to_name)}  Collisions: {len(collisions)}")

HASH_RE = re.compile(r'hash="([0-9A-Fa-f]{8})"')

def repl(m):
    h = m.group(1).lower()
    n = hash_to_name.get(h)
    if n is None: return m.group(0)
    return f'name="{n.replace("&","&amp;").replace(chr(34),"&quot;").replace("<","&lt;")}"'

total_before = total_after = files_changed = 0
for f in sorted(CLASSES.glob("*.binaryclass.xml")):
    text = f.read_text(encoding="utf-8")
    before = len(HASH_RE.findall(text))
    if before == 0: continue
    new_text = HASH_RE.sub(repl, text)
    after = len(HASH_RE.findall(new_text))
    if new_text != text and not DRY:
        f.write_text(new_text, encoding="utf-8")
        files_changed += 1
    total_before += before
    total_after += after

mode = "would resolve" if DRY else "resolved"
print(f"\n{mode}: {total_before - total_after} of {total_before} occurrences "
      f"({100*(total_before-total_after)/max(total_before,1):.1f}%)")
if not DRY:
    print(f"Files changed: {files_changed}")
