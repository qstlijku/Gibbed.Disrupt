"""Resolve `__unknown\\0xXXXXXXXXXXXXXXXX` lib/obj filenames using two
constraints:

  1. **Lex window**: the path string is sorted alphabetically by the FAT
     unpacker, so the unknown's lex neighbors in `patch_paths.txt` tell us
     what folder + name range it falls into (typically very narrow).
  2. **CamelCase corpus**: `wdl_strings.txt` (the DLL string dump) has
     ~78k CamelCase tokens covering most engine class names. Lowercased,
     these are candidate path basenames.

For each unknown hash, intersect candidates from the corpus that fit the
lex window, then verify by computing the Disrupt FNV-1 64-bit path hash
(with the `(h & 0x1FFFFFFFFFFFFFFF) | 0xA000000000000000` transform).

Typical hit rate: 1 match per target out of 200-1400 candidates in range.
Much faster than brute-forcing the full 78k corpus.

Usage:
  Edit the TARGETS list (hash + lex_lo + lex_hi + folder) and run.
  Lex bounds come from looking up the hash in patch_paths.txt and noting
  the path strings immediately before and after.
"""
import re

WDL_STRINGS = r"C:\Users\qstli\Downloads\wdl_strings.txt"

FNV64_OFFSET = 0xcbf29ce484222325
FNV64_PRIME  = 0x100000001b3

def disrupt_path_hash(s: str) -> int:
    """Disrupt's path hash: FNV-1 64 on the lowercase path, then a final
    transform that puts the result in the `0xA0...` range."""
    s = s.lower()
    h = FNV64_OFFSET
    for b in s.encode():
        h = (h * FNV64_PRIME) & 0xffffffffffffffff
        h ^= b
    return (h & 0x1FFFFFFFFFFFFFFF) | 0xA000000000000000


# (hash, lex_lower_bound, lex_upper_bound, folder_prefix)
# Lex bounds come from neighbors in patch_paths.txt (the path immediately
# before and after the `__unknown\0xHEX` entry). Use "{" as upper bound
# for "no upper" since "{" sorts after all lowercase letters.
TARGETS = [
    # examples from this session — replace with your targets:
    # (0xB0968FC8A9306DF6, "enticercontext",  "extendedprofiler",  "generated\\databases\\generic\\"),
    # (0xA3FAF488A4E0F46B, "zombieconfig",    "{",                  "generated\\databases\\generic\\"),
    # (0xBBADC3099287FF21, "castedcharacters","censusactivitytag",  "generated\\databases\\generic\\"),
]

# Pull all CamelCase tokens from the DLL string dump
tokens = set()
with open(WDL_STRINGS, encoding="utf-8", errors="ignore") as f:
    next(f)  # skip header
    for line in f:
        parts = line.rstrip("\n").split("\t")
        if len(parts) < 4: continue
        for m in re.finditer(r'\b([A-Z][a-zA-Z0-9_]*)\b', parts[3]):
            tokens.add(m.group(1))
print(f"Loaded {len(tokens)} CamelCase tokens from {WDL_STRINGS}")

EXTENSIONS = [".obj", ".lib"]
# Common Default-suffix and bare variants. _2ce33943 = CRC32("Default")
SUFFIXES = ["", "_2ce33943"]

for target_hash, lex_lo, lex_hi, folder in TARGETS:
    print(f"\n=== 0x{target_hash:016X} (lex {lex_lo!r} < X < {lex_hi!r}) ===")
    candidates = [t for t in tokens if lex_lo < t.lower() < lex_hi]
    print(f"  Candidates in lex range: {len(candidates)}")
    hits = []
    for tok in candidates:
        low = tok.lower()
        for suf in SUFFIXES:
            for ext in EXTENSIONS:
                path = f"{folder}{low}{suf}{ext}"
                if disrupt_path_hash(path) == target_hash:
                    hits.append((tok, path))
    print(f"  Hits: {len(hits)}")
    for tok, path in hits:
        print(f"    {tok} -> {path}")
