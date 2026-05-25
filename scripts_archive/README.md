# Archived schema/lib analysis scripts

One-off tools collected across sessions. Edit path constants at the top of
each script for your layout.

## Resolution

### `build_generic_names.py`
Walks every `.xml` (incl. subdirectories) under
`C:\Users\qstli\data\Databases\Generic`, collects every attribute and
element name, writes the sorted union to `bin/generic_names.txt`. That
file is the dictionary source for the resolution scripts.

### `resolve_schema_hashes.py`
Apply hash → name resolution to every `.binaryclass.xml` schema. Two
layers:
- 6 hardcoded Disrupt header CRC32 → name pairs (`disNomadObjectId`,
  `hidSingleObject`, `hidKey`, `hidValidationFailed`, `text_hidName`,
  `hidName`) — these don't appear in Generic exports so need the hardcode.
- CRC32(name) and CRC32("text_" + name) for every name in
  `generic_names.txt`. Catches the paired-field convention.

### `resolve_hashes_from_generic.py`
Older / heavier variant: walks Generic XMLs at runtime (no precomputed
list) and applies CRC32 resolution. Use this if you don't want to maintain
a separate names file.

### `resolve_unknown_lib_by_lex.py`
Brute-force resolve `__unknown\0xXXXXXXXXXXXXXXXX` lib/obj filenames using
two constraints:
1. **Lex window** — the unpacker stores entries sorted by path string,
   so lex neighbors in `UnpackLegion\patch_paths.txt` (or similar) tell
   you the folder + name range. Typically narrows the search to a few
   hundred candidates from the 78k corpus.
2. **CamelCase corpus** from `wdl_strings.txt` (DLL string dump).

Verifies hits with the Disrupt FNV-1 64-bit path hash (with the
`0xA0...` transform). High signal-to-noise — usually 1 hit per target.

Edit the `TARGETS` list with `(hash, lex_lo, lex_hi, folder_prefix)`.

## Scaffolding

### `scaffold_schemas.py`
Scaffold draft `.binaryclass.xml` + `.binaryobjectfile.xml` for classes
in `bin/common_libs_missing/` using Generic XMLs (field names) +
unpacked lib data (field hashes, structure, byte-size type inference).

### `scaffold_patch_missing.py`
Variant for `bin/patch_libs_missing/` and `bin/patch_unknown_libs/`.
Auto-detects lib vs obj format from the unpacked XML (not the filename
extension). Includes the standard Disrupt header resolution inline so
schemas with no Generic XML still get the base class header named.

## Diagnostics

### `diagnose_schema_vs_lib.py`
For one (or all) schemas, scans the matching `.lib` for every primitive
field's actual byte size and flags mismatches against the schema-declared
type. Useful for finding the bugs that trip ConvertBinaryObject:
- `Boolean` declared but data > 1 byte (likely Float / Int)
- `Float` declared but data 0/1 byte (likely Boolean) or 8 bytes (likely BinHex 8B Double)
- `Vector3` declared but data 16 bytes (should be Vector4)
- `Int16` declared but data 4 bytes (should be Int32 — the weapon `fBulletsPerClip` bug)
- `String` declared but no null terminator (likely BinHex)

### `categorize_warnings.py`
Reads a ConvertBinaryObject batch run log from stdin (or a file path)
and buckets every `could not find binary object file definition 'X'`
warning by which combination of (schema / file def / Generic / asset)
is present. Useful for triaging the "missing schema" set.

## Background

- FCB field-name hashes are standard **CRC32** of the attribute name
  as-is (case-sensitive). FNV doesn't apply at this layer.
- Lib/obj path hashes use **Disrupt FNV-1 64-bit** with a final
  `(h & 0x1FFFFFFFFFFFFFFF) | 0xA000000000000000` transform — all paths
  hash to values in the `0xA000000000000000`-`0xBFFFFFFFFFFFFFFF` range.
- Class filename suffixes like `_2ce33943` are CRC32 of "Default" (or
  another discriminator string). Same CRC32 algorithm; different
  hashed string.
- The `text_X` / `X` pair convention stores both a human-readable
  string (`text_X` = String) and its FNV64 hash (`X` = BinHex) — common
  for asset references (file paths, archetypes, etc).
