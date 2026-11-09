import { useState } from "react";
import { Card, number } from "../missionUI.jsx";
import { api } from "../../services/platformApi.ts";
import { useResource, RequestState, JsonDetails } from "./moduleSupport.jsx";
import { Layers3, ShieldAlert, ShieldCheck } from "lucide-react";

// The category name and service statement are taken from the API rather than restated
// here, so the panel cannot drift from app/science_classification.py.
function sourceLabel(model) {
  const sourceType = model.sourceType || "";
  if (/^NASA/i.test(sourceType)) return "NASA OSDR training data";
  if (/not NASA/i.test(sourceType)) return "external data, not NASA";
  if (model.sourceStudy) return `source type not recorded (${model.sourceStudy})`;
  return "source type not recorded";
}

function isNasaDerived(model) {
  return /^NASA/i.test(model.sourceType || "");
}

export function ScientificStatusPanel() {
  const state = useResource("/workflow/models");
  const models = state.data?.models || [];
  const nasa = models.filter(isNasaDerived);
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
            {nasa.length} of {models.length} models were trained on NASA OSDR data. The
            rest record a different or unstated source and are labelled as such: not
            every served model is NASA-trained. No served model reports calibrated
            probabilities, so the measured interval coverage below is an evaluation
            result and not a promise about a future campaign.
          </p>
          <div className="badge-row">
            <span className="pill green">{nasa.length} NASA-trained</span>
            <span className="pill">{models.length - nasa.length} other sources</span>
            <span className="pill amber">
              {models.filter((model) => model.runStatus === "retired").length} retired
            </span>
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
                  <span>Feature explanations</span>
                  <strong>{model.explanationAvailable ? "available" : "not available"}</strong>
                </div>
                {model.retiredReason && (
                  <div className="warning-box">
                    <p>{model.retiredReason}</p>
                  </div>
                )}
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
