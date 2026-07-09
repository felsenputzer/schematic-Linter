from schematic_linter.graph.serialize import load_graph
from schematic_linter.pipeline import run_pipeline


def test_pipeline_runs_end_to_end_against_sample_project(project1_dir, tmp_path):
    result = run_pipeline(project1_dir, output_dir=tmp_path)

    assert result.report_path.exists()
    assert result.graph_path.exists()
    assert result.report_path.parent == tmp_path

    html = result.report_path.read_text(encoding="utf-8")
    assert "Topology-Aware Netlist Linter Report" in html
    assert "data:image/png;base64," in html  # PDF snippets got embedded

    reloaded_graph = load_graph(result.graph_path)
    assert len(reloaded_graph.components) == len(result.graph.components)


def test_pipeline_known_findings_from_sample_project(project1_dir, tmp_path):
    """Cross-checks the pipeline's output against the specific,
    hand-verifiable issues known to be present in the bundled sample
    design (see project notes / TestData/Projekt1)."""

    result = run_pipeline(project1_dir, output_dir=tmp_path)
    by_rule = {}
    for f in result.findings:
        by_rule.setdefault(f.rule_id, []).append(f)

    assert by_rule["power_pin_miswire"][0].ref_des == ["U03"]
    assert by_rule["unconnected_power_pin"][0].ref_des == ["U04"]
    assert set(by_rule["redundant_pulls"][0].ref_des) == {"R01", "R02"}
    # 081708R12/08R09 are 0Ohm, but they sit between an op-amp output and a
    # transistor base -- not a pull resistor -- so they must NOT be
    # reported here (regression test for a real false positive).
    assert not by_rule.get("zero_ohm_pull_review")
    assert not by_rule.get("contention_pull_up_down")

    # U04's OE (pin 13) is wired to the chain net that should have gone to
    # its A (pin 14) pin instead -- a real pin-swap seeded in the sample
    # design. Caught by comparing against sibling 74XX595 instances U02/U03.
    sibling_mismatches = {f.ref_des[0]: f for f in by_rule["sibling_pin_mismatch"]}
    assert "U04" in sibling_mismatches
    assert sibling_mismatches["U04"].details["pin_name"] == "OE"
    # U02's SCK sits behind a series-termination resistor (R0003) on its way
    # to the common SCK bus -- must NOT be flagged (regression test for the
    # false positive found while designing this rule).
    assert "U02" not in sibling_mismatches

    error_findings = [f for f in result.findings if f.severity.value == "error"]
    assert len(error_findings) == 1


def test_pipeline_without_bom_or_pdf(project1_netlist_path, tmp_path):
    project_dir = tmp_path / "netlist_only"
    project_dir.mkdir()
    (project_dir / "TestDesign.ndf").write_bytes(project1_netlist_path.read_bytes())

    result = run_pipeline(project_dir, output_dir=tmp_path / "out")

    assert result.project.bom_path is None
    assert result.project.pdf_path is None
    assert result.report_path.exists()

    html = result.report_path.read_text(encoding="utf-8")
    assert "eBOM not provided" in html
    assert "schematic PDF not provided" in html
    assert "data:image/png;base64," not in html

    # value-dependent rule downgrades: no missing_decoupling (bom-gated).
    assert not [f for f in result.findings if f.rule_id == "missing_decoupling"]
    # Pull-up/down resistors now have unknown values (no eBOM) -> downgraded
    # to Info rather than silently skipped or errored.
    zero_ohm = [f for f in result.findings if f.rule_id == "zero_ohm_pull_review"]
    assert zero_ohm
    assert all(f.severity.value == "info" for f in zero_ohm)
    assert {f.ref_des[0] for f in zero_ohm} == {"R01", "R02", "R16", "R17"}
