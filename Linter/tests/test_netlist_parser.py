import pytest

from schematic_linter.parsers.netlist_parser import NetlistParseError, parse_netlist


def test_parse_real_netlist_record_count(project1_netlist_path):
    records = parse_netlist(project1_netlist_path)
    assert len(records) == 317


def test_parse_real_netlist_known_record(project1_netlist_path):
    records = parse_netlist(project1_netlist_path)
    hit = [r for r in records if r.ref_des == "051405C1" and r.pin_number == "1"]
    assert len(hit) == 1
    rec = hit[0]
    assert rec.net_name == "SIG_N"
    assert rec.comp_type == "CAPA"
    assert rec.pin_name == "A"
    assert not rec.is_power
    assert not rec.is_ground


def test_parse_real_netlist_ground_and_power_tags(project1_netlist_path):
    records = parse_netlist(project1_netlist_path)
    ground_records = [r for r in records if r.net_name == "GND"]
    power_records = [r for r in records if r.net_name == "IPSU_5V"]
    assert ground_records and all(r.is_ground for r in ground_records)
    assert power_records and all(r.is_power for r in power_records)


def test_parse_netlist_handles_multiline_wrapped_net_name(tmp_path):
    text = (
        '"BLK0001/SIGN0017"\n'
        ':                      : "B103281" : "CAPA" : "051405C5" : "1" : UNFIXED : "Z-abc.cmp156"\n'
        ': "A" :              ;\n'
    )
    path = tmp_path / "sample.ndf"
    path.write_text(text, encoding="utf-8")
    records = parse_netlist(path)
    assert len(records) == 1
    assert records[0].net_name == "BLK0001/SIGN0017"
    assert records[0].ref_des == "051405C5"


def test_parse_netlist_unconnected_pin_has_none_net_name(tmp_path):
    text = ': : "B1" : "IC" : "U1" : "1" : UNFIXED : "Z-abc.cmp1"\n: "NC" : ;\n'
    path = tmp_path / "sample.ndf"
    path.write_text(text, encoding="utf-8")
    records = parse_netlist(path)
    assert records[0].net_name is None
    assert not records[0].is_connected


def test_parse_netlist_wrong_field_count_raises(tmp_path):
    path = tmp_path / "bad.ndf"
    path.write_text('"NET" : "A" : "B" ;\n', encoding="utf-8")
    with pytest.raises(NetlistParseError):
        parse_netlist(path)


def test_parse_netlist_empty_file_raises(tmp_path):
    path = tmp_path / "empty.ndf"
    path.write_text("", encoding="utf-8")
    with pytest.raises(NetlistParseError):
        parse_netlist(path)


def test_parse_netlist_unterminated_record_raises(tmp_path):
    path = tmp_path / "truncated.ndf"
    path.write_text('"NET" : : "B" : "CAPA" : "C1" : "1" : UNFIXED : "Z-x.cmp1"\n: "A" :  ', encoding="utf-8")
    with pytest.raises(NetlistParseError):
        parse_netlist(path)
