import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { number } from "../pages/missionUI.jsx";

/**
 * The cumulative-biomass curve.
 *
 * Kept out of missionUI.jsx on purpose: that module is imported by the application shell, and
 * recharts is 69 kB gzipped. Living here means the chart library is fetched when a page that
 * actually draws a curve is opened, not on first paint.
 */
export function GrowthPlot({ result }) {
  return (
    <div
      className="growth-plot"
      role="img"
      aria-label="Simulated cumulative fresh biomass in grams over mission days"
    >
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart
          data={result?.dailyGrowthData || []}
          margin={{ top: 15, right: 15, left: 0, bottom: 0 }}
        >
          <defs>
            <linearGradient id="missionFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#75e6b4" stopOpacity={0.25} />
              <stop offset="100%" stopColor="#75e6b4" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid
            stroke="#233139"
            vertical={false}
            strokeDasharray="3 5"
          />
          <XAxis
            dataKey="day"
            tickLine={false}
            axisLine={false}
            tick={{ fill: "#8b9fa7", fontSize: 11 }}
            tickFormatter={(v) => `D${v}`}
          />
          <YAxis
            tickLine={false}
            axisLine={false}
            tick={{ fill: "#8b9fa7", fontSize: 11 }}
            width={48}
            tickFormatter={(v) => `${number(v / 1000)}k`}
          />
          <Tooltip
            contentStyle={{
              background: "#112027",
              border: "1px solid #33454d",
              borderRadius: 10,
              color: "#ebf5f4",
            }}
            formatter={(v, n) => [`${number(v)} g`, n]}
            labelFormatter={(v) => `Mission day ${v}`}
          />
          <Area
            type="monotone"
            dataKey="earthCumulative"
            name="Earth reference"
            stroke="#7385b4"
            strokeDasharray="5 5"
            fill="transparent"
            strokeWidth={1.5}
            isAnimationActive={false}
          />
          <Area
            type="monotone"
            dataKey="spaceCumulative"
            name="Selected habitat"
            stroke="#7be3b7"
            fill="url(#missionFill)"
            strokeWidth={2.5}
            isAnimationActive={false}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
