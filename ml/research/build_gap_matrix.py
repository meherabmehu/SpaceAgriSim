#!/usr/bin/env python3
"""Render docs/DATASET_GAP_MATRIX.md from data/research/dataset_gap_matrix.json.

The JSON is the source of truth. This script exists so the matrix cannot drift from the document
that quotes it: `--check` re-renders and fails when the committed markdown differs from what the
JSON says.

    python3 ml/research/build_gap_matrix.py [--check]
"""
from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "data" / "research" / "dataset_gap_matrix.json"
TARGET = ROOT / "docs" / "DATASET_GAP_MATRIX.md"

SEVERITIES = ["blocking", "major", "minor"]

CLOSING = (
    "## The two that matter most\n\n"
    "**`measured-eta`** and **`independent-et0`** decide how much the ET0 work is worth. The first "
    "says the platform computes a reference flux and cannot measure a crop's actual water use. The "
    "second says the target it validates against is one provider's reanalysis. Fixing the second is "
    "cheap and mechanical (an ERA5-Land token). Fixing the first requires an experiment.\n"
)


def short_status(gap: dict) -> str:
    """The matrix column keeps the first clause; the detail section keeps the whole sentence."""
    return gap["currentStatus"].split(";")[0].strip()


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
        f"Generated from `data/research/dataset_gap_matrix.json` on {date.today().isoformat()} "
        "by `ml/research/build_gap_matrix.py`. Edit the JSON, not this file.",
        "",
        matrix["scope"],
        "",
        f"**{len(gaps)} gaps recorded: blocking: {counts['blocking']}, "
        f"major: {counts['major']}, minor: {counts['minor']}.**",
        "",
        "None of them is closed. The point of the matrix is that each open gap has a named "
        "consequence for what the product is allowed to claim, and the product states that "
        "consequence rather than papering over it.",
        "",
        "## Severity",
        "",
        "| Severity | Meaning | Count |",
        "|---|---|---|",
    ]
    for severity in SEVERITIES:
        lines.append(f"| **{severity}** | {meaning[severity]} | {counts[severity]} |")

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
            "",
        ]
    return "\n".join(lines) + "\n" + CLOSING


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    matrix = json.loads(SOURCE.read_text(encoding="utf-8"))
    rendered = render(matrix)

    if args.check:
        if not TARGET.is_file():
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
