from schematic_linter.patterns import run_all_recognizers
from schematic_linter.rules import RuleContext, run_all_rules

from ..helpers import graph_from_records, pin


def _findings_for(graph):
    matches = run_all_recognizers(graph)
    ctx = RuleContext(graph=graph, matches=matches, has_bom=False)
    return [f for f in run_all_rules(ctx) if f.rule_id == "sibling_pin_mismatch"]


def _shift_register_records(oe_nets, a_nets, comp_type="FAKE_595"):
    """Three sibling ICs (U1/U2/U3) with VCC/GND/OE bussed pins and a
    per-instance 'A' chain pin, mirroring the real U02/U03/U04 shape."""

    records = []
    for idx, (ref, oe_net, a_net) in enumerate(zip(["U1", "U2", "U3"], oe_nets, a_nets), start=1):
        records += [
            pin(ref, "16", "VCC", net_name="VDD", net_type="POWER", comp_type=comp_type),
            pin(ref, "8", "GND", net_name="GND", net_type="GROUND", comp_type=comp_type),
            pin(ref, "13", "OE", net_name=oe_net, comp_type=comp_type),
            pin(ref, "14", "A", net_name=a_net, comp_type=comp_type),
        ]
    return records


def test_consistent_siblings_produce_no_finding():
    records = _shift_register_records(
        oe_nets=["EN", "EN", "EN"],
        a_nets=["CHAIN_IN", "CHAIN_1_2", "CHAIN_2_3"],
    )
    graph = graph_from_records(records)
    assert not _findings_for(graph)


def test_outlier_pin_is_flagged():
    records = _shift_register_records(
        oe_nets=["EN", "EN", "WRONG_NET"],
        a_nets=["CHAIN_IN", "CHAIN_1_2", "CHAIN_2_3"],
    )
    graph = graph_from_records(records)
    findings = _findings_for(graph)
    assert len(findings) == 1
    assert findings[0].ref_des[0] == "U3"
    assert findings[0].details["pin_name"] == "OE"
    assert findings[0].severity.value == "warning"


def test_outlier_behind_series_resistor_is_not_flagged():
    records = _shift_register_records(
        oe_nets=["EN", "EN", "EN_THRU_R"],
        a_nets=["CHAIN_IN", "CHAIN_1_2", "CHAIN_2_3"],
    )
    # R1 sits inline between U3's OE net and the common EN bus -- a
    # series-termination resistor, not a wiring mistake.
    records += [
        pin("R1", "1", "A", net_name="EN_THRU_R", comp_type="RESISTOR"),
        pin("R1", "2", "B", net_name="EN", comp_type="RESISTOR"),
    ]
    graph = graph_from_records(records)
    assert not _findings_for(graph)


def test_two_way_split_is_ambiguous_and_not_flagged():
    # 2 vs 2 -- no unanimous-minus-one majority, so this is left alone
    # rather than guessing which pair is "correct".
    records = []
    for idx, (ref, oe_net) in enumerate(zip(["U1", "U2", "U3", "U4"], ["EN", "EN", "OTHER", "OTHER"])):
        records += [
            pin(ref, "13", "OE", net_name=oe_net, comp_type="FAKE_595"),
            pin(ref, "14", "A", net_name=f"CHAIN_{idx}", comp_type="FAKE_595"),
            pin(ref, "16", "VCC", net_name="VDD", net_type="POWER", comp_type="FAKE_595"),
        ]
    graph = graph_from_records(records)
    assert not _findings_for(graph)


def test_generic_two_pin_passive_group_is_not_flagged():
    # 5 plain resistors with only "A"/"B" pins -- below the common-pin-name
    # threshold, so this group is never compared at all even though every
    # instance connects to a completely different pair of nets.
    records = []
    for i in range(5):
        records += [
            pin(f"R{i}", "1", "A", net_name=f"NET_{i}_A", comp_type="RESISTOR"),
            pin(f"R{i}", "2", "B", net_name=f"NET_{i}_B", comp_type="RESISTOR"),
        ]
    graph = graph_from_records(records)
    assert not _findings_for(graph)


def test_only_two_instances_are_never_compared():
    # Below SIBLING_GROUP_MIN_SIZE -- any difference between 2 instances is
    # a meaningless 50/50 split, so the rule stays silent.
    records = _shift_register_records(
        oe_nets=["EN", "DIFFERENT"],
        a_nets=["CHAIN_A", "CHAIN_B"],
    )  # zip stops at the shortest list -- only U1 and U2 get records
    graph = graph_from_records(records)
    assert not _findings_for(graph)


def test_real_project_flags_u04_oe_pin_swap(project1_findings):
    hits = [f for f in project1_findings if f.rule_id == "sibling_pin_mismatch"]
    by_ref = {f.ref_des[0]: f for f in hits}
    assert "U04" in by_ref
    assert by_ref["U04"].details["pin_name"] == "OE"
    # U02's SCK sits behind a series-termination resistor (R0003) -- must
    # not be flagged.
    assert "U02" not in by_ref
