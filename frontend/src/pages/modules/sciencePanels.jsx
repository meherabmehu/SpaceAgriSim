import { useState } from "react";
import { Card, number } from "../missionUI.jsx";
import { api } from "../../services/platformApi.ts";
import { useResource, RequestState, JsonDetails } from "./moduleSupport.jsx";
import { Layers3, ShieldAlert, ShieldCheck } from "lucide-react";

// Provenance comes from the API as a structured record (`provenance.category`), not from a regex
// over free-text artifact metadata. Phase 31 replaced that regex: four of the previous ten entries
// had no `sourceType` at all and were reported as "source type not recorded", and the ET0 emulator
// was counted as NASA-derived although it had been fitted on a *derived* product.
function sourceLabel(model) {
  const provenance = model.provenance || {};
  if (provenance.label) return provenance.label;
  if (model.sourceStudy) return `source not recorded (${model.sourceStudy})`;
  return "source not recorded";
}

function isNasaDerived(model) {
  return (model.provenance || {}).category === "nasa-measured";
}

export function ScientificStatusPanel() {
  const state = useResource("/workflow/models");
  const models = state.data?.models || [];
  const nasa = models.filter(isNasaDerived);
  const external = models.filter(
    (model) => (model.provenance || {}).category === "external-measured",
  );
  const unrecorded = models.filter(
    (model) => !(model.provenance || {}).category,
  );
  // Phase 35: these counts are derived from the per-model verdict instead of asserted in prose.
  // The sentence below used to state, unconditionally, that no served model reports calibrated
  // probabilities - which stopped being a complete description once one model's calibration was
  // measured out of fold, and would have stopped being true outright if one were ever calibrated.
  const decisionGrade = models.filter((model) => model.decisionGrade);
  const failed = models.filter(
    (model) => (model.evidenceVerdict || {}).verdict === "fails-independent-check",
  );
  const unchecked = models.filter(
    (model) => (model.evidenceVerdict || {}).verdict === "no-independent-check",
  );
  const measuredCalibration = models.filter(
    (model) => (model.probabilityCalibration || {}).measured,
  );
  return (
    <Card
      title="Scientific status of every served model"
      label="CLASSIFICATION, CALIBRATION AND EXPLAINABILITY"
      action={<Layers3 size={18} className="accent" />}
    >
      <RequestState state={state} />
      {models.length > 0 && (
        <>
          <p className="prose">
            {nasa.length} of {models.length} served models were trained on measurements
            produced by NASA experiments and retrieved from a NASA repository;{" "}
            {external.length} were trained on non-NASA measured data. Each card names the
            study and the repository. {decisionGrade.length} of {models.length} is currently
            decision grade: {failed.length} failed an independent check, {unchecked.length}
            have never been scored by one, so the measured interval coverage shown here is an
            evaluation result and not a promise about a future campaign.
            {measuredCalibration.length > 0
              ? ` ${measuredCalibration.length} model${measuredCalibration.length === 1 ? "" : "s"} report a measured probability calibration; none reports its probabilities as calibrated.`
              : " No served model reports a measured probability calibration."}
            Models withdrawn in Phase 31 are not listed here: their artifacts and evaluations
            are kept as documented negative results.
          </p>
          <div className="badge-row">
            <span className="pill green">{nasa.length} NASA-measured</span>
            <span className="pill">{external.length} non-NASA measured</span>
            <span className="pill green">{decisionGrade.length} decision grade</span>
            <span className="pill amber">{failed.length} failed an independent check</span>
            {unrecorded.length > 0 && (
              <span className="pill amber">{unrecorded.length} source unrecorded</span>
            )}
          </div>
          <div className="module-grid">
            {models.map((model) => (
              <Card
                key={model.modelId}
                title={model.name || model.modelId}
                label={`CATEGORY ${model.category} · ${model.categoryName || "unclassified"}`}
                action={
                  <span
                    className={
                      model.runStatus === "runnable" ? "pill green" : "pill amber"
                    }
                  >
                    {model.runStatus === "runnable" ? (
                      <ShieldCheck size={12} />
                    ) : (
                      <ShieldAlert size={12} />
                    )}
                    {model.runStatus}
                  </span>
                }
              >
                <div className="stat-pair">
                  <span>Input family</span>
                  <strong>{model.inputFamily}</strong>
                </div>
                <div className="stat-pair">
                  <span>Features required</span>
                  <strong>{model.featureCount}</strong>
                </div>
                <div className="stat-pair">
                  <span>Training source</span>
                  <strong>{sourceLabel(model)}</strong>
                </div>
                <div className="stat-pair">
                  <span>Calibrated probabilities</span>
                  <strong>{model.calibration?.calibrated ? "yes" : "no"}</strong>
                </div>
                {model.calibration && (
                  <p className="muted fine">
                    Nominal coverage {number(model.calibration.nominalCoverage, 2)} ·
                    measured {number(model.calibration.measuredCoverage, 4)} on{" "}
                    {model.calibration.measuredOn}
                  </p>
                )}
                <div className="stat-pair">
                  <span>Evidence verdict</span>
                  <strong>
                    {(model.evidenceVerdict || {}).verdict || "unrecorded"}
                  </strong>
                </div>
                {(model.evidenceVerdict || {}).reason && (
                  <p className="muted fine" role="note">
                    {(model.evidenceVerdict || {}).summary}
                    {(model.evidenceVerdict || {}).verdict === "fails-independent-check"
                      ? ` Measured: ${model.evidenceVerdict.reason}.`
                      : ""}
                  </p>
                )}
                <div className="stat-pair">
                  <span>Feature explanations</span>
                  <strong>{model.explanationAvailable ? "available" : "not available"}</strong>
                </div>
                <p className="muted fine">{model.inputFamilyDescription}</p>
              </Card>
            ))}
          </div>
          <JsonDetails title="Complete classification per model" data={state.data} />
        </>
      )}
    </Card>
  );
}

export function IndependencePanel() {
  const state = useResource("/explorer/overlaps");
  const [selected, setSelected] = useState([]);
  const [checked, setChecked] = useState(null);
  const [error, setError] = useState("");

  const toggle = (id) =>
    setSelected((current) =>
      current.includes(id) ? current.filter((item) => item !== id) : [...current, id],
    );

  const check = async () => {
    setError("");
    try {
      setChecked(await api("/explorer/independent-set", { ids: selected }));
    } catch (err) {
      setError(err.message);
    }
  };

  const data = state.data;
  const offsets = data?.redundantDeposits || {};
  const flagged = (data?.relations || []).filter(
    (relation) => relation.relation !== "unverified-overlap",
  );

  return (
    <Card
      title="How many studies is that, really?"
      label="DUPLICATE AND SHARED-SAMPLE SAFEGUARDS"
      action={<ShieldCheck size={18} className="accent" />}
    >
      <RequestState state={state} />
      {data && (
        <>
          <p className="prose">
            {data.accessionCount} accessions are {data.independentStudyCount} independent
            studies. A second deposit of the same arrays is not a replication, and
            material shared between two accessions is not two samples of plants.
          </p>
          <div className="badge-row">
            <span className="pill">{data.accessionCount} accessions</span>
            <span className="pill green">
              {data.independentStudyCount} independent
            </span>
            <span className="pill amber">
              {data.relationCounts["duplicate-measurement"]} duplicate
            </span>
            <span className="pill amber">
              {data.relationCounts["shared-sample-different-assay"]} shared material
            </span>
            <span className="pill">
              {data.relationCounts["unverified-overlap"]} unverified pairs
            </span>
          </div>

          {Object.entries(offsets).map(([id, record]) => (
            <div className="deposit-note" key={id}>
              <p>
                <strong>{id}</strong> is a second deposit of {record.redundantWith}.{" "}
                {record.reason}
              </p>
            </div>
          ))}

          <h3 className="sub-heading">Relations that must not be counted twice</h3>
          {flagged.map((relation) => (
            <article
              className="insight-row"
              key={`${relation.pair[0]}-${relation.pair[1]}`}
            >
              <h3>
                {relation.pair[0]} × {relation.pair[1]} · {relation.relation}
              </h3>
              <p>{data.relationMeaning[relation.relation]}</p>
              <small>
                {relation.sharedSamples != null
                  ? `${relation.sharedSamples} shared sample identifiers`
                  : "no identifier audit for this pair"}
                {relation.localReference ? ` · ${relation.localReference}` : ""}
              </small>
            </article>
          ))}

          <h3 className="sub-heading">Check a study set before counting it</h3>
          <div className="badge-row">
            {(data.relations || [])
              .flatMap((relation) => relation.pair)
              .filter((id, index, all) => all.indexOf(id) === index)
              .slice(0, 12)
              .map((id) => (
                <button
                  key={id}
                  type="button"
                  className={selected.includes(id) ? "pill green" : "pill"}
                  onClick={() => toggle(id)}
                >
                  {id}
                </button>
              ))}
          </div>
          <div className="module-actions">
            <button className="secondary-button" onClick={check} disabled={!selected.length}>
              Check independence
            </button>
          </div>
          {error && <div className="error-banner">{error}</div>}
          {checked && (
            <>
              <div className="stat-pair">
                <span>Requested → independent</span>
                <strong>
                  {checked.requested} → {checked.independentCount}
                </strong>
              </div>
              {checked.dropped.map((row) => (
                <article className="insight-row" key={row.id}>
                  <h3>
                    {row.id} dropped · {row.relation}
                  </h3>
                  <p>{row.reason}</p>
                  <small>conflicts with {row.conflictsWith}</small>
                </article>
              ))}
              {checked.unverifiedIndependence?.length > 0 && (
                <p className="muted fine">
                  Kept, but independence is unverified against at least one other
                  accession in the set.
                </p>
              )}
            </>
          )}
          <JsonDetails title="Full relation table and class meanings" data={data} />
        </>
      )}
    </Card>
  );
}
