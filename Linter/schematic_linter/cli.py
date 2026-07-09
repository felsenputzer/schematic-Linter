"""Command-line interface."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

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
def analyze(project_dir: Path, output_dir: Optional[Path]) -> None:
    """Analyze PROJECT_DIR: a folder with a netlist and optionally an eBOM and schematic PDF."""

    try:
        result = run_pipeline(project_dir, output_dir)
    except ProjectDiscoveryError as exc:
        console.print(f"[bold red]Input error:[/bold red] {exc}")
        sys.exit(2)
    except NonFlattenedNetlistError as exc:
        console.print(f"[bold red]Netlist rejected -- cannot analyze:[/bold red] {exc}")
        sys.exit(3)
    except (NetlistParseError, BomParseError) as exc:
        console.print(f"[bold red]Could not parse input file:[/bold red] {exc}")
        sys.exit(4)

    _print_summary(result)

    error_count = sum(1 for f in result.findings if f.severity == Severity.ERROR)
    if error_count:
        sys.exit(1)


def _print_summary(result: PipelineResult) -> None:
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
