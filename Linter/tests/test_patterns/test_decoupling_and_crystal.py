from schematic_linter.patterns.crystal_load_caps import recognize as recognize_crystal
from schematic_linter.patterns.decoupling_cap import recognize as recognize_decoupling

from ..helpers import graph_from_records, pin


def test_decoupling_cap_basic():
    graph = graph_from_records(
        [
            pin("C1", "1", "A", net_name="VCC", net_type="POWER"),
            pin("C1", "2", "B", net_name="GND", net_type="GROUND"),
        ]
    )
    matches = recognize_decoupling(graph)
    assert len(matches) == 1
    assert matches[0].details == {"capacitor": "C1", "power_net": "VCC", "ground_net": "GND"}


def test_decoupling_cap_not_matched_for_signal_to_ground_cap():
    graph = graph_from_records(
        [
            pin("C1", "1", "A", net_name="SIG"),
            pin("C1", "2", "B", net_name="GND", net_type="GROUND"),
        ]
    )
    assert recognize_decoupling(graph) == []


def test_crystal_reports_zero_load_caps_when_none_present():
    graph = graph_from_records(
        [
            pin("Y1", "1", "XIN", net_name="XIN", comp_type="QUARTZ"),
            pin("Y1", "2", "XOUT", net_name="XOUT", comp_type="QUARTZ"),
        ]
    )
    matches = recognize_crystal(graph)
    assert len(matches) == 1
    assert matches[0].details["load_caps"] == []


def test_crystal_with_two_load_caps():
    graph = graph_from_records(
        [
            pin("Y1", "1", "XIN", net_name="XIN", comp_type="QUARTZ"),
            pin("Y1", "2", "XOUT", net_name="XOUT", comp_type="QUARTZ"),
            pin("C1", "1", "A", net_name="XIN"),
            pin("C1", "2", "B", net_name="GND", net_type="GROUND"),
            pin("C2", "1", "A", net_name="XOUT"),
            pin("C2", "2", "B", net_name="GND", net_type="GROUND"),
        ]
    )
    matches = recognize_crystal(graph)
    assert len(matches) == 1
    assert sorted(matches[0].details["load_caps"]) == ["C1", "C2"]


def test_real_project_crystal_has_two_load_caps(project1_matches):
    crystal_matches = [m for m in project1_matches if m.kind == "crystal_load_caps"]
    assert len(crystal_matches) == 1
    assert sorted(crystal_matches[0].details["load_caps"]) == ["C0003", "C0004"]


def test_real_project_decoupling_caps_found_on_ipsu_5v(project1_matches):
    ipsu_decouplers = {m.details["capacitor"] for m in project1_matches if m.kind == "decoupling_cap" and m.details["power_net"] == "IPSU_5V"}
    assert len(ipsu_decouplers) == 6
