"""Phase 35: what the last phase changed on screen, captured three ways.

The Phase 34 gate compares one candidate against one baseline and cannot say which phase a pixel
belongs to. This script keeps the same discipline for Phase 35: the Phase 34 delivery commit
(0f01f31) is rebuilt in a separate worktree, the identical Playwright suite runs against it and
against the Phase 35 candidate, and three comparisons are reported.

    docs/screenshots/<name>.png                       the committed baselines
    docs/screenshots/phase35/parent/<name>.png        0f01f31 rebuilt, same suite, same viewports
    docs/screenshots/phase35/candidate/<name>.png     Phase 35 HEAD, same suite, same viewports

Two of the captures (`predictions-*`, `benchmarks-*`) are new in this phase, so they have no
committed baseline yet. They are reported as "new" rather than as drift, and they enter the gate
only once their baseline is installed from the verified candidate.

Every comparison uses the gate's own metric (`scripts/visual_regression.py`): canvas size equality
plus the share of pixels whose largest channel delta exceeds 16. No baseline is rewritten here.

Output: ml/evaluation/phase35_visual_drift.json
Run:    python ml/research/phase35_visual_drift.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
BASELINE = ROOT / "docs" / "screenshots"
PARENT = BASELINE / "phase35" / "parent"
CANDIDATE = BASELINE / "phase35" / "candidate"
OUTPUT = ROOT / "ml" / "evaluation" / "phase35_visual_drift.json"

# Identical to the gate, so a number here means the same thing as a number there.
PIXEL_BUDGET = 0.02
CHANNEL_THRESHOLD = 16


def changed_ratio(first: Path, second: Path) -> dict:
    left = np.asarray(Image.open(first).convert("RGB"), dtype=np.int16)
    right = np.asarray(Image.open(second).convert("RGB"), dtype=np.int16)
    if left.shape != right.shape:
        return {"sameSize": False, "changedPixelRatio": None, "passed": False,
                "firstSize": list(left.shape[1::-1]), "secondSize": list(right.shape[1::-1])}
    delta = np.abs(left - right).max(axis=2)
    ratio = float((delta > CHANNEL_THRESHOLD).mean())
    return {
        "sameSize": True,
        "changedPixelRatio": round(ratio, 6),
        "percentChanged": round(100.0 * ratio, 4),
        "passed": ratio <= PIXEL_BUDGET,
        "firstSize": list(left.shape[1::-1]),
        "secondSize": list(right.shape[1::-1]),
    }


def compare(first_dir: Path, second_dir: Path, names: list[str]) -> dict:
    rows = {}
    for name in names:
        first = first_dir / f"{name}.png"
        second = second_dir / f"{name}.png"
        if not (first.is_file() and second.is_file()):
            # A capture with no baseline is new, not drifting: the two cases must not be counted
            # together or a first-ever screenshot would read as a regression.
            rows[name] = {"skipped": True,
                          "reason": ("no baseline yet" if not first.is_file()
                                     else "capture missing on the candidate side")}
            continue
        rows[name] = changed_ratio(first, second)
    compared = {name: row for name, row in rows.items() if not row.get("skipped")}
    ratios = [row["changedPixelRatio"] for row in compared.values()
              if row["changedPixelRatio"] is not None]
    sizes_changed = [name for name, row in compared.items() if not row["sameSize"]]
    new = sorted(name for name, row in rows.items() if row.get("skipped")
                 and row.get("reason") == "no baseline yet")
    missing = sorted(name for name, row in rows.items() if row.get("skipped")
                     and row.get("reason") != "no baseline yet")
    return {
        "captures": rows,
        "compared": len(compared),
        "skipped": sorted(name for name, row in rows.items() if row.get("skipped")),
        "newWithoutBaseline": new,
        "missing": missing,
        "medianPercentChanged": round(float(np.median(ratios)), 4) if ratios else None,
        "maxPercentChanged": round(float(np.max(ratios)), 4) if ratios else None,
        "sizesChanged": sizes_changed,
        "budgetPercent": PIXEL_BUDGET * 100,
        "allWithinBudget": bool(ratios) and not sizes_changed
                            and max(ratios) <= PIXEL_BUDGET,
    }


def main() -> int:
    if not PARENT.is_dir() or not CANDIDATE.is_dir():
        print("captures missing: run the Playwright suite in both worktrees first")
        return 1
    names = sorted({path.stem for path in CANDIDATE.glob("*.png")}
                   | {path.stem for path in PARENT.glob("*.png")})
    report = {
        "schema": "spaceagrisim.visual_drift/1",
        "parentCommit": "0f01f314e7f9d8b54ab862a34f686b2c1f31bc7c",
        "candidateBranch": "phase35/final-completion",
        "method": ("Identical Playwright suite and viewports on both trees; per-capture share of "
                   "pixels whose largest channel delta exceeds 16, the gate's own metric."),
        "baselineToParent": compare(BASELINE, PARENT, names),
        "parentToCandidate": compare(PARENT, CANDIDATE, names),
        "baselineToCandidate": compare(BASELINE, CANDIDATE, names),
        "note": ("Read the three blocks in order. baseline->parent is drift this phase never "
                 "touched; parent->candidate is the change this phase is responsible for."),
    }
    OUTPUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    for key in ("baselineToParent", "parentToCandidate", "baselineToCandidate"):
        block = report[key]
        print(f"{key}: {block['compared']} captures, median "
              f"{block['medianPercentChanged']} %, max {block['maxPercentChanged']} %, "
              f"within budget: {block['allWithinBudget']}")
        for name, row in block["captures"].items():
            if row.get("skipped"):
                print(f"  {name}: skipped ({row['reason']})")
            elif not row["passed"]:
                size = ("size unchanged" if row["sameSize"] else
                        f"size {row['firstSize']} -> {row['secondSize']}")
                print(f"  {name}: {row.get('percentChanged')} % changed, {size}")
    print(f"wrote {OUTPUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
