import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PROJECT1_DIR = REPO_ROOT / "TestData" / "Projekt1"
PROJECT2_DIR = REPO_ROOT / "TestData" / "Projekt2"

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture(scope="session")
def project1_dir() -> Path:
    assert PROJECT1_DIR.is_dir(), f"Expected sample project at {PROJECT1_DIR}"
    return PROJECT1_DIR


@pytest.fixture(scope="session")
def project1_netlist_path(project1_dir: Path) -> Path:
    return project1_dir / "TestDesign.ndf"


@pytest.fixture(scope="session")
def project1_bom_path(project1_dir: Path) -> Path:
    return project1_dir / "BOM_for_purchase_without_TP_Fiducial.csv"


@pytest.fixture(scope="session")
def project1_pdf_path(project1_dir: Path) -> Path:
    return project1_dir / "TestDesign_To_PCB_System.pdf"


@pytest.fixture(scope="session")
def project1_graph(project1_netlist_path, project1_bom_path):
    from schematic_linter.graph import build_graph
    from schematic_linter.parsers import parse_bom, parse_netlist

    records = parse_netlist(project1_netlist_path)
    bom = parse_bom(project1_bom_path)
    return build_graph(records, bom)


@pytest.fixture(scope="session")
def project1_matches(project1_graph):
    from schematic_linter.patterns import run_all_recognizers

    return run_all_recognizers(project1_graph)


@pytest.fixture(scope="session")
def project1_findings(project1_graph, project1_matches):
    from schematic_linter.rules import RuleContext, run_all_rules

    ctx = RuleContext(graph=project1_graph, matches=project1_matches, has_bom=True)
    return run_all_rules(ctx)


@pytest.fixture(scope="session")
def project2_dir() -> Path:
    assert PROJECT2_DIR.is_dir(), f"Expected sample project at {PROJECT2_DIR}"
    return PROJECT2_DIR


@pytest.fixture(scope="session")
def project2_netlist_path(project2_dir: Path) -> Path:
    return project2_dir / "TestDesign.ndf"


@pytest.fixture(scope="session")
def project2_bom_path(project2_dir: Path) -> Path:
    return project2_dir / "BOM_for_purchase_without_TP_Fiducial.csv"


@pytest.fixture(scope="session")
def project2_graph(project2_netlist_path, project2_bom_path):
    from schematic_linter.graph import build_graph
    from schematic_linter.parsers import parse_bom, parse_netlist

    records = parse_netlist(project2_netlist_path)
    bom = parse_bom(project2_bom_path)
    return build_graph(records, bom)


@pytest.fixture(scope="session")
def project2_matches(project2_graph):
    from schematic_linter.patterns import run_all_recognizers

    return run_all_recognizers(project2_graph)


@pytest.fixture(scope="session")
def project2_findings(project2_graph, project2_matches):
    from schematic_linter.rules import RuleContext, run_all_rules

    ctx = RuleContext(graph=project2_graph, matches=project2_matches, has_bom=True)
    return run_all_rules(ctx)
