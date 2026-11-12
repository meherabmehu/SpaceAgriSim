#!/usr/bin/env python3
"""Render docs/DATASET_GAP_MATRIX.md from data/research/dataset_gap_matrix.

The JSON is the source of truth. This script exists so the matrix cannot drift from the document
that quotes it: `--check` re-renders and fails when the committed markdown differs from what the
JSON says.

    python3 ml/research/build_gap_matrix.py [--check]
"""
from __future__ import annotations
import sys

import argparse
import re
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)) if str(ROOT) not in sys.path else None  # noqa: E501
import safedata  # noqa: E402 - the repository data layer lives at the root
SOURCE = ROOT / "data" / "research" / "dataset_gap_matrix"
TARGET = ROOT / "docs" / "DATASET_GAP_MATRIX.md"

SEVERITIES = ["blocking", "major", "minor"]

CLOSING = (
    "## The two that matter most\n\n"
    "**`measured-eta`** and **`independent-et0`** decide how much the ET0 work is worth. The first "
    "says the platform computes a reference flux and cannot measure a crop's actual water use. The "
    "second says the target it validates against is one provider's reanalysis. Fixing the second is "
    "cheap and mechanical (an ERA5-Land token). Fixing the first requires an experiment.\n"
)


DECISION_KEY = re.compile(r"phase(\d+)Decision")


def decision_lines(gap: dict) -> list[str]:
    """Render any recorded per-phase decision, so a later decision cannot be filed and forgotten.

    The keys are named `phase<N>Decision` in the JSON; each one is a decision that was actually
    taken about this gap, and the point of the matrix is that the document says what was decided
    rather than only what is still missing.
    """
    lines = []
    for key in sorted(gap, key=lambda name: int((DECISION_KEY.fullmatch(name) or
                                                 re.match(r"phase(\d+)", name)).group(1))
                      if DECISION_KEY.fullmatch(name) else 10**6):
        match = DECISION_KEY.fullmatch(key)
        if not match:
            continue
        entry = gap[key]
        phase = match.group(1)
        detail = entry.get("what") or entry.get("whyRemoved") or ""
        lines.append(f"- **Phase {phase} decision:** {entry.get('decision', 'recorded')}"
                     + (f" - {detail}" if detail else ""))
        results = entry.get("results") or {}
        for model_id, outcome in results.items():
            lines.append(f"    - `{model_id}`: {outcome}")
        for artefact in entry.get("evidence") or []:
            lines.append(f"    - evidence: `{artefact}`")
        if entry.get("remainingWork"):
            lines.append(f"- **Remaining work:** {entry['remainingWork']}")
        if entry.get("whyNotClosed"):
            lines.append(f"- **Why this is still open:** {entry['whyNotClosed']}")
        elif entry.get("residualCapability"):
            lines.append(f"- **Residual capability:** {entry['residualCapability']}")
    return lines


def short_status(gap: dict) -> str:
    """The matrix column keeps the status token; the detail section keeps the whole sentence.

    Status tokens are CLOSED / PARTIALLY CLOSED / OPEN. Older entries predate the token field and
    fall back to the first clause of their status sentence, so the column never becomes a
    paragraph.
    """
    if gap.get("statusToken"):
        return gap["statusToken"]
    return gap["currentStatus"].split(";")[0].split(" - ")[0].strip()


def render(matrix: dict) -> str:
    gaps = sorted(matrix["gaps"], key=lambda gap: gap["rank"])
    counts = {severity: sum(1 for gap in gaps if gap["severity"] == severity)
              for severity in SEVERITIES}
    meaning = {}
    for gap in gaps:
        meaning.setdefault(gap["severity"], gap["severityMeaning"])

    lines = [
        "# SpaceAgriSim Dataset Gap Matrix",
        "",
        f"Generated from `data/research/dataset_gap_matrix` on {matrix['generatedOn']} "
        "by `ml/research/build_gap_matrix.py`. Edit the JSON, not this file.",
        "",
        matrix["scope"],
        "",
        f"**{len(gaps)} gaps recorded: blocking: {counts['blocking']}, "
        f"major: {counts['major']}, minor: {counts['minor']}.**",
        "",
        "A few are closed by decision rather than by data - the capability was removed instead of "
        "being kept behind a placeholder - and each of those says so and says what was searched "
        "first. The point of the matrix is that every gap, open or closed, has a named consequence "
        "for what the product is allowed to claim, and the product states that consequence rather "
        "than papering over it.",
        "",
        "## Severity",
        "",
        "| Severity | Meaning | Count |",
        "|---|---|---|",
    ]
    for severity in SEVERITIES:
        lines.append(f"| **{severity}** | {meaning[severity]} | {counts[severity]} |")

    # The counts are recomputed from the status tokens rather than read from whichever phase block
    # happens to be newest. A stored summary that disagrees with the entries above it is exactly the
    # kind of drift this file exists to prevent.
    tokens = [g.get("statusToken") or "OPEN" for g in matrix.get("gaps", [])]
    closed_by_decision = {"fractional-gravity", "yield-labels"}
    closed_by_data = sum(1 for g in matrix.get("gaps", [])
                         if (g.get("statusToken") == "CLOSED"
                             and g.get("id") not in closed_by_decision))
    latest = matrix.get("phase37") or matrix.get("phase36") or {}
    if latest:
        lines += [
            "",
            f"## Status after Phase {latest.get('phase', '')}".rstrip(),
            "",
            "Closure is counted three ways, because they are not the same thing. "
            f"**{closed_by_data}** gaps closed by data, "
            f"**{sum(1 for g in matrix.get('gaps', []) if g.get('id') in closed_by_decision)}** "
            "closed by removing the capability rather than finding a dataset, "
            f"**{tokens.count('PARTIALLY CLOSED')}** partially closed, "
            f"**{tokens.count('OPEN')}** still open.",
            "",
            (latest.get("note") or
             "Counts are recomputed from the status token on every entry, so the summary cannot "
             "disagree with the table below it."),
            "",
        ]

    lines += [
        "",
        "## Matrix",
        "",
        "| # | Capability | What is needed | Severity | Gap type | Status |",
        "|---|---|---|---|---|---|",
    ]
    for gap in gaps:
        lines.append(f"| {gap['rank']} | {gap['capability']} | {gap['needed']} | "
                     f"**{gap['severity']}** | {gap['gapType']} | {short_status(gap)} |")

    lines += ["", "## Detail", ""]
    for gap in gaps:
        lines += [
            f"### {gap['capability']}  `{gap['id']}`",
            "",
            f"- **Needed:** {gap['needed']}",
            f"- **Available:** {gap['available']}",
            f"- **Gap type:** {gap['gapType']}",
            f"- **Severity:** {gap['severity']} - {gap['severityMeaning']}",
            f"- **How it could be closed:** {gap['howCouldBeClosed']}",
            f"- **Current status:** {gap['currentStatus']}",
            *decision_lines(gap),
            "",
        ]
    return "\n".join(lines) + "\n" + CLOSING


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    matrix = safedata.load(SOURCE)
    rendered = render(matrix)

    if args.check:
        if not safedata.exists(TARGET):
            print(f"MISSING {TARGET.relative_to(ROOT)}")
            return 1
        if TARGET.read_text(encoding="utf-8") != rendered:
            print(f"STALE {TARGET.relative_to(ROOT)}: re-render from the JSON")
            return 1
        print(f"gap matrix up to date ({len(matrix['gaps'])} gaps)")
        return 0

    TARGET.write_text(rendered, encoding="utf-8")
    counts = {severity: sum(1 for gap in matrix["gaps"] if gap["severity"] == severity)
              for severity in SEVERITIES}
    print(f"wrote {TARGET.relative_to(ROOT)}: {len(matrix['gaps'])} gaps "
          f"({counts['blocking']} blocking, {counts['major']} major, {counts['minor']} minor)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
