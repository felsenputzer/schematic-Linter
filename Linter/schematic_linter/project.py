"""Discovers the netlist / eBOM / schematic-PDF inputs inside a project
folder.

Per spec, a "project" is just a folder containing up to three files: one
required netlist, and an optional eBOM and schematic PDF. This module only
does file discovery (by extension) -- it doesn't look inside any file.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Sequence


class ProjectDiscoveryError(Exception):
    """Raised when the project folder's inputs can't be unambiguously resolved."""


@dataclass(frozen=True)
class ProjectFiles:
    project_dir: Path
    netlist_path: Path
    bom_path: Optional[Path]
    pdf_path: Optional[Path]


def _find_candidates(project_dir: Path, patterns: Sequence[str]) -> List[Path]:
    found = set()
    for pattern in patterns:
        found.update(project_dir.glob(pattern))
    return sorted(found)


def _find_one(project_dir: Path, patterns: Sequence[str], kind_label: str, required: bool) -> Optional[Path]:
    matches = _find_candidates(project_dir, patterns)
    if not matches:
        if required:
            raise ProjectDiscoveryError(
                f"No {kind_label} file found in '{project_dir}' (looked for: {', '.join(patterns)})"
            )
        return None
    if len(matches) > 1:
        names = ", ".join(m.name for m in matches)
        raise ProjectDiscoveryError(
            f"Found multiple candidate {kind_label} files in '{project_dir}': {names}. "
            "A project folder must contain exactly one of each input type."
        )
    return matches[0]


def discover_project(project_dir: Path) -> ProjectFiles:
    project_dir = Path(project_dir)
    if not project_dir.is_dir():
        raise ProjectDiscoveryError(f"Project path '{project_dir}' is not a directory")

    netlist_path = _find_one(project_dir, ["*.ndf", "*.NDF"], "netlist (.ndf)", required=True)
    bom_path = _find_one(project_dir, ["*.csv", "*.CSV"], "eBOM (.csv)", required=False)
    pdf_path = _find_one(project_dir, ["*.pdf", "*.PDF"], "schematic PDF (.pdf)", required=False)

    return ProjectFiles(project_dir=project_dir, netlist_path=netlist_path, bom_path=bom_path, pdf_path=pdf_path)
