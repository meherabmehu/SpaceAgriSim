"""Phase 10: write the adopted conformal radii into the shipped artifacts.

`phase10_conformal_study.py` measures which method covers its nominal level.
This script computes the single radius the API will actually serve — calibrated
on all available biological groups by cross-conformal, because a deployable model
cannot reserve groups for calibration — and patches it into the three artifacts.

It patches in place. `scripts/build_registry.py` is not used: a full rebuild drops
curated fields (supersedes, status, samples, dataVersion) and Phase 9 already lost
and had to restore them once.

Nothing here tunes a radius to hit a coverage number. The method is fixed by
`phase10_uncertainty_decision.json`; this only fits it on the data that ships.
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ml" / "training"))
sys.path.insert(0, str(ROOT / "scripts"))
from conformal import _quantile, group_level_conformal, out_of_fold_residuals  # noqa: E402
from phase10_conformal_study import (lettuce, lettuce_fit, lettuce_v1_fit,  # noqa: E402
                                     microbial_absolute, microbial_fit,
                                     microbial_relative)

ALPHA = 0.10
SEED = 42
ARTIFACTS = ROOT / "ml" / "artifacts"
EVALUATION = ROOT / "ml" / "evaluation"
SEED_INNER = 5


def main() -> int:
    decision = json.loads((EVALUATION / "phase10_uncertainty_decision.json").read_text())
    measured = json.loads((EVALUATION / "phase10_conformal.json").read_text())["models"]

    loaders = {
        "mizuna-microbial-relative-load-v2": (microbial_relative, microbial_fit),
        "mizuna-microbial-load-v1": (microbial_absolute, microbial_fit),
        "lettuce-earth-growth-v1": (lettuce, lettuce_v1_fit),
        "lettuce-earth-growth-v2": (lettuce, lettuce_fit),
    }

    patched = {}
    for model_id, (loader, fit) in loaders.items():
        x, y, groups, _, features = loader()
        adopted = decision["decisions"][model_id]["adopted"]

        row_residuals = out_of_fold_residuals(fit, x, y, groups, n_splits=SEED_INNER, seed=SEED)
        row_radius = _quantile(row_residuals, ALPHA)
        group_worst = np.array([row_residuals[groups == g].max() for g in np.unique(groups)])
        group_radius = _quantile(group_worst, ALPHA)

        radius = group_radius if adopted == "group_level" else row_radius
        achieved = measured[model_id]["summary"][adopted]["empiricalCoverage"]

        block = {
            "method": ("group-level cross-conformal" if adopted == "group_level"
                       else "cross-conformal (CV+)"),
            "radius": round(float(radius), 6),
            "nominalCoverage": 1 - ALPHA,
            "achievedCoverage": achieved,
            "calibrationGroups": int(len(np.unique(groups))),
            "calibrationResiduals": int(len(group_worst) if adopted == "group_level" else len(row_residuals)),
            "exchangeabilityUnit": ("biological group (worst residual within group)"
                                    if adopted == "group_level" else "individual row"),
            "rowLevelRadiusForComparison": round(float(row_radius), 6),
            "groupLevelRadiusForComparison": round(float(group_radius), 6),
            "empiricallyCalibrated": True,
            "evidence": "ml/evaluation/phase10_conformal.json",
            "caveat": decision["decisions"][model_id]["honestCaveat"],
        }

        path = ARTIFACTS / f"{model_id}.json"
        artifact = json.loads(path.read_text())
        artifact["uncertainty"] = block
        artifact["interval"] = {
            "radius": block["radius"],
            "kind": (f"{int((1 - ALPHA) * 100)}% {block['method']} interval, "
                     f"measured held-out coverage {achieved:.3f}"),
            "nominalCoverage": 1 - ALPHA,
            "empiricalCoverage": achieved,
            "empiricallyCalibrated": True,
            "calibrationGroups": block["calibrationGroups"],
            "caveat": block["caveat"],
            "supersedes": ("Phase 9 split conformal, which measured 0.849 and 0.811 "
                           "against a nominal 0.90"
                           if "microbial" in model_id
                           else "Phase 9 90th-percentile residual range (uncalibrated)"),
        }
        artifact["phase10"] = {"uncertaintyRecalibratedAt": datetime.now(timezone.utc).isoformat(),
                               "method": block["method"]}
        path.write_text(json.dumps(artifact, indent=1, allow_nan=False) + "\n")
        patched[model_id] = {"path": str(path.relative_to(ROOT)),
                             "radius": block["radius"],
                             "method": block["method"],
                             "achievedCoverage": achieved}
        print(f"{model_id:36s} {block['method']:32s} radius {radius:9.4f}  "
              f"measured coverage {achieved:.3f}")

    registry_path = ARTIFACTS / "registry.json"
    registry = json.loads(registry_path.read_text())
    registry["trainedAt"] = datetime.now(timezone.utc).isoformat()
    for model in registry["models"]:
        if model["id"] in patched:
            model["sha256"] = hashlib.sha256(
                (ARTIFACTS / f"{model['id']}.json").read_bytes()).hexdigest()
    registry_path.write_text(json.dumps(registry, indent=1) + "\n")

    (EVALUATION / "phase10_uncertainty_patch.json").write_text(
        json.dumps({"alpha": ALPHA, "seed": SEED, "models": patched,
                    "note": ("Radii calibrated on every available biological group by "
                             "cross-conformal. Achieved coverage is the measured held-out "
                             "value from phase10_conformal.json, not a re-measurement on "
                             "the same data the radius was fit to.")},
                   indent=2) + "\n")
    print("\npatched artifacts and registry checksums")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
