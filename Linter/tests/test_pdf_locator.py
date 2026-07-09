import fitz
import pytest

from schematic_linter.graph.model import ComponentKind
from schematic_linter.pdf.cropper import crop_snippet, margin_for_kind
from schematic_linter.pdf.locator import find_ref_des


@pytest.fixture
def synthetic_doc():
    doc = fitz.open()
    page = doc.new_page(width=600, height=400)
    page.insert_text((50, 60), "R120")
    page.insert_text((50, 100), "R12A")
    page.insert_text((50, 140), "R12")
    page.insert_text((50, 180), "resistorR12notaword")
    yield doc
    doc.close()


def _word_rect(doc, text):
    words = doc[0].get_text("words")
    matches = [w for w in words if w[4] == text]
    assert len(matches) == 1, f"expected exactly one {text!r} word token, found {len(matches)}"
    w = matches[0]
    return fitz.Rect(w[0], w[1], w[2], w[3])


def test_exact_match_does_not_match_longer_designator(synthetic_doc):
    hits = find_ref_des(synthetic_doc, "R12")
    assert len(hits) == 1
    # the matched rect must be the standalone "R12" label, not "R120"/"R12A"
    assert hits[0].rect == _word_rect(synthetic_doc, "R12")


def test_no_match_returns_empty_list(synthetic_doc):
    assert find_ref_des(synthetic_doc, "R999") == []


def test_search_for_longer_designator_finds_it_exactly(synthetic_doc):
    hits = find_ref_des(synthetic_doc, "R120")
    assert len(hits) == 1
    assert hits[0].rect == _word_rect(synthetic_doc, "R120")


def test_real_pdf_exact_match_for_known_ref_des(project1_pdf_path):
    doc = fitz.open(project1_pdf_path)
    try:
        hits = find_ref_des(doc, "U03")
        assert len(hits) == 1

        # room-code-prefixed long-form ref-des must not spuriously match a
        # search for the short suffix, and vice versa
        assert find_ref_des(doc, "R12") == []
        long_hits = find_ref_des(doc, "081708R12")
        assert len(long_hits) == 1
    finally:
        doc.close()


def test_crop_margin_scales_with_component_kind():
    assert margin_for_kind(ComponentKind.IC) > margin_for_kind(ComponentKind.RESISTOR)


def test_crop_snippet_returns_png_bytes(project1_pdf_path):
    doc = fitz.open(project1_pdf_path)
    try:
        hit = find_ref_des(doc, "U03")[0]
        png_bytes = crop_snippet(doc, hit, ComponentKind.IC)
        assert png_bytes[:8] == b"\x89PNG\r\n\x1a\n"
    finally:
        doc.close()
