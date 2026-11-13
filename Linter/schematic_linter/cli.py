"""Command-line interface."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Collection, Mapping, Optional, Tuple

import click
from rich.console import Console
from rich.table import Table

from . import __version__
from .config import Severity
from .parsers.bom_parser import BomParseError
from .parsers.flatten_check import NonFlattenedNetlistError
from .parsers.netlist_parser import NetlistParseError
from .pipeline import PipelineResult, run_pipeline
from .project import ProjectDiscoveryError
from .rules import available_rules
from .settings import load_profile

console = Console()


@click.group()
@click.version_option(version=__version__, prog_name="schematic-linter")
def main() -> None:
    """Topology-aware netlist linter for flat Zuken Design Gateway netlists."""


@main.command()
@click.argument("project_dir", type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.option(
    "--output",
    "output_dir",
    type=click.Path(path_type=Path),
    default=None,
    help="Directory to write report.html and graph.json to (default: Reports/<project name>).",
)
@click.option(
    "--profile",
    "profile_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
    help="Check profile (.json, saved from the GUI) selecting checks and thresholds.",
)
@click.option(
    "--disable",
    "disabled",
    multiple=True,
    metavar="RULE_ID",
    help="Skip this check (repeatable). See 'schematic-linter list-rules'.",
)
def analyze(project_dir: Path, output_dir: Optional[Path], profile_path: Optional[Path], disabled: Tuple[str, ...]) -> None:
    """Analyze PROJECT_DIR: a folder with a netlist and optionally an eBOM and schematic PDF."""

    all_ids = [r.rule_id for r in available_rules()]
    unknown = sorted(set(disabled) - set(all_ids))
    if unknown:
        raise click.BadParameter(f"unknown rule id(s): {', '.join(unknown)}", param_hint="--disable")

    thresholds = {}
    skip = set(disabled)
    if profile_path is not None:
        try:
            profile = load_profile(profile_path)
        except ValueError as exc:
            raise click.BadParameter(str(exc), param_hint="--profile")
        thresholds = profile.thresholds
        skip |= set(profile.disabled_rules)

    enabled = [rid for rid in all_ids if rid not in skip] if skip else None
    exit_code, _result = run_analysis(project_dir, output_dir, enabled_rules=enabled, thresholds=thresholds)
    if exit_code:
        sys.exit(exit_code)


def run_analysis(
    project_dir: Path,
    output_dir: Optional[Path] = None,
    out: Optional[Console] = None,
    enabled_rules: Optional[Collection[str]] = None,
    thresholds: Optional[Mapping[str, object]] = None,
) -> Tuple[int, Optional[PipelineResult]]:
    """Runs the linter and prints a summary, *without* exiting the interpreter.

    Returns ``(exit_code, result)``: exit code 0 = no errors found, 1 = at
    least one Error-severity finding, 2/3/4 = input / non-flat netlist /
    parse problem (``result`` is ``None`` for those). This is the function to
    call from an interactive session (Spyder, Jupyter, IPython) where
    ``sys.exit()`` would be unwelcome -- see ``run_linter.py``.
    """

    out = out or console
    try:
        result = run_pipeline(
            Path(project_dir),
            Path(output_dir) if output_dir is not None else None,
            enabled_rules=enabled_rules,
            thresholds=thresholds,
        )
    except ProjectDiscoveryError as exc:
        out.print(f"[bold red]Input error:[/bold red] {exc}")
        return 2, None
    except NonFlattenedNetlistError as exc:
        out.print(f"[bold red]Netlist rejected -- cannot analyze:[/bold red] {exc}")
        return 3, None
    except (NetlistParseError, BomParseError) as exc:
        out.print(f"[bold red]Could not parse input file:[/bold red] {exc}")
        return 4, None

    _print_summary(result, out)

    error_count = sum(1 for f in result.findings if f.severity == Severity.ERROR)
    return (1 if error_count else 0), result


@main.command("list-rules")
def list_rules() -> None:
    """List all checks with their RULE_ID (for --disable)."""

    table = Table()
    table.add_column("RULE_ID", style="cyan", no_wrap=True)
    table.add_column("Check")
    table.add_column("Description")
    for rule in available_rules():
        table.add_row(rule.rule_id, rule.name, rule.description + ("  (needs eBOM)" if rule.requires_bom else ""))
    console.print(table)


@main.command()
def gui() -> None:
    """Open the graphical user interface."""

    from .gui import main as gui_main

    gui_main([])


def _print_summary(result: PipelineResult, console: Console = console) -> None:
    counts = {sev: 0 for sev in Severity}
    for finding in result.findings:
        counts[finding.severity] += 1

    console.print()
    table = Table(title=f"Schematic Linter \u2014 {result.project.project_dir.name}")
    table.add_column("Severity")
    table.add_column("Count", justify="right")
    table.add_row("[bold red]Error[/bold red]", str(counts[Severity.ERROR]))
    table.add_row("[bold yellow]Warning[/bold yellow]", str(counts[Severity.WARNING]))
    table.add_row("[bold blue]Info[/bold blue]", str(counts[Severity.INFO]))
    console.print(table)

    console.print(
        f"Inputs used: netlist={result.project.netlist_path.name}, "
        f"eBOM={result.project.bom_path.name if result.project.bom_path else 'none'}, "
        f"PDF={result.project.pdf_path.name if result.project.pdf_path else 'none'}"
    )
    console.print(f"Components: {len(result.graph.components)}  Nets: {len(result.graph.nets)}")
    console.print(f"Graph saved to:  [cyan]{result.graph_path}[/cyan]")
    console.print(f"Report saved to: [cyan]{result.report_path}[/cyan]")


if __name__ == "__main__":
    main()
