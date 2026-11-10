import { Card, number } from "../missionUI.jsx";
import { useResource, RequestState, Limitations } from "./moduleSupport.jsx";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
export function Comparison({ params }) {
  const state = useResource("/compare", params);
  const colors = ["#a4e2be", "#bac7dd", "#d6a580", "#a291d5"];
  const runs = state.data?.scenarios || [];
  const chart = runs.length
    ? runs[0].result.dailyGrowthData.map((point, i) =>
        Object.fromEntries([
          ["day", point.day],
          ...runs.map((run) => [
            run.name,
            run.result.dailyGrowthData[i]?.spaceCumulative,
          ]),
        ]),
      )
    : [];
  return (
    <>
      <div className="module-intro">
        <span className="pill">HYPOTHETICAL PRESSURIZED HABITATS</span>
        <p>
          Resources are matched across Earth, Moon, and Mars. Gravity and
          illustrative absorbed radiation presets differ; these are not outdoor
          surface crop predictions.
        </p>
      </div>
      <RequestState state={state} />
      <div className="module-grid">
        {runs.map((run, i) => (
          <Card
            key={run.name}
            title={run.name}
            label="MATHEMATICAL ESTIMATE"
            action={
              <span className="world-orb" style={{ background: colors[i] }} />
            }
          >
            <div className="comparison-value">
              {number(run.result.cropYield / 1000)}{" "}
              <small>kg fresh biomass</small>
            </div>
            <div className="stat-pair">
              <span>Water supplied</span>
              <strong>{number(run.result.waterUsed)} L</strong>
            </div>
            <div className="stat-pair">
              <span>Oxygen proxy</span>
              <strong>{number(run.result.estimatedOxygenProduced)} g</strong>
            </div>
            <div className="stat-pair">
              <span>Chronic dose</span>
              <strong>{run.result.inputs.radiation} mGy/day</strong>
            </div>
            <div className="stat-pair">
              <span>Uncertainty</span>
              <strong>Not empirically calibrated</strong>
            </div>
          </Card>
        ))}
      </div>
      {runs.length > 0 && (
        <Card
          title="Matched growth trajectories"
          label="CUMULATIVE BIOMASS (g)"
        >
          <div className="growth-plot">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chart}>
                <CartesianGrid stroke="#283943" strokeDasharray="3 5" />
                <XAxis dataKey="day" stroke="#8ca3b0" />
                <YAxis stroke="#8ca3b0" />
                <Tooltip
                  contentStyle={{
                    background: "#14232b",
                    borderColor: "#35464e",
                  }}
                />
                <Legend />
                {runs.map((run, i) => (
                  <Line
                    key={run.name}
                    dataKey={run.name}
                    stroke={colors[i]}
                    dot={false}
                    isAnimationActive={false}
                  />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </div>
        </Card>
      )}
      <Limitations items={state.data?.limitations} />
    </>
  );
}
