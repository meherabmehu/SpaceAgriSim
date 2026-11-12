"""Phase 32: one place where every served artifact's provenance, licence and scope is declared.

The Phase 31 audit closed with 19 documented gaps, and most of them were the same three fields
missing from the same artifacts: `sourceUrl`, `sourceType` and `license`. Those fields exist in
`data/metadata/dataset_manifest` and `data/research/dataset_catalog` already, so the gap
was never missing knowledge - it was knowledge that had not been carried to the card a user
actually reads, and would be lost again the next time an artifact was retrained.

Putting the values here rather than in nine training scripts means:

  * a retrain cannot silently drop them (`scripts/nasa_pipeline.save_json` applies this table to
    any payload whose `id` is a known model, and refuses to overwrite a non-empty value);
  * the licence text is copied from the manifest that recorded it, with the URL it came from, so
    a reader can check it rather than trust it;
  * `--check` fails if a committed artifact disagrees with this table, which makes the table the
    reviewed source of truth instead of a patch someone applied once.

Everything here was read from a record already in this repository. Nothing is inferred from a
model name, and where a licence could not be verified the entry says so instead of guessing.

Run:
    python ml/training/phase32_provenance.py           # patch artifacts in place
    python ml/training/phase32_provenance.py --check    # verify committed artifacts
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)) if str(ROOT) not in sys.path else None  # noqa: E501
import safedata  # noqa: E402 - the repository data layer lives at the root
ARTIFACTS = ROOT / "ml" / "artifacts"
CALIBRATION = ROOT / "ml" / "evaluation" / "phase32_radiation_calibration"

RETRIEVED = "2026-11-09"

OSDR_LICENSE = ("Public OSDR access; retain study attribution and comply with OSDR terms; do not "
                "assume every contributed file is public domain.")
OSDR_TERMS = "https://science.nasa.gov/reference/osdr-help-terms-and-conditions/"

WUR_LICENSE = "CC BY 4.0, declared in the dataset's RO-Crate (data/metadata/wur_lettuce_rocrate.py)"
WUR_TERMS = "https://creativecommons.org/licenses/by/4.0/"
WUR_CITATION = ("Meinen E., Carotti L., Graamans L., Puksic F., Butturini M., Stanghellini C. "
                "(2025). Data underlying the publication: Plant Factories Are Heating Up: "
                "Hunting for the Best Combination of Light Intensity, Air Temperature and "
                "Root-Zone Temperature in Lettuce Production. 4TU.ResearchData. "
                "https://doi.org/10.4121/5a7472f0-8a67-4ec0-84c9-9d032990d654.v1")
WUR_URL = "https://doi.org/10.4121/5a7472f0-8a67-4ec0-84c9-9d032990d654.v1"

NO_FORECAST = ("No operational forecast. This card describes what the model reproduces inside the "
               "measured domain; it is not a prediction of a future or unmeasured crop.")

PROVENANCE: dict[str, dict] = {
    "lettuce-earth-growth-v1": {
        "sourceUrl": WUR_URL,
        "sourceType": "external scientific data (not NASA): 4TU.ResearchData experiment tables",
        "license": WUR_LICENSE,
        "sourceLicense": WUR_LICENSE,
        "sourceLicenseUrl": WUR_TERMS,
        "sourceCitation": WUR_CITATION,
        "sourceRetrieved": RETRIEVED,
        "servedScope": ("Reproducibility only. Superseded by lettuce-earth-growth-v2, which was "
                        "better on every held-out experiment; kept so an earlier published number "
                        "can be regenerated, not for new predictions."),
        "operationalForecast": False,
        "harvestForecastClaim": "none",
        "archivalRecord": {
            "retained": True,
            "served": "reproducibility-only",
            "files": ["ml/artifacts/lettuce-earth-growth-v1"],
            "reason": "Superseded, not withdrawn: the artifact is still reachable so a report "
                      "that quoted it can be reproduced, with the supersession stated in every "
                      "response.",
        },
        "note": NO_FORECAST,
    },
    "lettuce-earth-growth-v2": {
        "sourceUrl": WUR_URL,
        "sourceType": "external scientific data (not NASA): 4TU.ResearchData experiment tables",
        "license": WUR_LICENSE,
        "sourceLicense": WUR_LICENSE,
        "sourceLicenseUrl": WUR_TERMS,
        "sourceCitation": WUR_CITATION,
        "sourceRetrieved": RETRIEVED,
        "servedScope": ("Retrospective interpolation within four WUR plant-factory experiments "
                        "(cv. Batavia Othilie, 2-29 days after transplant, PPFD 200-750, air and "
                        "root 20-32 C). An independent check failed: against Wicharuck et al. 2024 "
                        "(PeerJ 12:e17085, Thai greenhouse, 28 DAT) the model overpredicted by a "
                        "median 3.2x, range 1.7x-5.4x. The 0.870 leave-one-study-out R2 is "
                        "interpolation between four experiments, not transfer to a fifth."),
        "operationalForecast": False,
        "harvestForecastClaim": "none",
        "archivalRecord": {
            "retained": True,
            "served": "research surface with the failed independent check stated",
            "files": ["ml/artifacts/lettuce-earth-growth-v2",
                      "ml/evaluation/phase30_harvest_crossstudy"],
            "reason": "The failed external check is the result. Removing the card would remove "
                      "the evidence that the platform checked.",
        },
        "note": NO_FORECAST,
    },
    "lettuce-earth-growth-v3": {
        "sourceUrl": WUR_URL,
        "sourceType": "external scientific data (not NASA): 4TU.ResearchData experiment tables",
        "license": WUR_LICENSE,
        "sourceLicense": WUR_LICENSE,
        "sourceLicenseUrl": WUR_TERMS,
        "sourceCitation": WUR_CITATION,
        "sourceRetrieved": RETRIEVED,
        "servedScope": ("Fresh yield per square metre inside the measured WUR domain, divided by "
                        "the planting density the caller states. The pre-registered criterion was "
                        "30 % MAPE on an independent holdout; the model returned 41.6 % on "
                        "Touliatos et al. 2016 data, so it is served as a research surface that "
                        "reports its own failure, not as a forecast."),
        "operationalForecast": False,
        "harvestForecastClaim": "none",
        "archivalRecord": {
            "retained": True,
            "served": "research surface with the missed criterion stated",
            "files": ["ml/artifacts/lettuce-earth-growth-v3",
                      "ml/evaluation/phase29_harvest_diagnosis"],
            "reason": "The pre-registered failure is published with the model; withdrawing it "
                      "would also withdraw the evidence.",
        },
        "note": NO_FORECAST,
    },
    "mizuna-harvest-v1": {
        "sourceUrl": "https://osdr.nasa.gov/bio/repo/data/studies/OSD-655",
        "sourceType": "NASA OSDR (OSD-655) VEG-01/02 pick-and-eat harvest records",
        "license": OSDR_LICENSE,
        "sourceLicense": OSDR_LICENSE,
        "sourceLicenseUrl": OSDR_TERMS,
        "sourceCitation": ("NASA Open Science Data Repository, OSD-655: Pick-and-eat space crop "
                           "production flight testing on the International Space Station."),
        "sourceRetrieved": RETRIEVED,
        "servedScope": ("Withdrawn in Phase 31. Held-out R2 was -0.333, i.e. worse than predicting "
                        "the mean, so no forecast of mizuna harvest is offered by any route, "
                        "workflow, catalogue entry or assistant passage. The card is retained as "
                        "a non-serving record of that evaluation."),
        "operationalForecast": False,
        "harvestForecastClaim": "none",
        "archivalRecord": {
            "retained": True,
            "served": "no: withdrawn from every surface",
            "files": ["ml/artifacts/mizuna-harvest-v1"],
            "reason": "A withdrawn model keeps its artifact and its evaluation so the withdrawal "
                      "is auditable; backend/tests/test_phase32_no_forecast.py proves it is "
                      "unreachable.",
        },
        "note": NO_FORECAST,
    },
    "mizuna-microbial-load-v1": {
        "sourceUrl": "https://osdr.nasa.gov/bio/repo/data/studies/OSD-780",
        "sourceType": "NASA OSDR ALSDA plate-count measurement tables (LSDS-128)",
        "license": OSDR_LICENSE,
        "sourceLicense": OSDR_LICENSE,
        "sourceLicenseUrl": OSDR_TERMS,
        "sourceCitation": "NASA Open Science Data Repository, OSD-780: VEG-04A mizuna microbial load (plate counts).",
        "sourceRetrieved": RETRIEVED,
        "servedScope": ("Relative microbial load within the VEG-04A campaigns only. The model "
                        "predicts a within-campaign contrast; it carries no across-campaign "
                        "coverage and no absolute colony-count prediction."),
        "operationalForecast": False,
        "harvestForecastClaim": "none",
        "note": NO_FORECAST,
    },
    "mizuna-microbial-relative-load-v2": {
        "sourceUrl": "https://osdr.nasa.gov/bio/repo/data/studies/OSD-780",
        "sourceType": "NASA OSDR ALSDA plate-count measurement tables (LSDS-128)",
        "license": OSDR_LICENSE,
        "sourceLicense": OSDR_LICENSE,
        "sourceLicenseUrl": OSDR_TERMS,
        "sourceCitation": "NASA Open Science Data Repository, OSD-780: VEG-04A mizuna microbial load (plate counts).",
        "sourceRetrieved": RETRIEVED,
        "servedScope": ("Relative microbial load within the VEG-04A campaigns only, with a "
                        "conformal interval from the same campaigns. Measured coverage is "
                        "within-campaign; there is no second campaign in the repository against "
                        "which across-campaign coverage could be measured, and the response "
                        "says so."),
        "operationalForecast": False,
        "harvestForecastClaim": "none",
        "note": NO_FORECAST,
    },
    "radiation-quality-osd46-v1": {
        "sourceUrl": "https://osdr.nasa.gov/bio/repo/data/studies/OSD-46",
        "sourceType": "NASA OSDR microarray (GeneLab GLDS-46)",
        "license": OSDR_LICENSE,
        "sourceLicense": OSDR_LICENSE,
        "sourceLicenseUrl": OSDR_TERMS,
        "sourceCitation": ("NASA Open Science Data Repository, OSD-46: Gamma radiation and HZE "
                           "treatment of seedlings in Arabidopsis (UC Davis / Brookhaven)."),
        "sourceRetrieved": RETRIEVED,
        "sourceChecksum": ("data/raw/OSD-46/GLDS-46_array_normalized_expression_probeset_GLmicroarray.csv "
                           "sha256 f15c4179dbbebdfd39c53ffb906f6251ed1fc3fa3c926efc3c71c4736eefda27"),
        "servedScope": ("Classification of the applied treatment (control / 100 Gy gamma / 30 Gy "
                        "Fe-56) for Arabidopsis seedlings in OSD-46. Not a dose prediction, not a "
                        "plant-health score, not a crop, and not spaceflight. Probabilities are "
                        "measured, not calibrated, and the response reports the measurement."),
        "operationalForecast": False,
        "harvestForecastClaim": "none",
        "note": NO_FORECAST,
    },
    "radiation-exposure-osd46-v1": {
        "sourceUrl": "https://osdr.nasa.gov/bio/repo/data/studies/OSD-46",
        "sourceType": "NASA OSDR microarray (GeneLab GLDS-46)",
        "license": OSDR_LICENSE,
        "sourceLicense": OSDR_LICENSE,
        "sourceLicenseUrl": OSDR_TERMS,
        "sourceCitation": ("NASA Open Science Data Repository, OSD-46: Gamma radiation and HZE "
                           "treatment of seedlings in Arabidopsis (UC Davis / Brookhaven)."),
        "sourceRetrieved": RETRIEVED,
        "sourceChecksum": ("data/raw/OSD-46/GLDS-46_array_normalized_expression_probeset_GLmicroarray.csv "
                           "sha256 f15c4179dbbebdfd39c53ffb906f6251ed1fc3fa3c926efc3c71c4736eefda27"),
        "servedScope": ("Irradiated versus non-irradiated classification for Arabidopsis seedlings "
                        "in OSD-46. Controls do not appear on the array batch holding 20 of the 44 "
                        "arrays, so part of the separation may be array handling; the response "
                        "reports the batch-controlled supplementary figure as the one to quote."),
        "operationalForecast": False,
        "harvestForecastClaim": "none",
        "note": NO_FORECAST,
    },
    "tomato-flight-response-v1": {
        "sourceUrl": "https://osdr.nasa.gov/bio/repo/data/studies/OSD-767",
        "sourceType": "NASA OSDR (OSD-767) tomato transcriptome, flight versus ground",
        "license": OSDR_LICENSE,
        "sourceLicense": OSDR_LICENSE,
        "sourceLicenseUrl": OSDR_TERMS,
        "sourceCitation": ("NASA Open Science Data Repository, OSD-767: Stress and light spectral "
                           "quality influence the transcriptome of a tomato cultivar."),
        "sourceRetrieved": RETRIEVED,
        "servedScope": ("Classification of the recorded experimental context (flight versus "
                        "ground) from tomato expression. Not a health score, not a yield "
                        "prediction and not a stress diagnosis."),
        "operationalForecast": False,
        "harvestForecastClaim": "none",
        "note": NO_FORECAST,
    },
}

# Classifiers serve `predict_proba`. Where a calibration study exists it is cited by path, with
# the verdict it produced; where none exists the card has to say so rather than stay silent.
CALIBRATION_DECLARATIONS: dict[str, dict] = {
    "radiation-quality-osd46-v1": {
        "calibrated": False,
        "measured": True,
        "evidence": "ml/evaluation/phase32_radiation_calibration",
        "method": ("Leave-one-biological-group-out out-of-fold probabilities, the same split as the "
                   "reported accuracy (recomputed and asserted equal). Log loss, Brier score and a "
                   "10-bin ECE were measured; a nested temperature search was run and reported."),
        "servedScaling": "none",
        "scope": ("Measured within OSD-46 only. It does not transfer to other radiation qualities, "
                  "doses, organisms or platforms."),
        "statement": ("The class probabilities are uncalibrated scores from a regularised logistic "
                      "model, measured on 44 arrays from 22 biological groups. Read them as a "
                      "ranking, not as a probability that the class is correct."),
    },
    "radiation-exposure-osd46-v1": {
        "calibrated": False,
        "measured": True,
        "evidence": "ml/evaluation/phase32_radiation_calibration",
        "method": ("Leave-one-biological-group-out out-of-fold probabilities, the same split as the "
                   "reported accuracy. Log loss, Brier score and a 10-bin ECE were measured; a "
                   "nested temperature search was run and reported."),
        "servedScaling": "none",
        "scope": "Measured within OSD-46 only, and the class balance is confounded with array batch.",
        "statement": ("The class probabilities are uncalibrated scores. Controls do not appear on "
                      "the array batch holding 20 of the 44 arrays, so neither the score nor its "
                      "calibration can separate irradiation from array handling."),
    },
    "tomato-flight-response-v1": {
        "calibrated": False,
        "measured": False,
        "evidence": None,
        "servedScaling": "none",
        "scope": "Not measured: no independent flight-versus-ground replication is available.",
        "statement": ("The class probabilities are uncalibrated scores. No calibration study has "
                      "been run for this model, so the value ranks cases; it is not the probability "
                      "that the class is correct."),
    },
}


def apply(payload: dict) -> dict:
    """Add the declared fields to an artifact payload without overwriting what is already there.

    A non-empty existing value wins. That is deliberate: if a training script writes a more
    specific licence for a new dataset, this table must not flatten it back to the old one.
    `--check` then reports the disagreement rather than hiding it.
    """
    model_id = payload.get("id")
    declared = PROVENANCE.get(model_id)
    if declared is None:
        return payload
    for key, value in declared.items():
        if payload.get(key) in (None, "", [], {}):
            payload[key] = value
    calibration = CALIBRATION_DECLARATIONS.get(model_id)
    if calibration and not payload.get("probabilityCalibration"):
        payload["probabilityCalibration"] = calibration
    return payload


def patch_all() -> list[str]:
    changed = []
    for path in safedata.records(ARTIFACTS):
        payload = safedata.load(path)
        if not isinstance(payload, dict) or payload.get("id") not in PROVENANCE:
            continue
        before = json.dumps(payload, sort_keys=True)
        apply(payload)
        if json.dumps(payload, sort_keys=True) != before:
            safedata.dump(payload, path)
            changed.append(path.name)
    return changed


LICENCE_ALIASES = (("cc by 4.0", "CC-BY-4.0"), ("cc-by-4.0", "CC-BY-4.0"))


def _licence_identity(text: str) -> str:
    """Reduce a licence string to the identifier it asserts, so 'CC BY 4.0' == 'CC-BY-4.0'.

    The check exists to catch a *different licence*, not a different way of writing the same one.
    """
    lowered = (text or "").lower()
    for needle, canonical in LICENCE_ALIASES:
        if needle in lowered:
            return canonical
    return lowered.strip()


def check() -> list[str]:
    problems = []
    for path in safedata.records(ARTIFACTS):
        payload = safedata.load(path)
        if not isinstance(payload, dict) or payload.get("id") not in PROVENANCE:
            continue
        for key, value in PROVENANCE[payload["id"]].items():
            if payload.get(key) in (None, "", [], {}):
                problems.append(f"{path.name}: missing {key}")
            elif key in ("license", "sourceLicense") and (_licence_identity(payload[key])
                                                          != _licence_identity(value)):
                problems.append(f"{path.name}: {key} differs from the reviewed provenance table")
            elif key == "sourceUrl" and payload[key] != value:
                problems.append(f"{path.name}: {key} differs from the reviewed provenance table")
        if payload["id"] in CALIBRATION_DECLARATIONS:
            if not payload.get("probabilityCalibration"):
                problems.append(f"{path.name}: no probabilityCalibration declaration")
            elif payload["probabilityCalibration"].get("measured") and not safedata.exists(CALIBRATION):
                problems.append(f"{path.name}: cites a calibration record that does not exist")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.check:
        problems = check()
        if problems:
            print("provenance check failed:")
            for problem in problems:
                print(f"  {problem}")
            return 1
        print(f"provenance complete for {len(PROVENANCE)} artifacts")
        return 0
    changed = patch_all()
    print(f"patched {len(changed)} artifacts: {', '.join(changed) if changed else 'none needed'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
