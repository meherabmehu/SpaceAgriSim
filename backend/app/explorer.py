"""Phase 12: the dataset explorer's overlap safeguards.

The explorer exists to answer "how many *independent* studies support this claim?".
That question has a wrong answer that looks right: counting accessions. OSD-320 is a
second deposit of OSD-46 -- the same 44 Arabidopsis arrays, bit-identical across 22,810
probesets (Phase 11 numeric proof) -- so counting it as a replication invents evidence.

This module classifies every dataset pair into exactly one of four relations and gives
each an explicit, plain-language meaning. The vocabulary is closed on purpose: a pair
that no audit has examined is reported as `unverified-overlap`, never as `independent`,
because absence of a detected overlap is not evidence of independence.
"""
from __future__ import annotations
import safedata

import json
from functools import lru_cache

from app import research

AUDIT = research.EVALUATION / "phase11_duplicate_audit"

INDEPENDENT = "independent"
DUPLICATE = "duplicate-measurement"
SHARED_ASSAY = "shared-sample-different-assay"
UNVERIFIED = "unverified-overlap"

RELATION_MEANING = {
    DUPLICATE: ("The same physical measurements, deposited twice. Correlations between the "
                "two accessions are not evidence: they measure nothing but the duplicate."),
    SHARED_ASSAY: ("Different assays measured on the same biological material. Two "
                   "accessions, but not two independent samples of plants: treating them as "
                   "replicates inflates the effective sample size."),
    UNVERIFIED: ("Sample identifiers appear in both accessions, or no overlap audit has "
                 "covered this pair. It must not be assumed independent until a numeric "
                 "check is run."),
    INDEPENDENT: ("No shared sample identifiers were found in the identifier audit, and no "
                  "numeric-equivalence proof links the two accessions."),
}

# Deposits that are known to be redundant. They stay listed (the data is real and usable)
# but are excluded from every independent-study count.
REDUNDANT_DEPOSITS = {
    "OSD-320": {
        "redundantWith": "OSD-46",
        "reason": ("Phase 11 compared all 44 arrays across 22,810 probesets: minimum "
                   "correlation 1.000000 and maximum absolute difference 0.0. OSD-320 is a "
                   "second deposit of OSD-46, not an independent radiation study."),
        "localReference": "ml/evaluation/phase11_duplicate_audit#numericProof",
    },
}

# Assay vocabulary per accession, taken from the manifest text rather than guessed. Only
# used to describe a dataset; never to decide independence.
_ASSAY_HINTS = (
    ("transcriptom", "transcriptomics"),
    ("microarray", "microarray"),
    ("rna-seq", "RNA-seq"),
    ("16s", "16S amplicon"),
    ("its", "ITS amplicon"),
    ("metabolom", "metabolomics"),
    ("proteom", "proteomics"),
    ("methyl", "methylation (MAPit)"),
    ("elemental", "elemental analysis"),
)


@lru_cache(maxsize=1)
def _audit() -> dict:
    if not safedata.exists(AUDIT):
        return {}
    return safedata.load(AUDIT)


def _identifiers() -> dict[str, dict]:
    return _audit().get("identifierProvenance") or {}


def _audited_ids() -> set[str]:
    return set(_identifiers())


def _audit_pairs() -> list[dict]:
    return _audit().get("overlaps") or []


def _assays_for(study_id: str, dataset: dict | None) -> list[str]:
    if dataset is None:
        return []
    text = " ".join([dataset.get("title", ""), dataset.get("description", "")]).lower()
    found = []
    for needle, label in _ASSAY_HINTS:
        if needle in text and label not in found:
            found.append(label)
    return found


def _universe() -> dict[str, dict]:
    """Every accession the explorer knows about, from the manifest and the audit."""
    rows: dict[str, dict] = {}
    manifest = research.manifest()
    for dataset in manifest.get("datasets", []):
        rows[dataset["id"]] = {"dataset": dataset, "inManifest": True}
    for study_id in sorted(_audited_ids()):
        rows.setdefault(study_id, {"dataset": {}, "inManifest": False})
    return rows


def dataset_rows() -> list[dict]:
    """One row per accession, with its sample count and redundancy status.

    Cached: the relation table is a pairwise scan, so recomputing every row inside it
    turned a 4 ms response into 67 ms.
    """
    return list(_cached_rows())


@lru_cache(maxsize=1)
def _cached_rows() -> tuple[dict, ...]:
    identifiers = _identifiers()
    universe = _universe()
    rows = []
    for study_id in sorted(universe, key=lambda value: int(value.split("-")[1])):
        dataset = universe[study_id]["dataset"]
        provenance = identifiers.get(study_id) or {}
        redundancy = REDUNDANT_DEPOSITS.get(study_id)
        rows.append({
            "id": study_id,
            "title": dataset.get("title") or f"{study_id} (not acquired; audit metadata only)",
            "organisms": dataset.get("organisms") or [],
            "sourceType": dataset.get("sourceType"),
            "sourceUrl": dataset.get("sourceUrl"),
            "inManifest": universe[study_id]["inManifest"],
            "assays": _assays_for(study_id, dataset or None),
            "rawSampleNames": provenance.get("rawSampleNames"),
            "uniqueSampleCount": provenance.get("uniqueCanonicalNames"),
            "identifierAudited": bool(provenance),
            "redundantDeposit": bool(redundancy),
            "redundantWith": (redundancy or {}).get("redundantWith"),
            "redundancyReason": (redundancy or {}).get("reason"),
            "countsAsIndependentStudy": not redundancy,
            "usedByModels": _models_using(study_id),
        })
    return tuple(rows)


@lru_cache(maxsize=1)
def _registry_text() -> str:
    return json.dumps(research.model_registry()).lower()


def _models_using(study_id: str) -> list[str]:
    """Which served models cite this accession, by exact string match on the registry."""
    needle = study_id.lower()
    return sorted(model["id"] for model in research.model_registry()["models"]
                  if needle in json.dumps(model).lower())


def relation_between(left: str, right: str) -> dict:
    """Classify one pair. Never returns `independent` without a completed audit."""
    if left == right:
        return {"pair": [left, right], "relation": DUPLICATE,
                "note": "A dataset compared with itself is one study, not two.",
                "sharedSamples": 0, "countsAsIndependent": False}

    for row in _audit_pairs():
        if set(row["studies"]) == {left, right}:
            shared = row.get("sharedSamples") or 0
            audited_class = row.get("classification")
            if audited_class == "duplicate-measurement":
                relation = DUPLICATE
            elif audited_class == "shared-biological-sample-distinct-assay":
                relation = SHARED_ASSAY
            else:
                # Identifiers in common, numeric equivalence never established.
                relation = UNVERIFIED
            return {
                "pair": [left, right],
                "relation": relation,
                "auditClassification": audited_class,
                "sharedSamples": shared,
                "fractionOfSmaller": row.get("fractionOfSmaller"),
                "exampleSamples": (row.get("examples") or [])[:5],
                "assays": row.get("assays"),
                "countsAsIndependent": False,
                "conflicts": bool(shared) or relation == DUPLICATE,
                "localReference": "ml/evaluation/phase11_duplicate_audit#overlaps",
            }

    audited = _audited_ids()
    if left in audited and right in audited:
        return {"pair": [left, right], "relation": INDEPENDENT, "sharedSamples": 0,
                "countsAsIndependent": True, "conflicts": False,
                "localReference": "ml/evaluation/phase11_duplicate_audit#identifierProvenance"}
    return {"pair": [left, right], "relation": UNVERIFIED, "sharedSamples": None,
            "countsAsIndependent": False,
            # Unknown is not the same as contradictory: an unaudited accession cannot be
            # shown to conflict, so it is flagged rather than dropped from a study set.
            "conflicts": False,
            "note": "At least one accession has no identifier audit, so independence is unknown."}


def overlaps() -> dict:
    """Every non-independent relation, plus the meaning of each class."""
    rows = dataset_rows()
    by_id = {row["id"]: row for row in rows}
    relations = []
    ids = [row["id"] for row in rows]
    for index, left in enumerate(ids):
        for right in ids[index + 1:]:
            relation = relation_between(left, right)
            if relation["relation"] != INDEPENDENT:
                relations.append(relation)
    order = {DUPLICATE: 0, SHARED_ASSAY: 1, UNVERIFIED: 2, INDEPENDENT: 3}
    relations.sort(key=lambda row: (order[row["relation"]], row["pair"]))
    return {
        "relationCounts": {name: sum(1 for row in relations if row["relation"] == name)
                           for name in (DUPLICATE, SHARED_ASSAY, UNVERIFIED)},
        "relations": relations,
        "relationMeaning": RELATION_MEANING,
        "redundantDeposits": REDUNDANT_DEPOSITS,
        "independentStudyCount": sum(1 for row in rows if row["countsAsIndependentStudy"]),
        "accessionCount": len(rows),
        "auditedAccessionCount": sum(1 for row in rows if row["identifierAudited"]),
        "redundantDepositUse": {
            study_id: {
                "usedByModels": by_id[study_id]["usedByModels"],
                "reachableThrough": REDUNDANT_DEPOSITS[study_id]["redundantWith"],
            }
            for study_id in REDUNDANT_DEPOSITS if study_id in by_id
        },
        "note": ("Twenty accessions are not twenty studies. Redundant deposits are counted "
                 "once, shared material is reported as shared, and a pair with no audit is "
                 "reported as unverified rather than independent."),
    }


def independent_set(study_ids: list[str]) -> dict:
    """Reduce a requested study list to a defensible independent set.

    Greedy and order-preserving: the first accession wins, later conflicting ones are
    dropped with the reason, so the result is reproducible for a given input order.
    """
    rows = {row["id"]: row for row in dataset_rows()}
    unknown = [study_id for study_id in study_ids if study_id not in rows]
    kept: list[str] = []
    dropped: list[dict] = []
    for study_id in study_ids:
        if study_id in unknown:
            continue
        redundancy = REDUNDANT_DEPOSITS.get(study_id)
        if redundancy:
            dropped.append({"id": study_id, "relation": DUPLICATE,
                            "conflictsWith": redundancy["redundantWith"],
                            "reason": redundancy["reason"]})
            continue
        conflict = None
        for other in kept:
            relation = relation_between(study_id, other)
            if relation.get("conflicts"):
                conflict = (other, relation)
                break
        if conflict:
            dropped.append({"id": study_id, "relation": conflict[1]["relation"],
                            "conflictsWith": conflict[0],
                            "reason": RELATION_MEANING[conflict[1]["relation"]]})
        elif study_id not in kept:
            kept.append(study_id)
    unverified = [{"id": study_id,
                   "unverifiedAgainst": [other for other in kept
                                         if relation_between(study_id, other)["relation"]
                                         == UNVERIFIED]}
                  for study_id in kept
                  if any(relation_between(study_id, other)["relation"] == UNVERIFIED
                         for other in kept)]
    return {"requested": len(study_ids), "independent": kept,
            "independentCount": len(kept), "dropped": dropped, "unknown": unknown,
            "unverifiedIndependence": [row for row in unverified if row["unverifiedAgainst"]],
            "note": ("A count over this list must use independentCount, not len(requested). "
                     "Dropping is reported with the relation that caused it.")}
