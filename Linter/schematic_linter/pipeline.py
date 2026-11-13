"""Ties together discovery, parsing, graph building, pattern/rule
evaluation, and report generation into a single entry point used by the CLI."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Collection, List, Mapping, Optional

from . import config
from .config import GRAPH_FILENAME, REPORT_FILENAME, REPORTS_DIRNAME
from .graph import CircuitGraph, build_graph, save_graph
from .parsers import check_flattened, parse_bom, parse_netlist
from .patterns import run_all_recognizers
from .project import ProjectFiles, discover_project
from .report import generate_report
from .rules import RuleContext, available_rules, run_all_rules
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


def default_output_dir(project_dir: Path) -> Path:
    """Public alias of the default output location (shown in the GUI)."""

    return _default_output_dir(Path(project_dir))


ProgressCallback = Callable[[str], None]


def run_pipeline(
    project_dir: Path,
    output_dir: Optional[Path] = None,
    *,
    enabled_rules: Optional[Collection[str]] = None,
    thresholds: Optional[Mapping[str, object]] = None,
    progress: Optional[ProgressCallback] = None,
) -> PipelineResult:
    """Runs the whole analysis.

    ``enabled_rules``: rule ids to run (``None`` = all rules).
    ``thresholds``: overrides for ``config.TUNABLE_THRESHOLDS`` keys, applied
    only for this run (raises ``ValueError`` on an invalid value).
    ``progress``: called with a short human-readable status line per step.
    """

    def step(message: str) -> None:
        if progress is not None:
            progress(message)

    with config.override(thresholds):
        return _run(project_dir, output_dir, enabled_rules, dict(thresholds or {}), step)


def _run(project_dir, output_dir, enabled_rules, thresholds, step) -> PipelineResult:
    step(f"Looking for input files in {project_dir}")
    project = discover_project(project_dir)

    if output_dir is None:
        output_dir = _default_output_dir(project.project_dir)
    output_dir = Path(output_dir)

    step(f"Reading netlist {project.netlist_path.name}")
    pin_records = parse_netlist(project.netlist_path)
    check_flattened(pin_records)  # raises NonFlattenedNetlistError to reject non-flat netlists

    bom_entries = None
    if project.bom_path is not None:
        step(f"Reading eBOM {project.bom_path.name}")
        bom_entries = parse_bom(project.bom_path)

    step("Building component/net graph")
    graph = build_graph(pin_records, bom_entries)

    all_rules = available_rules()
    disabled = [r.name for r in all_rules if enabled_rules is not None and r.rule_id not in enabled_rules]
    changed_thresholds = [
        f"{t.label}: {thresholds[t.key]:g} (default {t.default:g})"
        for t in config.TUNABLE_THRESHOLDS
        if t.key in thresholds and float(thresholds[t.key]) != float(t.default)
    ]

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
        "disabled_checks": disabled,
        "changed_thresholds": changed_thresholds,
    }

    graph_path = output_dir / GRAPH_FILENAME
    step(f"Saving graph to {graph_path}")
    save_graph(graph, graph_path, metadata=metadata)

    step("Recognizing circuit patterns")
    matches = run_all_recognizers(graph)
    ctx = RuleContext(graph=graph, matches=matches, has_bom=bom_entries is not None)
    step(f"Running {len(all_rules) - len(disabled)} of {len(all_rules)} checks")
    findings = run_all_rules(ctx, enabled=enabled_rules)

    report_path = output_dir / REPORT_FILENAME
    step("Writing report" + (" (cropping schematic snippets from the PDF)" if project.pdf_path else ""))
    generate_report(graph, findings, report_path, metadata, pdf_path=project.pdf_path)

    return PipelineResult(
        project=project,
        graph=graph,
        findings=findings,
        graph_path=graph_path,
        report_path=report_path,
    )
