"""Crops an image snippet out of a schematic PDF page around a component's
text label, sized appropriately for the component's kind, with the exact
match highlighted.

A fixed-size crop window is fine for a 2-pin resistor but useless for a
large IC (either too tight to show its context, or -- if sized for the
IC -- wastefully large for a passive). The margin therefore comes from a
lookup table keyed by ``ComponentKind``. If even the largest configured
margin would still crop an area comparable to the whole page, we fall back
to rendering the full page with the match highlighted instead.
"""

from __future__ import annotations

from typing import Optional

import fitz

from ..config import (
    CROP_DPI,
    CROP_FULL_PAGE_AREA_FRACTION,
    CROP_MARGIN_LARGE,
    CROP_MARGIN_MEDIUM,
    CROP_MARGIN_SMALL,
)
from ..graph.model import ComponentKind
from .locator import TextHit

_MARGIN_BY_KIND = {
    ComponentKind.RESISTOR: CROP_MARGIN_SMALL,
    ComponentKind.CAPACITOR: CROP_MARGIN_SMALL,
    ComponentKind.INDUCTOR: CROP_MARGIN_SMALL,
    ComponentKind.DIODE: CROP_MARGIN_SMALL,
    ComponentKind.TESTPOINT: CROP_MARGIN_SMALL,
    ComponentKind.CRYSTAL: CROP_MARGIN_MEDIUM,
    ComponentKind.TRANSISTOR: CROP_MARGIN_MEDIUM,
    ComponentKind.CONNECTOR: CROP_MARGIN_MEDIUM,
    ComponentKind.IC: CROP_MARGIN_LARGE,
    ComponentKind.OTHER: CROP_MARGIN_MEDIUM,
}

_HIGHLIGHT_COLOR = (0.87, 0.11, 0.11)
_HIGHLIGHT_PAD = 4.0
_HIGHLIGHT_WIDTH = 2.2


def margin_for_kind(kind: ComponentKind) -> float:
    return _MARGIN_BY_KIND.get(kind, CROP_MARGIN_MEDIUM)


def _render_with_highlight(doc: fitz.Document, page_index: int, clip_rect: fitz.Rect, highlight_rect: fitz.Rect) -> bytes:
    """Renders ``clip_rect`` of a page to PNG bytes with a highlight box.

    Works on a throwaway single-page copy of the document so the
    highlight never leaks into crops for other findings on the same page.
    """

    tmp_doc = fitz.open()
    try:
        tmp_doc.insert_pdf(doc, from_page=page_index, to_page=page_index)
        tmp_page = tmp_doc[0]
        padded = highlight_rect + (-_HIGHLIGHT_PAD, -_HIGHLIGHT_PAD, _HIGHLIGHT_PAD, _HIGHLIGHT_PAD)
        tmp_page.draw_rect(padded, color=_HIGHLIGHT_COLOR, width=_HIGHLIGHT_WIDTH)

        zoom = CROP_DPI / 72.0
        matrix = fitz.Matrix(zoom, zoom)
        pixmap = tmp_page.get_pixmap(matrix=matrix, clip=clip_rect)
        return pixmap.tobytes("png")
    finally:
        tmp_doc.close()


def crop_snippet(doc: fitz.Document, hit: TextHit, kind: ComponentKind) -> bytes:
    """Return PNG bytes of a crop around ``hit``, sized for ``kind``."""

    page = doc[hit.page_index]
    page_rect = page.rect
    margin = margin_for_kind(kind)

    crop_rect = (hit.rect + (-margin, -margin, margin, margin)) & page_rect
    page_area = page_rect.width * page_rect.height
    crop_area = crop_rect.width * crop_rect.height

    if page_area <= 0 or crop_area / page_area >= CROP_FULL_PAGE_AREA_FRACTION:
        crop_rect = page_rect

    return _render_with_highlight(doc, hit.page_index, crop_rect, hit.rect)


def open_pdf(path) -> Optional[fitz.Document]:
    try:
        return fitz.open(path)
    except Exception:
        return None
