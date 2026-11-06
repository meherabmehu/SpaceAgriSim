import { Card, number } from "../missionUI.jsx";
import { api } from "../../services/platformApi.ts";
import {
  useResource,
  RequestState,
  Limitations,
  JsonDetails,
} from "./moduleSupport.jsx";
import { useState } from "react";
import EarthLettucePrediction from './EarthLettucePrediction.jsx';
import {
  ArrowRight,
  Database,
  ExternalLink,
  Search,
  Sprout,
} from "lucide-react";
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
export function Predictions({ models, registryError }) {
  const [inputs, setInputs] = useState({
    crop: "mizuna",
    waterSuppliedL: 1.5,
    establishedPlants: 2,
    environment: "flight",
    spectrum: "red",
  });
  const [prediction, setPrediction] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const predict = async () => {
    setBusy(true);
    setError("");
    setPrediction(null);
    try {
      setPrediction(await api("/predict/mizuna-harvest-v1", inputs));
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };
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
      <div className="module-grid">
        {models?.models?.map((model) => (
          <Card
            key={model.id}
            title={model.name || model.id}
            label={model.task || "EXPERIMENTAL MODEL"}
            action={
              <span className="pill green">
                {model.artifactExists ? "Artifact saved" : model.status}
              </span>
            }
          >
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
                Baseline MAE: {number(model.baselineMetrics.MAE, 3)} ?{" "}
                {model.samples} samples ? {model.groups} groups
              </p>
            )}
            <p className="muted fine">{model.validation}</p>
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
        (m) => m.id === "mizuna-harvest-v1" && m.artifactExists,
      ) && (
        <Card
          title="Mizuna harvest experiment"
          label="OSD-655 · EXPLORATORY REGRESSION"
        >
          <p className="prose">
            Predict fresh harvest mass per plant pillow using the measured
            VEG-04A experimental domain. This model cannot recommend irrigation
            or infer causality.
          </p>
          <div className="control-grid">
            <label className="field">
              Total water supplied (L)
              <input
                type="number"
                min="0"
                max="20"
                step="0.1"
                value={inputs.waterSuppliedL}
                onChange={(e) =>
                  setInputs({
                    ...inputs,
                    waterSuppliedL: Number(e.target.value),
                  })
                }
              />
            </label>
            <label className="field">
              Established plants
              <input
                type="number"
                min="1"
                max="6"
                step="1"
                value={inputs.establishedPlants}
                onChange={(e) =>
                  setInputs({
                    ...inputs,
                    establishedPlants: Number(e.target.value),
                  })
                }
              />
            </label>
            <label className="field">
              Experimental environment
              <select
                value={inputs.environment}
                onChange={(e) =>
                  setInputs({ ...inputs, environment: e.target.value })
                }
              >
                <option value="flight">Flight</option>
                <option value="ground">Ground</option>
              </select>
            </label>
            <label className="field">
              Study lighting group
              <select
                value={inputs.spectrum}
                onChange={(e) =>
                  setInputs({ ...inputs, spectrum: e.target.value })
                }
              >
                <option value="red">Red group</option>
                <option value="blue">Blue group</option>
              </select>
            </label>
          </div>
          <div className="module-actions">
            <button
              className="primary-button"
              onClick={predict}
              disabled={busy}
            >
              {busy ? "Predicting…" : "Run saved model"}
              <ArrowRight size={14} />
            </button>
          </div>
          {error && (
            <div className="error-banner" role="alert">
              {error}
            </div>
          )}
          {prediction && (
            <>
              <div className="comparison-value">
                {number(prediction.prediction)} <small>{prediction.unit}</small>
              </div>
              <p className="muted fine">
                Empirical residual range: {number(prediction.interval?.low)}–
                {number(prediction.interval?.high)} g. Uncalibrated; not a
                confidence guarantee.
              </p>
              <Limitations items={prediction.warnings} />
              <JsonDetails data={prediction} />
            </>
          )}
        </Card>
      )}
      {models?.models?.some(
        (m) => m.id === "tomato-flight-response-v1" && m.artifactExists,
      ) && <MolecularPrediction />}
      {models?.models?.some(m=>m.id==='lettuce-earth-growth-v1'&&m.artifactExists)&&<EarthLettucePrediction/>}
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
        <p className="warning-box">
          Loaded {example.sample} from {example.sourceStudy}. This is a training
          specimen for checking inference, not independent validation.
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
