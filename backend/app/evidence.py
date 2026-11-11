"""Evidence-grounded retrieval over verified repository artifacts.

The research assistant answers from a corpus built **only** from things the
repository can prove: the pinned dataset manifest, the model registry, the
scientific classification taxonomy, the committed evaluation artifacts, and a
small set of curated methodology statements drawn from the documentation.

Design decisions that matter more than the retrieval algorithm
--------------------------------------------------------------
1. **Evidence is data, never instruction.** Retrieved text is untrusted input. It is
   scanned for instruction-like content (imperatives addressed to an assistant,
   role-play framing, prompt delimiters, tool invocation syntax) and any document
   containing it is quarantined rather than paraphrased. The assistant composes
   answers by *selecting and quoting* evidence, so a successful injection would have
   to survive being quoted as a quotation.

2. **No citation may be invented.** Every answer is assembled from citation records
   that already exist in the corpus. There is no path by which a sentence enters an
   answer without a `source` record attached, because answers are built as
   `(text, citation_index)` pairs and the renderer refuses text without an index.

3. **Secrets never enter the corpus.** Documents are screened for token-shaped
   strings, credential assignments and private filesystem paths before indexing.

4. **No LLM is required.** The deterministic composer answers by extractive
   selection with extractive summaries. An optional configured LLM may *rephrase*
   retrieved passages, but it is given no capability to add sources, and if it is
   not configured the platform still answers.

The scoring is BM25 over a small in-process index. At 19 datasets, 16 classified
features and 8 models, a vector database would be ceremony: the corpus is a few
hundred passages and the whole thing builds in milliseconds.
"""
from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BUNDLE = Path(__file__).resolve().parents[1] / "scientific_data"
DATA = (BUNDLE if BUNDLE.exists() else ROOT) / "data"
ARTIFACTS = (BUNDLE if BUNDLE.exists() else ROOT) / "ml" / "artifacts"
EVALUATION = (BUNDLE if BUNDLE.exists() else ROOT) / "ml" / "evaluation"

MAX_QUESTION_CHARS = 400
MAX_PASSAGE_CHARS = 900
TOP_K = 6
BM25_K1 = 1.4
BM25_B = 0.72

# Instruction-shaped content that has no business in a scientific metadata field.
# These are checked against document text before indexing; a hit quarantines the
# document rather than being silently stripped, because silently stripping would
# hide an attack instead of reporting it.
INJECTION_PATTERNS = (
    re.compile(r"ignore\s+(?:all\s+|any\s+)?(?:previous|above|prior|earlier)\s+"
               r"(?:instructions?|prompts?|rules?)", re.I),
    re.compile(r"disregard\s+(?:the\s+)?(?:above|previous|prior|system)", re.I),
    re.compile(r"\bsystem\s*prompt\b", re.I),
    re.compile(r"\byou\s+are\s+now\s+(?:a|an|the)\b", re.I),
    re.compile(r"\bnew\s+instructions?\s*:", re.I),
    re.compile(r"</?(?:system|assistant|user|instructions?|prompt)\s*>", re.I),
    re.compile(r"\[/?(?:INST|SYS)\]", re.I),
    re.compile(r"\b(?:assistant|ai|model)\s*:\s*you\s+must\b", re.I),
    re.compile(r"\bexecute\s+(?:the\s+following|this)\s+command\b", re.I),
    re.compile(r"\bcurl\s+https?://", re.I),
    re.compile(r"<\s*script\b", re.I),
)

# Anything that looks like a credential, a private key or a personal filesystem path.
SECRET_PATTERNS = (
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{16,}"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"\bsk-[A-Za-z0-9]{20,}"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"(?i)\b(?:api[_-]?key|secret|password|passwd|token)\s*[:=]\s*"
               r"[\"']?[A-Za-z0-9_\-\.]{12,}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"(?<![\w/])/(?:home|root|Users)/[A-Za-z0-9._-]+"),
)

TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9\-_.]*")
# Hyphenated compounds are common in this corpus ("training-eligibility",
# "cross-study", "held-out"). Indexing them whole *and* in parts means a question
# about "training" can reach a passage that only contains "training-eligibility".
COMPOUND_SPLIT = re.compile(r"[-_/.]")
STOPWORDS = frozenset("""
a an the is are was were be been being do does did doing have has had having
of in on at to for from by with about into over after before between during
what which who whom whose when where why how and or but if then than that this
these those it its they them their there here can could should would may might
will shall must not no nor so such as any all some more most other only own same
very just also both each few many much i me my we our us you your he she his her
please tell explain show give list does did done get got make made want need
""".split())


@dataclass
class Passage:
    """One citable unit of evidence."""
    id: str
    source_id: str
    kind: str                 # dataset | model | classification | evaluation | methodology | literature
    title: str
    text: str
    accession: str | None = None
    url: str | None = None
    local_ref: str | None = None
    limitations: list[str] = field(default_factory=list)
    measured: bool = True     # False when the passage describes a model or estimate
    tokens: list[str] = field(default_factory=list)

    def citation(self) -> dict:
        """The citation record handed to the user. Never synthesised downstream."""
        return {
            "sourceId": self.source_id,
            "kind": self.kind,
            "title": self.title,
            "accession": self.accession,
            "url": self.url,
            "localReference": self.local_ref,
            "evidenceClass": ("measured data" if self.measured
                              else "model or estimate, not a measurement"),
            "limitations": self.limitations[:4],
        }


def _stem(token: str) -> str:
    """Crude, deterministic suffix folding.

    Its only job is to let "training" match "trained" and "predictions" match
    "predict". A real stemmer would need a dependency and would make retrieval
    results harder to reproduce; this is eight lines and fully deterministic.
    """
    for suffix in ("ations", "ation", "ings", "ing", "ions", "ion", "ies", "ers", "er",
                   "ed", "es", "s"):
        if len(token) > len(suffix) + 3 and token.endswith(suffix):
            return token[: -len(suffix)]
    return token


def tokenize(text: str) -> list[str]:
    """Tokens plus their stems, so recall is not lost to inflection."""
    raw = [t for t in TOKEN_RE.findall(text.lower()) if len(t) > 1 and t not in STOPWORDS]
    tokens = list(raw)
    for token in raw:
        parts = [p for p in COMPOUND_SPLIT.split(token) if len(p) > 1]
        if len(parts) > 1:
            tokens.extend(parts)
    tokens.extend(_stem(t) for t in list(tokens))
    return tokens


def _metric(name, value) -> str:
    """Format one metric without assuming it is a scalar.

    Phase 9 artifacts store some metrics as per-class lists (per-class recall, for
    example), so a naive `f"{v:.4g}"` raises on a real artifact. Formatting is
    therefore type-directed rather than assumed.
    """
    if isinstance(value, bool):
        return f"{name} {value}"
    if isinstance(value, (int, float)):
        return f"{name} {value:.4g}"
    if isinstance(value, (list, tuple)):
        rendered = ", ".join(f"{_metric('', v).strip()}" for v in value[:6])
        return f"{name} [{rendered}]"
    if isinstance(value, dict):
        rendered = ", ".join(f"{k}={_metric('', v).strip()}" for k, v in list(value.items())[:6])
        return f"{name} {{{rendered}}}"
    return f"{name} {value}"


def _validation_summary(validation) -> str:
    """One sentence of validation per protocol, never a nested object stringified.

    Phase 19 changed a model's `validation` from a string to a structured object. Passing that
    straight through `_clean` put the whole nested dict into the retrieval corpus: a single model
    card became several kilobytes of metric JSON, which both drowned its own limitations and gave
    unrelated questions a spurious lexical match on words like "yield" and "predicted".
    """
    if isinstance(validation, str):
        return _clean(validation)
    if not isinstance(validation, dict):
        return ""
    def study_name(block) -> str:
        """First author and year are enough to identify a source; a full citation is not a passage."""
        raw = _clean(block.get("study", "unnamed"))
        return raw if len(raw) <= 90 else raw[:87].rstrip(" ,;:") + "..."

    parts = []
    internal = validation.get("internal")
    if isinstance(internal, dict):
        metrics = internal.get("metrics") or {}
        metrics_text = ", ".join(f"{k} {v:.4g}" if isinstance(v, (int, float)) else f"{k} {v}"
                                 for k, v in metrics.items())
        parts.append(f"internal {internal.get('protocol', 'held-out')}: {metrics_text}")
    independent = validation.get("independent")
    if isinstance(independent, dict):
        metrics = independent.get("metrics") or {}
        parts.append(
            f"independent holdout {study_name(independent)}: "
            f"MAPE {metrics.get('MAPE')} % against a {independent.get('acceptanceCriterionPct')} % "
            f"criterion, passed {independent.get('passed')}"
            + (f"; {independent.get('verdict')}" if independent.get("verdict") else ""))
    development = validation.get("development")
    if isinstance(development, dict):
        metrics = development.get("metrics") or {}
        parts.append(
            f"development set {study_name(development)}: MAPE {metrics.get('MAPE')} % "
            f"(used for model selection: {development.get('usedForModelSelection')}; counts as "
            f"validation: {development.get('countsAsValidation')})")
    return "; ".join(part for part in parts if part.strip())


def _clean(value) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def screen(text: str) -> dict:
    """Classify a candidate document before it is allowed into the corpus."""
    hits = []
    for pattern in INJECTION_PATTERNS:
        match = pattern.search(text)
        if match:
            hits.append(match.group(0)[:60])
    secrets = []
    for pattern in SECRET_PATTERNS:
        match = pattern.search(text)
        if match:
            secrets.append(pattern.pattern[:40])
    return {"injection": hits, "secrets": secrets,
            "safe": not hits and not secrets}


def _read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


# --------------------------------------------------------------------------
# Corpus construction
# --------------------------------------------------------------------------
def _dataset_passages(quarantine: list) -> list[Passage]:
    from app import research

    passages = []
    manifest = research.manifest()
    for dataset in manifest.get("datasets", []):
        accession = _clean(dataset.get("id"))
        title = _clean(dataset.get("title")) or accession
        organisms = ", ".join(dataset.get("organisms") or []) or "not recorded"
        assays = ", ".join(dataset.get("assayTypes") or []) or "not recorded"
        description = _clean(dataset.get("description"))
        text = (f"NASA OSDR study {accession}. Title: {title}. Organisms: {organisms}. "
                f"Assays: {assays}. Version {dataset.get('version', 'unrecorded')}, "
                f"metadata verified {dataset.get('verifiedAt', 'unrecorded')}. "
                f"Description: {description[:MAX_PASSAGE_CHARS]}")
        verdict = screen(text)
        if not verdict["safe"]:
            quarantine.append({"sourceId": accession, "kind": "dataset",
                               "injection": verdict["injection"],
                               "secrets": verdict["secrets"]})
            continue
        limitations = [
            "A registered study is not a downloaded training table; assays and "
            "physiological labels remain separate.",
        ]
        if not (dataset.get("files") or []):
            limitations.append("No linked data files are recorded for this study.")
        passages.append(Passage(
            id=f"dataset::{accession}", source_id=accession, kind="dataset",
            title=f"{accession} — {title}", text=text, accession=accession,
            url=dataset.get("sourceUrl") or dataset.get("metadataUrl"),
            local_ref=f"data/metadata/dataset_manifest.json#{accession}",
            limitations=limitations, measured=True))
    return passages


def _duplicate_note(accession: str) -> dict | None:
    audit = _read_json(EVALUATION / "phase11_duplicate_audit.json")
    if not audit:
        return None
    for pair in audit.get("duplicates", []):
        if accession in pair.get("studies", []):
            other = [s for s in pair["studies"] if s != accession]
            return {"other": other[0] if other else None,
                    "classification": pair.get("classification"),
                    "sharedSamples": pair.get("sharedSamples")}
    return None


def _model_passages(quarantine: list) -> list[Passage]:
    from app import research
    from app.science_classification import CATEGORY_NAMES, SERVICE_ALLOWED, feature_by_id

    passages = []
    registry = research.model_registry()
    for model in registry.get("models", []):
        model_id = _clean(model.get("id"))
        classification = feature_by_id(model_id)
        metrics = model.get("metrics") or {}
        metric_text = ", ".join(_metric(k, v) for k, v in metrics.items()) or "none recorded"
        limitations = list(model.get("limitations") or [])
        text = (f"Model {model_id} ({_clean(model.get('name'))}), version "
                f"{_clean(model.get('version'))}, status {_clean(model.get('status'))}. "
                f"Task: {_clean(model.get('task'))}. Source: "
                f"{_clean(model.get('sourceStudy'))} "
                f"({_clean(model.get('sourceType')) or 'source type not recorded'}). "
                f"Inputs: {', '.join(model.get('features') or [])}. "
                f"Target: {_clean(model.get('target'))} "
                f"[{_clean(model.get('unit'))}]. Training rows {model.get('samples')} over "
                f"{model.get('groups')} independent groups. Held-out metrics: {metric_text}. "
                f"Validation: {_validation_summary(model.get('validation'))}. "
                + (f"Scientific category {classification.category}: "
                   f"{CATEGORY_NAMES[classification.category]}. "
                   f"Service allowance: {SERVICE_ALLOWED[classification.category]}. "
                   if classification else "")
                # Phase 32: the scope the model is served under travels with every passage the
                # assistant can quote. Without it a retrieval hit could describe a research
                # surface as if it were an operational forecast, which is exactly the
                # contradiction Phase 31 withdrew a model over.
                + (f" Served scope: {_clean(model.get('servedScope'))}."
                   if model.get("servedScope") else "")
                + (f"Limitations: {' '.join(limitations[:4])}" if limitations else ""))
        verdict = screen(text)
        if not verdict["safe"]:
            quarantine.append({"sourceId": model_id, "kind": "model",
                               "injection": verdict["injection"],
                               "secrets": verdict["secrets"]})
            continue
        passages.append(Passage(
            id=f"model::{model_id}", source_id=model_id, kind="model",
            title=f"Model {model_id} — {_clean(model.get('name'))}",
            text=text, url=model.get("sourceUrl"),
            local_ref=f"ml/artifacts/registry.json#{model_id}",
            limitations=limitations or ["No model-specific limitations are recorded."],
            measured=False))
    # Excluded candidates are evidence too: users ask why they are not served.
    for feature in _excluded_features():
        passages.append(Passage(
            id=f"excluded::{feature['id']}", source_id=feature["id"],
            kind="classification", title=f"Excluded candidate {feature['id']}",
            text=(f"{feature['name']} is classified category {feature['category']} "
                  f"({feature['categoryName']}), status {feature['status']}. "
                  f"Evidence: {feature['evidence']} Not served: {feature['surface']}. "
                  + " ".join(feature.get("notes") or [])),
            local_ref="backend/app/science_classification.py",
            limitations=feature.get("notes") or [], measured=False))
    return passages


def _excluded_features() -> list[dict]:
    from app.science_classification import FEATURES

    return [f.to_dict() for f in FEATURES if f.category == 6 or "excluded" in f.surface]


def _evaluation_passages(quarantine: list) -> list[Passage]:
    """Committed findings, each one a citable record rather than a paraphrase."""
    curated = [
        ("phase11-duplicate-osd320", "eval",
         "OSD-320 duplicates OSD-46 (Phase 11 duplication audit)",
         ("OSD-320 holds the same Affymetrix arrays as OSD-46 under a second accession. "
          "44 arrays and 22,810 probesets were compared: minimum Pearson correlation "
          "1.000000 and maximum absolute difference 0.0. OSD-320 must therefore never be "
          "used as independent validation of a radiation model trained on OSD-46."),
         "phase11_duplicate_audit.json", None,
         ["The finding is a numeric identity check on the processed matrices, not a "
          "metadata comparison."]),
        ("phase11-harvest-zero", "eval", "No harvest or biomass dataset exists in the corpus (Phase 11 sweep)",
         ("A sweep of all 231 OSDR studies holding a usable processed matrix against four "
          "question vocabularies returned zero candidates carrying harvest or biomass "
          "measurements paired with an environmental gradient for a leafy crop. The mizuna "
          "harvest gap cannot be closed by adding rows from this corpus."),
         "phase11_dataset_discovery.json", None,
         ["Zero candidates is a statement about the 231 studies scanned, not about all "
          "biology that has ever been measured."]),
        ("phase11-gravity-osd346", "eval", "OSD-346 gravity signal is not separable from flight run (Phase 11)",
         ("The OSD-346 partial-gravity signal is confounded with flight run. No gravity "
          "level appears in more than one run, the mean within-run gravity range is 0.192 g "
          "or 18 percent of the 1.05 g span, flight run is identifiable from expression at "
          "balanced accuracy 0.6944, and the run-centred correlation reverses sign "
          "(rho -0.7981)."),
         "phase11_gravity_batch.json", None,
         ["Nine gravity levels across six runs cannot be separated from run-level "
          "variation at this sample size."]),
        ("phase11-radiation-nested", "eval", "No radiation learner beats the served model under nested selection (Phase 11)",
         ("Six candidate configurations were scored under leave-one-biological-group-out "
          "with gene selection inside each fold. The apparent gain from a 25-gene panel was "
          "one held-out group out of twenty-two (1 win, 0 losses, 21 ties). When the "
          "configuration was chosen by inner cross-validation inside every outer fold, the "
          "result was 0.037 below the shipped model on radiation quality and exactly level "
          "on exposure. No model was promoted."),
         "phase11_radiation_validation.json", None,
         ["Clinical or agronomic significance cannot be inferred from balanced accuracy on "
          "44 arrays."]),
        ("phase11-explainability", "eval", "Radiation explanations agree at the top and nowhere else (Phase 11)",
         ("Across four model classes the top five genes agree with mean overlap 0.80 for "
          "radiation quality and 1.00 for exposure, while rank correlation across the whole "
          "40-gene panel is 0.016. Between 90 and 100 percent of panel genes show zero "
          "permutation drop, so no single gene is individually necessary. Top-ranked "
          "features are attributions of the fitted model, not causes."),
         "phase11_explainability.json", None,
         ["Permutation importance is an attribution, not an intervention."]),
        ("phase11-ood-rejected", "eval", "The novelty detector fails its own controls (Phase 11)",
         ("Two out-of-distribution scores were tested against three controls: a verified "
          "duplicate that must look ordinary, a different platform that must be flagged, "
          "and held-out groups that must not be flagged. The Mahalanobis score passed one "
          "of three controls and the nearest-neighbour score two of three, with the "
          "platform-shifted study scoring lower than the training data itself. No threshold "
          "is validated and none is served."),
         "phase11_ood_uncertainty.json", None,
         ["No validated out-of-distribution threshold exists for this platform."]),
        ("phase10-dose", "eval", "The dose classifier stays excluded (Phase 10 and Phase 11)",
         ("OSD-782 has valid absorbed-dose labels at 0, 10 and 100 Gy, but dose is not "
          "recoverable. Holding timepoint fixed gives a mean within-timepoint Spearman of "
          "0.224 at p 0.158 with the sign reversing at 3 hours, and a boundary fitted "
          "through the 0 and 100 Gy anchors places 10 Gy samples at a median predicted "
          "84.8 Gy. The labels are valid; the expression response does not form a dose axis."),
         "phase11_dose_generalization.json", None,
         ["36 libraries over three dose levels cannot support a dose-response model."]),
        ("phase10-coverage", "eval", "Interval coverage is measured, not guaranteed (Phase 10 and Phase 11)",
         ("Every served interval reports measured held-out coverage separately from its "
          "nominal level. Measured group-level coverage is 0.9919 for both microbial "
          "models, 0.9606 for lettuce v2 and 0.9393 for lettuce v1, against a nominal 0.90. "
          "These are measurements on held-out groups, not guarantees, because multiple "
          "tissues from one pillow and two campaigns are not a sample of future campaigns."),
         "phase10_uncertainty_decision.json", None,
         ["Conformal coverage is marginal under exchangeability, which future campaigns "
          "need not satisfy."]),
        ("phase10-cross-study", "eval", "Cross-study radiation transfer failed (Phase 10)",
         ("Transfer from OSD-46 to OSD-782 failed under every harmonisation attempted "
          "(z-score, rank, quantile map and pathway), scoring 0.5 balanced accuracy. The "
          "target's own contrast is learnable within the study (0.812 with timepoints held "
          "out) but does not survive an unseen dose and timepoint cell (0.438), which is the "
          "condition a cross-study transfer actually faces."),
         "phase10_cross_study.json", None,
         ["The negative is about transfer, not about the absence of signal in the target."]),
        ("phase11-microbial", "eval", "The flight microbial effect replicates, but a new campaign is not promised (Phase 11)",
         ("The flight-versus-ground contrast in culturable aerobic leaf load is +3.06 log10 "
          "CFU per gram in VEG-04A and +2.64 in VEG-04B with cluster-bootstrap intervals "
          "excluding zero. Random-effects pooling gives +2.820 with a confidence interval "
          "of 2.327 to 3.314, but a 95 percent prediction interval for a new campaign of "
          "-0.377 to 6.018, which includes zero. The effect is tissue-specific: soil and "
          "root strata span zero."),
         "phase11_microbial_campaigns.json", None,
         ["Two campaigns cannot estimate between-campaign heterogeneity reliably, so the "
          "prediction interval is wide and provisional."]),
    ]
    passages = []
    for source_id, kind, title, text, artifact, url, limitations in curated:
        verdict = screen(text)
        if not verdict["safe"]:
            quarantine.append({"sourceId": source_id, "kind": "evaluation",
                               "injection": verdict["injection"],
                               "secrets": verdict["secrets"]})
            continue
        passages.append(Passage(
            id=f"finding::{source_id}", source_id=source_id, kind="evaluation",
            title=title, text=text, url=url,
            local_ref=f"ml/evaluation/{artifact}", limitations=limitations,
            measured=False))
    return passages


def _methodology_passages(quarantine: list) -> list[Passage]:
    curated = [
        ("method-ood", "Methodology: why no out-of-distribution flag is served",
         ("The platform does not present an out-of-distribution flag as validated. Phase 11 "
          "tested two candidate detectors against a verified duplicate, a platform shift and "
          "held-out groups, and neither passed. Schema-based domain checks are used instead: "
          "input features must match the model schema exactly, values must fall inside the "
          "recorded training domain, and the payload states which checks were applied."),
         "docs/PHASE11_UNCERTAINTY_OOD.md"),
        ("method-simulator", "Methodology: what the habitat simulator estimates",
         ("The space agriculture simulator is an assumption-based mathematical model, "
          "category 5, hypothetical scenario exploration. It is not NASA-calibrated for "
          "Moon or Mars crop growth, and no lunar or Martian predictive validation exists. "
          "Its radiation, light, temperature and humidity response factors are heuristic "
          "scenario assumptions. The gravity response was removed in Phase 30 rather than kept as "
          "a placeholder: no recovered dataset measures plant production as a function of "
          "gravity level, so the simulator "
          "now has no gravity input, factor or control. The separately trained Earth lettuce "
          "regression is category 3 from external measured data and is no longer served as a "
          "harvest forecast, because its independent evaluations failed."),
         "docs/SIMULATION_METHODOLOGY.md"),
        ("method-withdrawn-models",
         "Methodology: mizuna harvest mass and absolute microbial load are not served",
         ("Phase 31 withdrew two models from the platform rather than keeping them as cards. "
          "mizuna-harvest-v1 (NASA OSD-655) predicted mizuna harvest fresh mass per pillow: its "
          "held-out R2 was -0.333 against a training-mean baseline of -0.138, i.e. worse than "
          "predicting the mean, on 14 usable samples from a single experiment whose two arms also "
          "differ in target definition. mizuna-microbial-load-v1 (NASA OSD-780) predicted absolute "
          "leaf microbial load: leave-one-campaign-out R2 was -0.55 for VEG-04A and -0.58 for "
          "VEG-04B, worse than the mean on both, because the campaign offset is what fails to "
          "transfer. Neither has an endpoint, a catalogue row or a dashboard card any more, and "
          "there is no replacement harvest predictor. The within-campaign relative microbial model "
          "mizuna-microbial-relative-load-v2 remains served and is the only microbial prediction. "
          "The fitted ET0 emulator was withdrawn in the same phase: it was trained on derived "
          "FAO-56 output, was about 19 % worse than Hargreaves-Samani on an unseen site, and only "
          "the FAO-56 physics is served now."),
         "docs/PHASE31_REMOVED_MODELS.md"),
        ("method-classification", "Methodology: the six-category scientific classification",
         ("Every prediction surface is classified into one of six categories: 1 NASA-measured "
          "and directly supported; 2 NASA-calibrated with compatible measurements; 3 "
          "experimentally supported by non-NASA data; 4 mechanistic calculation with explicit "
          "assumptions; 5 hypothetical scenario exploration; 6 unsupported scientific "
          "prediction. Category 6 may not be served as a prediction at all, which is why two "
          "trained models are excluded from the registry."),
         "backend/app/science_classification.py"),
        ("method-features", "Methodology: molecular classifiers need a full feature vector",
         ("A transcriptomic classifier requires exactly the gene features it was trained on. "
          "A partial expression vector is rejected with HTTP 422 and a count of missing "
          "features rather than being imputed. Reference profiles returned by the API are "
          "class centroids of the training data and are labelled synthetic, because a "
          "centroid is not a measured specimen."),
         "backend/app/routes/research.py"),
        ("method-training-eligibility",
         "Eligibility: which NASA targets could support future predictive training",
         ("The committed training-eligibility audit lists 4 existing tasks, 12 NTRS candidate "
          "targets and 9 refused tasks, and its `readyForPredictiveTraining` list is empty. "
          "Six targets are trainable but constrained, meaning a model can be fitted and its "
          "error characterised, but it cannot be validated out of sample. Deep learning is "
          "explicitly not permitted: the largest measured target is 123 samples across 35 "
          "groups and 2 campaigns. Nine targets were refused outright, including wheat "
          "biomass time series with n = 1 per age, and wheat harvest yield with 16 trays from "
          "a single study."),
         "data/metadata/phase7_training_eligibility.json"),
        ("method-provenance", "Methodology: dataset provenance and checksums",
         ("Each registered study records a version, a metadata SHA-256 and a verification "
          "timestamp. Downloaded training tables are separate from the registry, so a study "
          "being registered does not mean its matrices were used for training."),
         "docs/DATA_PROVENANCE.md"),
    ]
    passages = []
    for source_id, title, text, ref in curated:
        verdict = screen(text)
        if not verdict["safe"]:
            quarantine.append({"sourceId": source_id, "kind": "methodology",
                               "injection": verdict["injection"],
                               "secrets": verdict["secrets"]})
            continue
        passages.append(Passage(
            id=f"method::{source_id}", source_id=source_id, kind="methodology",
            title=title, text=text, local_ref=ref, measured=False,
            limitations=["Documentation describes implemented behaviour; it is not a "
                         "measurement."]))
    return passages



# Resolved like every other runtime asset: the serverless bundle carries data/ under
# backend/scientific_data, so a repo-root-only path silently produced an empty corpus in
# production while passing locally.
LITERATURE = DATA / "literature" / "ntrs_bpc.json"

# NASA records evaluated outside the biomass-production-chamber set: a ground light-quality study with
# measured endpoints for the two crops the simulator models, and an ethylene-sensitivity reprint that
# defines a closed-chamber risk the simulator does not carry. Kept in their own file so the BPC
# bundle and its page-level quotes stay exactly as they were.
SUPPLEMENT = DATA / "literature" / "ntrs_supplement.json"

# A NASA technical report page is quoted as evidence with its page number. It is measured data
# in the everyday sense — somebody measured a canopy — but it is a *literature* measurement:
# ground-based, one chamber, one cultivar, one campaign, and not a Moon or Mars result. Every
# passage repeats those boundaries so the assistant cannot borrow it for a space claim.
LITERATURE_LIMITS = [
    "Ground-based closed chamber at Kennedy Space Center; not a Moon, Mars or ISS measurement.",
    "One chamber, one cultivar and one campaign: not a transferable response surface.",
    "Quoted from a scanned NASA technical report; table cells are not machine-parsed, so a "
    "number must be read on the cited page.",
]


SUPPLEMENT_LIMITS = [
    "Ground-based growth-chamber or greenhouse work; not a Moon, Mars or ISS result.",
    "One cultivar per crop and one campaign per study: not a transferable response surface.",
    "Recorded as citable evidence. No coefficient is fitted from it, so it does not change any "
    "simulated number.",
]


def _supplement_passages(quarantine: list) -> list[Passage]:
    """NASA records that are citable but deliberately not modelled."""
    if not SUPPLEMENT.is_file():
        return []
    payload = _read_json(SUPPLEMENT)
    passages: list[Passage] = []
    for record_id, report in (payload.get("reports") or {}).items():
        label = report.get("label") or record_id
        title = report.get("title") or record_id
        abstract = (report.get("abstract") or "").strip()
        nature = (report.get("dataNature") or "").strip()
        why = (report.get("whyItMatters") or "").strip()
        if abstract:
            text = (f"{label} ({record_id}) — {title}. {report.get('stiType', '')}. "
                    f"What was measured: {abstract} Data nature: {nature} Why the platform holds "
                    f"it: {why}")
            verdict = screen(text)
            if not verdict["safe"]:
                quarantine.append({"sourceId": f"NTRS-{record_id}", "kind": "literature",
                                   "injection": verdict["injection"], "secrets": verdict["secrets"]})
            else:
                passages.append(Passage(
                    id=f"supplement::{record_id}::abstract",
                    source_id=f"NTRS-{record_id}", kind="literature",
                    title=f"{label} — {title}", text=text, url=report.get("url"), measured=True,
                    local_ref=f"data/literature/ntrs_supplement.json#{record_id}",
                    limitations=SUPPLEMENT_LIMITS + ([report.get("limits", [""])[0]] if report.get("limits") else [])))
        for page in report.get("measurementPages") or []:
            excerpt = (page.get("excerpt") or "").strip()
            if not excerpt:
                continue
            terms = ", ".join(page.get("terms") or [])
            text = (f"{label} ({record_id}), page {page['page']} — {title}. Recorded conditions and "
                    f"findings: {terms}. Text on that page: {excerpt}")
            verdict = screen(text)
            if not verdict["safe"]:
                quarantine.append({"sourceId": f"NTRS-{record_id}", "kind": "literature",
                                   "injection": verdict["injection"], "secrets": verdict["secrets"]})
                continue
            passages.append(Passage(
                id=f"supplement::{record_id}::p{page['page']}::{len(passages)}",
                source_id=f"NTRS-{record_id}", kind="literature",
                title=f"{label} p.{page['page']} — {title}", text=text,
                url=f"{report.get('url')}", measured=True,
                local_ref=f"data/literature/ntrs_supplement.json#{record_id}:p{page['page']}",
                limitations=SUPPLEMENT_LIMITS))
    return passages


def _literature_passages(quarantine: list) -> list[Passage]:
    if not LITERATURE.is_file():
        return []
    payload = _read_json(LITERATURE)
    passages: list[Passage] = []
    for record_id, report in (payload.get("reports") or {}).items():
        label = report.get("label") or record_id
        title = report.get("title") or record_id
        abstract = (report.get("abstract") or "").strip()
        if abstract:
            text = (
                f"{label} ({record_id}) — {title}. NASA technical report abstract: {abstract} "
                f"These are ground-based closed-chamber measurements of a crop canopy in the "
                f"NASA Biomass Production Chamber, not measurements made on the Moon, on Mars "
                f"or on the International Space Station.")
            verdict = screen(text)
            if verdict["safe"]:
                passages.append(Passage(
                    id=f"literature::{record_id}::abstract",
                    source_id=f"NTRS-{record_id}", kind="literature",
                    title=f"{label} abstract — {title}",
                    text=text, url=report.get("url"), measured=True,
                    local_ref=f"data/literature/ntrs_bpc.json#{record_id}",
                    limitations=LITERATURE_LIMITS + [report.get("whyItMatters") or ""]))
            else:
                quarantine.append({"sourceId": f"NTRS-{record_id}", "kind": "literature",
                                   "injection": verdict["injection"],
                                   "secrets": verdict["secrets"]})
        for page in report.get("measurementPages") or []:
            excerpt = (page.get("excerpt") or "").strip()
            if not excerpt:
                continue
            terms = ", ".join(page.get("terms") or [])
            text = (
                f"{label} ({record_id}), page {page['page']} — {title}. "
                f"Measurement language on this page: {terms}. Quoted text: {excerpt}")
            verdict = screen(text)
            if not verdict["safe"]:
                quarantine.append({"sourceId": f"NTRS-{record_id}", "kind": "literature",
                                   "injection": verdict["injection"],
                                   "secrets": verdict["secrets"]})
                continue
            passages.append(Passage(
                id=f"literature::{record_id}::p{page['page']}",
                source_id=f"NTRS-{record_id}", kind="literature",
                title=f"{label} p.{page['page']} — {title}",
                text=text, url=f"{report.get('url')}#page={page['page']}", measured=True,
                local_ref=f"data/literature/ntrs_bpc.json#{record_id}:p{page['page']}",
                limitations=LITERATURE_LIMITS))
    return passages


@lru_cache(maxsize=1)
def corpus() -> dict:
    """Build the index once per process. Returns passages, idf and quarantine log."""
    quarantine: list = []
    passages = (_dataset_passages(quarantine) + _model_passages(quarantine)
                + _evaluation_passages(quarantine)
                + _methodology_passages(quarantine)
                + _literature_passages(quarantine)
                + _supplement_passages(quarantine))
    # Attach duplicate-safeguard context to dataset passages.
    for passage in passages:
        if passage.kind != "dataset":
            continue
        note = _duplicate_note(passage.source_id)
        if note:
            passage.text += (f" Duplicate safeguard: {passage.source_id} is classified "
                             f"{note['classification']} with respect to {note['other']}, "
                             f"sharing {note['sharedSamples']} samples. It must not be "
                             f"presented as independent evidence alongside that study.")
            passage.limitations.append(
                f"{note['classification']} relative to {note['other']}.")
    for passage in passages:
        passage.tokens = tokenize(passage.text + " " + passage.title)

    document_frequency: dict[str, int] = {}
    for passage in passages:
        for token in set(passage.tokens):
            document_frequency[token] = document_frequency.get(token, 0) + 1
    total = max(len(passages), 1)
    idf = {token: math.log(1 + (total - freq + 0.5) / (freq + 0.5))
           for token, freq in document_frequency.items()}
    average_length = sum(len(p.tokens) for p in passages) / total
    return {"passages": passages, "idf": idf, "averageLength": average_length,
            "quarantine": quarantine, "builtFrom": _count_by_kind(passages)}


# Words that belong to the corpus's own subject matter, so a match on them alone says
# nothing about whether the question is answerable. "Tell me about the space centre" must
# not be grounded by the word "space" appearing in a hundred passages.
GENERIC_TERMS = {
    "space", "center", "centre", "station", "nasa", "osdr", "iss", "agency",
    "data", "dataset", "datasets", "study", "studies", "record", "records",
    "model", "models", "result", "results", "analysis", "evidence", "project",
    "mission", "experiment", "experiments", "plant", "plants", "growth", "grow",
    "crop", "crops", "research", "source", "sources", "database", "sample", "samples",
}


def _grounded_matches(query: set[str], matched: set[str]) -> bool:
    """A match must include a term that is specific to the question, not just generic.

    Retrieval is allowed to be generous; grounding is not. If the question contains a
    specific term and only generic terms matched, the passage has not answered it.
    """
    specific = {token for token in query if token not in GENERIC_TERMS}
    if not specific:
        return True
    return bool({token for token in matched if token not in GENERIC_TERMS})


def search(question: str, limit: int = TOP_K) -> list[tuple[Passage, float]]:
    """BM25 over the corpus, with a light phrase bonus for accession codes."""
    index = corpus()
    query = tokenize(question)
    if not query:
        return []
    wanted_accessions = {m.group(0).upper() for m in
                         re.finditer(r"\bOSD[-\s]?\d+\b", question, re.I)}
    scored = []
    for passage in index["passages"]:
        counts = {}
        for token in passage.tokens:
            counts[token] = counts.get(token, 0) + 1
        score = 0.0
        matched = set()
        for token in dict.fromkeys(query):
            frequency = counts.get(token, 0)
            if not frequency:
                continue
            matched.add(token)
            weight = index["idf"].get(token, 0.0)
            denominator = frequency + BM25_K1 * (
                1 - BM25_B + BM25_B * len(passage.tokens) / index["averageLength"])
            score += weight * frequency * (BM25_K1 + 1) / denominator
        # Plain BM25 lets one rare word carry a passage: "future" appears twice in a
        # short passage and outranks every dataset record for a question about which
        # datasets exist. Scaling by the fraction of distinct query terms actually
        # matched, and requiring more than one match when the question has more than
        # one, makes a passage earn its rank by covering the question rather than by
        # containing a single unusual word.
        distinct = set(query)
        if score > 0:
            coverage = len(matched) / max(len(distinct), 1)
            if len(distinct) > 2 and len(matched) < 2:
                score = 0.0
            elif not _grounded_matches(distinct, matched):
                score = 0.0
            else:
                score *= coverage
        if wanted_accessions:
            if passage.accession in wanted_accessions:
                score += 6.0
            elif any(code in passage.text.upper() for code in wanted_accessions):
                score += 3.0
        if score > 0:
            scored.append((passage, score))
    scored.sort(key=lambda pair: -pair[1])
    return scored[:limit]


def passage_by_id(passage_id: str) -> Passage | None:
    for passage in corpus()["passages"]:
        if passage.id == passage_id:
            return passage
    return None


# Passage kinds that make up the corpus, in the order the UI should show them, mapped to
# the label the assistant reports. Every kind a passage can carry must appear here: the
# breakdown is published next to the total, so an unlisted kind makes the two disagree
# (classification passages were missing from it until this was made total by construction).
KIND_LABELS = {
    "dataset": "datasets",
    "evaluation": "findings",
    "model": "models",
    "methodology": "methodology",
    "classification": "classifications",
    "literature": "literature",
}


def _count_by_kind(passages) -> dict[str, int]:
    """Counts per passage kind, covering every kind present in `passages`.

    Derived from the passages themselves rather than from the builders, so the published
    breakdown always sums to the published total. A kind added later is counted
    automatically instead of silently vanishing from the breakdown.
    """
    counts: dict[str, int] = {}
    for passage in passages:
        counts[passage.kind] = counts.get(passage.kind, 0) + 1
    ordered = {label: counts[kind] for kind, label in KIND_LABELS.items() if counts.get(kind)}
    for kind, count in sorted(counts.items()):
        if kind not in KIND_LABELS:
            ordered[kind] = count
    return ordered


def stats() -> dict:
    index = corpus()
    return {
        "passages": len(index["passages"]),
        "byKind": index["builtFrom"],
        "quarantined": len(index["quarantine"]),
        "quarantine": index["quarantine"],
        "maxQuestionChars": MAX_QUESTION_CHARS,
        "retrieval": "BM25 over verified repository artifacts; no external service",
    }
