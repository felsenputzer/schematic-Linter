from schematic_linter.rules import RuleContext, run_all_rules

from ..helpers import graph_from_records, pin


def test_clean_divider_pair_is_not_reported_as_contention():
    graph = graph_from_records(
        [
            pin("R1", "1", "A", net_name="VCC", net_type="POWER"),
            pin("R1", "2", "B", net_name="TAP"),
            pin("R2", "1", "A", net_name="TAP"),
            pin("R2", "2", "B", net_name="GND", net_type="GROUND"),
            pin("U1", "1", "AIN", net_name="TAP", comp_type="IC"),
        ]
    )
    from schematic_linter.patterns import run_all_recognizers

    matches = run_all_recognizers(graph)
    ctx = RuleContext(graph=graph, matches=matches, has_bom=False)
    findings = run_all_rules(ctx)
    assert not any(f.rule_id == "contention_pull_up_down" for f in findings)


def test_extra_pull_up_alongside_divider_is_reported_as_real_contention():
    # Two pull-ups + one pull-down on the same net: not a clean 2-resistor
    # divider anymore (voltage_divider.py only matches exactly 2 resistors
    # on the tap), so this must be flagged as genuine contention.
    graph = graph_from_records(
        [
            pin("R1", "1", "A", net_name="VCC", net_type="POWER"),
            pin("R1", "2", "B", net_name="SIG"),
            pin("R2", "1", "A", net_name="VCC", net_type="POWER"),
            pin("R2", "2", "B", net_name="SIG"),
            pin("R3", "1", "A", net_name="SIG"),
            pin("R3", "2", "B", net_name="GND", net_type="GROUND"),
            pin("U1", "1", "IN", net_name="SIG", comp_type="IC"),
        ]
    )
    from schematic_linter.patterns import run_all_recognizers

    matches = run_all_recognizers(graph)
    ctx = RuleContext(graph=graph, matches=matches, has_bom=False)
    findings = run_all_rules(ctx)

    contention = [f for f in findings if f.rule_id == "contention_pull_up_down"]
    assert len(contention) == 1
    assert set(contention[0].ref_des) == {"R1", "R2", "R3"}

    redundant = [f for f in findings if f.rule_id == "redundant_pulls"]
    assert len(redundant) == 1
    assert set(redundant[0].ref_des) == {"R1", "R2"}


def test_real_project_has_no_contention_finding(project1_findings):
    assert not any(f.rule_id == "contention_pull_up_down" for f in project1_findings)


def test_real_project_redundant_pull_up_on_fault(project1_findings):
    matches = [f for f in project1_findings if f.rule_id == "redundant_pulls"]
    assert len(matches) == 1
    assert set(matches[0].ref_des) == {"R01", "R02"}
    assert matches[0].nets == ["FAULT"]
