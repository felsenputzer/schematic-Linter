"""Optional schematic-PDF support: exact ref-des lookup + adaptive cropping."""

from __future__ import annotations

from typing import Optional

import fitz

from ..graph.model import ComponentKind
from .cropper import crop_snippet, open_pdf
from .locator import TextHit, find_ref_des

__all__ = ["TextHit", "find_ref_des", "crop_snippet", "open_pdf", "get_snippet_for_ref_des"]


def get_snippet_for_ref_des(doc: fitz.Document, ref_des: str, kind: ComponentKind) -> Optional[bytes]:
    """Convenience: find + crop in one call. Returns ``None`` if not found."""

    hits = find_ref_des(doc, ref_des)
    if not hits:
        return None
    hit = hits[0]
    return crop_snippet(doc, hit, kind)
