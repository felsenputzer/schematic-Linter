# Topology-Aware Netlist Linter

A command-line tool for electronics engineers that finds design mistakes in
a schematic by analyzing its **structural connectivity** — not by
simulating it. It parses a flat Zuken Design Gateway netlist (optionally
enriched with an eBOM and a searchable schematic PDF), builds a
component/net graph, recognizes common circuit topology patterns (voltage
dividers, RC filters, pull-ups/downs, decoupling caps, crystal load caps,
...), checks them against a rule set, and writes a single self-contained
HTML report with cropped schematic snippets for each finding.

No simulation, no LVS, no hierarchical/unflattened netlist support —
purely a fast, structural sanity check you can run before/alongside
review.

## Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

This installs the `schematic-linter` command (backed by `networkx`,
`PyMuPDF`, `Jinja2`, `click`, and `rich`).

### Standalone Windows build

For running on a Windows machine with no Python installed at all, see
[`packaging/windows/`](packaging/windows/): a PyInstaller spec and build
script that produce a single self-contained `schematic-linter.exe`. It's
built and smoke-tested on a real Windows runner by
[`.github/workflows/windows.yml`](../.github/workflows/windows.yml) on every
push.

## Usage

```bash
schematic-linter analyze path/to/ProjectFolder
```

`ProjectFolder` must contain **exactly one** `.ndf` netlist, and may
optionally contain **one** eBOM `.csv` and **one** schematic `.pdf`. By
default, output is written to `Reports/<ProjectFolder name>/` (found by
walking up from the project folder for an existing `Reports` sibling
directory; falls back to creating one next to the project folder). Use
`--output DIR` to override.

Two files are produced:

- `report.html` — a standalone report (all schematic snippets are embedded
  as base64 images, so it's a single file you can email/archive).
- `graph.json` — the full component/net graph, saved independently of the
  report so it can be reused/inspected later without re-parsing anything.

The process exits non-zero if any `Error`-severity finding was produced,
so it's usable as a CI gate.

`report.html` is interactive: click any of the Findings/Errors/Warnings/Infos
badges at the top to hide/show findings of that severity (click it again, or
click the "Findings" badge, to bring them back) — handy for focusing on one
severity at a time in a large report.

## How it works

```
netlist (+ eBOM, + PDF)
  -> parsers/          parse netlist & eBOM, parse component values, sanity-check flatness
  -> graph/             build a Component/Net graph (networkx), tag POWER/GROUND nets
  -> patterns/          recognize topology patterns (divider, RC filter, pull-up/down, ...)
  -> rules/             check patterns (+ graph) against a rule set -> Findings
  -> pdf/ + report/     crop matching schematic snippets, render the HTML report
```

Patterns and rules are each auto-discovered from their package (one file
per pattern/rule) — adding either is just adding a new file that exports
`recognize()` (patterns) or `evaluate()` (rules).

### Findings

Each finding has a severity:

- **Error** — a structural problem that's almost certainly wrong (e.g. a
  pull-up and pull-down fighting on the same net with no valid divider
  explanation; a `VCC`-named pin wired to a `GROUND`-tagged net).
- **Warning** — a likely problem worth a human look (redundant pulls, a
  resistor shared between two RC filter paths, a resistor that feeds a node
  shared by two or more independently-filtered RC branches (a common source
  impedance that couples otherwise-independent measurements — see
  `shared_source_resistor`), a missing crystal load cap, an unconnected
  power/ground pin, a 0Ω "pull" resistor, a pin wired differently from
  same-named pins on sibling instances of the same repeated part).
- **Info** — worth noting but often fine (an unloaded divider tap, more
  decoupling caps than expected with no clear bulk cap, a single-pin net).

Rules that depend on a component's value (e.g. "is this pull resistor
0Ω?") **degrade gracefully** rather than silently skipping or erroring
when the eBOM is missing or doesn't cover that part: they still run, at
`Info` severity, with a `value unknown — check manually` note. A rule that
inherently can't produce a meaningful signal without the eBOM at all (only
`missing_decoupling`, per spec) is skipped entirely when no eBOM is given.

## Known limitations

- **Sibling pin consistency (`sibling_pin_mismatch`) only helps for
  repeated parts.** It flags a pin that connects to a different net than
  the same-named pin on 3+ sibling instances of the identical part (same
  netlist comp-type) — e.g. it catches a shift register whose `OE` pin is
  swapped with its `A` pin relative to two other, identically-wired
  instances of the same chip, with no per-part pin-function or datasheet
  knowledge at all. It requires a part to repeat at least 3 times with a
  unanimous-minus-one majority (a 2-vs-2 split, for instance, is left
  alone as ambiguous rather than guessed at), and nets are canonicalized
  through inline 2-pin series resistors/inductors first so a legitimate
  series-termination resistor isn't mistaken for a mismatch. It **cannot**
  catch a pin swap on a one-off/unique IC — that would require real
  per-part pin-function/datasheet knowledge, which is out of scope for a
  purely topology-aware tool.
- **Non-flattened netlist detection is currently a stub.** A candidate
  heuristic (reject if one ref-des maps to more than one internal
  placement/instance id) was designed and tested against the bundled
  sample netlist, and rejected: it produces false positives on entirely
  valid flattened designs (multi-gate ICs and multi-pin connectors in the
  sample get a distinct instance id per gate/pin). Rather than ship a
  heuristic that would reject good designs, `parsers/flatten_check.py`
  currently always passes, with a clear docstring and TODO, pending a real
  non-flattened sample to validate a heuristic against.
- Component classification and value parsing are heuristic (reference
  designator prefix + component-type/description keywords). They're
  table-driven and easy to extend, but an unusual part-numbering scheme
  could still be misclassified as `OTHER`.
- **Power/ground anchor nets are taken *only* from the netlist's own
  `NET_TYPE` tag** (`POWER`/`GROUND`/blank) -- there is deliberately no
  name-based guessing (e.g. "starts with V", "contains RAW"). An earlier
  version of this tool added such a fallback and it backfired: nets named
  `RAW_1`/`RAW_2` in the sample design looked like supply rails by name
  but are actually op-amp-output-to-transistor-base feedback nodes, and
  guessing "power" from the name caused two resistors in that path
  (`081708R12`, `08R09`) to be misreported as "0Ω pull-up resistors". If a
  netlist doesn't reliably tag its power/ground nets, those nets simply
  won't be treated as anchors -- which is the safer failure mode.
- PDF cropping only works if the PDF has a text layer (a scanned image PDF
  won't have any locatable ref-des labels); the report is still generated
  without images in that case.
- **`shared_rc_resistor` vs. `shared_source_resistor`** cover two distinct
  ways a resistor can inadvertently couple two RC filters: `shared_rc_resistor`
  flags a single resistor that itself has a decoupling/filter capacitor on
  *both* of its terminal nets (it's literally part of two filters at once);
  `shared_source_resistor` flags a *different, upstream* resistor that feeds
  a node shared by two or more separate branch resistors, each going on to
  its own independent RC filter (e.g. two redundant measurement dividers fed
  from the same op-amp output through one shared resistor) — the coupling
  here comes from the shared node's non-negligible source impedance, not
  from any single resistor belonging to two filters. Both degrade to `Info`
  when the eBOM doesn't cover a relevant resistor's value, and neither flags
  a link resistor whose eBOM value resolves to (approximately) 0Ω, since
  that's not really adding any impedance.

## Testing

```bash
pip install -e ".[dev]"
pytest
```

The test suite includes unit tests per parser/pattern/rule module plus an
end-to-end test that runs the full pipeline against `TestData/Projekt1`
and checks it reproduces the specific, hand-verified issues known to be
present in that sample design (a miswired IC power pin, a redundant
pull-up, a shared RC filter resistor, an unconnected ground pin, a
sibling-instance pin swap on a shift register's `OE` pin, and no
false-positive pull-up/pull-down contention on the sample's legitimate
voltage divider) -- as well as regression tests for false positives found
and fixed along the way (see "Known limitations" above).

`TestData/Projekt2` is a second, larger sample with different reference
designators (an external RefDes-numbering change) that additionally
contrasts a good and a bad redundant-measurement front end: `R18`/`R19`
(with `C11`/`C12`) each tap the same op-amp output directly, so they don't
influence each other, while `R15`/`R16`/`R17` (with `C09`/`C10`) is the same
circuit with one extra resistor (`R15`) inserted between the op-amp and the
split -- current from either branch now develops a voltage drop across
`R15` that's visible to the other, which `shared_source_resistor` flags.
