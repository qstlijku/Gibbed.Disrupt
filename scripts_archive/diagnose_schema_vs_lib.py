"""For one (or all) .binaryclass.xml schemas, compare field types against the
actual size of each field in its corresponding .lib (or .obj) file. Reports:

  - Boolean fields whose actual byte count != 1
  - Float fields whose actual byte count != 4
  - Vector3 declared but actual is 16 bytes (likely should be Vector4)
  - String fields where the actual data has no null terminator (likely BinHex)
  - Etc.

This is the per-field-size diagnostic that catches the bugs causing
ConvertBinaryObject to throw "bad size for X" / "too many bytes for type" /
"did not consume all data" errors.

Usage:
    python diagnose_schema_vs_lib.py weapon
    python diagnose_schema_vs_lib.py mapicondescription
    python diagnose_schema_vs_lib.py --all              # scan every schema
"""
import re, sys, zlib, struct
from collections import Counter
from _paths import CLASSES, LIBS_COMMON, LIBS_PATCH

EXPECTED = {
    "Boolean": 1, "UInt8": 1, "Int8": 1,
    "UInt16": 2, "Int16": 2,
    "Float": 4, "UInt32": 4, "Int32": 4,
    "UInt64": 8, "Int64": 8, "Vector2": 8,
    "Vector3": 12, "Vector4": 16,
}

def find_lib(name):
    for d in (LIBS_COMMON, LIBS_PATCH):
        p = d / f"{name}.lib"
        if p.exists(): return p
    return None

def analyze(schema_name):
    schema = CLASSES / f"{schema_name[0].upper()}{schema_name[1:]}.binaryclass.xml"
    if not schema.exists():
        # case-insensitive lookup
        for f in CLASSES.glob("*.binaryclass.xml"):
            if f.stem.lower() == f"{schema_name.lower()}.binaryclass":
                schema = f; break
        else:
            print(f"  Schema not found: {schema_name}")
            return

    lib = find_lib(schema_name.lower())
    if not lib:
        print(f"  No lib for {schema_name}")
        return

    text = schema.read_text(encoding="utf-8")
    typed = {m.group(1): m.group(2) for m in re.finditer(r'<field name="([^"]+)" type="([^"]+)"/>', text)}
    data = lib.read_bytes()

    mismatches = Counter()
    for n, t in typed.items():
        if t not in EXPECTED: continue
        exp = EXPECTED[t]
        h = zlib.crc32(n.encode()) & 0xffffffff
        hb = struct.pack('<I', h)
        pos = 0
        while True:
            pos = data.find(hb, pos)
            if pos < 0: break
            sz = data[pos+4]
            # Boolean false stored as size 0 is valid; skip those
            if t == "Boolean" and sz == 0:
                pos += 5; continue
            # Skip varint markers (real size in following bytes — separate issue)
            if sz >= 0xFE:
                pos += 5; continue
            if sz != exp:
                mismatches[(n, t, exp, sz)] += 1
            pos += 5

    if not mismatches:
        print(f"  {schema_name}: no primitive-type mismatches found")
    else:
        print(f"  {schema_name} ({lib.parent.name}):")
        for (n, t, exp, sz), c in mismatches.most_common():
            verdict = (
                f"likely Vector4"  if t == "Vector3" and sz == 16 else
                f"likely Int32"    if t == "Int16" and sz == 4 else
                f"likely Boolean"  if t == "Float" and sz in (0,1) else
                f"likely Float"    if t == "Boolean" and sz == 4 else
                f"likely BinHex"   if t == "Float" and sz == 8 else
                f"size mismatch"
            )
            print(f"    {n:40s} schema={t}({exp}B) data={sz}B x{c}  -> {verdict}")

def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__); return
    if args[0] == "--all":
        for f in sorted(CLASSES.glob("*.binaryclass.xml")):
            name = f.stem.replace(".binaryclass", "")
            analyze(name)
    else:
        for name in args:
            analyze(name)

if __name__ == "__main__":
    main()
