"""One-off: scaffold patch_libs_missing + patch_unknown_libs items, with the
6 standard Disrupt header hashes resolved. Also post-processes ALL existing
schemas to resolve those headers wherever they remain as bare hashes.

Format (lib wrapper vs bare obj) is detected from the .lib.xml/.obj.xml
content (root tag), not the file extension — so misnamed .lib files
holding obj structures still get the right file-def format.
"""
import re, shutil
import xml.etree.ElementTree as ET
from pathlib import Path
from collections import defaultdict

PROJECT_ROOT = Path(r"C:\Users\qstli\Downloads\Gibbed.Disrupt-wasdennnoch\bin\projects\WDL\binary objects")
CLASSES = PROJECT_ROOT / "classes"
FILES   = PROJECT_ROOT / "files"
GTC_C   = Path(r"C:\Users\qstli\Downloads\Gibbed Tools copy\Gibbed Tools\projects\WDL\binary objects\classes")
GTC_F   = Path(r"C:\Users\qstli\Downloads\Gibbed Tools copy\Gibbed Tools\projects\WDL\binary objects\files")

SOURCE_DIRS = [
    Path(r"C:\Users\qstli\Downloads\Gibbed.Disrupt-wasdennnoch\bin\patch_libs_missing"),
    Path(r"C:\Users\qstli\Downloads\Gibbed.Disrupt-wasdennnoch\bin\patch_unknown_libs"),
]

HEADER_NAMES = {
    "1FE8D41C": ("disNomadObjectId", "BinHex"),
    "61FC6B02": ("hidSingleObject", "Boolean"),
    "389F6DA7": ("hidKey", "BinHex"),
    "A788914C": ("hidValidationFailed", "Boolean"),
    "9D8873F8": ("text_hidName", "String"),
    "B9295CC7": ("hidName", "BinHex"),
}


def infer_type(hex_values):
    nonempty = [v for v in hex_values if v]
    sizes = {len(v) // 2 for v in nonempty} if nonempty else set()
    any_empty = any(v == "" for v in hex_values)
    if not sizes: return "Boolean"
    if any_empty and sizes <= {1}: return "BinHex"
    if len(sizes) > 1:
        if all(v.endswith("00") for v in nonempty): return "String"
        return "BinHex"
    sz = next(iter(sizes))
    if sz == 1: return "BinHex"
    if sz == 12: return "Vector3"
    if sz == 16: return "Vector4"
    return "BinHex"


class Node:
    def __init__(self, key):
        self.key = key
        self.fields = defaultdict(list)
        self.children = {}


def collect(node, el):
    for child in el:
        if child.tag == "field":
            h = (child.get("hash") or "").upper()
            v = (child.text or "").strip()
            if h: node.fields[h].append(v)
        elif child.tag == "object":
            k = (child.get("hash") or child.get("name") or "").upper()
            if k not in node.children:
                node.children[k] = Node(k)
            collect(node.children[k], child)


def emit(node, indent=1):
    pad = "\t" * indent
    out = []
    for h, vs in node.fields.items():
        if h in HEADER_NAMES:
            nm, t = HEADER_NAMES[h]
            out.append(f'{pad}<field name="{nm}" type="{t}"/>')
        else:
            out.append(f'{pad}<field hash="{h}" type="{infer_type(vs)}"/>')
    for k, ch in node.children.items():
        out.append(f'{pad}<object hash="{k}">')
        out.extend(emit(ch, indent+1))
        out.append(f'{pad}</object>')
    return out


def class_and_file_names(base):
    """For 0x... bases, use Unknown_<HEX>. Otherwise PascalCase."""
    if base.startswith(("0x", "0X")):
        hex_part = base[2:].upper()
        return f"Unknown_{hex_part}Parameters", f"Unknown_{hex_part}", base
    pas = base[0].upper() + base[1:]
    return f"{pas}Parameters", pas, pas


def detect_format(xml_path, src_dir, base):
    """Returns ('lib', root_hash) if it's a lib (root <object name="lib">)
    or ('obj', root_hash) if it's a bare obj root.

    For lib format the .lib.xml typically uses <object external="..."/>
    placeholders — we peek into the subfolder to find an actual entry's
    root hash.
    """
    try: root = ET.parse(xml_path).getroot()
    except: return None, None
    if root.tag == "object" and root.get("name") == "lib":
        # Try inline children with hash first
        for ch in root:
            if ch.tag == "object" and ch.get("hash"):
                return "lib", ch.get("hash").upper()
        # Externals — find any per-entry XML in the subfolder
        subdir = src_dir / base
        if subdir.exists() and subdir.is_dir():
            for entry in subdir.rglob("*.xml"):
                try: er = ET.parse(entry).getroot()
                except: continue
                if er.tag == "object" and er.get("hash"):
                    return "lib", er.get("hash").upper()
        return None, None
    if root.tag == "object" and root.get("hash"):
        return "obj", root.get("hash").upper()
    return None, None


def find_entries(src_dir, base, fmt):
    """Find the unpacked XML entries to extract field structure from."""
    if fmt == "lib":
        # Multi-export subfolder
        subdir = src_dir / base
        if subdir.exists() and subdir.is_dir():
            return sorted(subdir.rglob("*.xml"))
        # Fall back to the lib.xml itself (it has root + children)
        f = src_dir / f"{base}.lib.xml"
        return [f] if f.exists() else []
    # obj format: just the single obj.xml or lib.xml file
    for ext in (".obj.xml", ".lib.xml"):
        f = src_dir / f"{base}{ext}"
        if f.exists(): return [f]
    return []


def build_tree_for_lib(entries, root_hash):
    """For lib format, entries are per-item XMLs whose root is <object hash="HASH">.
    Aggregate all of them into a single class Node."""
    root = Node(root_hash)
    for p in entries:
        try: tree = ET.parse(p).getroot()
        except: continue
        # The per-entry root is <object hash="root_hash"> directly
        if tree.tag == "object" and tree.get("hash"):
            collect(root, tree)
        elif tree.tag == "object" and tree.get("name") == "lib":
            # The .lib.xml fallback — walk into its children
            for ch in tree:
                if ch.tag == "object":
                    collect(root, ch)
    return root


def build_tree_for_obj(xml_path, root_hash):
    """For obj format, the XML root IS the class. Just walk its children."""
    root = Node(root_hash)
    try: tree = ET.parse(xml_path).getroot()
    except: return root
    collect(root, tree)
    return root


# === Pass 1: scaffold patch_libs_missing + patch_unknown_libs ===
generated = 0
for src_dir in SOURCE_DIRS:
    print(f"\n--- {src_dir.name} ---")
    for asset in sorted(list(src_dir.glob("*.lib")) + list(src_dir.glob("*.obj"))):
        base = asset.stem
        # Determine source format from the unpacked XML
        for ext in (".lib.xml", ".obj.xml"):
            xml_path = src_dir / f"{base}{ext}"
            if xml_path.exists(): break
        else:
            print(f"  SKIP {base}: no unpacked XML found"); continue

        fmt, root_hash = detect_format(xml_path, src_dir, base)
        if not fmt:
            print(f"  SKIP {base}: couldn't detect format"); continue

        entries = find_entries(src_dir, base, fmt)
        if not entries:
            print(f"  SKIP {base}: no entries"); continue

        if fmt == "lib":
            root = build_tree_for_lib(entries, root_hash)
        else:
            root = build_tree_for_obj(entries[0], root_hash)

        class_name, schema_basename, filedef_name = class_and_file_names(base)

        schema_lines = ['<?xml version="1.0" encoding="utf-8"?>',
                        f'<class name="{class_name}">']
        schema_lines.extend(emit(root, indent=1))
        schema_lines.append('</class>')

        if fmt == "lib":
            file_lines = ['<?xml version="1.0" encoding="utf-8"?>',
                          f'<file name="{filedef_name}">',
                          '\t<object name="lib">',
                          f'\t\t<object hash="{root_hash}">',
                          f'\t\t\t<inherit name="{class_name}"/>',
                          '\t\t</object>',
                          '\t</object>',
                          '</file>']
        else:
            file_lines = ['<?xml version="1.0" encoding="utf-8"?>',
                          f'<file name="{filedef_name}">',
                          f'\t<object hash="{root_hash}">',
                          f'\t\t<inherit name="{class_name}"/>',
                          '\t</object>',
                          '</file>']

        for c_dir in (CLASSES, GTC_C):
            (c_dir / f"{schema_basename}.binaryclass.xml").write_text("\n".join(schema_lines), encoding="utf-8")
        for f_dir in (FILES, GTC_F):
            (f_dir / f"{schema_basename}.binaryobjectfile.xml").write_text("\n".join(file_lines), encoding="utf-8")

        generated += 1
        print(f"  {fmt:3s}  {base}  ->  {schema_basename}")

print(f"\nScaffolded {generated} new/replaced schemas + file defs.")


# === Pass 2: post-process ALL schemas to resolve the 6 standard header hashes ===
HEADER_RE = re.compile(r'<field hash="([0-9A-Fa-f]{8})" type="[^"]+"/>')

def header_repl(m):
    h = m.group(1).upper()
    if h in HEADER_NAMES:
        nm, t = HEADER_NAMES[h]
        return f'<field name="{nm}" type="{t}"/>'
    return m.group(0)

resolved_total = 0
files_changed = 0
for src_dir in (CLASSES, GTC_C):
    for f in src_dir.glob("*.binaryclass.xml"):
        text = f.read_text(encoding="utf-8")
        new = HEADER_RE.sub(header_repl, text)
        if new != text:
            n = sum(1 for m in HEADER_RE.finditer(text) if m.group(1).upper() in HEADER_NAMES)
            f.write_text(new, encoding="utf-8")
            files_changed += 1
            resolved_total += n
print(f"\nHeader resolution: {resolved_total} hash references resolved across {files_changed} files (both trees)")
