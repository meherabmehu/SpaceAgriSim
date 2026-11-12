"""Phase 34: separate pre-existing visual drift from this phase's changes.

The Phase 33 gate compared one candidate against one baseline, which cannot say *when* a pixel
moved. This phase rebuilt the Phase 33 parent commit (e7ee855) in a separate worktree, ran the
identical Playwright suite against it, and ran the same suite again on the Phase 34 candidate. All
three sets are now on disk:

    docs/screenshots/<name>.png                     the committed Phase 9 baselines
    docs/screenshots/phase34/parent/<name>.png      e7ee855 rebuilt, same suite, same viewports
    docs/screenshots/phase34/candidate/<name>.png   Phase 34 HEAD, same suite, same viewports

Three comparisons per capture:

    baseline -> parent       drift that already existed before Phase 34 touched anything
    parent   -> candidate    what Phase 34 actually changed
    baseline -> candidate    the number the visual gate reports

Every comparison uses the gate's own metric (`scripts/visual_regression.py`): canvas size equality
plus the share of pixels whose largest channel delta exceeds 16. No baseline is rewritten here.

Output: ml/evaluation/phase34_visual_drift
Run:    python ml/research/phase34_visual_drift.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from screenshot_store import names_in, resolve  # noqa: E402  (sibling module, not a package)

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)) if str(ROOT) not in sys.path else None  # noqa: E501
import safedata  # noqa: E402 - the repository data layer lives at the root
BASELINE = ROOT / "docs" / "screenshots"
PARENT = BASELINE / "phase34" / "parent"
CANDIDATE = BASELINE / "phase34" / "candidate"
OUTPUT = ROOT / "ml" / "evaluation" / "phase34_visual_drift"

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
        # A capture that was byte-identical to another is not missing: the dedupe pass recorded
        # where its bytes live, so the comparison still shows 0.000 % rather than a gap.
        first, first_alias = resolve(first_dir / f"{name}.png")
        second, second_alias = resolve(second_dir / f"{name}.png")
        if first is None or second is None:
            rows[name] = {"skipped": True,
                          "reason": "capture missing on one side"}
            continue
        row = changed_ratio(first, second)
        if first_alias or second_alias:
            # Say which side came from an identical copy, so 0.000 % is explained rather than
            # assumed: this is the same bytes, resolved through the dedupe manifest.
            row["identicalCopyOf"] = {"first": first_alias, "second": second_alias}
        rows[name] = row
    compared = {name: row for name, row in rows.items() if not row.get("skipped")}
    ratios = [row["changedPixelRatio"] for row in compared.values()
              if row["changedPixelRatio"] is not None]
    sizes_changed = [name for name, row in compared.items() if not row["sameSize"]]
    return {
        "captures": rows,
        "compared": len(compared),
        "skipped": sorted(name for name, row in rows.items() if row.get("skipped")),
        "medianPercentChanged": round(float(np.median(ratios)), 4) if ratios else None,
        "maxPercentChanged": round(float(np.max(ratios)), 4) if ratios else None,
        "sizesChanged": sizes_changed,
        "budgetPercent": PIXEL_BUDGET * 100,
        "allWithinBudget": bool(ratios) and not sizes_changed
                            and max(ratios) <= PIXEL_BUDGET,
    }


def main() -> int:
    names = names_in(PARENT, CANDIDATE)
    if not names:
        print("captures missing: run the Playwright suite in both worktrees first")
        return 1
    report = {
        "schema": "spaceagrisim.visual_drift/1",
        "parentCommit": "e7ee85582bfc4224e9f94a4f0d3e85672dcc95fa",
        "candidateBranch": "phase34/evidence",
        "method": ("Identical Playwright suite and viewports on both trees; per-capture share of "
                   "pixels whose largest channel delta exceeds 16, the gate's own metric."),
        "baselineToParent": compare(BASELINE, PARENT, names),
        "parentToCandidate": compare(PARENT, CANDIDATE, names),
        "baselineToCandidate": compare(BASELINE, CANDIDATE, names),
        "note": ("Read the three blocks in order. baseline->parent is drift this phase never "
                 "touched; parent->candidate is the change this phase is responsible for."),
    }
    safedata.dump(report, OUTPUT)
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
