from schematic_linter.patterns import run_all_recognizers
from schematic_linter.rules import RuleContext, run_all_rules

from ..helpers import bom_entry, graph_from_records, pin


def _pull_up_graph(value_raw=None):
    records = [
        pin("R1", "1", "A", net_name="VCC", net_type="POWER"),
        pin("R1", "2", "B", net_name="SIG"),
        pin("U1", "1", "IN", net_name="SIG", comp_type="IC"),
    ]
    bom = {"R1": bom_entry("R1", value_raw)} if value_raw is not None else None
    return graph_from_records(records, bom)


def _findings_for(graph, has_bom):
    matches = run_all_recognizers(graph)
    ctx = RuleContext(graph=graph, matches=matches, has_bom=has_bom)
    return run_all_rules(ctx)


def test_zero_ohm_pull_up_is_warning_when_value_known():
    graph = _pull_up_graph("0R")
    findings = _findings_for(graph, has_bom=True)
    hits = [f for f in findings if f.rule_id == "zero_ohm_pull_review"]
    assert len(hits) == 1
    assert hits[0].severity.value == "warning"
    assert "0" in hits[0].description or "jumper" in hits[0].description


def test_normal_value_pull_up_has_no_zero_ohm_finding():
    graph = _pull_up_graph("10k")
    findings = _findings_for(graph, has_bom=True)
    assert not [f for f in findings if f.rule_id == "zero_ohm_pull_review"]


def test_unknown_value_pull_up_downgrades_to_info():
    graph = _pull_up_graph(value_raw=None)
    findings = _findings_for(graph, has_bom=False)
    hits = [f for f in findings if f.rule_id == "zero_ohm_pull_review"]
    assert len(hits) == 1
    assert hits[0].severity.value == "info"
    assert hits[0].note == "value unknown \u2014 check manually"


def test_power_pin_tied_to_ground_is_error():
    graph = graph_from_records(
        [
            pin("U1", "1", "VCC", net_name="GND", net_type="GROUND", comp_type="IC"),
        ]
    )
    findings = _findings_for(graph, has_bom=False)
    hits = [f for f in findings if f.rule_id == "power_pin_miswire"]
    assert len(hits) == 1
    assert hits[0].severity.value == "error"
    assert hits[0].ref_des == ["U1"]


def test_ground_pin_tied_to_power_is_error():
    graph = graph_from_records(
        [
            pin("U1", "1", "GND", net_name="VCC", net_type="POWER", comp_type="IC"),
        ]
    )
    findings = _findings_for(graph, has_bom=False)
    hits = [f for f in findings if f.rule_id == "power_pin_miswire"]
    assert len(hits) == 1


def test_correctly_wired_power_pin_has_no_finding():
    graph = graph_from_records(
        [
            pin("U1", "1", "VCC", net_name="VCC", net_type="POWER", comp_type="IC"),
            pin("U1", "2", "GND", net_name="GND", net_type="GROUND", comp_type="IC"),
        ]
    )
    findings = _findings_for(graph, has_bom=False)
    assert not [f for f in findings if f.rule_id == "power_pin_miswire"]


def test_unconnected_ground_pin_is_warning():
    graph = graph_from_records(
        [
            pin("U1", "1", "GND", net_name=None, comp_type="IC"),
        ]
    )
    findings = _findings_for(graph, has_bom=False)
    hits = [f for f in findings if f.rule_id == "unconnected_power_pin"]
    assert len(hits) == 1
    assert hits[0].severity.value == "warning"


def test_unconnected_generic_gpio_is_not_flagged():
    graph = graph_from_records(
        [
            pin("U1", "1", "RA4", net_name=None, comp_type="IC"),
        ]
    )
    findings = _findings_for(graph, has_bom=False)
    assert not [f for f in findings if f.rule_id == "unconnected_power_pin"]


def test_real_project_power_pin_miswire_finding(project1_findings):
    hits = [f for f in project1_findings if f.rule_id == "power_pin_miswire"]
    assert len(hits) == 1
    assert hits[0].ref_des == ["U03"]
    assert hits[0].nets == ["GND"]


def test_real_project_unconnected_power_pin_finding(project1_findings):
    hits = [f for f in project1_findings if f.rule_id == "unconnected_power_pin"]
    assert len(hits) == 1
    assert hits[0].ref_des == ["U04"]


def test_real_project_has_no_zero_ohm_pull_finding(project1_findings):
    # 081708R12/08R09 are 0Ohm and were originally (incorrectly) reported
    # here -- they actually sit between an op-amp output and a transistor
    # base, not a pull resistor, because their net ("RAW_1"/"RAW_2") isn't
    # tagged POWER by the netlist. This is a regression test for that.
    assert not [f for f in project1_findings if f.rule_id == "zero_ohm_pull_review"]
