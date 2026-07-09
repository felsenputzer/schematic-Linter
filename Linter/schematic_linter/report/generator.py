"""Assembles and renders the standalone HTML report.

All images are embedded as base64 ``data:`` URIs directly in the HTML, so
the report is a single file that's readable with no external dependencies
(no separate image files, no CDN assets, no network access needed).
"""

from __future__ import annotations

import base64
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .. import __version__
from ..config import Severity
from ..graph.model import CircuitGraph
from ..pdf import get_snippet_for_ref_des, open_pdf
from ..rules.base import Finding

_TEMPLATE_DIR = Path(__file__).parent / "templates"
_TEMPLATE_NAME = "report.html.j2"

MAX_IMAGES_PER_FINDING = 2


@dataclass
class FindingImage:
    ref_des: str
    data_uri: str


@dataclass
class ReportFinding:
    finding: Finding
    images: List[FindingImage] = field(default_factory=list)


def _severity_sort_key(finding: Finding):
    return (finding.severity.rank, finding.rule_id, finding.title)


def _build_images(graph: CircuitGraph, pdf_doc, ref_des_list: List[str]) -> List[FindingImage]:
    images: List[FindingImage] = []
    if pdf_doc is None:
        return images

    for ref_des in ref_des_list[:MAX_IMAGES_PER_FINDING]:
        component = graph.get_component(ref_des)
        if component is None:
            continue
        try:
            png_bytes = get_snippet_for_ref_des(pdf_doc, ref_des, component.kind)
        except Exception:
            png_bytes = None
        if png_bytes is None:
            continue
        encoded = base64.b64encode(png_bytes).decode("ascii")
        images.append(FindingImage(ref_des=ref_des, data_uri=f"data:image/png;base64,{encoded}"))

    return images


def generate_report(
    graph: CircuitGraph,
    findings: List[Finding],
    output_path: Path,
    metadata: Dict,
    pdf_path: Optional[Path] = None,
) -> Path:
    """Renders the HTML report to ``output_path`` and returns that path."""

    pdf_doc = open_pdf(pdf_path) if pdf_path is not None else None

    try:
        sorted_findings = sorted(findings, key=_severity_sort_key)
        report_findings = [
            ReportFinding(finding=f, images=_build_images(graph, pdf_doc, f.ref_des)) for f in sorted_findings
        ]

        counts = {
            "error": sum(1 for f in findings if f.severity == Severity.ERROR),
            "warning": sum(1 for f in findings if f.severity == Severity.WARNING),
            "info": sum(1 for f in findings if f.severity == Severity.INFO),
        }

        metadata = dict(metadata)
        metadata.setdefault("tool_version", __version__)

        env = Environment(
            loader=FileSystemLoader(str(_TEMPLATE_DIR)),
            autoescape=select_autoescape(["html"]),
        )
        template = env.get_template(_TEMPLATE_NAME)
        html = template.render(
            metadata=metadata,
            counts=counts,
            total=len(findings),
            report_findings=report_findings,
        )

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(html, encoding="utf-8")
        return output_path
    finally:
        if pdf_doc is not None:
            pdf_doc.close()
