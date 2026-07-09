from schematic_linter.patterns.rc_lowpass import recognize

from ..helpers import graph_from_records, pin


def test_rc_lowpass_basic():
    graph = graph_from_records(
        [
            pin("R1", "1", "A", net_name="SRC"),
            pin("R1", "2", "B", net_name="MID"),
            pin("C1", "1", "A", net_name="MID"),
            pin("C1", "2", "B", net_name="GND", net_type="GROUND"),
        ]
    )
    matches = recognize(graph)
    assert len(matches) == 1
    assert matches[0].details == {
        "resistor": "R1",
        "capacitor": "C1",
        "source_net": "SRC",
        "mid_net": "MID",
        "ground_net": "GND",
    }


def test_resistor_shared_between_two_filter_paths_produces_two_matches():
    # R1 sits between NET_A and NET_B; NET_A has its own cap to GND1 and
    # NET_B has its own cap to GND2 -- R1 is the shared resistor of two
    # independent RC filter paths (see shared_rc_resistor rule).
    graph = graph_from_records(
        [
            pin("R1", "1", "X", net_name="NET_A"),
            pin("R1", "2", "Y", net_name="NET_B"),
            pin("C1", "1", "A", net_name="NET_A"),
            pin("C1", "2", "B", net_name="GND1", net_type="GROUND"),
            pin("C2", "1", "A", net_name="NET_B"),
            pin("C2", "2", "B", net_name="GND2", net_type="GROUND"),
        ]
    )
    matches = recognize(graph)
    resistors_involved = {m.details["resistor"] for m in matches}
    assert resistors_involved == {"R1"}
    assert len(matches) == 2


def test_real_project_has_expected_shared_resistor(project1_matches):
    from collections import defaultdict

    by_resistor = defaultdict(set)
    for m in project1_matches:
        if m.kind == "rc_lowpass":
            by_resistor[m.details["resistor"]].add(m.details["mid_net"])

    assert len(by_resistor["051405R8"]) >= 2
