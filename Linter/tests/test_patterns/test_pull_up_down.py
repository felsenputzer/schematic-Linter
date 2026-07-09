from schematic_linter.patterns.pull_down import recognize as recognize_pull_down
from schematic_linter.patterns.pull_up import recognize as recognize_pull_up

from ..helpers import graph_from_records, pin


def test_pull_up_detected_when_signal_reaches_ic_pin():
    graph = graph_from_records(
        [
            pin("R1", "1", "A", net_name="VCC", net_type="POWER"),
            pin("R1", "2", "B", net_name="SIG"),
            pin("U1", "1", "IN", net_name="SIG", comp_type="IC"),
        ]
    )
    matches = recognize_pull_up(graph)
    assert len(matches) == 1
    assert matches[0].details["resistor"] == "R1"
    assert matches[0].details["power_net"] == "VCC"
    assert matches[0].details["signal_net"] == "SIG"


def test_pull_up_not_detected_without_ic_on_signal_net():
    graph = graph_from_records(
        [
            pin("R1", "1", "A", net_name="VCC", net_type="POWER"),
            pin("R1", "2", "B", net_name="SIG"),
            pin("R2", "1", "A", net_name="SIG"),
            pin("R2", "2", "B", net_name="OTHER"),
        ]
    )
    assert recognize_pull_up(graph) == []


def test_pull_down_detected_when_signal_reaches_ic_pin():
    graph = graph_from_records(
        [
            pin("R1", "1", "A", net_name="GND", net_type="GROUND"),
            pin("R1", "2", "B", net_name="SIG"),
            pin("U1", "1", "IN", net_name="SIG", comp_type="IC"),
        ]
    )
    matches = recognize_pull_down(graph)
    assert len(matches) == 1
    assert matches[0].details["ground_net"] == "GND"


def test_real_project_has_expected_redundant_pull_ups(project1_matches):
    pull_ups_on_fault = {m.details["resistor"] for m in project1_matches if m.kind == "pull_up" and m.details["signal_net"] == "FAULT"}
    assert pull_ups_on_fault == {"R01", "R02"}


def test_real_project_divider_leg_is_still_recognized_as_pull_up_and_down(project1_matches):
    # R16/R17 form a legitimate voltage divider that also happens to feed
    # an IC pin -- patterns are purely structural, so both should still
    # show up here; it's the *rule* layer's job to not call this
    # contention (see test_rules/test_contention_pull_up_down.py).
    up = {m.details["resistor"] for m in project1_matches if m.kind == "pull_up" and m.details["signal_net"] == "IPSU_5V_MEAS"}
    down = {m.details["resistor"] for m in project1_matches if m.kind == "pull_down" and m.details["signal_net"] == "IPSU_5V_MEAS"}
    assert up == {"R16"}
    assert down == {"R17"}
