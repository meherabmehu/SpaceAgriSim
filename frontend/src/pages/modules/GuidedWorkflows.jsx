import { useCallback, useMemo, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Droplets,
  FlaskConical,
  Leaf,
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
 * Two complete scientific workflows plus two measured panels, operated from the browser.
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
  { id: "harvest", label: "Harvest evidence (removed)", icon: Sprout },
  { id: "light", label: "Light quality & stress", icon: FlaskConical },
  { id: "cea", label: "Controlled environment (wheat)", icon: Leaf },
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

/* ------------------------------------------------------- harvest: the removed capability */

/**
 * This tab used to run a lettuce harvest forecast. Phase 30 evaluated that model the only way that
 * counts - leave-one-study-out over published studies it had never seen - and it missed the 30 %
 * criterion by more than a factor of ten, with the mean baseline selected out of fold. The forecast
 * was removed rather than kept behind a warning, so this panel has no run control at all: it shows
 * the decision, every evaluation that failed, and the measured-versus-predicted record that
 * survives, because a failed model is still evidence about the data.
 */
export function HarvestWorkflow() {
  const capability = useResource("/workflows/harvest-prediction/capability");
  const parity = useResource("/workflows/harvest-prediction/parity");

  const evaluation = capability.data?.evaluations || [];
  const points = parity.data?.points || [];

  return (
    <div className="workflow-panel" aria-label="Harvest evidence panel">
      <RequestState state={capability} />
      {capability.data ? (
        <>
          <Card
            title="1 · What this workflow was, and why it is gone"
            label="DECISION"
            action={<Pill tone="warn">removed in Phase 30 · no forecast is served</Pill>}
          >
            <p className="fine">
              The harvest forecast did not meet the project&apos;s independent-error criterion and has
              been withdrawn, not hidden behind a warning. Nothing on this page predicts a harvest
              mass: there is no run button, and the endpoint that used to produce one answers with a
              formal removal notice instead of a number.
            </p>
            <dl className="kv-list">
              <div>
                <dt>Criterion</dt>
                <dd>{number(capability.data.acceptanceCriterionPct, 0)} % MAPE on independent data, unchanged</dd>
              </div>
              <div>
                <dt>Operational forecast</dt>
                <dd>{capability.data.operationalForecast ? "yes" : "no"}</dd>
              </div>
              <div>
                <dt>Reason</dt>
                <dd>{capability.data.reason}</dd>
              </div>
            </dl>
          </Card>

          <Card
            title="2 · Every evaluation, including the ones that failed"
            label="VALIDATION RECORD"
            action={<Pill tone={evaluation.some((item) => item.passed) ? "warn" : "ok"}>
              {evaluation.filter((item) => item.countsAsValidation).length} independent · none passed
            </Pill>}
          >
            <div className="data-table-wrap">
              <table className="data-table">
                <caption className="sr-only">Independent and development evaluations of the withdrawn model</caption>
                <thead>
                  <tr>
                    <th scope="col">Evaluation</th>
                    <th scope="col">Protocol</th>
                    <th scope="col">n</th>
                    <th scope="col">MAPE</th>
                    <th scope="col">Counts as validation</th>
                    <th scope="col">Passed</th>
                  </tr>
                </thead>
                <tbody>
                  {evaluation.map((item) => (
                    <tr key={item.id}>
                      <th scope="row">{item.id}</th>
                      <td>{item.protocol}</td>
                      <td>{item.metrics.n ?? "—"}</td>
                      <td>{item.metrics.MAPE === null || item.metrics.MAPE === undefined
                        ? "—" : `${number(item.metrics.MAPE, 1)} %`}</td>
                      <td>{item.countsAsValidation ? "yes" : "no — development only"}</td>
                      <td>
                        {item.passed === null || item.passed === undefined
                          ? <span className="pill">not scored</span>
                          : item.passed
                            ? <span className="pill pill-ok">passed</span>
                            : <span className="pill pill-warn">failed</span>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="fine">
              A development figure is not a validation figure. The rows marked &quot;not scored&quot;
              informed model selection, so they cannot be quoted as evidence that the model works.
            </p>
            <Limitations items={capability.data.limitations || []} />
            <JsonDetails data={capability.data} />
          </Card>

          <Card
            title="3 · Measured versus what the model said"
            label="PARITY"
            action={<Pill tone="warn">{points.length} measured points</Pill>}
          >
            <RequestState state={parity} />
            {points.length ? (
              <>
                <div className="data-table-wrap">
                  <table className="data-table">
                    <caption className="sr-only">Measured harvest mass against the withdrawn model&apos;s output</caption>
                    <thead>
                      <tr>
                        <th scope="col">Observation</th>
                        <th scope="col">Set</th>
                        <th scope="col">Measured (g/plant)</th>
                        <th scope="col">Model said (g/plant)</th>
                        <th scope="col">Ratio</th>
                      </tr>
                    </thead>
                    <tbody>
                      {points.map((point) => (
                        <tr key={point.id}>
                          <th scope="row">{point.id}</th>
                          <td>
                            {point.set}
                            {point.countsAsValidation ? null : <span className="muted"> · development</span>}
                          </td>
                          <td>{number(point.measuredG, 1)}</td>
                          <td>{number(point.predictedG, 1)}</td>
                          <td>{number(point.ratio, 2)}×</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <p className="fine">{parity.data.caveat}</p>
                <Limitations items={parity.data.limitations || []} />
                <JsonDetails data={parity.data} />
              </>
            ) : null}
          </Card>
        </>
      ) : null}
    </div>
  );
}

/* ------------------------------------- controlled-environment wheat: measured, no model */

/**
 * The Phase 30 acquisition that answered half of the light/CO2/temperature gap: 39 chamber runs of
 * wheat with measured grain yield and a logged environment. A response surface was fitted to it and
 * failed its sealed holdout, so this panel reports measured group summaries - mean yield per band
 * with a between-experiment interval - and states that it is not a response function.
 */
export function CeaEvidenceWorkflow() {
  const capability = useResource("/workflows/light-stress/controlled-environment/capability");
  const [selection, setSelection] = useState({ factor: "co2Ppm", band: "ambient" });
  const [state, setState] = useState({ data: null, error: "", loading: false });

  const bands = capability.data?.fields?.[1]?.options || {};
  const factorOptions = capability.data?.fields?.[0]?.options || [];
  const bandOptions = bands[selection.factor] || [];

  const run = async () => {
    setState({ data: null, error: "", loading: true });
    try {
      const payload = await api("/workflows/light-stress/controlled-environment/run", {
        selections: [selection],
      });
      setState({ data: payload, error: "", loading: false });
    } catch (error) {
      setState({ data: null, error: error.message, loading: false });
    }
  };

  const result = state.data;

  return (
    <div className="workflow-panel" aria-label="Controlled-environment wheat evidence">
      <RequestState state={capability} />
      {capability.data ? (
        <>
          <Card
            title="1 · Pick an environmental factor and a band"
            label="MEASURED GROUP"
            action={<Pill tone="ok">measured · no prediction</Pill>}
          >
            <p className="fine">
              {capability.data.dataset.experiments} controlled-environment experiments of{" "}
              {capability.data.crop.name} cv. {capability.data.crop.cultivar},{" "}
              {capability.data.dataset.subplotRows} destructive harvest sub-plots, from{" "}
              <a href={capability.data.dataset.doi} rel="noreferrer noopener" target="_blank">
                {capability.data.dataset.doi}
              </a>{" "}
              ({capability.data.dataset.license}). You choose a real partition of the experiments; the
              panel reports what those runs measured.
            </p>
            <div className="field-row">
              <label className="field" htmlFor="cea-factor">
                <span className="field-heading">Factor</span>
                <select
                  id="cea-factor"
                  value={selection.factor}
                  onChange={(event) => {
                    const factor = event.target.value;
                    setSelection({ factor, band: bands[factor][0] });
                  }}
                >
                  {factorOptions.map((name) => <option key={name} value={name}>{name}</option>)}
                </select>
              </label>
              <label className="field" htmlFor="cea-band">
                <span className="field-heading">Band</span>
                <select
                  id="cea-band"
                  value={selection.band}
                  onChange={(event) => setSelection({ ...selection, band: event.target.value })}
                >
                  {bandOptions.map((name) => <option key={name} value={name}>{name}</option>)}
                </select>
              </label>
            </div>
            <div className="module-actions">
              <button type="button" className="primary-button" onClick={run} disabled={state.loading}>
                <Play size={15} /> {state.loading ? "Reading the measured table…" : "Show measured results"}
              </button>
              <span className="muted fine">
                Anything outside the measured bands is not offered: this panel partitions experiments,
                it does not extrapolate.
              </span>
            </div>
            {state.error ? <div className="error-banner" role="alert">{state.error}</div> : null}
          </Card>

          <Card
            title="2 · What the model attempt found"
            label="ATTEMPTED SURFACE"
            action={<Pill tone="warn">not served</Pill>}
          >
            <p className="fine">{capability.data.predictiveModel.reason}</p>
            <dl className="kv-list">
              <div><dt>Criterion</dt><dd>{number(capability.data.predictiveModel.criterion, 0)} % MAPE</dd></div>
              <div><dt>Selected candidate</dt><dd>{capability.data.predictiveModel.selected}</dd></div>
              <div><dt>Holdout MAPE</dt><dd>{number(capability.data.predictiveModel.holdoutMapePct, 2)} %</dd></div>
              <div><dt>Holdout R²</dt><dd>{number(capability.data.predictiveModel.holdoutR2, 4)}</dd></div>
              <div><dt>Sealed experiments</dt><dd>{capability.data.predictiveModel.holdoutExperiments}</dd></div>
            </dl>
          </Card>

          {result ? (
            <Card
              title="3 · Measured results for that band"
              label="OUTPUT"
              action={<Pill tone="ok">measured observation</Pill>}
            >
              <div className="data-table-wrap">
                <table className="data-table">
                  <caption className="sr-only">Measured grain yield for the selected band</caption>
                  <thead>
                    <tr>
                      <th scope="col">Band</th>
                      <th scope="col">Experiments</th>
                      <th scope="col">Mean (kg/m2)</th>
                      <th scope="col">95 % interval on the mean</th>
                      <th scope="col">Median</th>
                      <th scope="col">Range</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.groups.map((group) => (
                      <tr key={`${group.factor}-${group.band}`}>
                        <th scope="row">{group.label}</th>
                        <td>{group.measured.n}</td>
                        <td>{number(group.measured.mean, 3)}</td>
                        <td>
                          {number(group.measured.meanCiLow, 3)} – {number(group.measured.meanCiHigh, 3)}
                        </td>
                        <td>{number(group.measured.median, 3)}</td>
                        <td>
                          {number(group.measured.min, 3)} – {number(group.measured.max, 3)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p className="fine">
                Daily light integral against measured yield across all experiments: Pearson{" "}
                {number(result.dliRelationship.pearson, 3)}, Spearman{" "}
                {number(result.dliRelationship.spearman, 3)}. {result.dliRelationship.note}
              </p>
              <p className="fine">{result.method.noTest}</p>
              <Limitations items={result.limitations} />
              <JsonDetails data={result} />
            </Card>
          ) : null}
        </>
      ) : null}
    </div>
  );
}

const DAY_OPTIONS = [
  { value: 35, label: "Harvest day 35" },
  { value: 28, label: "Fluorescence day 28" },
];

const LIGHT_DEFAULT_TRAITS = ["freshWeightG", "fvPOverFmP", "phiNO"];

/**
 * The third workflow.
 *
 * It is built to the same shape as the other two — inputs with units and reasons, a real backend
 * run, side-by-side comparison, evidence, limitations — with one deliberate difference: there is no
 * prediction anywhere on this panel. Every number is the mean of measurements made in one published
 * experiment, and the panel says that at the top rather than in a footnote, because a user who
 * expects a simulator needs to know before they read the table, not after.
 */
export function LightStressWorkflow() {
  const capability = useResource("/workflows/light-stress/capability");
  const traits = useMemo(() => capability.data?.fields?.[1]?.options || [], [capability.data]);
  const regimes = useMemo(() => capability.data?.regimes || [], [capability.data]);
  const [selections, setSelections] = useState(null);
  const [chosenTraits, setChosenTraits] = useState(LIGHT_DEFAULT_TRAITS);
  const [state, setState] = useState({ data: null, error: "", loading: false, at: null });

  const starting = useMemo(
    () => [
      { key: "light-0", label: "Control", regime: "control", daysAfterSowing: 35 },
      { key: "light-1", label: "T2 · increasing green", regime: "t2", daysAfterSowing: 35 },
    ],
    [],
  );
  const scenarios = selections ?? starting;

  const setScenario = (index, patch) => {
    setSelections((current) => (current ?? starting).map(
      (item, i) => (i === index ? { ...item, ...patch } : item)));
  };
  const addScenario = () => {
    setSelections((current) => {
      const source = current ?? starting;
      const used = new Set(source.map((item) => item.regime));
      const next = regimes.find((candidate) => !used.has(candidate.regime)) || regimes[0];
      return [...source, {
        key: `light-${Date.now()}`, label: next?.label?.split(":")[0] || "Regime",
        regime: next?.regime || "control", daysAfterSowing: 35,
      }];
    });
  };
  const removeScenario = (index) => {
    setSelections((current) => (current ?? starting).filter((_, i) => i !== index));
  };

  const run = useCallback(async () => {
    setState({ data: null, error: "", loading: true, at: null });
    try {
      const payload = await api("/workflows/light-stress/run", {
        scenarios: scenarios.map((scenario) => ({
          label: scenario.label,
          regime: scenario.regime,
          traits: chosenTraits,
          daysAfterSowing: scenario.daysAfterSowing,
        })),
      });
      setState({ data: payload, error: "", loading: false, at: new Date().toLocaleTimeString() });
    } catch (error) {
      setState({ data: null, error: error.message, loading: false, at: null });
    }
  }, [scenarios, chosenTraits]);

  const result = state.data;

  return (
    <div className="workflow-panel" aria-label="Light quality and stress workflow">
      <RequestState state={capability} />
      {capability.data ? (
        <>
          <div className="workflow-warning" role="note">
            <FlaskConical size={15} />
            <div>
              <strong>Measured, not simulated.</strong> This workflow reports groups of plants that
              were actually grown and measured in one published experiment
              ({capability.data.crop.cultivar}, {capability.data.fixedConditions.ppfdUmolPerM2S}{" "}
              µmol/m²/s, {capability.data.fixedConditions.photoperiodHours} h). It has no model, no
              response surface and no prediction for a treatment that was not run.
            </div>
          </div>

          <Card
            title="1 · Choose the regimes to compare"
            label="Input"
            action={<Pill tone="ok">{regimes.length} measured regimes</Pill>}
          >
            <p className="fine">
              Each regime is a measured group. The experiment varied only the spectral composition
              of the light; PPFD, photoperiod, temperature and CO₂ were held constant, so this panel
              offers no control for them — moving them here would be a fabricated result, not a
              feature.
            </p>

            <div className="workflow-scenario-grid">
              {scenarios.map((scenario, index) => (
                <section className="workflow-scenario" key={scenario.key}>
                  <header>
                    <input
                      className="scenario-name"
                      aria-label={`Scenario ${index + 1} name`}
                      value={scenario.label}
                      onChange={(event) => setScenario(index, { label: event.target.value })}
                    />
                    {scenarios.length > 1 ? (
                      <button
                        type="button"
                        className="ghost-button"
                        onClick={() => removeScenario(index)}
                        aria-label={`Remove ${scenario.label}`}
                      >
                        <Trash2 size={14} />
                      </button>
                    ) : null}
                  </header>
                  <label className="field workflow-field" htmlFor={`light-regime-${index}`}>
                    <span className="field-heading"><span>Regime</span></span>
                    <select
                      id={`light-regime-${index}`}
                      aria-label={`Regime for ${scenario.label}`}
                      value={scenario.regime}
                      onChange={(event) => setScenario(index, { regime: event.target.value })}
                    >
                      {regimes.map((regime) => (
                        <option key={regime.regime} value={regime.regime}>
                          {regime.regime.toUpperCase()} · {regime.greenFractionPct}% green
                          {regime.confoundsSpectrumWithDensity ? " · 1.25× density" : ""}
                        </option>
                      ))}
                    </select>
                    <small>
                      {regimes.find((regime) => regime.regime === scenario.regime)?.label}
                    </small>
                  </label>
                  <label className="field workflow-field" htmlFor={`light-day-${index}`}>
                    <span className="field-heading"><span>Measurement day</span></span>
                    <select
                      id={`light-day-${index}`}
                      aria-label={`Measurement day for ${scenario.label}`}
                      value={scenario.daysAfterSowing}
                      onChange={(event) =>
                        setScenario(index, { daysAfterSowing: Number(event.target.value) })}
                    >
                      {DAY_OPTIONS.map((option) => (
                        <option key={option.value} value={option.value}>{option.label}</option>
                      ))}
                    </select>
                    <small>
                      Fluorescence and SPAD were read on days 28 and 35; harvest traits were measured
                      at day 35 only, so the day control has no effect on them.
                    </small>
                  </label>
                </section>
              ))}
            </div>

            <div className="module-actions">
              <button
                type="button"
                className="secondary-button"
                onClick={addScenario}
                disabled={state.loading || scenarios.length >= capability.data.maxScenarios}
              >
                <Plus size={14} /> Add regime
              </button>
              <span className="muted fine">
                Up to {capability.data.maxScenarios} regimes per comparison.
              </span>
            </div>

            <fieldset className="workflow-fieldset">
              <legend>Traits to report</legend>
              <div className="workflow-chip-row">
                {traits.map((trait) => {
                  const checked = chosenTraits.includes(trait.value);
                  return (
                    <label
                      key={trait.value}
                      className={checked ? "workflow-chip on" : "workflow-chip"}
                    >
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={() =>
                          setChosenTraits((current) =>
                            current.includes(trait.value)
                              ? current.filter((value) => value !== trait.value)
                              : [...current, trait.value])}
                      />
                      {trait.label} <span className="muted">({trait.unit})</span>
                    </label>
                  );
                })}
              </div>
            </fieldset>

            <div className="module-actions">
              <button
                type="button"
                className="primary-button"
                onClick={run}
                disabled={state.loading || !chosenTraits.length || !scenarios.length}
              >
                <Play size={15} />
                {state.loading ? "Summarising the measurements…" : "Compare regimes"}
              </button>
              <span className="muted fine">
                Reads the processed tables built from the deposited workbook; no value is computed in
                the browser.
              </span>
            </div>
            {state.loading ? (
              <div className="skeleton" role="status">Reading measured groups…</div>
            ) : null}
            {state.error ? <div className="error-banner" role="alert">{state.error}</div> : null}
          </Card>

          {result ? (
            <>
              <Card
                title="2 · Measured means and spread"
                label="Output"
                action={<Pill tone="ok">read {state.at}</Pill>}
              >
                <div className="data-table-wrap">
                  <table className="data-table">
                    <caption className="sr-only">
                      Measured group means with bootstrap intervals, by regime and trait
                    </caption>
                    <thead>
                      <tr>
                        <th scope="col">Regime</th>
                        <th scope="col">Trait</th>
                        <th scope="col">n</th>
                        <th scope="col">Mean ± SD</th>
                        <th scope="col">90 % CI of the mean</th>
                        <th scope="col">Day</th>
                      </tr>
                    </thead>
                    <tbody>
                      {result.comparison.rows.map((row) => (
                        <tr key={`${row.regime}-${row.trait}`}>
                          <th scope="row">{row.label}</th>
                          <td>{row.traitLabel} <span className="muted">({row.unit})</span></td>
                          <td>{row.n}</td>
                          <td>{number(row.mean)} ± {number(row.standardDeviation)}</td>
                          <td>{number(row.ciLow)} – {number(row.ciHigh)}</td>
                          <td>{row.daysAfterSowing ?? "harvest"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                {result.comparison.deltas.length ? (
                  <>
                    <h3>Difference from the control</h3>
                    <div className="data-table-wrap">
                      <table className="data-table">
                        <thead>
                          <tr>
                            <th scope="col">Comparison</th>
                            <th scope="col">Trait</th>
                            <th scope="col">Δ</th>
                            <th scope="col">Δ (%)</th>
                            <th scope="col">Intervals separated</th>
                            <th scope="col">Reading</th>
                          </tr>
                        </thead>
                        <tbody>
                          {result.comparison.deltas.map((delta) => (
                            <tr key={`${delta.label}-${delta.trait}`}>
                              <th scope="row">{delta.label} vs {delta.comparedWith}</th>
                              <td>{delta.traitLabel}</td>
                              <td>{number(delta.difference)} <span className="muted">{delta.unit}</span></td>
                              <td>
                                {delta.relativeDifferenceMeaningful === false
                                  ? <span className="muted">not meaningful</span>
                                  : `${number(delta.relativeDifference * 100, 1)}`}
                              </td>
                              <td>
                                {delta.meansAreSeparated ? (
                                  <span className="pill pill-ok">yes</span>
                                ) : (
                                  <span className="pill pill-warn">no</span>
                                )}
                              </td>
                              <td className="fine">{delta.note}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </>
                ) : null}

                {result.scenarios.map((scenario) => {
                  const welch = scenario.traits
                    .map((trait) => ({ trait, test: trait.versusControl?.welch }))
                    .filter((entry) => entry.test);
                  if (!welch.length) return null;
                  return (
                    <div className="workflow-warning" role="status" key={`welch-${scenario.regime}`}>
                      <AlertTriangle size={15} />
                      <div>
                        <strong>{scenario.label} — within-experiment tests</strong>
                        <ul>
                          {welch.map(({ trait, test }) => (
                            <li key={trait.trait}>
                              {trait.label}: Welch t = {number(test.t, 2)}, df ={" "}
                              {number(test.degreesOfFreedom, 1)}, p = {number(test.pValue, 4)};
                              Hedges g = {number(trait.versusControl.hedgesG, 2)}.
                            </li>
                          ))}
                        </ul>
                        <p className="fine">{result.method.pseudoReplication}. A p-value here is a
                          within-experiment quantity, not a repeatability claim.</p>
                      </div>
                    </div>
                  );
                })}
              </Card>

              <Card title="3 · Evidence, conditions and what is not supported" label="Provenance">
                <div className="stat-pair">
                  <div>
                    <span className="muted">Source</span>
                    <strong>{result.provenance.source.dataset}</strong>
                  </div>
                  <div>
                    <span className="muted">DOI · licence</span>
                    <strong>{result.provenance.source.doi} · {result.provenance.source.license}</strong>
                  </div>
                  <div>
                    <span className="muted">Raw file SHA-256 verified</span>
                    <strong>{result.provenance.verifiedAgainstManifest ? "yes" : "no"}</strong>
                  </div>
                  <div>
                    <span className="muted">Measurement basis</span>
                    <strong>{result.provenance.source.measurementBasis}</strong>
                  </div>
                </div>
                <p className="fine">
                  {result.provenance.source.citation}. Raw file{" "}
                  <code>{result.provenance.rawFileSha256.slice(0, 16)}…</code>; processed tables{" "}
                  {result.provenance.processedFiles.map((file) => file.split("/").pop()).join(", ")}.
                </p>

                <h3>Factors this workflow can and cannot move</h3>
                <div className="data-table-wrap">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th scope="col">Factor</th>
                        <th scope="col">Supported</th>
                        <th scope="col">Why</th>
                      </tr>
                    </thead>
                    <tbody>
                      {result.factors.map((factor) => (
                        <tr key={factor.factor}>
                          <th scope="row">{factor.factor}</th>
                          <td>
                            {factor.supported ? (
                              <span className="pill pill-ok">yes</span>
                            ) : (
                              <span className="pill pill-warn">no</span>
                            )}
                          </td>
                          <td className="fine">{factor.limitation}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <p className="fine">
                  Method: {result.method.name}. Bootstrap resamples {result.method.bootstrapResamples},
                  seed {result.method.bootstrapSeed}. Composite stress score:{" "}
                  {result.method.compositeScore}.
                </p>
                <Limitations items={result.limitations} />
                <JsonDetails data={result} />
              </Card>
            </>
          ) : null}
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
            <Pill tone="ok"><CheckCircle2 size={12} /> 1 measured panel</Pill>
            <Pill tone="warn"><ShieldCheck size={12} /> 1 removed · 1 documented gap</Pill>
          </div>
        }
      >
        <p className="fine">
          Two workflows a user can complete without touching the API — a reference water balance and
          a measured light-quality comparison — plus a measured controlled-environment panel and one
          honest tombstone. Phase 30 removed harvest forecasting: the model missed the unchanged 30 %
          independent-error criterion by more than a factor of ten on published studies it had never
          seen, so the tab now shows the evidence and the decision rather than a prediction. The
          response surface for PPFD, CO₂ and temperature is still a documented gap: the wheat series
          was acquired and fitted, the fit failed its sealed holdout by an order of magnitude, and no
          surface is served.
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

      {tab === "water" ? <WaterDemandWorkflow /> : null}
      {tab === "harvest" ? <HarvestWorkflow /> : null}
      {tab === "light" ? <LightStressWorkflow /> : null}
      {tab === "cea" ? <CeaEvidenceWorkflow /> : null}
    </div>
  );
}
