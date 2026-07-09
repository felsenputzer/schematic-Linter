"""Ties together discovery, parsing, graph building, pattern/rule
evaluation, and report generation into a single entry point used by the CLI."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from .config import GRAPH_FILENAME, REPORT_FILENAME, REPORTS_DIRNAME
from .graph import CircuitGraph, build_graph, save_graph
from .parsers import check_flattened, parse_bom, parse_netlist
from .patterns import run_all_recognizers
from .project import ProjectFiles, discover_project
from .report import generate_report
from .rules import RuleContext, run_all_rules
from .rules.base import Finding


@dataclass
class PipelineResult:
    project: ProjectFiles
    graph: CircuitGraph
    findings: List[Finding]
    graph_path: Path
    report_path: Path


def _default_output_dir(project_dir: Path) -> Path:
    """Reports/<project folder name>, anchored at whichever ancestor of the
    project folder already has a ``Reports`` directory (matching this
    repo's ``TestData/<project>`` + ``Reports/<project>`` layout); falls
    back to creating one next to the project folder's parent."""

    candidates = [project_dir.parent.parent / REPORTS_DIRNAME, project_dir.parent / REPORTS_DIRNAME]
    for candidate in candidates:
        if candidate.is_dir():
            return candidate / project_dir.name
    return project_dir.parent / REPORTS_DIRNAME / project_dir.name


def run_pipeline(project_dir: Path, output_dir: Optional[Path] = None) -> PipelineResult:
    project = discover_project(project_dir)

    if output_dir is None:
        output_dir = _default_output_dir(project.project_dir)
    output_dir = Path(output_dir)

    pin_records = parse_netlist(project.netlist_path)
    check_flattened(pin_records)  # raises NonFlattenedNetlistError to reject non-flat netlists

    bom_entries = None
    if project.bom_path is not None:
        bom_entries = parse_bom(project.bom_path)

    graph = build_graph(pin_records, bom_entries)

    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    metadata = {
        "project_name": project.project_dir.name,
        "netlist_file": project.netlist_path.name,
        "bom_file": project.bom_path.name if project.bom_path else None,
        "pdf_file": project.pdf_path.name if project.pdf_path else None,
        "has_bom": bom_entries is not None,
        "has_pdf": project.pdf_path is not None,
        "component_count": len(graph.components),
        "net_count": len(graph.nets),
        "generated_at": generated_at,
    }

    graph_path = output_dir / GRAPH_FILENAME
    save_graph(graph, graph_path, metadata=metadata)

    matches = run_all_recognizers(graph)
    ctx = RuleContext(graph=graph, matches=matches, has_bom=bom_entries is not None)
    findings = run_all_rules(ctx)

    report_path = output_dir / REPORT_FILENAME
    generate_report(graph, findings, report_path, metadata, pdf_path=project.pdf_path)

    return PipelineResult(
        project=project,
        graph=graph,
        findings=findings,
        graph_path=graph_path,
        report_path=report_path,
    )
