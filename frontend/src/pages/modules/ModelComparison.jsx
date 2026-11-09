import { GitCompareArrows } from "lucide-react";
import { Card, number } from "../missionUI.jsx";
import { useResource, RequestState, JsonDetails } from "./moduleSupport.jsx";
import { validationText } from "../../services/formatters.js";

/**
 * Side-by-side view of the served models.
 *
 * The table shows, per model, its own metric against its own baseline, the validation scheme that
 * produced it, and the input domain it is valid in. There is deliberately no combined score and no
 * ordering: an R² on a transcriptomic classifier and an MAE on a harvest regression measure
 * different things, and any single ranking column would be an invented comparison.
 */
export function ModelComparison() {
  const state = useResource("/models");
  const models = state.data?.models || [];
  // The lettuce artifact's own `validation` field describes the scheme used when it was trained.
  // An external check has since been run against an independent study, so that has to be shown
  // beside the artifact's own wording rather than left to a report nobody reads.
  const external = useResource("/external-validation");
  const externalCheck = external.data?.externalCheck;

  const rows = models.map((model) => {
    const metrics = model.metrics || {};
    const baseline = model.baselineMetrics || {};
    const primary = metrics.MAE ?? metrics.accuracy ?? metrics.macroF1 ?? metrics.R2;
    const baselinePrimary = baseline.MAE ?? baseline.accuracy ?? baseline.macroF1 ?? baseline.R2;
    return { model, metrics, baseline, primary, baselinePrimary };
  });

  return (
    <>
      <div className="module-intro">
        <span className="pill">
          <GitCompareArrows size={12} /> Model registry
        </span>
        <h2>Every served model, its measured error, and the domain it is valid in</h2>
        <p>
          These models answer different questions. The table lets you compare each one with its own
          baseline and read its validation scheme — not rank one against another, which the metrics
          do not support.
        </p>
      </div>

      <RequestState state={state} />

      {rows.length > 0 && (
        <Card title="Served models" label={`${rows.length} ARTIFACT-BACKED MODELS`}>
          <div className="table-scroll">
            <table className="data-table compare-table">
              <thead>
                <tr>
                  <th scope="col">Model</th>
                  <th scope="col">Task / target</th>
                  <th scope="col">Version</th>
                  <th scope="col">Error</th>
                  <th scope="col">Baseline</th>
                  <th scope="col">Validation</th>
                  <th scope="col">Domain</th>
                </tr>
              </thead>
              <tbody>
                {rows.map(({ model, metrics, baseline, primary, baselinePrimary }) => (
                  <tr key={model.id}>
                    <td>
                      <strong>{model.name || model.id}</strong>
                      <p className="muted mono">{model.id}</p>
                    </td>
                    <td>
                      {model.task || "—"}
                      <p className="muted">
                        {model.target || "—"}
                        {model.unit ? ` (${model.unit})` : ""}
                      </p>
                    </td>
                    <td>{model.version}</td>
                    <td>
                      {primary === undefined ? "—" : number(primary, 2)}
                      <p className="muted">
                        {Object.entries(metrics).map(([key, value]) => `${key} ${number(value, 2)}`).join(" · ")}
                      </p>
                    </td>
                    <td>
                      {baselinePrimary === undefined ? "—" : number(baselinePrimary, 2)}
                      <p className="muted">
                        {Object.entries(baseline).map(([key, value]) => `${key} ${number(value, 2)}`).join(" · ") || "none recorded"}
                      </p>
                    </td>
                    <td className="wrap">
                      {validationText(model) || "—"}
                      {model.id === externalCheck?.modelId ? (
                        externalCheck.available && (
                          <p className="muted">
                            External check {externalCheck.verdict.passed ? "passed" : "failed"}:{" "}
                            {externalCheck.verdict.headline.toLowerCase()} ({externalCheck.citation}).
                          </p>
                        )
                      ) : null}
                    </td>
                    <td className="wrap">
                      {model.domain
                        ? Object.entries(model.domain)
                            .map(([key, range]) => `${key} ${number(range.min, 1)}–${number(range.max, 1)}`)
                            .join(", ")
                        : "not declared"}
                      {model.samples !== undefined && (
                        <p className="muted">
                          {number(model.samples, 0)} samples
                          {model.groups !== undefined ? ` · ${number(model.groups, 0)} groups` : ""}
                        </p>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="muted">
            "Baseline" is the reference predictor recorded with each artifact, on the same split.
            A model that does not beat its own baseline is reported as such, not hidden.
          </p>
        </Card>
      )}

      {rows.length === 0 && !state.loading && !state.error && (
        <Card title="No models registered">
          <p className="muted">The registry is reachable but lists no artifact-backed models.</p>
        </Card>
      )}

      <Card title="What this view does not say">
        <ul className="reading-list">
          <li>It does not rank models. Different tasks, units and metrics are not commensurable.</li>
          <li>
            A wide error bar on one model does not make another model better, and a good R² on a
            narrow domain is not evidence outside that domain.
          </li>
          <li>
            None of these models validates the habitat simulator's crop forecasts; the benchmark
            panel is where that comparison is made, with its own caveats.
          </li>
        </ul>
        <JsonDetails title="Inspect the registry payload" data={state.data} />
      </Card>
    </>
  );
}
