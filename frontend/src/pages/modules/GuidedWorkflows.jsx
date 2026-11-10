import { useCallback, useMemo, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Droplets,
  Play,
  Plus,
  ShieldCheck,
  Sprout,
  Trash2,
} from "lucide-react";
import { Card, number } from "../missionUI.jsx";
import { api } from "../../services/platformApi.ts";
import { Limitations, JsonDetails, useResource, RequestState } from "./moduleSupport.jsx";

/**
 * Two complete scientific workflows, operated end to end from the browser.
 *
 * Why this page exists
 * --------------------
 * The platform already had the pieces: a reference-ET0 implementation, a validated water-use
 * benchmark, a lettuce model with a calibrated interval, and a generic "run one model" endpoint.
 * What it did not have was a journey. A user who wanted to know how much water a crop needs had to
 * know which endpoint to call and which equations existed; a user who wanted a harvest estimate had
 * to know a model id and its exact feature schema.
 *
 * Each panel here does the whole job: labelled inputs with units, ranges and a reason for each
 * control, a real backend run, several scenarios compared side by side, the measured evidence laid
 * against the prediction, the uncertainty, and the limitations. Nothing is computed in the browser:
 * every number on the page came back from the API, and the raw response is one click away.
 *
 * What this page deliberately does not do
 * ---------------------------------------
 * It does not draw a passing verdict the science does not support. The harvest panel shows a model
 * whose independent holdout failed a pre-registered 30 % criterion, and the panel says so above the
 * result rather than in a footnote.
 */

const TABS = [
  { id: "water", label: "Water demand & irrigation", icon: Droplets },
  { id: "harvest", label: "Crop growth & harvest", icon: Sprout },
];

function Pill({ tone = "muted", children }) {
  return <span className={tone === "muted" ? "pill" : `pill pill-${tone}`}>{children}</span>;
}

function Field({ field, value, onChange, disabled }) {
  const id = `wf-${field.name}`;
  return (
    <label className="field workflow-field" htmlFor={id}>
      <span className="field-heading">
        <span>
          {field.label} <span className="muted">({field.unit})</span>
          {field.required === false ? <span className="muted"> · optional</span> : null}
        </span>
        <input
          id={id}
          name={field.name}
          aria-label={field.label}
          type="number"
          inputMode="decimal"
          min={field.min}
          max={field.max}
          step={field.step}
          value={value ?? ""}
          disabled={disabled}
          onChange={(event) => onChange(field.name, event.target.value)}
        />
      </span>
      <input
        type="range"
        aria-label={`${field.label} slider`}
        min={field.min}
        max={field.max}
        step={field.step}
        value={Number.isFinite(Number(value)) ? Number(value) : field.min}
        disabled={disabled}
        onChange={(event) => onChange(field.name, event.target.value)}
      />
      <small>
        {field.min}–{field.max} {field.unit}. {field.why}
      </small>
    </label>
  );
}

function ScenarioEditor({ scenarios, fields, onChange, onAdd, onRemove, disabled, max }) {
  return (
    <div className="scenario-editor">
      <div className="scenario-tabs" role="tablist" aria-label="Scenarios">
        {scenarios.map((scenario, index) => (
          <button
            key={scenario.key}
            type="button"
            role="tab"
            aria-selected={scenario.active}
            className={scenario.active ? "scenario-tab active" : "scenario-tab"}
            onClick={() => onChange({ activeIndex: index })}
          >
            {scenario.label || `Scenario ${index + 1}`}
            {scenarios.length > 1 ? (
              <span
                className="scenario-remove"
                role="button"
                tabIndex={0}
                aria-label={`Remove ${scenario.label || `scenario ${index + 1}`}`}
                onClick={(event) => {
                  event.stopPropagation();
                  onRemove(index);
                }}
                onKeyDown={(event) => {
                  if (event.key === "Enter" || event.key === " ") {
                    event.stopPropagation();
                    onRemove(index);
                  }
                }}
              >
                <Trash2 size={13} />
              </span>
            ) : null}
          </button>
        ))}
        {scenarios.length < max ? (
          <button type="button" className="scenario-tab add" onClick={onAdd} disabled={disabled}>
            <Plus size={14} /> Add scenario
          </button>
        ) : null}
      </div>

      {scenarios.map((scenario, index) =>
        scenario.active ? (
          <div className="control-grid workflow-inputs" key={scenario.key}>
            {fields.map((field) => (
              <Field
                key={field.name}
                field={field}
                disabled={disabled}
                value={scenario.values[field.name]}
                onChange={(name, value) => onChange({ index, values: { [name]: value } })}
              />
            ))}
          </div>
        ) : null,
      )}
    </div>
  );
}

/** Keep a long scenario name from running into the bar; the full name is in the table above. */
function truncate(text, limit) {
  const value = String(text || "");
  return value.length > limit ? `${value.slice(0, limit - 1)}…` : value;
}

/** A labelled horizontal bar with an interval whisker, drawn as SVG so no chart library ships. */
function IntervalBars({ rows, unit, label, lowKey, highKey, valueKey, ariaLabel }) {
  const width = 560;
  const rowHeight = 44;
  const padLeft = 150;
  // The value label is drawn to the right of each bar, so the right margin has to leave room for it
  // at the widest value; without this the last scenario's label is clipped by the viewBox.
  const padRight = 104;
  const height = Math.max(80, rows.length * rowHeight + 24);
  const values = rows.flatMap((row) => [row[lowKey] ?? row[valueKey], row[highKey] ?? row[valueKey]]);
  const max = Math.max(...values, 1) * 1.05;
  const span = width - padLeft - padRight;
  const scale = (value) => padLeft + (value / max) * span;

  return (
    <div className="workflow-bars-wrap">
    <svg className="workflow-bars" viewBox={`0 0 ${width} ${height}`} role="img" aria-label={ariaLabel}>
      {[0, 0.5, 1].map((fraction) => (
        <g key={fraction}>
          <line x1={padLeft} x2={width - padRight} y1={8 + fraction * (height - 32)}
                y2={8 + fraction * (height - 32)} stroke="#233139" strokeDasharray="3 5" />
          <text x={padLeft - 8} y={12 + fraction * (height - 32)} textAnchor="end"
                fill="#8b9fa7" fontSize="9">
            {number(max * (1 - fraction))}
          </text>
        </g>
      ))}
      {rows.map((row, index) => {
        const y = 18 + index * rowHeight;
        const value = row[valueKey];
        const low = row[lowKey];
        const high = row[highKey];
        return (
          <g key={row.label}>
            <text x={8} y={y + 12} fill="#becdd4" fontSize="11">
              {truncate(row.label, 20)}
            </text>
            <rect x={padLeft} y={y} width={Math.max(1, scale(value) - padLeft)} height={16}
                  rx={3} fill="#367eaf" opacity={0.85} />
            {low !== undefined && high !== undefined ? (
              <g stroke="#b0eed0" strokeWidth="1.5">
                <line x1={scale(low)} x2={scale(high)} y1={y + 8} y2={y + 8} />
                <line x1={scale(low)} x2={scale(low)} y1={y + 2} y2={y + 14} />
                <line x1={scale(high)} x2={scale(high)} y1={y + 2} y2={y + 14} />
              </g>
            ) : null}
            <text
              x={Math.min(scale(Math.max(value, high ?? value)) + 6, width - 4)}
              y={y + 12}
              textAnchor={scale(Math.max(value, high ?? value)) + 6 > width - 4 ? "end" : "start"}
              fill="#e6eef1"
              fontSize="10"
            >
              {number(value)} {unit}
            </text>
          </g>
        );
      })}
      <text x={padLeft} y={height - 4} fill="#809aa7" fontSize="9">{label}</text>
    </svg>
    </div>
  );
}

// A module-level constant so the dependency list stays a list of simple expressions.
const NO_EXTRA_KEYS = [];
const WATER_EXTRA_KEYS = ["crop"];

function useWorkflow(workflowId, fieldsFromCapability, extraKeys = NO_EXTRA_KEYS) {
  const [state, setState] = useState({ data: null, error: "", loading: false, at: null });

  const run = useCallback(
    async (scenarios) => {
      setState({ data: null, error: "", loading: true, at: null });
      try {
        const payload = await api(`/workflows/${workflowId}/run`, {
          scenarios: scenarios.map((scenario) => {
            const body = { label: scenario.label };
            extraKeys.forEach((key) => {
              if (scenario.values[key] !== undefined && scenario.values[key] !== "") {
                body[key] = scenario.values[key];
              }
            });
            fieldsFromCapability.forEach((field) => {
              const raw = scenario.values[field.name];
              if (raw === "" || raw === undefined || raw === null) {
                if (field.required === false) return;
              }
              body[field.name] = Number(raw);
            });
            return body;
          }),
        });
        setState({ data: payload, error: "", loading: false, at: new Date().toLocaleTimeString() });
      } catch (error) {
        setState({ data: null, error: error.message, loading: false, at: null });
      }
    },
    [workflowId, fieldsFromCapability, extraKeys],
  );

  return { ...state, run };
}

function defaultsFor(fields, preset) {
  const values = {};
  fields.forEach((field) => {
    if (preset[field.name] !== undefined) values[field.name] = preset[field.name];
    else if (field.required === false) values[field.name] = "";
    else values[field.name] = field.default ?? field.min;
  });
  return values;
}

/**
 * Scenario state for both workflows.
 *
 * The starting scenarios depend on the capability document, which arrives asynchronously. Holding
 * them in an effect that copies the payload into state would render twice on every load and, with
 * the project's React 19 lint rules, is a build error. Deriving the starting set from the capability
 * and only storing what the user actually changed keeps a single render path: state is `null` until
 * someone touches it.
 */
function useScenarioState(presets, fields, keyPrefix) {
  const [edited, setEdited] = useState(null);
  const [activeIndex, setActiveIndex] = useState(0);
  const starting = useMemo(
    () =>
      presets.map((preset, index) => ({
        key: `${keyPrefix}-${index}`,
        label: preset.label,
        values: { ...(preset.crop ? { crop: preset.crop } : {}), ...defaultsFor(fields, preset.values) },
      })),
    [presets, fields, keyPrefix],
  );
  const base = edited ?? starting;
  const scenarios = base.map((item, index) => ({ ...item, active: index === activeIndex }));

  const update = useCallback((patch) => {
    if (patch.activeIndex !== undefined) {
      setActiveIndex(patch.activeIndex);
      return;
    }
    setEdited((current) => {
      const source = current ?? starting;
      return source.map((item, index) =>
        index === patch.index ? { ...item, values: { ...item.values, ...patch.values } } : item,
      );
    });
  }, [starting]);

  const add = useCallback(() => {
    setEdited((current) => {
      const source = current ?? starting;
      const baseValues = source[activeIndex]?.values ?? {};
      setActiveIndex(source.length);
      return [
        ...source,
        { key: `${keyPrefix}-${Date.now()}`, label: `Scenario ${source.length + 1}`,
          values: { ...baseValues } },
      ];
    });
  }, [starting, activeIndex, keyPrefix]);

  const remove = useCallback((index) => {
    setEdited((current) => {
      const source = current ?? starting;
      return source.filter((_, i) => i !== index);
    });
    setActiveIndex(0);
  }, [starting]);

  return { scenarios, activeIndex, update, add, remove, ready: fields.length > 0 };
}

/* ------------------------------------------------------------------ water demand */

const WATER_PRESETS = [
  {
    label: "Dhaka, March",
    crop: "lettuce",
    values: {
      growingAreaM2: 10, daysAfterTransplant: 20, tmaxC: 33, tminC: 22,
      relativeHumidityPct: 55, solarRadiationMJm2: 20, windSpeedMs: 2,
      dayOfYear: 80, latitude: 23.8, elevationM: 8, plantsPerM2: 25,
    },
  },
  {
    label: "Hot dry spell",
    crop: "lettuce",
    values: {
      growingAreaM2: 10, daysAfterTransplant: 20, tmaxC: 38, tminC: 27,
      relativeHumidityPct: 35, solarRadiationMJm2: 26, windSpeedMs: 3.5,
      dayOfYear: 80, latitude: 23.8, elevationM: 8, plantsPerM2: 25,
    },
  },
];

export function WaterDemandWorkflow() {
  const capability = useResource("/workflows/water-demand/capability");
  const fields = useMemo(() => capability.data?.fields || [], [capability.data]);
  const runner = useWorkflow("water-demand", fields, WATER_EXTRA_KEYS);
  const { scenarios, activeIndex, update, add, remove } = useScenarioState(
    WATER_PRESETS, fields, "water");

  const result = runner.data;
  const rows = useMemo(() => result?.comparison?.rows || [], [result]);
  const chartRows = useMemo(
    () =>
      rows.map((row) => ({
        label: row.label,
        value: row.demandEt0ReferenceLPerDay,
        cropRelative: row.demandCropRelativeLPerDay,
      })),
    [rows],
  );
  const bench = result?.scenarios?.[0]?.measuredBench;

  return (
    <div className="workflow-panel" aria-label="Water demand workflow">
      <RequestState state={capability} />
      {capability.data ? (
        <Card
          title="1 · Choose the crop and the site"
          label="Input"
          action={<Pill tone="ok">{capability.data.crops.length} crops supported</Pill>}
        >
          <p className="fine">
            Every input below is used by the calculation, with one exception that the results state
            out loud: ambient temperature, humidity, radiation and wind move the ET0-reference
            column and leave the crop-relative column untouched, because that equation has no
            climate input at all.
          </p>
          <label className="field workflow-field" htmlFor="wf-crop">
            <span className="field-heading">
              <span>Crop</span>
              <select
                id="wf-crop"
                aria-label="Crop"
                value={scenarios[activeIndex]?.values.crop || "lettuce"}
                onChange={(event) => update({ index: activeIndex, values: { crop: event.target.value } })}
              >
                {capability.data.crops.map((crop) => (
                  <option key={crop.key} value={crop.key}>
                    {crop.name} · Kc {crop.kc}
                    {crop.hasMeasuredBench ? " · has measured water-use evidence" : ""}
                  </option>
                ))}
              </select>
            </span>
            <small>
              Lettuce is the only crop with measured water-use evidence in this repository. The
              others get a computed demand and an explicit statement that no measurement exists.
            </small>
          </label>

          <ScenarioEditor
            scenarios={scenarios}
            fields={fields}
            max={capability.data.maxScenarios}
            disabled={runner.loading}
            onChange={update}
            onAdd={add}
            onRemove={remove}
          />

          <div className="module-actions">
            <button
              type="button"
              className="primary-button"
              onClick={() => runner.run(scenarios)}
              disabled={runner.loading || !scenarios.length}
            >
              <Play size={15} /> {runner.loading ? "Running the calculation…" : "Run water demand"}
            </button>
            <span className="muted fine">
              Runs the real backend: FAO-56 reference ET0, both demand equations, and the measured
              benchmark.
            </span>
          </div>
          {runner.loading ? (
            <div className="skeleton" role="status">Running reference ET0 and crop demand…</div>
          ) : null}
          {runner.error ? (
            <div className="error-banner" role="alert">{runner.error}</div>
          ) : null}
        </Card>
      ) : null}

      {result ? (
        <>
          <Card
            title="2 · Results and scenario comparison"
            label="Output"
            action={<Pill tone="ok">computed {runner.at}</Pill>}
          >
            <div className="data-table-wrap">
              <table className="data-table">
                <caption className="sr-only">
                  Daily water demand per scenario in litres per day
                </caption>
                <thead>
                  <tr>
                    <th scope="col">Scenario</th>
                    <th scope="col">ET0 (mm/day)</th>
                    <th scope="col">Method</th>
                    <th scope="col">ET0-reference (L/day)</th>
                    <th scope="col">Crop-relative (L/day)</th>
                    <th scope="col">Remaining cycle (L)</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => (
                    <tr key={row.label}>
                      <th scope="row">{row.label}</th>
                      <td>{number(row.et0MmPerDay, 2)}</td>
                      <td>{row.et0PrimaryMethod}</td>
                      <td>{number(row.demandEt0ReferenceLPerDay, 2)}</td>
                      <td>{number(row.demandCropRelativeLPerDay, 2)}</td>
                      <td>{number(row.litresRemainingCycle, 1)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <IntervalBars
              rows={chartRows}
              unit="L/day"
              valueKey="value"
              label="ET0-reference demand, litres per day"
              ariaLabel="Daily water demand per scenario, ET0-reference equation, litres per day"
            />

            {result.comparison.deltas.length ? (
              <div className="data-table-wrap">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th scope="col">Comparison</th>
                      <th scope="col">Δ ET0 (mm/day)</th>
                      <th scope="col">Δ demand (L/day)</th>
                      <th scope="col">Δ demand (%)</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.comparison.deltas.map((delta) => (
                      <tr key={delta.label}>
                        <th scope="row">{delta.label} vs {delta.vs}</th>
                        <td>{number(delta.et0MmPerDayDelta, 2)}</td>
                        <td>{number(delta.demandLPerDayDelta, 2)}</td>
                        <td>{number(delta.demandPctDelta)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : null}
            <p className="fine">{result.comparison.note}</p>

            <div className="stat-pair">
              <div>
                <span className="muted">Both equations, first scenario</span>
                <strong>
                  {number(result.scenarios[0].demand.et0Reference.litresPerDay, 2)} L/day ET0-reference
                  · {number(result.scenarios[0].demand.cropRelative.litresPerDay, 2)} L/day
                  crop-relative
                </strong>
              </div>
              <div>
                <span className="muted">Ratio, crop-relative ÷ ET0-reference</span>
                <strong>
                  ×{number(result.scenarios[0].demand.agreement.cropRelativeOverEt0Reference)}
                  {result.scenarios[0].demand.agreement.arbitrated ? "" : " · unarbitrated"}
                </strong>
              </div>
            </div>
            <p className="fine">{result.scenarios[0].demand.climateSensitivity.note}</p>
          </Card>

          <Card title="3 · The measured evidence, beside the estimate" label="Evidence">
            {bench?.available && bench.applies ? (
              <>
                <div className="stat-pair">
                  <div>
                    <span className="muted">Measured, greenhouse lettuce (mL/pot/day)</span>
                    <strong>{number(bench.measuredMlPerPotPerDay)}</strong>
                  </div>
                  <div>
                    <span className="muted">As a flux on the pot-surface assumption (L/m2/day)</span>
                    <strong>{number(bench.measuredLPerM2PerDay)}</strong>
                  </div>
                  <div>
                    <span className="muted">This scenario, same denominator (L/m2/day)</span>
                    <strong>{number(bench.scenarioLPerM2PerDay)}</strong>
                  </div>
                  <div>
                    <span className="muted">Source hash verified</span>
                    <strong>{bench.hashVerified ? "yes" : "no"}</strong>
                  </div>
                </div>
                <p className="fine">{bench.comparisonCaveat}</p>
                <p className="fine">
                  {bench.study.citation} · DOI {bench.study.doi} · {bench.study.license} ·{" "}
                  {bench.measuredDates} measurement dates · {bench.study.measurementBasis}
                </p>
              </>
            ) : (
              <p className="fine">{bench?.reason || "No measured benchmark applies to this crop."}</p>
            )}

            <h3>Evidence layers</h3>
            <div className="data-table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th scope="col">Kind</th>
                    <th scope="col">What</th>
                    <th scope="col">Measured?</th>
                    <th scope="col">Provenance</th>
                  </tr>
                </thead>
                <tbody>
                  {result.evidence.layers.map((layer) => (
                    <tr key={layer.what}>
                      <th scope="row">{layer.kind}</th>
                      <td>{layer.what}</td>
                      <td>{layer.isMeasurement ? "yes" : "no"}</td>
                      <td className="fine">{layer.provenance}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="fine">{result.evidence.distinction}</p>
            <Limitations items={result.limitations} />
            <JsonDetails data={result} />
          </Card>
        </>
      ) : null}
    </div>
  );
}

/* --------------------------------------------------------------- harvest prediction */

const HARVEST_PRESETS = [
  {
    label: "Plant factory, 16 h",
    values: {
      daysAfterTransplant: 21, airTemperature: 24, rootTemperature: 24, ppfd: 400,
      photoperiodHours: 16, plantDensityPerM2: 25,
    },
  },
  {
    label: "Shorter photoperiod, 12 h",
    values: {
      daysAfterTransplant: 21, airTemperature: 24, rootTemperature: 24, ppfd: 400,
      photoperiodHours: 12, plantDensityPerM2: 25,
    },
  },
];

export function HarvestWorkflow() {
  const capability = useResource("/workflows/harvest-prediction/capability");
  const parity = useResource("/workflows/harvest-prediction/parity");
  const fields = useMemo(() => capability.data?.fields || [], [capability.data]);
  const runner = useWorkflow("harvest-prediction", fields);
  const { scenarios, update, add, remove } = useScenarioState(
    HARVEST_PRESETS, fields, "harvest");

  const result = runner.data;
  const rows = useMemo(() => result?.comparison?.rows || [], [result]);

  return (
    <div className="workflow-panel" aria-label="Harvest prediction workflow">
      <RequestState state={capability} />
      {capability.data ? (
        <Card
          title="1 · Growth stage and environment"
          label="Input"
          action={<Pill tone="warn">model status: trained-exploratory</Pill>}
        >
          <p className="fine">
            The selected model is <strong>{capability.data.modelId}</strong>. It predicts fresh yield
            per square metre from the daily light integral and divides by the density you state. The
            daily light integral is derived from PPFD × photoperiod, so the two light controls act
            together — a 16 h plant factory and a 12 h greenhouse at the same PPFD are different
            inputs, which is exactly what the predecessor model could not represent.
          </p>

          <ScenarioEditor
            scenarios={scenarios}
            fields={fields}
            max={capability.data.maxScenarios}
            disabled={runner.loading}
            onChange={update}
            onAdd={add}
            onRemove={remove}
          />

          <div className="module-actions">
            <button
              type="button"
              className="primary-button"
              onClick={() => runner.run(scenarios)}
              disabled={runner.loading || !scenarios.length}
            >
              <Play size={15} /> {runner.loading ? "Running the model…" : "Run harvest prediction"}
            </button>
            <span className="muted fine">
              Runs the served artifact byte-for-byte, with its conformal interval and its domain checks.
            </span>
          </div>
          {runner.loading ? <div className="skeleton" role="status">Running the lettuce model…</div> : null}
          {runner.error ? <div className="error-banner" role="alert">{runner.error}</div> : null}
        </Card>
      ) : null}

      {result ? (
        <>
          <Card
            title="2 · Results"
            label="Output"
            action={
              result.modelValidatedForForecasting ? (
                <Pill tone="ok">holdout passed</Pill>
              ) : (
                <Pill tone="warn">holdout failed · not a forecast</Pill>
              )
            }
          >
            <p className="fine">{result.statusNote}</p>
            <div className="data-table-wrap">
              <table className="data-table">
                <caption className="sr-only">Predicted fresh shoot mass per plant by scenario</caption>
                <thead>
                  <tr>
                    <th scope="col">Scenario</th>
                    <th scope="col">DLI (mol/m2/day)</th>
                    <th scope="col">g/m2</th>
                    <th scope="col">g/plant</th>
                    <th scope="col">Interval (g/plant)</th>
                    <th scope="col">Previous model (g/plant)</th>
                    <th scope="col">Warnings</th>
                  </tr>
                </thead>
                <tbody>
                  {result.scenarios.map((scenario) => (
                    <tr key={scenario.label}>
                      <th scope="row">{scenario.label}</th>
                      <td>{number(scenario.prediction.dailyLightIntegralMolPerM2Day)}</td>
                      <td>{number(scenario.prediction.perAreaYieldGPerM2, 0)}</td>
                      <td>{number(scenario.prediction.freshShootMassGPerPlant, 2)}</td>
                      <td>
                        {number(scenario.prediction.intervalLowG, 1)} – {number(scenario.prediction.intervalHighG, 1)}
                      </td>
                      <td>{number(scenario.recordPrediction.freshShootMassGPerPlant, 1)}</td>
                      <td>
                        {scenario.validation.warnings.length ? (
                          <span className="pill pill-warn">{scenario.validation.warnings.length}</span>
                        ) : (
                          <span className="pill pill-ok">in domain</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <IntervalBars
              rows={rows.map((row) => ({
                label: row.label,
                value: row.predictionG,
                low: row.intervalLowG,
                high: row.intervalHighG,
              }))}
              unit="g/plant"
              valueKey="value"
              lowKey="low"
              highKey="high"
              label="Fresh shoot mass per plant with its 90 % conformal interval"
              ariaLabel="Predicted fresh shoot mass per plant by scenario with intervals"
            />

            {result.scenarios.map((scenario) =>
              scenario.validation.warnings.length ? (
                <div className="workflow-warning" role="status" key={`warn-${scenario.label}`}>
                  <AlertTriangle size={15} />
                  <div>
                    <strong>{scenario.label}</strong>
                    <ul>
                      {scenario.validation.warnings.map((warning) => (
                        <li key={warning}>{warning}</li>
                      ))}
                    </ul>
                  </div>
                </div>
              ) : null,
            )}

            {result.comparison.deltas.length ? (
              <div className="data-table-wrap">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th scope="col">Comparison</th>
                      <th scope="col">Δ (g/plant)</th>
                      <th scope="col">Δ (%)</th>
                      <th scope="col">Intervals overlap</th>
                      <th scope="col">Reading</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.comparison.deltas.map((delta) => (
                      <tr key={delta.label}>
                        <th scope="row">{delta.label} vs {delta.vs}</th>
                        <td>{number(delta.predictionDeltaG, 2)}</td>
                        <td>{number(delta.predictionPctDelta)}</td>
                        <td>{delta.intervalsOverlap ? "yes" : "no"}</td>
                        <td className="fine">{delta.note}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : null}
          </Card>

          <Card title="3 · How well this model actually does" label="Validation">
            <div className="stat-pair">
              <div>
                <span className="muted">Internal, leave-one-experiment-out</span>
                <strong>MAE {number(result.validation.internalMetrics?.MAE)} g/m2</strong>
              </div>
              <div>
                <span className="muted">Independent holdout, Touliatos 2016</span>
                <strong>
                  {number(result.validation.independentCheck?.metrics?.MAPE)} % MAPE vs{" "}
                  {result.validation.independentCheck?.acceptanceCriterionPct} % criterion
                </strong>
              </div>
              <div>
                <span className="muted">Verdict fixed in advance</span>
                <strong>{result.validation.independentCheck?.passed ? "passed" : "failed"}</strong>
              </div>
            </div>
            <p className="fine">{result.validation.independentCheck?.verdict}</p>
            <p className="fine">{result.validation.developmentCheck?.why}</p>

            {parity.data ? (
              <div className="data-table-wrap">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th scope="col">Observation</th>
                      <th scope="col">Set</th>
                      <th scope="col">Measured (g)</th>
                      <th scope="col">Predicted (g)</th>
                      <th scope="col">Ratio</th>
                    </tr>
                  </thead>
                  <tbody>
                    {parity.data.points.map((point) => (
                      <tr key={point.id}>
                        <th scope="row">{point.id}</th>
                        <td>
                          {point.set === "independent" ? (
                            <span className="pill pill-warn">independent · counted</span>
                          ) : (
                            <span className="pill">development · not counted</span>
                          )}
                        </td>
                        <td>{number(point.measuredG)}</td>
                        <td>{number(point.predictedG)}</td>
                        <td>{number(point.ratio, 2)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <RequestState state={parity} />
            )}
            <p className="fine">{parity.data?.caveat}</p>

            <div className="data-table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th scope="col">Evidence layer</th>
                    <th scope="col">What</th>
                    <th scope="col">Measured?</th>
                    <th scope="col">Provenance</th>
                  </tr>
                </thead>
                <tbody>
                  {result.evidence.layers.map((layer) => (
                    <tr key={layer.what}>
                      <th scope="row">{layer.kind}</th>
                      <td>{layer.what}</td>
                      <td>{layer.isMeasurement ? "yes" : "no"}</td>
                      <td className="fine">{layer.provenance}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="fine">
              Controls the model does not use: {result.method.notUsed.join(", ")}.{" "}
              {result.method.notUsedNote}
            </p>
            <Limitations items={result.limitations} />
            <JsonDetails data={result} />
          </Card>
        </>
      ) : null}
    </div>
  );
}

/* ------------------------------------------------------------------------- page */

export function GuidedWorkflows() {
  const [tab, setTab] = useState("water");
  return (
    <div className="module-stack">
      <Card
        title="Guided scientific workflows"
        label="END-TO-END SCIENCE"
        action={
          <div className="badge-row">
            <Pill tone="ok"><CheckCircle2 size={12} /> 2 complete</Pill>
            <Pill tone="warn"><ShieldCheck size={12} /> 1 documented gap</Pill>
          </div>
        }
      >
        <p className="fine">
          Two workflows a user can complete without touching the API: enter parameters, run the real
          calculation, compare scenarios, and read the measured evidence, the uncertainty and the
          limitations. A third candidate — environmental stress — is not offered, because no
          validated response surface for spectrum, CO₂ or irradiance stress exists in this
          repository. Shipping a slider that moves a warning string is not a workflow.
        </p>
        <div className="scenario-tabs workflow-tabs" role="tablist" aria-label="Workflow">
          {TABS.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              type="button"
              role="tab"
              aria-selected={tab === id}
              className={tab === id ? "scenario-tab active" : "scenario-tab"}
              onClick={() => setTab(id)}
            >
              <Icon size={14} /> {label}
            </button>
          ))}
        </div>
      </Card>

      {tab === "water" ? <WaterDemandWorkflow /> : <HarvestWorkflow />}
    </div>
  );
}
