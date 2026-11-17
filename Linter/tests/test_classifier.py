from schematic_linter.graph.classifier import SOURCE_COMP_TYPE, SOURCE_REF_DES, classify
from schematic_linter.graph.model import ComponentKind
from schematic_linter.patterns.registry import run_all_recognizers
from schematic_linter.rules.base import RuleContext
from schematic_linter.rules.registry import run_all_rules

from .helpers import bom_entry, graph_from_records, pin


def test_x_prefix_is_a_special_testpoint_not_a_crystal():
    result = classify("X1", ["OTHER"], pin_names=["POS"])
    assert result.kind == ComponentKind.TESTPOINT
    assert result.source == SOURCE_REF_DES
    assert not result.notes


def test_y_prefix_passive_crystal():
    result = classify("Y1", ["QUARTZ_NX2016AA"], "QTZ 20MHz 10ppm 5pF SMD", pin_names=["1", "2", "3", "4"])
    assert result.kind == ComponentKind.CRYSTAL
    assert not result.notes


def test_y_prefix_on_power_net_is_an_oscillator():
    result = classify("Y2", ["CLOCK_4PIN"], pin_names=["1", "2", "3", "4"], on_power_net=True)
    assert result.kind == ComponentKind.OSCILLATOR


def test_y_prefix_with_oscillator_pin_names_is_an_oscillator():
    result = classify("Y3", ["CLOCK_4PIN"], pin_names=["EN", "GND", "OUT", "VDD"])
    assert result.kind == ComponentKind.OSCILLATOR


def test_oscillator_keyword_in_bom_description():
    result = classify("Y4", ["CLOCK_4PIN"], "OSC 25MHz 3.3V SMD", pin_names=["1", "2", "3", "4"])
    assert result.kind == ComponentKind.OSCILLATOR


def test_library_symbol_overrides_wrong_designator_and_is_noted():
    # A crystal mistakenly named with the test-point prefix:
    result = classify("X5", ["QUARTZ_NX2016AA"], pin_names=["1", "2", "3", "4"])
    assert result.kind == ComponentKind.CRYSTAL
    assert result.source == SOURCE_COMP_TYPE
    assert result.notes and "QUARTZ_NX2016AA" in result.notes[0]


def test_bom_description_disagreement_is_noted_but_prefix_kept():
    result = classify("Y6", ["UNKNOWN_SYMBOL"], "IR LED 850nm", pin_names=["A", "C"])
    assert result.kind == ComponentKind.CRYSTAL
    assert result.notes


def test_single_pin_part_cannot_be_a_crystal():
    result = classify("Y7", ["OTHER"], pin_names=["1"])
    assert result.kind == ComponentKind.OTHER
    assert result.notes


def _findings(records, bom=None):
    graph = graph_from_records(records, bom)
    return run_all_rules(RuleContext(graph=graph, matches=run_all_recognizers(graph), has_bom=bom is not None))


def test_special_testpoint_does_not_trigger_crystal_rule():
    findings = _findings([pin("X1", "1", "POS", net_name="SIG")])
    assert not [f for f in findings if f.rule_id == "crystal_missing_load_caps"]


def test_oscillator_skips_load_caps_but_needs_decoupling():
    records = [
        pin("Y1", "1", "EN", net_name="VCC", net_type="POWER"),
        pin("Y1", "2", "GND", net_name="GND", net_type="GROUND"),
        pin("Y1", "3", "OUT", net_name="CLK"),
        pin("Y1", "4", "VDD", net_name="VCC", net_type="POWER"),
        pin("U1", "1", "CLKIN", net_name="CLK"),
    ]
    findings = _findings(records, {"Y1": bom_entry("Y1", "25MHz", "OSC 25MHz 3.3V")})
    assert not [f for f in findings if f.rule_id == "crystal_missing_load_caps"]
    assert [f for f in findings if f.rule_id == "missing_decoupling" and f.ref_des == ["Y1"]]


def test_designator_mismatch_rule_reports_misnamed_crystal():
    records = [
        pin("X5", "1", "1", net_name="XIN", comp_type="QUARTZ_NX2016AA"),
        pin("X5", "2", "2", net_name="XOUT", comp_type="QUARTZ_NX2016AA"),
    ]
    hits = [f for f in _findings(records) if f.rule_id == "designator_kind_mismatch"]
    assert len(hits) == 1 and hits[0].ref_des == ["X5"]


def test_real_projects_have_no_designator_mismatch(project1_findings):
    assert not [f for f in project1_findings if f.rule_id == "designator_kind_mismatch"]
