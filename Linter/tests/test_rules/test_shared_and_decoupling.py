from schematic_linter.patterns import run_all_recognizers
from schematic_linter.rules import RuleContext, run_all_rules

from ..helpers import bom_entry, graph_from_records, pin


def _findings_for(graph, has_bom):
    matches = run_all_recognizers(graph)
    ctx = RuleContext(graph=graph, matches=matches, has_bom=has_bom)
    return run_all_rules(ctx)


def test_shared_rc_resistor_flagged():
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
    findings = _findings_for(graph, has_bom=False)
    hits = [f for f in findings if f.rule_id == "shared_rc_resistor"]
    assert len(hits) == 1
    assert hits[0].severity.value == "warning"
    assert "R1" in hits[0].ref_des


def test_missing_decoupling_requires_bom():
    records = [
        pin("U1", "1", "VCC", net_name="VCC", net_type="POWER", comp_type="IC"),
    ]
    graph = graph_from_records(records)
    assert not [f for f in _findings_for(graph, has_bom=False) if f.rule_id == "missing_decoupling"]

    hits = [f for f in _findings_for(graph, has_bom=True) if f.rule_id == "missing_decoupling"]
    assert len(hits) == 1
    assert hits[0].ref_des == ["U1"]


def test_missing_decoupling_absent_when_decoupling_cap_present():
    graph = graph_from_records(
        [
            pin("U1", "1", "VCC", net_name="VCC", net_type="POWER", comp_type="IC"),
            pin("C1", "1", "A", net_name="VCC", net_type="POWER"),
            pin("C1", "2", "B", net_name="GND", net_type="GROUND"),
        ]
    )
    assert not [f for f in _findings_for(graph, has_bom=True) if f.rule_id == "missing_decoupling"]


def test_excess_decoupling_without_bulk_cap():
    records = []
    for i in range(1, 6):
        records.append(pin(f"C{i}", "1", "A", net_name="VCC", net_type="POWER"))
        records.append(pin(f"C{i}", "2", "B", net_name="GND", net_type="GROUND"))
    bom = {f"C{i}": bom_entry(f"C{i}", "100nF") for i in range(1, 6)}
    graph = graph_from_records(records, bom)

    findings = _findings_for(graph, has_bom=True)
    hits = [f for f in findings if f.rule_id == "excess_decoupling_no_bulk"]
    assert len(hits) == 1
    assert hits[0].severity.value == "info"


def test_excess_decoupling_with_bulk_cap_is_fine():
    records = []
    for i in range(1, 6):
        records.append(pin(f"C{i}", "1", "A", net_name="VCC", net_type="POWER"))
        records.append(pin(f"C{i}", "2", "B", net_name="GND", net_type="GROUND"))
    records.append(pin("CBULK", "1", "A", net_name="VCC", net_type="POWER"))
    records.append(pin("CBULK", "2", "B", net_name="GND", net_type="GROUND"))
    bom = {f"C{i}": bom_entry(f"C{i}", "100nF") for i in range(1, 6)}
    bom["CBULK"] = bom_entry("CBULK", "100uF")
    graph = graph_from_records(records, bom)

    findings = _findings_for(graph, has_bom=True)
    assert not [f for f in findings if f.rule_id == "excess_decoupling_no_bulk"]


def test_unloaded_divider_flagged_when_tap_has_no_other_connection():
    graph = graph_from_records(
        [
            pin("R1", "1", "A", net_name="VCC", net_type="POWER"),
            pin("R1", "2", "B", net_name="TAP"),
            pin("R2", "1", "A", net_name="TAP"),
            pin("R2", "2", "B", net_name="GND", net_type="GROUND"),
        ]
    )
    findings = _findings_for(graph, has_bom=False)
    hits = [f for f in findings if f.rule_id == "unloaded_divider"]
    assert len(hits) == 1
    assert hits[0].severity.value == "info"


def test_loaded_divider_not_flagged():
    graph = graph_from_records(
        [
            pin("R1", "1", "A", net_name="VCC", net_type="POWER"),
            pin("R1", "2", "B", net_name="TAP"),
            pin("R2", "1", "A", net_name="TAP"),
            pin("R2", "2", "B", net_name="GND", net_type="GROUND"),
            pin("U1", "1", "AIN", net_name="TAP", comp_type="IC"),
        ]
    )
    findings = _findings_for(graph, has_bom=False)
    assert not [f for f in findings if f.rule_id == "unloaded_divider"]


def test_crystal_missing_load_caps_warns():
    graph = graph_from_records(
        [
            pin("Y1", "1", "XIN", net_name="XIN", comp_type="QUARTZ"),
            pin("Y1", "2", "XOUT", net_name="XOUT", comp_type="QUARTZ"),
            pin("C1", "1", "A", net_name="XIN"),
            pin("C1", "2", "B", net_name="GND", net_type="GROUND"),
        ]
    )
    findings = _findings_for(graph, has_bom=False)
    hits = [f for f in findings if f.rule_id == "crystal_missing_load_caps"]
    assert len(hits) == 1
    assert hits[0].severity.value == "warning"


def test_floating_single_pin_net():
    graph = graph_from_records(
        [
            pin("R1", "1", "A", net_name="LONELY"),
        ]
    )
    findings = _findings_for(graph, has_bom=False)
    hits = [f for f in findings if f.rule_id == "floating_single_pin_net"]
    assert len(hits) == 1
    assert hits[0].nets == ["LONELY"]


def test_real_project_shared_rc_resistors(project1_findings):
    hits = {f.ref_des[0] for f in project1_findings if f.rule_id == "shared_rc_resistor"}
    assert hits == {"051405R3", "051405R4", "051405R5", "051405R6", "051405R8", "051405R9"}


def test_shared_source_resistor_flagged_when_nonzero():
    """R1 feeds NET_A, which fans out (through R2 and R3) into two
    independently-filtered branches -- current from either branch develops
    a voltage drop across R1 that's visible to the other."""

    graph = graph_from_records(
        [
            pin("R1", "1", "A", net_name="SOURCE"),
            pin("R1", "2", "B", net_name="NET_A"),
            pin("R2", "1", "A", net_name="NET_A"),
            pin("R2", "2", "B", net_name="NET_B"),
            pin("C1", "1", "A", net_name="NET_B"),
            pin("C1", "2", "B", net_name="GND1", net_type="GROUND"),
            pin("U1", "1", "AIN", net_name="NET_B", comp_type="IC"),
            pin("R3", "1", "A", net_name="NET_A"),
            pin("R3", "2", "B", net_name="NET_C"),
            pin("C2", "1", "A", net_name="NET_C"),
            pin("C2", "2", "B", net_name="GND2", net_type="GROUND"),
            pin("U2", "1", "AIN", net_name="NET_C", comp_type="IC"),
        ],
        bom={"R1": bom_entry("R1", "3.3K")},
    )
    findings = _findings_for(graph, has_bom=True)
    hits = [f for f in findings if f.rule_id == "shared_source_resistor"]
    assert len(hits) == 1
    assert hits[0].severity.value == "warning"
    assert set(hits[0].ref_des) == {"R1", "R2", "R3", "C1", "C2"}


def test_shared_source_resistor_not_flagged_when_zero_ohm():
    """Same topology, but the feed resistor is a 0\u03a9 link -- negligible,
    so the two branches aren't really coupled and this should not fire."""

    graph = graph_from_records(
        [
            pin("R1", "1", "A", net_name="SOURCE"),
            pin("R1", "2", "B", net_name="NET_A"),
            pin("R2", "1", "A", net_name="NET_A"),
            pin("R2", "2", "B", net_name="NET_B"),
            pin("C1", "1", "A", net_name="NET_B"),
            pin("C1", "2", "B", net_name="GND1", net_type="GROUND"),
            pin("U1", "1", "AIN", net_name="NET_B", comp_type="IC"),
            pin("R3", "1", "A", net_name="NET_A"),
            pin("R3", "2", "B", net_name="NET_C"),
            pin("C2", "1", "A", net_name="NET_C"),
            pin("C2", "2", "B", net_name="GND2", net_type="GROUND"),
            pin("U2", "1", "AIN", net_name="NET_C", comp_type="IC"),
        ],
        bom={"R1": bom_entry("R1", "0R")},
    )
    findings = _findings_for(graph, has_bom=True)
    assert not [f for f in findings if f.rule_id == "shared_source_resistor"]


def test_shared_source_resistor_degrades_to_info_without_value():
    graph = graph_from_records(
        [
            pin("R1", "1", "A", net_name="SOURCE"),
            pin("R1", "2", "B", net_name="NET_A"),
            pin("R2", "1", "A", net_name="NET_A"),
            pin("R2", "2", "B", net_name="NET_B"),
            pin("C1", "1", "A", net_name="NET_B"),
            pin("C1", "2", "B", net_name="GND1", net_type="GROUND"),
            pin("U1", "1", "AIN", net_name="NET_B", comp_type="IC"),
            pin("R3", "1", "A", net_name="NET_A"),
            pin("R3", "2", "B", net_name="NET_C"),
            pin("C2", "1", "A", net_name="NET_C"),
            pin("C2", "2", "B", net_name="GND2", net_type="GROUND"),
            pin("U2", "1", "AIN", net_name="NET_C", comp_type="IC"),
        ]
    )
    findings = _findings_for(graph, has_bom=False)
    hits = [f for f in findings if f.rule_id == "shared_source_resistor"]
    assert len(hits) == 1
    assert hits[0].severity.value == "info"
    assert hits[0].note is not None


def test_real_project2_shared_source_resistor_flags_bad_pair_only(project2_findings):
    """Testproject2 rebuilds the same redundant-measurement front end twice
    with different ref-des: R15/R16/R17/C09/C10 has an extra 3.3k resistor
    (R15) feeding both RC branches -- a real common-impedance coupling risk.
    R18/R19/C11/C12 is the same circuit without that extra resistor (both
    dividers tap the op-amp output directly) and must NOT be flagged."""

    hits = [f for f in project2_findings if f.rule_id == "shared_source_resistor"]
    bad_pair_hits = [f for f in hits if "R15" in f.ref_des]
    assert len(bad_pair_hits) == 1
    assert set(bad_pair_hits[0].ref_des) == {"R15", "R16", "R17", "C09", "C10"}
    assert bad_pair_hits[0].severity.value == "warning"

    assert not any({"R18", "R19"} & set(f.ref_des) for f in hits)


def test_real_project2_shared_rc_resistor_does_not_flag_good_pair(project2_findings):
    """The 0\u03a9-fed good pair (R18/R19) must not trip the older
    shared_rc_resistor heuristic either (it previously did, because a
    decoupling cap sitting on the op-amp's own output net looked -- purely
    structurally -- like a second independent filter tap through R18/R19)."""

    hits = [f for f in project2_findings if f.rule_id == "shared_rc_resistor"]
    assert not any({"R18", "R19"} & set(f.ref_des) for f in hits)


def test_real_project_excess_decoupling_on_ipsu_5v(project1_findings):
    hits = [f for f in project1_findings if f.rule_id == "excess_decoupling_no_bulk"]
    assert len(hits) == 1
    assert hits[0].nets == ["IPSU_5V"]


def test_real_project_crystal_has_no_missing_load_cap_warning(project1_findings):
    assert not [f for f in project1_findings if f.rule_id == "crystal_missing_load_caps"]
