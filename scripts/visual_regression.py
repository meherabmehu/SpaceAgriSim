"""Visual regression gate: compare fresh screenshots against committed baselines.

Phase 9 had to add two prediction cards to the platform without touching the
visual design. "I did not change the CSS" is a claim; this script makes it a
measurement.

The baselines live in docs/screenshots and are versioned. Fresh screenshots are
produced by the Playwright suite (e2e/mission.spec.js writes mission-<viewport>.png).

Two things are checked per viewport:
  1. identical canvas size - a height change means the layout moved;
  2. the share of pixels whose largest channel delta exceeds a threshold.

The second check needs a tolerance. Text antialiasing and font availability differ
between machines, so a byte-identical screenshot is not a realistic gate; a layout
change, a palette change or a moved card all produce diffs far above the budget,
while pure rasterisation differences stay well below it.

Usage:
    python scripts/visual_regression.py                 # compare fresh vs baseline
    python scripts/visual_regression.py --refresh       # rewrite the baselines
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SCREENSHOTS = ROOT / "docs" / "screenshots"
REPORT = ROOT / "ml" / "evaluation" / "phase9_visual_regression.json"
FRESH = ROOT / "frontend" / "test-results" / "screenshots"

# A single changed card or a palette shift moves several percent of the canvas.
# Antialiasing alone stays around a fraction of one percent.
PIXEL_BUDGET = 0.02       # 2 % of pixels may differ
CHANNEL_THRESHOLD = 16    # ignore sub-perceptual channel noise

VIEWPORTS = ("mission-desktop", "mission-tablet", "mission-mobile")

# The Phase 9 prediction cards are new, so Phase 9 also establishes their first
# baseline. Later phases compare against these to prove the cards did not drift.
RADIATION_MODELS = ("radiation-quality-osd46-v1", "radiation-exposure-osd46-v1")
RADIATION = tuple(f"radiation-{viewport}-{model}"
                  for viewport in ("desktop", "tablet", "mobile")
                  for model in RADIATION_MODELS)
ALL_CAPTURES = VIEWPORTS + RADIATION


def compare(baseline_path: Path, fresh_path: Path) -> dict:
    baseline = Image.open(baseline_path).convert("RGB")
    fresh = Image.open(fresh_path).convert("RGB")
    result = {
        "baseline": str(baseline_path.relative_to(ROOT)),
        "fresh": str(fresh_path.relative_to(ROOT))
        if fresh_path.is_relative_to(ROOT) else str(fresh_path),
        "baselineSize": list(baseline.size),
        "freshSize": list(fresh.size),
        "sameSize": baseline.size == fresh.size,
    }
    if not result["sameSize"]:
        result.update({"changedPixelRatio": None, "passed": False,
                       "reason": "canvas size changed, so the layout moved"})
        return result
    difference = np.abs(np.asarray(baseline, dtype=np.int16)
                        - np.asarray(fresh, dtype=np.int16))
    changed = int((difference.max(axis=2) > CHANNEL_THRESHOLD).sum())
    total = baseline.size[0] * baseline.size[1]
    ratio = changed / total
    result.update({
        "changedPixels": changed,
        "totalPixels": total,
        "changedPixelRatio": round(ratio, 6),
        "maxChannelDelta": int(difference.max()),
        "passed": ratio <= PIXEL_BUDGET,
        "reason": ("within tolerance" if ratio <= PIXEL_BUDGET
                   else f"{ratio:.2%} of pixels changed, budget {PIXEL_BUDGET:.0%}"),
    })
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh", action="store_true",
                        help="accept the fresh screenshots as the new baselines")
    parser.add_argument("--fresh-dir", default=str(FRESH),
                        help=("directory holding the freshly captured screenshots; "
                              "defaults to the Playwright output tree so the "
                              "committed baselines are never overwritten"))
    args = parser.parse_args()

    fresh_dir = Path(args.fresh_dir)
    # A baseline that does not exist yet is reported and then created from the
    # fresh capture, which is how a brand-new component gets its first baseline.
    # A missing *fresh* capture is always an error: it means the suite did not run.
    missing_fresh = [name for name in ALL_CAPTURES
                     if not (fresh_dir / f"{name}.png").is_file()]
    if missing_fresh:
        print(f"no fresh screenshots for {missing_fresh}; run the Playwright suite first",
              file=sys.stderr)
        return 2
    names = list(ALL_CAPTURES)
    if args.refresh:
        for name in names:
            target = SCREENSHOTS / f"{name}.png"
            target.parent.mkdir(parents=True, exist_ok=True)
            Image.open(fresh_dir / f"{name}.png").save(target)
        print(f"refreshed {len(names)} baselines")
    new_baselines = [name for name in ALL_CAPTURES
                     if not (SCREENSHOTS / f"{name}.png").is_file()]

    if new_baselines:
        for name in new_baselines:
            target = SCREENSHOTS / f"{name}.png"
            Image.open(fresh_dir / f"{name}.png").save(target)
        print(f"created first baseline(s): {', '.join(new_baselines)}")

    results = [compare(SCREENSHOTS / f"{name}.png", fresh_dir / f"{name}.png")
               for name in names]

    for entry in results:
        status = "PASS" if entry["passed"] else "FAIL"
        ratio = entry["changedPixelRatio"]
        print(f"  {status}  {Path(entry['fresh']).name:24s} "
              f"{'n/a' if ratio is None else f'{ratio:.3%}':>7s} differing  "
              f"{entry['reason']}")

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps({
        "phase": 9,
        "purpose": ("Verify that adding the Phase 9 prediction cards did not alter "
                    "the existing visual design."),
        "pixelBudget": PIXEL_BUDGET,
        "firstBaselinesCreated": new_baselines,
        "channelThreshold": CHANNEL_THRESHOLD,
        "viewports": results,
        "passed": all(entry["passed"] for entry in results),
        "note": ("A tolerance is required because text rasterisation differs between "
                 "machines. Canvas size must match exactly: that is the layout guard."),
    }, indent=2) + "\n")
    print(f"\nwrote {REPORT.relative_to(ROOT)}")
    return 0 if all(entry["passed"] for entry in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
