"""Shared path constants for schema/lib analysis scripts.

Tweak these to point at your local layout.
"""
from pathlib import Path

# Canonical edit location for WDL .binaryclass.xml schemas
CLASSES = Path(r"C:\Users\qstli\Downloads\Gibbed.Disrupt-wasdennnoch\bin\projects\WDL\binary objects\classes")

# Dare editor's Generic XML dump (authoritative attribute-name source)
GENERIC = Path(r"C:\Users\qstli\data\Databases\Generic")

# Unpacked .lib folders to analyse against
LIBS_COMMON = Path(r"C:\Users\qstli\Downloads\Gibbed.Disrupt-wasdennnoch\bin\common_libs")
LIBS_PATCH  = Path(r"C:\Users\qstli\Downloads\Gibbed.Disrupt-wasdennnoch\bin\patch_full_libs")
LIBS_UNKNOWN = Path(r"C:\Users\qstli\Downloads\Gibbed.Disrupt-wasdennnoch\bin\patch_full_unknown_libs")
