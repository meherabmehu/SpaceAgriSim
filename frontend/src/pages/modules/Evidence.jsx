import { Card, number } from "../missionUI.jsx";
import { api } from "../../services/platformApi.ts";
import { validationText } from "../../services/formatters.js";
import {
  useResource,
  RequestState,
  Limitations,
  JsonDetails,
} from "./moduleSupport.jsx";
import { useState } from "react";
import EarthLettucePrediction from './EarthLettucePrediction.jsx';
import { ScientificStatusPanel, IndependencePanel } from './sciencePanels.jsx';
import RadiationTranscriptomicPrediction from './RadiationTranscriptomicPrediction.jsx';
import {
  ArrowRight,
  Database,
  ExternalLink,
  Search,
  Sprout,
} from "lucide-react";
/**
 * What the Phase 36 and 37 acquisitions actually bought, served with the label that says what each
 * number is. The surface exists because the alternative is a report nobody opens: a reader of the running
 * product can see the measured ET result, the projected-climate response and the six gaps that did
 * not close, in the same place as the study registry.
 *
 * The panel deliberately leads with the number that did not move - no model became decision-grade -
 * rather than with the datasets acquired. Progress that is real but does not change a decision is
 * still worth reporting, but it must not look like a changed decision.
 */
function AcquisitionEvidence() {
  const state = useResource("/acquisition-evidence");
  const data = state.data;
  if (state.error) {
    return (
      <Card title="Acquisition evidence" label="PHASE 36–37 · MEASURED, DERIVED, PREDICTED">
        <p className="muted fine">Evidence surface unavailable: {state.error}</p>
      </Card>
    );
  }
  if (!data) {
    return (
      <Card title="Acquisition evidence" label="PHASE 36–37 · MEASURED, DERIVED, PREDICTED">
        <p className="muted fine">Loading acquisition evidence…</p>
      </Card>
    );
  }
  const gaps = data.gaps || {};
  const water = data.waterUse || {};
  const climate = data.projectedClimate || {};
  const models = data.models || {};
  const modelEvidence = data.modelEvidence || {};
  const spectrum = data.spectrumLight || {};
  return (
    <Card
      title="What the last acquisition changed, and what it did not"
      label="PHASE 36–37 · MEASURED, DERIVED, PREDICTED"
      action={<span className="pill">{gaps.total} documented gaps</span>}
    >
      <p className="prose">
        Seven independent datasets were acquired across these two phases and every
        byte checksummed. The point of this panel is the distinction the labels
        carry: a measured value came off an instrument, a derived value is
        arithmetic this repository performs on measurements, and a predicted value
        is a model output that is not an observation of anything.
      </p>
      <div className="data-table-wrap">
        <table>
          <thead>
            <tr>
              <th>GAP STATUS</th>
              <th>CLOSED BY DATA</th>
              <th>CLOSED BY DECISION</th>
              <th>PARTIALLY CLOSED</th>
              <th>OPEN</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>{gaps.total} recorded</td>
              <td>{gaps.closedByData}</td>
              <td>{gaps.closedByDecision}</td>
              <td>{gaps.partiallyClosed}</td>
              <td>{gaps.open}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <p className="muted fine">{gaps.note}</p>

      {spectrum.available && (
        <>
          <h3>Green light did not cost yield · {spectrum.design?.crop}</h3>
          <p className="prose">
            The simulator has always treated green photons as largely wasted. This is the first
            trial here that can test that, because every arm targeted the same{" "}
            {number(spectrum.design?.ppfdTargetUmolPerM2PerS, 0)} µmol m⁻² s⁻¹ and shared the same{" "}
            {spectrum.design?.photoperiod} photoperiod, so a difference cannot be a difference in
            photon supply.
          </p>
          <div className="data-table-wrap">
            <table>
              <thead>
                <tr>
                  <th>ARM</th>
                  <th>PLANTS</th>
                  <th>FRESH MASS (g)</th>
                  <th>SD</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(spectrum.freshWeightByArm || {}).map(([arm, row]) => (
                  <tr key={arm}>
                    <td>{arm}</td>
                    <td>{number(row.plants, 0)}</td>
                    <td>{number(row.meanGrams, 2)}</td>
                    <td>{number(row.sdGrams, 2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <ul className="limitation-list">
            {Object.entries(spectrum.contrasts || {}).map(([name, row]) => (
              <li key={name}>
                <strong>derived</strong> · {name.replace(/([A-Z])/g, " $1").toLowerCase()} ·{" "}
                {number(row.differenceGramsPerPlant, 2)} g per plant (permutation p ={" "}
                {number(row.permutationP, 4)}, {number(row.permutations, 0)} permutations; 95 %
                interval {number(row.bootstrap95?.[0], 2)} to {number(row.bootstrap95?.[1], 2)} g).
              </li>
            ))}
            {spectrum.excludedArm && (
              <li className="muted">
                <strong>unavailable</strong> · {spectrum.excludedArm.arm} is excluded:{" "}
                {spectrum.excludedArm.reason}
              </li>
            )}
          </ul>
          <p className="muted fine">{spectrum.whatThisShows}</p>
        </>
      )}

      {water.available && (
        <>
          <h3>Measured evapotranspiration, held against the model</h3>
          <ul className="limitation-list">
            <li>
              <strong>derived</strong> · FAO-56 on measured available energy against
              eddy-covariance latent heat: r = {number(water.formulation?.correlation, 4)} over{" "}
              {number(water.formulation?.siteDays, 0)} site-days, bias{" "}
              {number(water.formulation?.biasMmPerDay, 3)} mm/day.
            </li>
            <li>
              <strong>derived</strong> · measured ET ÷ modelled ET0 from six weighable
              lysimeters: median {number(water.level?.medianImpliedKcActiveDays, 3)} over{" "}
              {number(water.level?.activeDays, 0)} active days.
            </li>
            <li className="muted">{water.limitation}</li>
          </ul>
        </>
      )}

      {climate.available && (
        <>
          <h3>Projected environment · {climate.model}, {climate.scenario}</h3>
          <p className="muted fine">
            <strong>predicted</strong> · {climate.baselineWindow} against {climate.futureWindow} at{" "}
            {climate.gridResolution}. {climate.caveat}
          </p>
          <div className="data-table-wrap">
            <table>
              <thead>
                <tr>
                  <th>SITE</th>
                  <th>ΔT (°C)</th>
                  <th>ΔVPD (kPa)</th>
                  <th>ΔDLI (mol/m²/d)</th>
                  <th>Δ DAYS &gt;30 °C</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(climate.sites || {}).map(([site, delta]) => (
                  <tr key={site}>
                    <td>{site.replace(/_/g, " ")}</td>
                    <td>{number(delta.meanTasC, 2)}</td>
                    <td>{number(delta.meanVpdKpa, 2)}</td>
                    <td>{number(delta.meanDliMolM2D, 2)}</td>
                    <td>{number(delta.daysAbove30C, 0)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      {modelEvidence.available ? (
        <>
          <h3>Models re-audited against this phase · no retraining, no threshold moved</h3>
          <p className="prose">
            {number(modelEvidence.counts?.scoredOnNewEvidence, 0)} of{" "}
            {number(modelEvidence.counts?.served, 0)} served models could be scored on what this
            phase acquired: all {number(modelEvidence.counts?.notTestedByNewEvidence, 0)} fall
            outside their own declared input domain, so none could be tested without contradicting
            its own card. Decision-grade models: {number(modelEvidence.counts?.decisionGradeBefore, 0)}{" "}
            before, {number(modelEvidence.counts?.decisionGradeAfter, 0)} after.
          </p>
          <ul className="limitation-list">
            {Object.entries(modelEvidence.classification || {}).map(([id, row]) => (
              <li key={id}>
                <strong>{row.verdict}</strong> · {id}
              </li>
            ))}
          </ul>
        </>
      ) : (
        models.available && (
          <>
            <h3>Models re-evaluated · no retraining, no threshold moved</h3>
            <p className="prose">
              {number(models.counts?.scored, 0)} of {number(models.counts?.served, 0)} served models
              could be scored on the new independent campaign:{" "}
              {number(models.counts?.domainRefused, 0)} fall outside their own declared domain and{" "}
              {number(models.counts?.noNewEvidence, 0)} have no new evidence bearing on them.
              Decision-grade models: {number(models.counts?.decisionGradeBefore, 0)} before,{" "}
              {number(models.counts?.decisionGradeAfter, 0)} after.
            </p>
            <p className="muted fine">{models.note}</p>
          </>
        )
      )}
      <JsonDetails title="Every gap, its evidence and its remaining work" data={data} />
    </Card>
  );
}

export function Datasets({ registry, registryError }) {
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState(null);
  const rows = (registry?.datasets || []).filter((row) =>
    JSON.stringify(row).toLowerCase().includes(search.toLowerCase()),
  );
  return (
    <>
      <div className="module-intro">
        <span className="pill">
          <Database size={12} />
          OFFICIAL NASA OSDR REGISTRY
        </span>
        <p>
          Browse verified study metadata. A registered study is not
          automatically a downloaded training table. Molecular assays, images,
          and physiological labels remain separate.
        </p>
      </div>
      {registryError && (
        <div className="error-banner">
          Registry unavailable: {registryError}
        </div>
      )}
      <IndependencePanel />
      <AcquisitionEvidence />
      <Card
        title="Study catalog"
        label="VERIFIED SOURCE RECORDS"
        action={
          <span className="pill">
            {registry?.datasets?.length ?? "—"} studies
          </span>
        }
      >
        <div className="search-row">
          <Search size={16} className="muted" />
          <input
            type="search"
            aria-label="Search NASA datasets"
            placeholder="Search study ID, organism, or assay…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <div className="data-table-wrap">
          <table>
            <thead>
              <tr>
                <th>STUDY / TITLE</th>
                <th>ORGANISM</th>
                <th>SAMPLES</th>
                <th>STATUS</th>
                <th>INSPECT</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id}>
                  <td>
                    <a href={row.sourceUrl} target="_blank" rel="noreferrer">
                      {row.id}{" "}
                      <ExternalLink size={10} style={{ display: "inline" }} />
                    </a>
                    <span className="dataset-title">{row.title}</span>
                  </td>
                  <td>
                    {Array.isArray(row.organisms)
                      ? row.organisms.join(", ")
                      : row.organisms || "See metadata"}
                  </td>
                  <td>{row.sampleCount ?? "Not reported"}</td>
                  <td>{row.status || "Metadata verified"}</td>
                  <td>
                    <button
                      className="secondary-button"
                      onClick={() => setSelected(row.id)}
                    >
                      Details
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {!rows.length && (
          <p className="empty-state">
            {registry ? "No matching studies." : "Loading NASA registry…"}
          </p>
        )}
      </Card>
      {selected && <DatasetDetail id={selected} key={selected} />}
      <JsonDetails
        title="Dataset coverage and eligibility"
        data={registry?.coverage || registry}
      />
    </>
  );
}
function DatasetDetail({ id }) {
  const state = useResource(`/datasets/${id}`);
  const preview = useResource(`/datasets/${id}/preview`);
  const data = state.data;
  return (
    <Card
      title={`${id} · Provenance & processed data`}
      label="SOURCE INSPECTION"
    >
      <RequestState state={state} />
      {data && (
        <>
          <p className="prose">{data.title}</p>
          <JsonDetails
            title="Files, eligibility, licensing and limitations"
            data={data}
          />
        </>
      )}
      <RequestState state={preview} />
      {preview.data?.tables?.map((table, i) => (
        <div key={i}>
          <h3>
            {table.name} · {table.rowCount} rows
          </h3>
          <p className="muted fine">{table.note}</p>
          <div className="data-table-wrap">
            <table>
              <thead>
                <tr>
                  {table.columns.map((c) => (
                    <th key={c}>{c}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {table.rows.slice(0, 10).map((row, j) => (
                  <tr key={j}>
                    {table.columns.map((column, k) => (
                      <td key={column}>
                        {String(
                          Array.isArray(row) ? row[k] : (row[column] ?? "—"),
                        )}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ))}
      {preview.data?.tables?.length === 0 && (
        <p className="empty-state">
          No processed tabular preview is available for this study.
        </p>
      )}
    </Card>
  );
}
const VERDICT_BADGE = {
  "passes-independent-check": { label: "Independent check passed", tone: "green" },
  "fails-independent-check": { label: "Independent check failed", tone: "amber" },
  "no-independent-check": { label: "No independent check", tone: "amber" },
  unrecorded: { label: "Evidence unrecorded", tone: "amber" },
};

function EvidenceBadge({ verdict }) {
  // Phase 35: every served model carries a verdict derived from a committed measurement. The
  // badge is driven by that field, so a model that fails its independent check cannot be
  // presented here as if it had passed one.
  const badge = VERDICT_BADGE[verdict?.verdict] || VERDICT_BADGE.unrecorded;
  return (
    <span className={`pill ${badge.tone}`} title={verdict?.summary || ""}>
      {badge.label}
    </span>
  );
}

export function Predictions({ models, registryError }) {
  // Phase 31 removed the mizuna harvest form from this panel: its model was worse than
  // predicting the training mean (held-out R2 -0.333 vs -0.138) and was withdrawn from the
  // API, the registry and the workflow catalogue. What remains here runs only served models.
  return (
    <>
      <div className="module-intro">
        <span className="pill">ARTIFACT-BACKED MODEL REGISTRY</span>
        <p>
          Only models with a saved, verified artifact can be run. NASA-trained
          exploratory models have narrower scope than the habitat simulator and
          do not validate its lettuce, tomato, or radish forecasts.
        </p>
      </div>
      {registryError && (
        <div className="error-banner">
          Model registry unavailable: {registryError}
        </div>
      )}
      <ScientificStatusPanel />
      <div className="module-grid">
        {models?.models?.map((model) => (
          <Card
            key={model.id}
            title={model.name || model.id}
            label={model.task || "EXPERIMENTAL MODEL"}
            action={
              <span className="badge-row">
                <span className="pill">
                  {model.artifactExists ? "Artifact verified" : model.status}
                </span>
                <EvidenceBadge verdict={model.evidenceVerdict} />
              </span>
            }
          >
            {model.evidenceVerdict?.summary && (
              <p className="muted fine" role="note">
                {model.evidenceVerdict.summary}
                {model.evidenceVerdict.verdict === "fails-independent-check" &&
                model.evidenceVerdict.reason
                  ? ` Measured: ${model.evidenceVerdict.reason}.`
                  : ""}
              </p>
            )}
            <div className="stat-pair">
              <span>Version</span>
              <strong>{model.version}</strong>
            </div>
            <div className="stat-pair">
              <span>Target</span>
              <strong>
                {typeof model.target === "object"
                  ? JSON.stringify(model.target)
                  : model.target}
              </strong>
            </div>
            <div className="badge-row">
              {Object.entries(model.metrics || {}).map(([key, value]) => (
                <span className="pill" key={key}>
                  {key}: {number(value, 3)}
                </span>
              ))}
            </div>
            {model.baselineMetrics && (
              <p className="muted fine">
                Baseline MAE: {number(model.baselineMetrics.MAE, 3)} ·{" "}
                {model.samples} samples · {model.groups} groups
              </p>
            )}
            <p className="muted fine">{validationText(model)}</p>
            <JsonDetails
              title="Validation metrics and input schema"
              data={{
                metrics: model.metrics,
                features: model.features,
                training: model.training,
                source: model.sourceStudy,
              }}
            />
            <Limitations items={model.limitations} />
          </Card>
        ))}
      </div>
      {!models && !registryError && (
        <div className="empty-state">Loading model registry…</div>
      )}
      {models?.models?.some(
        (m) => m.id === "tomato-flight-response-v1" && m.artifactExists,
      ) && <MolecularPrediction />}
      {models?.models?.some(m=>m.id==='lettuce-earth-growth-v1'&&m.artifactExists)&&<EarthLettucePrediction/>}
      {models?.models?.some(m=>m.id==='radiation-quality-osd46-v1'&&m.artifactExists)&&<RadiationTranscriptomicPrediction/>}
    </>
  );
}
function MolecularPrediction() {
  const [expression, setExpression] = useState("");
  const [example, setExample] = useState(null);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const load = async () => {
    setBusy(true);
    setError("");
    try {
      const data = await api("/models/tomato-flight-response-v1/example");
      setExpression(JSON.stringify(data.expression, null, 2));
      setExample(data);
      setResult(null);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };
  const predict = async () => {
    setBusy(true);
    setError("");
    setResult(null);
    try {
      const parsed = JSON.parse(expression);
      setResult(
        await api("/predict/tomato-flight-response-v1", { expression: parsed }),
      );
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <Card
      title="Tomato molecular response"
      label="OSD-767 · FLIGHT-CONTEXT CLASSIFICATION"
    >
      <p className="prose">
        Provide the exact gene features as normalized log1p(CPM). This
        classifier distinguishes experimental flight/ground context. It does not
        predict plant health, stress severity, harvest yield, or causal
        spaceflight effects.
      </p>
      <div className="module-actions">
        <button className="secondary-button" onClick={load} disabled={busy}>
          Load measured training example
        </button>
      </div>
      {example && (
        <p className="muted">
          Loaded {example.sample} from {example.sourceStudy}. This is a training specimen for
          checking inference, not independent validation.
        </p>
      )}
      <label className="field">
        Normalized gene expression JSON
        <textarea
          className="expression-input"
          aria-label="Normalized gene expression JSON"
          rows="8"
          value={expression}
          onChange={(e) => {
            setExpression(e.target.value);
            setExample(null);
            setResult(null);
          }}
          placeholder='{"gene-ID": 1.2, ...}'
        />
      </label>
      <div className="module-actions">
        <button
          className="primary-button"
          disabled={busy || !expression}
          onClick={predict}
        >
          {busy ? "Computing…" : "Classify molecular context"}
        </button>
      </div>
      {error && (
        <div className="error-banner" role="alert">
          {error}
        </div>
      )}
      {result && (
        <>
          <div className="comparison-value">
            {result.prediction}
            <small> experimental context</small>
          </div>
          <p className="muted fine">
            Uncalibrated flight probability:{" "}
            {number(result.probabilityFlight, 3)}. Flight and batch effects may
            be confounded.
          </p>
          <Limitations items={result.warnings} />
        </>
      )}
    </Card>
  );
}
export function Crops({
  config,
  result,
  params,
  setParam,
  navigate,
  registry,
}) {
  return (
    <>
      <div className="module-intro">
        <span className="pill">CROP PROFILES · EXPLICIT ASSUMPTIONS</span>
        <p>
          Baseline growth cycles, harvest mass, and water demand come from the
          existing mathematical crop profiles. NASA study associations provide
          research context, not parameter calibration.
        </p>
      </div>
      <div className="module-grid three">
        {config.crops.map((crop) => (
          <Card
            key={crop.key}
            title={crop.name}
            label="CONTROLLED HABITAT PROFILE"
          >
            <div className="crop-icon">
              <Sprout size={31} />
            </div>
            <div className="stat-pair">
              <span>Assumed cycle</span>
              <strong>{crop.growthDurationDays} days</strong>
            </div>
            <div className="stat-pair">
              <span>Reference harvest</span>
              <strong>{number(crop.harvestBiomassG)} g/m²/cycle</strong>
            </div>
            <p className="prose">
              {crop.key === "lettuce"
                ? "Leafy edible biomass; rapid canopy development in the assumed cycle."
                : crop.key === "tomato"
                  ? "Fruit-bearing crop; fixed cycles simplify continuous fruit production."
                  : "Root crop; fresh edible root mass is represented using an assumed harvest index."}
            </p>
            {params.crop === crop.key && result && (
              <div className="stat-pair">
                <span>Current scenario biomass</span>
                <strong>{number(result.cropYield)} g</strong>
              </div>
            )}
            <button
              className="wide-link"
              onClick={() => {
                setParam("crop", crop.key);
                navigate("laboratory");
              }}
            >
              Simulate {crop.name.toLowerCase()}
              <ArrowRight size={14} />
            </button>
            <JsonDetails
              title="Full profile and physiology assumptions"
              data={crop}
            />
          </Card>
        ))}
      </div>
      <Card title="Research associations" label="LIVE STUDY REGISTRY">
        <p className="prose">
          Inspect official organisms and study titles before selecting evidence.
          Radish and tomato crop parameters are not validated simply because a
          related NASA study exists.
        </p>
        {(registry?.datasets || [])
          .filter((row) => /lettuce|radish|tomato/i.test(row.title || ""))
          .map((row) => (
            <div className="stat-pair" key={row.id}>
              <a href={row.sourceUrl} target="_blank" rel="noreferrer">
                {row.id}
              </a>
              <span>{row.title}</span>
            </div>
          ))}
      </Card>
    </>
  );
}
