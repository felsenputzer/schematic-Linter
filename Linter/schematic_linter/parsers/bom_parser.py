"""Parser for the engineering BOM (eBOM) CSV export.

The observed export (semicolon-delimited) looks like::

    TITLE: ;Bill of Materials;
    DATE: ;07/07/2026   14:44
    DESIGN: ;TestDesign
    Variant: ;
    ROOM;PART_NUMBER;Qty;Ref Des;DESCRIPTION;PKGS;STATUS;VALUE;
    eBB000959_02;B000021351;1;051405C1;CER 1nF 10% 50V X7R 0603;0603;Allowed;1nF;

The first few lines are free-form metadata, not part of the table, so the
parser scans for the real header row (identified by the presence of a
``Ref Des`` column) before handing the rest to ``csv.DictReader``.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Dict


class BomParseError(Exception):
    """Raised when the eBOM file cannot be parsed."""


@dataclass(frozen=True)
class BomEntry:
    """One row of the eBOM, keyed by reference designator."""

    ref_des: str
    part_number: str
    description: str
    package: str
    status: str
    raw_value: str


def _find_header_index(lines: list[str]) -> int:
    for idx, line in enumerate(lines):
        header_cells = [c.strip().upper() for c in line.split(";")]
        if "REF DES" in header_cells:
            return idx
    raise BomParseError(
        "Could not locate the eBOM header row (expected a column literally "
        "named 'Ref Des'). Is this a Design Gateway eBOM export?"
    )


def parse_bom(path: Path) -> Dict[str, BomEntry]:
    """Parse an eBOM CSV file into a mapping of ref-des -> ``BomEntry``."""

    path = Path(path)
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    lines = text.splitlines()
    if not lines:
        raise BomParseError(f"eBOM file '{path}' is empty")

    header_idx = _find_header_index(lines)
    reader = csv.DictReader(lines[header_idx:], delimiter=";")

    entries: Dict[str, BomEntry] = {}
    for row in reader:
        ref_des = (row.get("Ref Des") or "").strip()
        if not ref_des:
            continue
        entries[ref_des] = BomEntry(
            ref_des=ref_des,
            part_number=(row.get("PART_NUMBER") or "").strip(),
            description=(row.get("DESCRIPTION") or "").strip(),
            package=(row.get("PKGS") or "").strip(),
            status=(row.get("STATUS") or "").strip(),
            raw_value=(row.get("VALUE") or "").strip(),
        )

    if not entries:
        raise BomParseError(f"eBOM file '{path}' parsed but contained no usable rows")

    return entries
