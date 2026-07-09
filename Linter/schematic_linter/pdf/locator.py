"""Finds the exact location of a reference designator's text label in a
searchable schematic PDF.

The key requirement (see project spec's "known design challenges") is that
searching for a short designator like ``"R12"`` must never match
``"R120"``, ``"R12A"``, or incidental text that merely contains those
characters. PyMuPDF's built-in ``page.search_for()`` does substring
matching across joined text, which is exactly the failure mode we need to
avoid. Instead, this module tokenizes each page into words (as PyMuPDF
already splits them for rendering, which is how ref-des silkscreen labels
are typically extracted: as single whitespace-delimited tokens) and only
accepts a hit when a word -- or a run of adjacent words on the same line
that concatenate with no gap -- is *exactly equal* to the designator.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

import fitz

_MAX_WORD_RUN = 4  # guards against pathological concatenation search cost


@dataclass(frozen=True)
class TextHit:
    page_index: int
    rect: fitz.Rect


def _line_key(word) -> tuple:
    _x0, _y0, _x1, _y1, _text, block_no, line_no, _word_no = word
    return (block_no, line_no)


def find_ref_des(doc: fitz.Document, ref_des: str) -> List[TextHit]:
    """Return every exact match of ``ref_des`` as a standalone label in the PDF.

    Case-sensitive on purpose: reference designators are conventionally
    upper-case, and case-sensitivity avoids accidental matches against
    unrelated lower-case body text.
    """

    hits: List[TextHit] = []

    for page_index in range(len(doc)):
        page = doc[page_index]
        words = page.get_text("words")

        # 1) Fast path: a single word token equals the designator exactly.
        for w in words:
            if w[4] == ref_des:
                hits.append(TextHit(page_index=page_index, rect=fitz.Rect(w[0], w[1], w[2], w[3])))

        # 2) Fallback: some PDF generators split a label across adjacent
        #    word tokens on the same line (e.g. "R" + "12"). Only accept a
        #    concatenation that is an *exact* match for the whole
        #    designator, never a partial/substring match.
        by_line: dict = {}
        for w in words:
            by_line.setdefault(_line_key(w), []).append(w)

        for line_words in by_line.values():
            line_words.sort(key=lambda w: w[0])
            for start in range(len(line_words)):
                combined = ""
                for end in range(start, min(start + _MAX_WORD_RUN, len(line_words))):
                    combined += line_words[end][4]
                    if combined == ref_des and end > start:
                        x0 = line_words[start][0]
                        y0 = min(w[1] for w in line_words[start : end + 1])
                        x1 = line_words[end][2]
                        y1 = max(w[3] for w in line_words[start : end + 1])
                        hits.append(TextHit(page_index=page_index, rect=fitz.Rect(x0, y0, x1, y1)))
                        break
                    if len(combined) >= len(ref_des) and combined != ref_des[: len(combined)]:
                        break

    return hits
