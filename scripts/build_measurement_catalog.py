#!/usr/bin/env python3
"""Build the Phase 7 measurement catalog for the twelve requested targets.

The catalog is generated from the extracted tables rather than typed by hand, so
a target cannot cite a variable that does not exist in the extraction output.
Every referenced variable is resolved against the CSVs produced by
`extract_ntrs_tables.py`; a dangling reference aborts the build.

Status vocabulary (fixed, and used verbatim in the docs and the final report):

  measured                 a number was printed in the source with a page citation
  measured-approximate     read from a graph or a stated range midpoint
  measured-derivable       not printed, but exactly recomputable from printed values
  not-measured             searched for and absent from the recovered corpus
  out-of-scope             exists in the source but is not this target

Eligibility vocabulary (feeds Part B):

  ready / statistical / mechanistic / plausibility-only / insufficient

Run: python scripts/build_measurement_catalog.py
"""
from __future__ import annotations

import csv
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)) if str(ROOT) not in sys.path else None  # noqa: E501
import safedata  # noqa: E402 - the repository data layer lives at the root
PROCESSED = ROOT / "data" / "processed"
METADATA = ROOT / "data" / "metadata"
OUT = METADATA / "phase7_measurement_catalog"

SOURCES = {
    "TM-102784": {"ntrsId": "19900009537",
                  "title": "Continuous Hydroponic Wheat Production Using a Recirculating System",
                  "year": 1989,
                  "studyType": "NASA BPC ground chamber, single crop cycle set"},
    "TM-102788": {"ntrsId": "19900016137",
                  "title": "Carbon Dioxide and Water Exchange Rates by a Wheat Crop in NASA's Biomass Production Chamber",
                  "year": 1990,
                  "studyType": "NASA BPC ground chamber, 86-day continuous monitoring"},
    "TM-103494": {"ntrsId": "19900016140",
                  "title": "System Development and Early Biological Tests in NASA's Biomass Production Chamber",
                  "year": 1990,
                  "studyType": "NASA BPC ground chamber, five sequential system phases"},
}


def load_csv(name: str) -> list[dict]:
    with (PROCESSED / name).open(newline="") as handle:
        return list(csv.DictReader(handle))


def gas_lookup() -> dict[str, dict]:
    return {row["variable"]: row for row in load_csv("ntrs_wheat_gas_exchange.csv")}


def bpc_lookup() -> dict[str, dict]:
    return {row["variable"]: row for row in load_csv("ntrs_bpc_water_balance.csv")}


GAS = gas_lookup()
BPC = bpc_lookup()
HARVEST = load_csv("ntrs_wheat_harvest_trays.csv")
GROWTH = load_csv("ntrs_wheat_growth_series.csv")

PROBLEMS: list[str] = []


def ev(store: dict, variable: str, field: str = "value"):
    """Resolve a variable in an extraction CSV or record a dangling reference."""
    row = store.get(variable)
    if row is None:
        PROBLEMS.append(f"catalog references unknown variable '{variable}'")
        return None
    return row[field]


def provenance(store: dict, variable: str) -> dict:
    row = store.get(variable, {})
    return {
        "sourceReport": row.get("sourceReport"),
        "ntrsId": row.get("ntrsId"),
        "page": int(row["page"]) if row.get("page") else None,
        "evidenceString": row.get("evidenceString"),
        "provenanceVerified": row.get("provenanceVerified") == "True",
    }


def point(store, variable, *, status="measured", basis=None):
    row = store.get(variable)
    if row is None:
        PROBLEMS.append(f"catalog references unknown variable '{variable}'")
        return {}
    return {
        "variable": variable,
        "value": float(row["value"]),
        "unit": row["unit"],
        "status": status,
        "measurementBasis": basis or row["measurementBasis"],
        "note": row["note"],
        **provenance(store, variable),
    }


def tray_area_discrepancy() -> dict:
    """Quantify the report's own two mutually inconsistent tray areas."""
    total_biomass_g = sum(float(r["totalBiomassG"]) for r in HARVEST) / len(HARVEST)
    seed_g = sum(float(r["totalMassG"]) for r in HARVEST) / len(HARVEST)
    # Published per-m2 column averages recomputed from the tray table.
    seed_per_m2 = sum(float(r["seedMassPerM2G"]) for r in HARVEST) / len(HARVEST)
    seed_published_mean = 532.0   # Table 7 bottom row, printed average
    return {
        "authorStatedM2": 0.24,
        "biomassImpliedM2": round(total_biomass_g / 1546.0, 4),
        "seedImpliedM2FromPublishedAverage": round(seed_g / seed_published_mean, 4),
        "seedImpliedM2FromRecomputedAverage": round(seed_g / seed_per_m2, 4),
        "seedPerM2PublishedAverage": seed_published_mean,
        "seedPerM2RecomputedAverage": round(seed_per_m2, 2),
        "totalBiomassPerM2Published": 1546.0,
        "note": ("The report states 0.24 m2 and its total-dry-matter average of "
                 "1546 g/m2 reproduces exactly at 0.24 m2 (371.0 / 0.24 = 1545.8). "
                 "Its seed-mass-per-m2 column does not agree: the printed column "
                 "average of 532 g/m2 requires 0.2328 m2, and the column average "
                 "recomputed from the 16 printed tray values (520.25 g/m2) requires "
                 "0.238 m2. So the two published columns assume different tray "
                 "areas, by roughly 1-3 %. All three figures are recorded; none is "
                 "silently corrected."),
    }


TARGETS = [
    {
        "id": 1,
        "name": "biomass time series",
        "status": "measured",
        "eligibility": "statistical",
        "eligibilityNote": (
            "Seven destructive harvests at seven distinct ages from ONE study. A "
            "growth curve can be fitted and its residuals characterised, but the "
            "series contains no replicate trays at any single age, so it cannot "
            "support a cross-validated predictive model."
        ),
        "evidence": [
            {"kind": "table", "source": "TM-102784", "table": "Table 10 (p.43)",
             "description": "total dry matter per tray, per plant, per m2, per m3",
             "rows": len(GROWTH),
             "values": [{"ageDays": int(r["ageDays"]),
                         "dryMassPerM2G": float(r["dryMassPerM2G"]),
                         "dryMassPerTrayG": float(r["dryMassPerTrayG"])}
                        for r in GROWTH]},
            {"kind": "table", "source": "TM-102784", "table": "Table 9 (p.43)",
             "description": "plant height, tiller and leaf area at the same seven ages"},
        ],
        "replicates": "n=7 ages, 1 tray per age",
        "extraction": "positional column extraction with arithmetic and aggregate validation",
    },
    {
        "id": 2,
        "name": "fresh and dry harvest yield",
        "status": "measured",
        "eligibility": "statistical",
        "eligibilityNote": (
            "16 trays of dry-matter harvest yield from one study, with a documented "
            "stress allocation across trays. Tray-level variation can be modelled "
            "descriptively; the unit is DRY matter, not fresh weight, so it cannot "
            "be converted to the simulator's fresh-weight basis without an assumed "
            "water fraction."
        ),
        "evidence": [
            {"kind": "table", "source": "TM-102784", "table": "Table 6 and Table 7 (p.40-41)",
             "description": "per-tray age, height, plants, heads, spikelets, seeds, seed mass, total biomass, EBI",
             "rows": len(HARVEST)},
            {"kind": "statement", "source": "TM-102784", "page": 38,
             "description": ("authors' own summary: 520 g/m2 seed dry matter and "
                             "1546 g/m2 total plant dry matter, EBI 32.4 %")},
        ],
        "unitCaveat": (
            "DRY matter. Phase 6's simulator expresses yield as edible FRESH weight "
            "per m2, so direct comparison is impossible without an assumed dry-matter "
            "fraction. The report prints no fresh weight for these harvests."
        ),
        "replicates": "16 trays (independent trays, staggered ages 71-75 d)",
        "extraction": "validated positional extraction reproducing all 8 published mean/STD pairs",
    },
    {
        "id": 3,
        "name": "water uptake",
        "status": "measured",
        "eligibility": "plausibility-only",
        "eligibilityNote": (
            "Two independent studies report stand water use, but neither reports "
            "per-tray or per-plant replicates, and both are confounded by leakage. "
            "The numbers bound the simulator's assumed peak water demand; they do "
            "not define a response surface."
        ),
        "evidence": [
            point(GAS, "stand_transpiration_mean"),
            point(GAS, "stand_transpiration_mean_areal"),
            point(BPC, "water_added_total"),
            point(BPC, "stand_transpiration_areal_mean"),
        ],
        "replicates": "2 studies, single stand-level integration each",
        "extraction": "printed statements with page-level provenance",
        "studyContrast": {
            "TM-102788": {"arealLPerM2Day": ev(GAS, "stand_transpiration_mean_areal"),
                          "ppfdUmolM2S": ev(GAS, "ppf_mean_growth"),
                          "photoperiodH": 20},
            "TM-103494": {"arealLPerM2Day": ev(BPC, "stand_transpiration_areal_mean"),
                          "ppfdUmolM2S": ev(BPC, "ppfd_phase4"),
                          "photoperiodH": 20},
            "note": ("The two areal values (4.5 vs 6.1 L/m2/day) are the same order "
                     "but not the same number; condensate-based and integrator-based "
                     "water accounting are not interchangeable."),
        },
    },
    {
        "id": 4,
        "name": "transpiration",
        "status": "measured",
        "eligibility": "plausibility-only",
        "eligibilityNote": (
            "Peak and cycle-mean rates are printed, and TM-103494 states the whole "
            "cycle profile qualitatively (rises to full ground cover, then flat to "
            "senescence). No per-day transpiration series is printed anywhere in the "
            "recovered corpus, so a temporal response shape cannot be fitted."
        ),
        "evidence": [
            point(GAS, "stand_transpiration_peak"),
            point(GAS, "stand_transpiration_mean"),
            point(GAS, "stand_transpiration_mean_areal"),
            point(BPC, "stand_transpiration_areal_mean"),
        ],
        "replicates": "stand level only",
        "extraction": "printed statements with page-level provenance",
    },
    {
        "id": 5,
        "name": "water recovery",
        "status": "measured-approximate",
        "eligibility": "plausibility-only",
        "eligibilityNote": (
            "A single condensate-versus-added balance, 0.924, over one 74-day cycle "
            "in a chamber that leaked 20-40 % of its volume per day. It is the only "
            "measured recovery figure recovered and it is reported by the authors as "
            "a transpiration proxy, not a closed-loop recovery test. n=1 study."
        ),
        "evidence": [
            point(BPC, "water_condensed_total"),
            point(BPC, "water_added_total"),
            {"kind": "derived", "source": "TM-103494", "pages": [12, 13],
             "quantity": "waterRecoveredFraction",
             "value": round(float(ev(BPC, "water_condensed_total"))
                            / float(ev(BPC, "water_added_total")), 4),
             "derivation": "condensed 3615 L / added 3914 L",
             "status": "measured-derivable"},
            {"kind": "table", "source": "TM-103494", "table": "Table 2 (p.12-13)",
             "description": "chamber water balance: condensed, added, acid added"},
        ],
        "caveat": ("Chamber leaked 20-40 %/day during this phase and the added-water "
                   "total includes plumbing losses, so the 0.924 figure is a lower "
                   "bound on recovery in a well-sealed system, not a design value."),
        "replicates": "1 study, 1 balance period",
        "extraction": "printed statements with page-level provenance",
    },
    {
        "id": 6,
        "name": "CO2 assimilation",
        "status": "measured",
        "eligibility": "plausibility-only",
        "eligibilityNote": (
            "Peak, cycle-mean and net daily fixation are all printed, plus a "
            "qualitative irradiance response. All are stand-level integrated values "
            "from two ground studies; there is no per-sample replication, so only "
            "bounds and signs are defensible."
        ),
        "evidence": [
            point(GAS, "stand_photosynthesis_peak"),
            point(GAS, "stand_photosynthesis_mean"),
            point(GAS, "dark_respiration_mean"),
            point(GAS, "dark_respiration_peak"),
            point(GAS, "net_carbon_fixed_per_day"),
            point(GAS, "net_carbon_fixed_mass"),
        ],
        "replicates": "2 studies, stand level",
        "extraction": "printed statements with page-level provenance",
    },
    {
        "id": 7,
        "name": "O2 evolution",
        "status": "not-measured",
        "eligibility": "insufficient",
        "eligibilityNote": (
            "Oxygen is never reported as a measured quantity. It appears only in "
            "framing statements about what a CELSS must provide. Producing an O2 "
            "number would require applying a stoichiometric assumption to the CO2 "
            "figures, which converts a measurement into a model output; that is "
            "exactly the confusion Phase 7 exists to remove."
        ),
        "evidence": [],
        "searchRecord": ("Full-text scan of the recovered corpus: 'oxygen'/'O2' occurs "
                         "only in CELSS framing sentences (TM-102788 p.4, TM-102784 "
                         "p.9,13) and in a volatile-organic-compound context in "
                         "TM-109192. No measured O2 rate, concentration series or "
                         "evolution curve was found."),
        "replicates": "none",
        "extraction": "negative finding, documented",
    },
    {
        "id": 8,
        "name": "photosynthetic response to irradiance",
        "status": "measured",
        "eligibility": "plausibility-only",
        "eligibilityNote": (
            "The response is printed as a described shape with two anchor points - "
            "net CO2 production at 60 umol/m2/s, a compensation point near 190-200, "
            "and linear increase to the 750 maximum tested. There is no tabulated "
            "response curve and no replicate at any irradiance, so only the sign, the "
            "linearity claim and the compensation point are usable."
        ),
        "evidence": [
            point(GAS, "light_compensation_point"),
            point(GAS, "ppf_response_lower_bound"),
            point(GAS, "ppf_response_upper_bound"),
            {"kind": "statement", "source": "TM-102788", "page": 13,
             "description": "net CO2 uptake increases linearly with PPF across 60-750 umol/m2/s"},
            {"kind": "statement", "source": "TM-103494", "page": 24,
             "description": "photosynthesis increased linearly with irradiance to the 750 maximum tested"},
        ],
        "replicates": "none (described response, two anchor points)",
        "extraction": "printed statements with page-level provenance",
    },
    {
        "id": 9,
        "name": "PPFD and photoperiod response",
        "status": "measured",
        "eligibility": "insufficient",
        "eligibilityNote": (
            "Two operating points exist (534 umol/m2/s at 20 h and 660 at 24 h in "
            "Phase II, 530 at 20 h in Phase IV), and each has a harvest yield. But "
            "they come from different system phases with different sealing, nutrient "
            "control and, in Phase IV, documented copper deficiency. The two points "
            "are therefore confounded with phase, and no photoperiod series exists at "
            "constant irradiance. Two confounded points cannot identify a response."
        ),
        "evidence": [
            point(GAS, "ppf_mean_growth"),
            point(BPC, "ppfd_phase2"),
            point(BPC, "photoperiod_phase2"),
            point(BPC, "ppfd_phase4"),
            point(BPC, "daily_light_integral_phase4"),
            point(BPC, "crop_growth_rate_biomass"),
            point(BPC, "crop_growth_rate_biomass_phase4"),
            point(BPC, "ppfd_end_tray_penalty", status="measured-approximate"),
        ],
        "confounds": ["system phase", "sealing and leakage rate", "copper deficiency in Phase IV",
                      "different nutrient control maturity"],
        "replicates": "2-3 operating points, none replicated",
        "extraction": "printed statements with page-level provenance",
    },
    {
        "id": 10,
        "name": "gravity-dependent growth",
        "status": "not-measured",
        "eligibility": "insufficient",
        "eligibilityNote": (
            "Every recovered report is a ground-based chamber study at 1 g. No "
            "microgravity, partial-gravity, clinostat or flight plant-growth "
            "measurement exists in the recovered corpus. The simulator's gravity "
            "factor therefore remains an assumption and cannot be calibrated."
        ),
        "evidence": [],
        "searchRecord": ("Full-text scan for 'microgravity', 'gravity', 'clinostat': "
                         "one incidental mention on TM-102784 p.13 in a citation "
                         "context. No gravity manipulation and no gravity response "
                         "measurement found."),
        "replicates": "none",
        "extraction": "negative finding, documented",
    },
    {
        "id": 11,
        "name": "radiation dose-response",
        "status": "not-measured",
        "eligibility": "insufficient",
        "eligibilityNote": (
            "No radiation dose paired with a plant response was found. 'Radiation' "
            "in these reports refers to lamp emission spectra, which is a lighting "
            "variable, not a dose. The simulator's radiation-sensitivity "
            "coefficients remain unsupported assumptions."
        ),
        "evidence": [],
        "searchRecord": ("Full-text scan for 'radiation', 'dose', 'gray', 'mGy': all "
                         "hits are spectral-irradiance or lamp-output contexts "
                         "(TM-103494 p.22-23 compares HPS to fluorescent spectra; "
                         "TM-102784 p.12,20,51,56 concern lamp and irradiance "
                         "measurement). No absorbed-dose measurement."),
        "replicates": "none",
        "extraction": "negative finding, documented",
    },
    {
        "id": 12,
        "name": "measured stress outcomes",
        "status": "measured",
        "eligibility": "insufficient",
        "eligibilityNote": (
            "Stress is recorded as a binary per-tray allocation with narrative cause "
            "(water stress on trays 1, 2, 4, 8; manganese stress on trays 6 and 7). "
            "There is no severity score, no measurement of the stressor, and no "
            "control arm. This supports a descriptive grouping label and nothing "
            "more; using it as a regression target would be manufacturing a label "
            "the source never measured."
        ),
        "evidence": [
            {"kind": "table", "source": "TM-102784", "table": "Table 6 footnotes (p.40)",
             "description": "* water stress, ^ micronutrient stress (particularly Mn)",
             "labeledTrays": {"water": [1, 2, 4, 8], "micronutrient": [6, 7],
                              "none": [3, 5, 9, 10, 11, 12, 13, 14, 15, 16]}},
            {"kind": "statement", "source": "TM-103494", "page": 19,
             "description": ("flag-leaf epinastic rolling with poor seed set, later "
                             "attributed to low tissue copper")},
        ],
        "replicates": "5 labeled of 16 trays, 1 binary label each",
        "extraction": "footnote transcription with tray-level allocation",
    },
]


def checksums() -> dict:
    manifest = METADATA / "phase7_ntrs_checksums"
    if not safedata.exists(manifest):
        return {"available": False}
    payload = safedata.load(manifest)
    entries = payload.get("documents", payload) if isinstance(payload, dict) else payload
    documents = {}
    for entry in entries:
        documents[entry["id"]] = {
            "label": entry.get("label"),
            "sha256": entry.get("sha256"),
            "bytes": entry.get("bytes"),
            "pages": entry.get("pages"),
            "url": entry.get("url"),
        }
    return {
        "available": True,
        "manifest": "data/metadata/phase7_ntrs_checksums",
        "algorithm": "SHA-256 over the downloaded PDF bytes",
        "documents": documents,
    }


def file_digest(path: Path) -> str:
    return hashlib.sha256(safedata.bytes(path)).hexdigest()


def main() -> int:
    catalog = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "phase": 7,
        "purpose": (
            "What was actually measured, where, on what basis, and whether it can "
            "support training. Built from the extraction CSVs so no target can cite "
            "an unextracted value."
        ),
        "statusVocabulary": {
            "measured": "printed in the source with a page citation",
            "measured-approximate": "graph-read or stated-range midpoint",
            "measured-derivable": "exactly recomputable from printed values",
            "not-measured": "searched for and absent from the recovered corpus",
        },
        "eligibilityVocabulary": {
            "ready": "clean per-sample target with replication; trainable now",
            "statistical": "replicated but too small or single-study for predictive CV",
            "mechanistic": "usable to constrain an equation, not to fit a learner",
            "plausibility-only": "bounds or signs only",
            "insufficient": "cannot support any quantitative claim",
        },
        "sources": SOURCES,
        "checksums": checksums(),
        "outputs": {
            "ntrs_wheat_harvest_trays.csv": file_digest(PROCESSED / "ntrs_wheat_harvest_trays.csv"),
            "ntrs_wheat_growth_series.csv": file_digest(PROCESSED / "ntrs_wheat_growth_series.csv"),
            "ntrs_wheat_gas_exchange.csv": file_digest(PROCESSED / "ntrs_wheat_gas_exchange.csv"),
            "ntrs_bpc_water_balance.csv": file_digest(PROCESSED / "ntrs_bpc_water_balance.csv"),
        },
        "trayAreaDiscrepancy": tray_area_discrepancy(),
        "targets": TARGETS,
    }
    counts: dict[str, int] = {}
    for target in TARGETS:
        counts[target["status"]] = counts.get(target["status"], 0) + 1
    catalog["summary"] = {
        "targets": len(TARGETS),
        "byStatus": counts,
        "byEligibility": {},
    }
    for target in TARGETS:
        key = target["eligibility"]
        catalog["summary"]["byEligibility"][key] = (
            catalog["summary"]["byEligibility"].get(key, 0) + 1)

    if PROBLEMS:
        print("CATALOG REJECTED - dangling references:", file=sys.stderr)
        for problem in PROBLEMS:
            print("  -", problem, file=sys.stderr)
        return 1

    OUT.parent.mkdir(parents=True, exist_ok=True)
    safedata.dump(catalog, OUT)
    print("CATALOG BUILT")
    print(f"  targets       : {len(TARGETS)}")
    for status, count in sorted(counts.items()):
        print(f"  {status:<22}: {count}")
    print(f"  eligibility   : {catalog['summary']['byEligibility']}")
    print(f"  written       : {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
