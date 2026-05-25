"""Scaffold draft .binaryclass.xml and .binaryobjectfile.xml definitions for
missing classes, using Generic XMLs (for field names) and unpacked lib data
(for field hashes, structure, and value-size-based type inference).

Input:
  - bin/common_libs_missing/<name>/*.xml          (multi-export per-entry XMLs)
  - bin/common_libs_missing/<name>.lib.xml        (fallback when no subfolder)
  - generic_refs_missing_schemas/<Name>.xml       (single-file Generic class)
  - generic_refs_missing_schemas/<Name>/*.xml     (directory-form Generic class)

Output:
  - scaffolded_schemas/classes/<Name>.binaryclass.xml
  - scaffolded_schemas/files/<Name>.binaryobjectfile.xml
"""
import re, zlib, xml.etree.ElementTree as ET
from pathlib import Path
from collections import defaultdict

LIBS_MISSING = Path(r"C:\Users\qstli\Downloads\Gibbed.Disrupt-wasdennnoch\bin\common_libs_missing")
GENERIC_REFS = Path(r"C:\Users\qstli\Downloads\Gibbed.Disrupt-wasdennnoch\generic_refs_missing_schemas")
# Write directly to the canonical wasdennnoch tree so they're live for testing.
# Overwrites existing scaffolds on re-run; manually-corrected ones survive only
# if they keep the auto-generated structure.
PROJECT_ROOT = Path(r"C:\Users\qstli\Downloads\Gibbed.Disrupt-wasdennnoch\bin\projects\WDL\binary objects")
OUT_CLASSES  = PROJECT_ROOT / "classes"
OUT_FILES    = PROJECT_ROOT / "files"
for d in (OUT_CLASSES, OUT_FILES):
    d.mkdir(parents=True, exist_ok=True)


def crc32_hex(s):
    return f"{zlib.crc32(s.encode()) & 0xffffffff:08X}"


def collect_generic_names(base_lower):
    """Return set of all attribute + element names from Generic for this class.
    Handles both single .xml and directory-of-.xml forms.
    """
    names = set()
    for f in GENERIC_REFS.glob("*.xml"):
        if f.stem.lower() == base_lower:
            try:
                for el in ET.parse(f).getroot().iter():
                    names.add(el.tag)
                    for k in el.attrib:
                        names.add(k)
            except Exception:
                pass
            return names
    for d in GENERIC_REFS.iterdir():
        if d.is_dir() and d.name.lower() == base_lower:
            for f in d.glob("*.xml"):
                try:
                    for el in ET.parse(f).getroot().iter():
                        names.add(el.tag)
                        for k in el.attrib:
                            names.add(k)
                except Exception:
                    pass
            return names
    return names


REFERENCE_PREFIXES = ("file", "arch", "tag", "snd", "obj", "ev",
                       "stim", "ent", "rule", "rulesmith", "loadout",
                       "scripted", "humanconfig", "droneconfig")

# Disrupt's standard class header has two Boolean hid* fields hardcoded in the base.
# Other hid* fields are typically 8B BinHex (FNV64 hash IDs) and fall through to
# size-based inference, which handles them correctly.
HID_BOOLEANS = {"hidSingleObject", "hidValidationFailed"}

def infer_type(name, hex_values):
    """Infer field type from the field's name pattern + observed byte sizes.

    Disrupt Hungarian-style prefixes carry strong type signals. Size-based
    fallback applies when the name gives no hint. BinHex is the safe default.
    """
    nonempty = [v for v in hex_values if v]
    sizes = {len(v) // 2 for v in nonempty} if nonempty else set()
    any_empty = any(v == "" for v in hex_values)

    # ---- Name-prefix overrides (highest priority) ----
    if name:
        # text_X paired with a hash field is the resolved-name half
        if name.startswith("text_"):
            return "String"
        # Hardcoded Boolean hid* fields from the base class
        if name in HID_BOOLEANS:
            return "Boolean"
        # dis* = discriminator / hash ID (almost always BinHex; rare String exceptions)
        if name.startswith("dis"):
            if name.endswith("Name") or name.endswith("String"):
                return "String"
            return "BinHex"
        # Reference-type prefixes -> always BinHex (8B FNV64 IDs typically)
        if any(name.startswith(p) for p in REFERENCE_PREFIXES):
            return "BinHex"
        # sel* = enum/selection; small int, BinHex is safe default
        if name.startswith("sel"):
            return "BinHex"
        # color*Color = RGB/RGBA value (Vector3 or Vector4 depending on actual size)
        if name.startswith("color") and name.endswith("Color"):
            if sizes == {12}: return "Vector3"
            if sizes == {16}: return "Vector4"
            return "BinHex"  # uncertain; keep safe
        if name.startswith("color"):
            # other color* (like colorremapset) is a reference, not a color value
            return "BinHex"
        # vec2/vec3/vec4 prefixes
        if name.startswith("vec2"): return "Vector2" if sizes == {8}  else "BinHex"
        if name.startswith("vec3"): return "Vector3" if sizes == {12} else "BinHex"
        if name.startswith("vec4"): return "Vector4" if sizes == {16} else "BinHex"

    # ---- Size-based with light name hints ----
    if not sizes:
        # All empty - field exists only with size-0 (Boolean false sentinel)
        if name and name.startswith("b"): return "Boolean"
        return "Boolean"  # default for size-0-only fields

    # Mixed 0 + 1 byte is the classic Boolean (false=0B / true=1B encoding)
    if any_empty and sizes <= {1}:
        if name and name.startswith("b"): return "Boolean"
        return "BinHex"  # unknown 1-byte = BinHex (could be UInt8/Int8/Enum)

    # Variable non-zero sizes -> String (if null-terminated) or BinHex
    if len(sizes) > 1:
        if all(v.endswith("00") for v in nonempty):
            return "String"
        return "BinHex"

    sz = next(iter(sizes))
    if sz == 1:
        if name and name.startswith("b"): return "Boolean"
        return "BinHex"
    if sz == 2:
        if name and (name.startswith("i") or name.startswith("n")): return "Int16"
        if name and name.startswith("u"): return "UInt16"
        return "BinHex"
    if sz == 4:
        if name:
            if name.startswith("f"): return "Float"
            if name.startswith("u"): return "UInt32"
            if name.startswith("i") or (name.startswith("n") and not name.startswith("name") and not name.startswith("nd")):
                return "Int32"
        return "BinHex"
    if sz == 8:
        # 8B is usually FNV64 ID -> BinHex. Could also be Int64/UInt64/Double but
        # we have no Double FieldType and BinHex round-trips safely.
        return "BinHex"
    if sz == 12: return "Vector3"
    if sz == 16: return "Vector4"
    return "BinHex"


class Node:
    def __init__(self, hash_or_name):
        self.hash_or_name = hash_or_name
        self.fields = defaultdict(list)
        self.children = {}


def collect_from_entry(node, el):
    for child in el:
        if child.tag == "field":
            h = child.get("hash")
            v = (child.text or "").strip()
            if h:
                node.fields[h.upper()].append(v)
        elif child.tag == "object":
            ch = (child.get("hash") or child.get("name") or "").upper()
            if ch not in node.children:
                node.children[ch] = Node(ch)
            collect_from_entry(node.children[ch], child)


def build_type_tree(class_basename):
    subdir = LIBS_MISSING / class_basename
    entries = []
    if subdir.exists() and subdir.is_dir():
        entries = sorted(subdir.glob("*.xml"))
    else:
        for ext in (".lib.xml", ".obj.xml"):
            f = LIBS_MISSING / f"{class_basename}{ext}"
            if f.exists():
                entries = [f]
                break
    if not entries:
        return None, []
    root = None
    for p in entries:
        try:
            tree_root = ET.parse(p).getroot()
        except Exception as ex:
            print(f"    parse error {p.name}: {ex}")
            continue
        if tree_root.tag == "object" and tree_root.get("hash"):
            if root is None:
                root = Node(tree_root.get("hash").upper())
            collect_from_entry(root, tree_root)
    return root, entries


def emit_schema(node, name_dict, indent=1):
    lines = []
    pad = "\t" * indent
    for fhash, values in node.fields.items():
        nm = name_dict.get(fhash)
        t = infer_type(nm, values)
        if nm:
            lines.append(f'{pad}<field name="{nm}" type="{t}"/>')
        else:
            lines.append(f'{pad}<field hash="{fhash}" type="{t}"/>')
    for chash, child in node.children.items():
        nm = name_dict.get(chash)
        attr = f'name="{nm}"' if nm else f'hash="{chash}"'
        lines.append(f"{pad}<object {attr}>")
        lines.extend(emit_schema(child, name_dict, indent + 1))
        lines.append(f"{pad}</object>")
    return lines


def class_name_from_base(base):
    return base[0].upper() + base[1:] + "Parameters"


# Track each basename's source (lib vs obj) — they need different file-def formats
sources = {}
for f in LIBS_MISSING.glob("*.lib"):
    sources[f.stem] = "lib"
# .obj keeps its _HHHHHHHH suffix — each variant gets its own schema + file def
# (matches the rewardglobalsettings_* convention).
for f in LIBS_MISSING.glob("*.obj"):
    sources[f.stem] = "obj"

print(f"Scaffolding {len(sources)} missing classes ({sum(1 for v in sources.values() if v == 'lib')} libs, {sum(1 for v in sources.values() if v == 'obj')} objs)")
generated = 0
empty = 0
for base in sorted(sources):
    source = sources[base]
    # Generic XML is keyed by bare name (without _HHHHHHHH suffix)
    bare_name = re.sub(r"_[0-9a-fA-F]{8}$", "", base).lower()
    generic_names = collect_generic_names(bare_name)
    name_dict = {crc32_hex(n): n for n in generic_names}
    # text_X fields are an FCB-storage convention not exposed in Generic XML.
    # For every name in Generic, also add CRC32("text_<name>") -> "text_<name>"
    # so paired text_X hashes resolve correctly.
    for n in list(generic_names):
        text_name = f"text_{n}"
        name_dict[crc32_hex(text_name)] = text_name

    root, entries = build_type_tree(base)
    class_nm = class_name_from_base(base)
    file_basename = base[0].upper() + base[1:]

    if root is None or (len(root.fields) == 0 and len(root.children) == 0):
        empty += 1
        schema_lines = [
            '<?xml version="1.0" encoding="utf-8"?>',
            f'<class name="{class_nm}">',
            "\t<!-- TODO: no binary entries observed; populate from Generic XML / docs -->",
            "</class>",
        ]
        (OUT_CLASSES / f"{file_basename}.binaryclass.xml").write_text(
            "\n".join(schema_lines), encoding="utf-8"
        )
        continue

    schema_lines = [
        '<?xml version="1.0" encoding="utf-8"?>',
        f'<class name="{class_nm}">',
    ]
    schema_lines.extend(emit_schema(root, name_dict, indent=1))
    schema_lines.append("</class>")
    (OUT_CLASSES / f"{file_basename}.binaryclass.xml").write_text(
        "\n".join(schema_lines), encoding="utf-8"
    )

    # File-def format depends on source:
    # - lib: wraps in <object name="lib"> with universal entry hash 72DE4948
    # - obj: bare <object hash="..."> with the obj's actual class hash
    # File-def format depends on source:
    # - lib: wraps in <object name="lib"> with universal entry hash 72DE4948
    # - obj: bare <object hash="..."> with the obj's actual class hash
    if source == "lib":
        file_lines = [
            '<?xml version="1.0" encoding="utf-8"?>',
            f'<file name="{file_basename}">',
            '\t<object name="lib">',
            f'\t\t<object hash="{root.hash_or_name}">',
            f'\t\t\t<inherit name="{class_nm}"/>',
            "\t\t</object>",
            "\t</object>",
            "</file>",
        ]
    else:  # obj
        file_lines = [
            '<?xml version="1.0" encoding="utf-8"?>',
            f'<file name="{file_basename}">',
            f'\t<object hash="{root.hash_or_name}">',
            f'\t\t<inherit name="{class_nm}"/>',
            "\t</object>",
            "</file>",
        ]
    (OUT_FILES / f"{file_basename}.binaryobjectfile.xml").write_text(
        "\n".join(file_lines), encoding="utf-8"
    )
    generated += 1

print(f"\nGenerated {generated} schemas + {generated} file defs ({empty} empty stubs)")
print(f"Output: {PROJECT_ROOT}")
