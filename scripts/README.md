# Schema / lib analysis scripts

Tooling for working with WDL `.binaryclass.xml` schemas and the FCB lib/obj
files that Gibbed.Disrupt.ConvertBinaryObject reads. Paths are set in
`_paths.py` — edit there if your layout differs.

## Scripts

### `resolve_hashes_from_generic.py`
One-shot pass: walks every `.xml` in `GENERIC`, computes CRC32 of every
attribute and element name, then rewrites `<field hash="HHHHHHHH" .../>` in
every schema under `CLASSES` to `<field name="..." .../>` when the hash
matches a known name.

```
python resolve_hashes_from_generic.py        # apply in place
python resolve_hashes_from_generic.py --dry  # report only, no writes
```

### `inventory_libs_vs_generic.py`
Cross-tabulates the three sets — Generic XMLs, unpacked assets (`.lib` +
`.obj`), and our schemas. Useful for "how many Generic classes are we missing
a schema for?", "which schemas have no backing asset?", etc. Also classifies
the orphan Generic XMLs by entry count (stub vs small vs substantive — the
latter are typically classes embedded inside parent libs).

```
python inventory_libs_vs_generic.py
```

### `categorize_warnings.py`
Reads a ConvertBinaryObject batch run log from stdin (or a file path arg) and
buckets every `could not find binary object file definition 'X'` warning by
which combination of (schema / file def / Generic / asset) is present.

```
python categorize_warnings.py < run_log.txt
python categorize_warnings.py run_log.txt
```

Legend: `S` = schema present, `F` = file def present, `G` = Generic XML
present, `L` = asset (.lib/.obj) present. The `def-able from Generic` bucket
is the immediate-win recovery target.

### `diagnose_schema_vs_lib.py`
For one (or all) schemas, scans the matching `.lib` for every primitive
field's actual size and flags mismatches against the schema-declared type.
Catches the bugs that trip ConvertBinaryObject:

- `Boolean` declared but actual size > 1 (likely Float / Int)
- `Float` declared but actual size 0/1 (likely Boolean) or 8 (likely BinHex 8B FNV64 / Double)
- `Vector3` declared but actual size 16 (should be Vector4)
- `Int16` declared but actual size 4 (should be Int32 — the weapon `fBulletsPerClip` bug)
- `String` declared but no null terminator (likely BinHex)

```
python diagnose_schema_vs_lib.py weapon
python diagnose_schema_vs_lib.py mapicondescription chasechopperparams
python diagnose_schema_vs_lib.py --all       # scan everything
```

## Background notes

- Field-name hashes in `.binaryclass.xml` are standard **CRC32** of the
  attribute name as-is (case-sensitive). FNV-1 / FNV-1a do not apply here.
- The `text_X` (String) + `X` (BinHex) pair pattern is the FCB-storage
  convention for file/asset references: text form for human-readable display
  + 8-byte FNV64 hash for engine lookup. Most schemas with file-reference
  fields follow this pattern.
- Some `<class hash="HHHHHHHH">` filename suffixes like `_2ce33943` are CRC32
  of `Default` (the variant/instance discriminator), not the class name.
- "Generic XML" = the editor's Dare-format export at the path in `_paths.py`.
  It uses resolved attribute names directly — it's the cleanest hash → name
  dictionary source.
