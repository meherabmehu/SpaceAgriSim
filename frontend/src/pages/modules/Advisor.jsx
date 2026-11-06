import { Card, number } from "../missionUI.jsx";
import { api } from "../../services/platformApi.ts";
import {
  useResource,
  RequestState,
  Limitations,
  JsonDetails,
} from "./moduleSupport.jsx";
import { useState } from "react";
import { ArrowRight, ShieldCheck, Sparkles } from "lucide-react";
import {
  CartesianGrid,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
export function Advisor({ params, setParam, setNotice }) {
  const advice = useResource("/advisor", params);
  const [optimization, setOptimization] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const optimize = async () => {
    setBusy(true);
    setError("");
    try {
      setOptimization(await api("/optimize", params));
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <>
      <div className="module-intro">
        <span className="pill">
          <Sparkles size={12} />
          DETERMINISTIC SCIENTIFIC ADVISOR
        </span>
        <p>
          Numerical statements are computed by the backend. No language model
          invents results or citations. Recommendations optimize assumptions,
          and require independent biological and engineering validation.
        </p>
      </div>
      <Card
        title="What your mission is telling you"
        label="LIVE FACTOR ANALYSIS"
      >
        <RequestState state={advice} />
        {advice.data?.insights?.map((insight, i) => (
          <article className="insight-row" key={i}>
            <h3>{insight.title}</h3>
            <p>{insight.text}</p>
            <small>SOURCE · {insight.source}</small>
          </article>
        ))}
      </Card>
      <Card
        title="Explore feasible trade-offs"
        label="BOUNDED MULTI-OBJECTIVE SEARCH"
        action={<ShieldCheck size={18} className="accent" />}
      >
        <p className="prose">
          Compare crop biomass, fresh make-up water, and light input across a
          bounded parameter grid. Gravity, radiation, crop, area, and duration
          stay fixed. Light input is a proxy, not electrical demand.
        </p>
        <div className="module-actions">
          <button className="primary-button" disabled={busy} onClick={optimize}>
            {busy ? "Evaluating configurations…" : "Find trade-offs"}
            <ArrowRight size={15} />
          </button>
        </div>
        {error && <div className="error-banner">{error}</div>}
        {optimization && (
          <>
            <p className="muted fine">
              {optimization.candidateCount} candidates evaluated ·{" "}
              {optimization.pareto?.length} nondominated points ·{" "}
              {optimization.method}
            </p>
            <div className="growth-plot">
              <ResponsiveContainer width="100%" height="100%">
                <ScatterChart>
                  <CartesianGrid stroke="#293b45" />
                  <XAxis
                    dataKey="netWaterL"
                    name="Net make-up water"
                    unit=" L"
                    stroke="#8da4b1"
                  />
                  <YAxis
                    dataKey="yieldG"
                    name="Biomass"
                    unit=" g"
                    stroke="#8da4b1"
                  />
                  <Tooltip
                    cursor={{ strokeDasharray: "3 3" }}
                    contentStyle={{
                      background: "#14232b",
                      borderColor: "#35464e",
                    }}
                  />
                  <Scatter
                    data={optimization.pareto}
                    fill="#a6e5c4"
                    isAnimationActive={false}
                  />
                </ScatterChart>
              </ResponsiveContainer>
            </div>
            <div className="stat-pair">
              <span>Yield-priority recommendation</span>
              <strong>
                {number(optimization.recommendation?.yieldG)} g ·{" "}
                {number(optimization.recommendation?.netWaterL)} L
              </strong>
            </div>
            <button
              className="secondary-button"
              onClick={() => {
                Object.entries(
                  optimization.recommendation.configuration,
                ).forEach(([k, v]) => setParam(k, v));
                setNotice(
                  "Applied the exploratory recommendation. Review the model limitations.",
                );
                setOptimization(null);
              }}
            >
              Apply recommendation
            </button>
            <JsonDetails
              title="Sensitivity, constraints, baseline and Pareto points"
              data={optimization}
            />
            <Limitations items={optimization.limitations} />
          </>
        )}
      </Card>
      <Limitations items={advice.data?.limitations} />
    </>
  );
}
