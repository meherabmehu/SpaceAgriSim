import { useEffect, useMemo, useState } from "react";
import { Card, number } from "../missionUI.jsx";
import { api } from "../../services/platformApi.ts";
import { authorizationHeader } from "../../services/auth.ts";
import { useResource, RequestState, Limitations, JsonDetails } from "./moduleSupport.jsx";
import {
  AlertTriangle,
  CheckCircle2,
  ClipboardList,
  Download,
  FlaskConical,
  Save,
  ShieldCheck,
} from "lucide-react";

/**
 * The scientific workflow, end to end: evidence -> model selection -> input validation ->
 * inference -> interpretation -> saved analysis -> export.
 *
 * Every step is served by the API rather than re-derived here. The page renders what the backend
 * decided, including the refusals: a retired model cannot be selected, an out-of-range input is
 * rejected with the reason, and an uncalibrated output is labelled as such instead of being given
 * a confidence interval it does not have.
 */

const EXPORT_FORMATS = ["json", "csv", "md"];

function Step({ index, title, detail, children }) {
  return (
    <section className="workflow-step" aria-label={`Step ${index}: ${title}`}>
      <div className="step-heading">
        <span className="step-index" aria-hidden="true">
          {index}
        </span>
        <div>
          <h3>{title}</h3>
          {detail ? <p className="fine">{detail}</p> : null}
        </div>
      </div>
      {children}
    </section>
  );
}

function StatusPill({ status }) {
  const tone =
    status === "runnable" ? "ok" : status === "retired" ? "danger" : "warn";
  return <span className={`pill pill-${tone}`}>{status}</span>;
}

async function downloadAnalysis(id, format) {
  const response = await fetch(`/api/analyses/${id}/export/${format}`, {
    headers: authorizationHeader(),
  });
  if (!response.ok) throw new Error(`Export failed (${response.status})`);
  const url = URL.createObjectURL(await response.blob());
  const link = document.createElement("a");
  link.href = url;
  link.download = `spaceagrisim-analysis-${id.slice(0, 8)}.${format}`;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function ScientificWorkflow({ session, onRequireSignIn, setNotice }) {
  const catalogue = useResource("/workflow/models");
  const models = useMemo(() => catalogue.data?.models || [], [catalogue.data]);

  // Selection, draft inputs and results are all keyed by model. Deriving "is this result about
  // the model currently selected" rather than resetting state in an effect means a verdict for
  // one model can never be displayed under another model's inputs, and there is no cascading
  // render when the reader switches models.
  const [choice, setChoice] = useState("");
  const selected =
    choice ||
    (models.find((row) => row.runStatus === "runnable") || models[0])?.modelId ||
    "";
  const model = useMemo(
    () => models.find((row) => row.modelId === selected) || null,
    [models, selected],
  );

  const [draft, setDraft] = useState({ modelId: "", inputs: {} });
  const inputs = draft.modelId === selected ? draft.inputs : {};

  const [results, setResults] = useState({
    modelId: "",
    validation: null,
    run: null,
    saved: null,
  });
  const current = results.modelId === selected ? results : {};
  const validation = current.validation || null;
  const run = current.run || null;
  const saved = current.saved || null;

  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [savedList, setSavedList] = useState(null);

  useEffect(() => {
    if (!session) return undefined;
    const controller = new AbortController();
    api("/analyses?limit=5", undefined, controller.signal)
      .then((data) => setSavedList(data))
      .catch(() => setSavedList(null));
    return () => controller.abort();
  }, [session, saved]);

  const payload = () => {
    const features = model?.features || [];
    // Every declared feature must be supplied. Sending a short object would let the API reject a
    // request the page could have caught, and sending an empty one would look like a bad model
    // rather than an incomplete form.
    if (!features.length) return null;
    const parsed = {};
    for (const feature of features) {
      const value = inputs[feature];
      const numeric = Number(value);
      if (value === "" || value === undefined || !Number.isFinite(numeric)) return null;
      parsed[feature] = numeric;
    }
    return parsed;
  };

  const validate = async () => {
    const features = payload();
    if (!features) {
      setError("Enter a number for every model input.");
      return;
    }
    setBusy("validate");
    setError("");
    try {
      const verdict = await api("/workflow/validate", { modelId: selected, inputs: features });
      setResults({ modelId: selected, validation: verdict, run: null, saved: null });
      setNotice?.("Inputs validated against the model's recorded domain.");
    } catch (err) {
      setResults({ modelId: selected, validation: null, run: null, saved: null });
      setError(err.message);
    } finally {
      setBusy("");
    }
  };

  const infer = async (save = false) => {
    const features = payload();
    if (!features) {
      setError("Enter a number for every model input.");
      return;
    }
    if (save && !session) {
      setError("Sign in to save this analysis to your account.");
      onRequireSignIn?.();
      return;
    }
    setBusy(save ? "save" : "run");
    setError("");
    try {
      const result = await api("/workflow/run", {
        modelId: selected,
        inputs: features,
        save,
        title: save ? `${selected} analysis` : null,
      });
      setResults((previous) => ({
        modelId: selected,
        validation: previous.modelId === selected ? previous.validation : null,
        run: result,
        saved: result.saved || null,
      }));
      if (save && result.saved) setNotice?.("Analysis saved to your account.");
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy("");
    }
  };

  const exportAnalysis = async (format) => {
    if (!saved) return;
    try {
      await downloadAnalysis(saved.id, format);
      setNotice?.(`${format.toUpperCase()} export downloaded.`);
    } catch (err) {
      setError(err.message);
    }
  };

  const output = run?.output || null;
  const classification = run?.scientificClassification || null;

  return (
    <>
      <div className="module-intro">
        <span className="pill">
          <FlaskConical size={12} />
          EVIDENCE TO EXPORTED ANALYSIS
        </span>
        <p>
          Select a served model, enter its inputs, and run it. Nothing here is a measurement: a
          molecular classifier returns a class probability and a regressor returns an estimate,
          both labelled with what the model actually does and what it does not.
        </p>
      </div>

      <RequestState state={catalogue} />
      {error ? (
        <div className="error-banner" role="alert">
          {error}
        </div>
      ) : null}

      <Stepper />

      <Card title="1 · Model and its evidence" label="Selection">
        {!models.length && !catalogue.loading ? (
          <p className="empty-state">
            No models are available. The registry could not be read, so nothing can be run.
          </p>
        ) : (
          <div className="module-grid">
            {models.map((row) => {
              const retired = row.runStatus === "retired";
              return (
                <button
                  key={row.modelId}
                  type="button"
                  className={`model-choice${selected === row.modelId ? " selected" : ""}`}
                  onClick={() => {
                    if (retired) return;
                    setChoice(row.modelId);
                    setError("");
                  }}
                  disabled={retired}
                  aria-pressed={selected === row.modelId}
                  aria-disabled={retired}
                  title={retired ? row.retiredReason || "Retired model" : row.name}
                >
                  <div className="card-heading">
                    <strong>{row.name || row.modelId}</strong>
                    <StatusPill status={row.runStatus} />
                  </div>
                  <p className="fine">{row.inputFamilyDescription}</p>
                  <p className="fine">
                    Category {row.category} · {row.categoryName}
                  </p>
                  {retired ? (
                    <p className="fine">
                      <AlertTriangle size={12} /> {row.retiredReason}
                    </p>
                  ) : null}
                </button>
              );
            })}
          </div>
        )}

        {model ? (
          <div className="config-summary">
            <p>
              <strong>Source study:</strong> {model.sourceStudy} ·{" "}
              <strong>Type:</strong> {model.sourceType || "not recorded"} ·{" "}
              <strong>Output:</strong> {model.target || "class label"}{" "}
              {model.outputUnit ? `(${model.outputUnit})` : ""}
            </p>
            {model.calibration ? (
              <p className="fine">
                {model.calibration.calibrated
                  ? `Interval calibrated: measured coverage ${number(model.calibration.measuredCoverage, 3)} against a nominal ${number(model.calibration.nominalCoverage, 2)}.`
                  : "No calibrated prediction interval is available for this model. Treat the point estimate as exploratory."}
              </p>
            ) : (
              <p className="fine">
                No calibration record: this model's output is not accompanied by a validated
                uncertainty interval.
              </p>
            )}
          </div>
        ) : null}
      </Card>

      <Card title="2 · Inputs" label="What the model accepts">
        {model ? (
          <>
            <p className="fine">
              Exactly {model.featureCount} features, in the model's own units. Any other field name
              is rejected by the API rather than ignored.
            </p>
            <div className="control-grid">
              {(model.features || []).map((feature) => (
                <label className="field" key={feature}>
                  <span className="field-heading">{feature}</span>
                  <input
                    type="number"
                    step="any"
                    inputMode="decimal"
                    value={inputs[feature] ?? ""}
                    onChange={(event) => {
                      const value = event.target.value;
                      setDraft((previous) => {
                        const base = previous.modelId === selected ? previous.inputs : {};
                        return { modelId: selected, inputs: { ...base, [feature]: value } };
                      });
                    }}
                    aria-label={`${feature} value`}
                  />
                </label>
              ))}
            </div>
            <div className="module-actions">
              <button className="secondary-button" onClick={validate} disabled={busy !== ""}>
                <ShieldCheck size={16} />
                {busy === "validate" ? "Validating…" : "Validate inputs"}
              </button>
            </div>
          </>
        ) : (
          <p className="empty-state">Select a model to see the inputs it requires.</p>
        )}
      </Card>

      <Card title="3 · Validation" label="Before anything runs">
        {!validation ? (
          <p className="empty-state">
            Inputs have not been validated yet. Running without validating is allowed; the run
            performs the same checks and returns the same errors.
          </p>
        ) : (
          <>
            <p className="fine">
              <CheckCircle2 size={14} /> Valid for {validation.modelId} · category{" "}
              {validation.classification?.category} ({validation.classification?.categoryName})
            </p>
            <div className="data-table-wrap">
              <table>
                <thead>
                  <tr>
                    <th scope="col">Check</th>
                    <th scope="col">Result</th>
                  </tr>
                </thead>
                <tbody>
                  {(validation.checks || []).map((check) => (
                    <tr key={check.name || check.check}>
                      <td>{check.name || check.check}</td>
                      <td>{check.passed ? "pass" : check.detail || "fail"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </Card>

      <Card title="4 · Inference and interpretation" label="Model output, not a measurement">
        <div className="module-actions">
          <button
            className="primary-button"
            onClick={() => infer(false)}
            disabled={busy !== "" || !model}
          >
            <FlaskConical size={16} />
            {busy === "run" ? "Running…" : "Run model"}
          </button>
          <button
            className="secondary-button"
            onClick={() => infer(true)}
            disabled={busy !== "" || !model}
          >
            <Save size={16} />
            {busy === "save" ? "Saving…" : "Run and save"}
          </button>
        </div>

        {!run ? (
          <p className="empty-state">
            No inference has been run in this session. Outputs are computed on request and never
            replayed from a stored example.
          </p>
        ) : (
          <>
            <div className="metric-grid">
              <div className="metric-tile">
                <span className="eyebrow">Prediction</span>
                <span className="metric-value">
                  {output?.prediction == null ? "—" : String(output.prediction)}
                </span>
                <span className="fine">{model?.outputUnit || "class label"}</span>
              </div>
              <div className="metric-tile">
                <span className="eyebrow">Output kind</span>
                <span className="metric-value">{output?.kind || "—"}</span>
                <span className="fine">
                  {output?.calibrated ? "calibrated interval" : "uncalibrated point estimate"}
                </span>
              </div>
              <div className="metric-tile">
                <span className="eyebrow">Evidence category</span>
                <span className="metric-value">{classification?.category ?? "—"}</span>
                <span className="fine">{classification?.categoryName}</span>
              </div>
            </div>

            {Array.isArray(output?.probabilities) ? (
              <div className="data-table-wrap">
                <table>
                  <caption className="fine">
                    Class probabilities. These are model outputs and are not calibrated
                    probabilities of a biological outcome.
                  </caption>
                  <thead>
                    <tr>
                      <th scope="col">Class</th>
                      <th scope="col">Probability</th>
                    </tr>
                  </thead>
                  <tbody>
                    {output.probabilities.map((row) => (
                      <tr key={row.label}>
                        <td>{row.label}</td>
                        <td>{number(row.probability, 3)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : null}

            {run.interpretation ? (
              <div className="prose">
                <h3 className="sub-heading">Interpretation</h3>
                <p>{run.interpretation.summary}</p>
                {run.interpretation.statements?.length ? (
                  <ul className="claim-list">
                    {run.interpretation.statements.map((statement, index) => (
                      <li key={index}>{statement}</li>
                    ))}
                  </ul>
                ) : null}
              </div>
            ) : null}

            {run.evidence?.claims?.length ? (
              <div className="prose">
                <h3 className="sub-heading">Evidence behind the interpretation</h3>
                <ol className="citation-list">
                  {run.evidence.claims.map((claim, index) => (
                    <li key={index}>
                      <p>{claim.text}</p>
                      <div className="citation-meta">
                        {claim.sourceId ? <span>{claim.sourceId}</span> : null}
                        {claim.accession ? <span>Accession {claim.accession}</span> : null}
                      </div>
                    </li>
                  ))}
                </ol>
              </div>
            ) : null}

            <Limitations items={run.limitations} />
            <JsonDetails data={run} />
          </>
        )}
      </Card>

      <Card title="5 · Saved analysis and export" label="Private to your account">
        {!session ? (
          <p className="empty-state">
            Sign in to save an analysis. Running a model needs no account; storing the result does,
            because saved analyses belong to a person.{" "}
            <button className="wide-link" onClick={() => onRequireSignIn?.()}>
              Sign in
            </button>
          </p>
        ) : !saved ? (
          <p className="empty-state">
            Nothing saved from this session yet. Use “Run and save” above.
          </p>
        ) : (
          <>
            <p className="fine">
              Saved as <code>{saved.id}</code> · {saved.title}
            </p>
            <div className="module-actions">
              {EXPORT_FORMATS.map((format) => (
                <button
                  key={format}
                  className="secondary-button"
                  onClick={() => exportAnalysis(format)}
                >
                  <Download size={14} /> {format.toUpperCase()}
                </button>
              ))}
            </div>
            <p className="fine">
              Exports carry the model output and its interpretation, plus a header stating that this
              is model output and not a measurement.
            </p>
          </>
        )}

        {session && savedList?.analyses?.length ? (
          <div className="prose">
            <h3 className="sub-heading">
              <ClipboardList size={14} /> Recent analyses on this account
            </h3>
            <p className="fine">
              Showing {savedList.analyses.length} of {savedList.pagination?.total ?? 0} ·{" "}
              {savedList.usage?.count ?? 0}/{savedList.usage?.maxCount ?? "—"} used
            </p>
            <ul className="claim-list">
              {savedList.analyses.map((row) => (
                <li key={row.id}>
                  <strong>{row.title}</strong> · {row.modelId} ·{" "}
                  {new Date(row.createdAt).toLocaleString()}
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </Card>
    </>
  );
}

function Stepper() {
  const steps = [
    "evidence",
    "model selection",
    "validation",
    "inference",
    "interpretation",
    "saved analysis",
    "export",
  ];
  return (
    <ol className="workflow-timeline" aria-label="Workflow steps">
      {steps.map((step, index) => (
        <li key={step}>
          <span className="timeline-node" aria-hidden="true">
            {index + 1}
          </span>
          <span className="fine">{step}</span>
        </li>
      ))}
    </ol>
  );
}
