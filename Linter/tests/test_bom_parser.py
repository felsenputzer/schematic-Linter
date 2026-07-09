import pytest

from schematic_linter.parsers.bom_parser import BomParseError, parse_bom


def test_parse_real_bom_known_entry(project1_bom_path):
    entries = parse_bom(project1_bom_path)
    assert "051405R1" in entries
    entry = entries["051405R1"]
    assert entry.raw_value == "5.6K"
    assert entry.part_number == "B000028822"


def test_parse_real_bom_skips_metadata_header_lines(project1_bom_path):
    entries = parse_bom(project1_bom_path)
    assert "TITLE" not in entries
    assert all(ref for ref in entries)


def test_parse_bom_missing_header_raises(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text("A;B;C\n1;2;3\n", encoding="utf-8")
    with pytest.raises(BomParseError):
        parse_bom(path)


def test_parse_bom_empty_file_raises(tmp_path):
    path = tmp_path / "empty.csv"
    path.write_text("", encoding="utf-8")
    with pytest.raises(BomParseError):
        parse_bom(path)


def test_component_missing_from_bom_is_not_an_error(project1_bom_path):
    entries = parse_bom(project1_bom_path)
    assert "SOME_REF_DES_NOT_IN_BOM" not in entries
