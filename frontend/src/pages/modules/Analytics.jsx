import { Card, number } from "../missionUI.jsx";
import { useResource, RequestState, JsonDetails } from "./moduleSupport.jsx";
import { ArrowDownToLine } from "lucide-react";
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
export function Analytics({
  params,
  result,
  exportReport,
  setParam,
  setNotice,
  session,
}) {
  // Saved scenarios are private account history: `GET /scenarios` is authenticated. The request
  // used to be issued unconditionally, so a signed-out visitor got a red "Authentication is
  // required" banner directly beside the sign-in prompt on the same card. The resource is now
  // gated on the session, which is what `RequestState` and `useResource` expect.
  const history = useResource(session ? "/scenarios" : null);
  const chart = result?.dailyLifeSupportData || [];
  const restore = (row) => {
    Object.entries(row.configuration).forEach(([key, value]) =>
      setParam(key, value),
    );
    setNotice(`Restored ${row.name}.`);
  };
  return (
    <>
      <div className="module-actions">
        {["pdf", "csv", "json"].map((format) => (
          <button
            key={format}
            className="secondary-button"
            disabled={!result}
            onClick={() => exportReport(format)}
          >
            <ArrowDownToLine size={14} />
            Download {format.toUpperCase()}
          </button>
        ))}
      </div>
      <div className="module-grid">
        <Card title="Daily water balance" label="LITERS · SIMULATED">
          <TimeSeries
            data={chart}
            series={["waterDemand", "waterUsed", "waterRecovered"]}
            colors={["#b7c5cf", "#89c6e6", "#a1dcb4"]}
          />
        </Card>
        <Card title="Gas exchange proxy" label="GRAMS · BIOMASS-DERIVED">
          <TimeSeries
            data={chart}
            series={["co2Removed", "o2Produced"]}
            colors={["#b5a2d8", "#8cd5cf"]}
          />
        </Card>
      </div>
      <Card title="Daily mission ledger" label="EXPORTABLE MODEL OUTPUT">
        <div className="data-table-wrap">
          <table>
            <thead>
              <tr>
                <th>DAY</th>
                <th>WATER SUPPLY (L)</th>
                <th>RECOVERED (L)</th>
                <th>CO₂ (g)</th>
                <th>O₂ (g)</th>
              </tr>
            </thead>
            <tbody>
              {chart.map((day) => (
                <tr key={day.day}>
                  <td>{day.day}</td>
                  <td>{number(day.waterUsed, 3)}</td>
                  <td>{number(day.waterRecovered, 3)}</td>
                  <td>{number(day.co2Removed, 3)}</td>
                  <td>{number(day.o2Produced, 3)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
      <Card title="Saved scenarios" label="PRIVATE ACCOUNT HISTORY">
        {session ? (
          <>
            <RequestState state={history} />
            {history.data?.scenarios?.length === 0 && (
              <p className="empty-state">
                Use “Save scenario” to retain your current configuration.
              </p>
            )}
            {history.data?.scenarios?.map((row) => (
              <div className="stat-pair" key={row.id}>
                <span>
                  {row.name}
                  <br />
                  <small>{row.created_at}</small>
                </span>
                <button className="secondary-button" onClick={() => restore(row)}>
                  Restore
                </button>
              </div>
            ))}
          </>
        ) : (
          <p className="muted fine">
            Sign in to view scenarios saved to your account. Do not store
            sensitive information.
          </p>
        )}
        <JsonDetails title="Current reproducible configuration" data={params} />
      </Card>
    </>
  );
}
function TimeSeries({ data, series, colors }) {
  return (
    <div className="growth-plot">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data}>
          <CartesianGrid stroke="#293b45" vertical={false} />
          <XAxis dataKey="day" stroke="#8da4b1" tick={{ fontSize: 10 }} />
          <YAxis stroke="#8da4b1" width={45} tick={{ fontSize: 10 }} />
          <Tooltip
            contentStyle={{ background: "#14232b", borderColor: "#35464e" }}
            formatter={(v) => number(v, 3)}
          />
          <Legend wrapperStyle={{ fontSize: 9 }} />
          {series.map((key, i) => (
            <Line
              key={key}
              dataKey={key}
              stroke={colors[i]}
              dot={false}
              isAnimationActive={false}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
