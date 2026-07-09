"""Parser for flat Zuken Design Gateway (.ndf) netlists.

The exported format is a stream of semicolon-terminated records, one per
component pin, of the form::

    "NET_NAME" : NET_TYPE : "PART_NUMBER" : "COMP_TYPE" : "REF_DES" : "PIN_NUM" : STATUS : "INSTANCE_ID"
    : "PIN_NAME" :              ;

``NET_TYPE`` is blank, ``GROUND``, or ``POWER`` -- the exporter already
tells us which nets are power/ground anchors, so no name-guessing is
needed. Whitespace (including newlines) is used purely for column
alignment/line-wrapping and carries no semantic meaning: a record may be
wrapped across two or three physical lines when a field (typically the net
name) is long. This parser therefore ignores line breaks entirely and
tokenizes on unquoted ``:`` (field separator) and ``;`` (record
terminator), treating anything between double quotes as literal content.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

_EXPECTED_FIELD_COUNT = 10


class NetlistParseError(Exception):
    """Raised when the netlist cannot be parsed into pin records."""


@dataclass(frozen=True)
class PinRecord:
    """One component-pin-to-net connection, as exported by the netlist."""

    net_name: Optional[str]
    net_type: Optional[str]  # None | "GROUND" | "POWER"
    part_number: str
    comp_type: str
    ref_des: str
    pin_number: str
    status: str
    instance_id: str
    pin_name: str

    @property
    def is_power(self) -> bool:
        return self.net_type == "POWER"

    @property
    def is_ground(self) -> bool:
        return self.net_type == "GROUND"

    @property
    def is_connected(self) -> bool:
        return bool(self.net_name)


def _tokenize_records(text: str) -> List[List[str]]:
    """Split raw netlist text into a list of field lists, one per record.

    Quote-aware: colons/semicolons/newlines inside double quotes are taken
    literally and never treated as separators.
    """

    records: List[List[str]] = []
    fields: List[str] = []
    buf: List[str] = []
    in_quotes = False

    for ch in text:
        if ch == '"':
            in_quotes = not in_quotes
            continue
        if not in_quotes and ch == ":":
            fields.append("".join(buf).strip())
            buf = []
        elif not in_quotes and ch == ";":
            fields.append("".join(buf).strip())
            records.append(fields)
            fields = []
            buf = []
        elif not in_quotes and ch in "\r\n":
            buf.append(" ")
        else:
            buf.append(ch)

    trailing = "".join(buf).strip()
    if trailing:
        raise NetlistParseError(
            "Netlist ended mid-record (unterminated content after last "
            f"';': {trailing[:80]!r}). The export may be truncated."
        )
    return records


def parse_netlist(path: Path) -> List[PinRecord]:
    """Parse a flat Zuken .ndf netlist file into a list of ``PinRecord``."""

    path = Path(path)
    text = path.read_text(encoding="utf-8", errors="replace")
    raw_records = _tokenize_records(text)

    if not raw_records:
        raise NetlistParseError(f"Netlist '{path}' contains no parsable records")

    pin_records: List[PinRecord] = []
    for idx, fields in enumerate(raw_records):
        if len(fields) != _EXPECTED_FIELD_COUNT:
            raise NetlistParseError(
                f"Record #{idx} in '{path}' has {len(fields)} fields, "
                f"expected {_EXPECTED_FIELD_COUNT}. Fields parsed: {fields!r}. "
                "The netlist format may differ from the supported flat "
                "Zuken Design Gateway export."
            )
        (
            net_name,
            net_type,
            part_number,
            comp_type,
            ref_des,
            pin_number,
            status,
            instance_id,
            pin_name,
            _trailing,
        ) = fields

        if not ref_des:
            raise NetlistParseError(f"Record #{idx} in '{path}' has an empty reference designator")

        pin_records.append(
            PinRecord(
                net_name=net_name or None,
                net_type=net_type or None,
                part_number=part_number,
                comp_type=comp_type,
                ref_des=ref_des,
                pin_number=pin_number,
                status=status,
                instance_id=instance_id,
                pin_name=pin_name,
            )
        )

    return pin_records
