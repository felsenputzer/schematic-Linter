import pytest

from schematic_linter.project import ProjectDiscoveryError, discover_project


def test_discover_real_project(project1_dir):
    files = discover_project(project1_dir)
    assert files.netlist_path.suffix == ".ndf"
    assert files.bom_path is not None and files.bom_path.suffix == ".csv"
    assert files.pdf_path is not None and files.pdf_path.suffix == ".pdf"


def test_discover_missing_netlist_raises(tmp_path):
    with pytest.raises(ProjectDiscoveryError):
        discover_project(tmp_path)


def test_discover_ambiguous_netlist_raises(tmp_path):
    (tmp_path / "a.ndf").write_text("x", encoding="utf-8")
    (tmp_path / "b.ndf").write_text("x", encoding="utf-8")
    with pytest.raises(ProjectDiscoveryError):
        discover_project(tmp_path)


def test_discover_netlist_only_project(tmp_path):
    (tmp_path / "only.ndf").write_text("x", encoding="utf-8")
    files = discover_project(tmp_path)
    assert files.bom_path is None
    assert files.pdf_path is None
