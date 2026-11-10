import { useMemo, useState } from "react";
import { Droplets, Scale, TriangleAlert, ShieldCheck } from "lucide-react";
import { Card, number } from "../missionUI.jsx";
import { useResource, RequestState, Limitations } from "./moduleSupport.jsx";

/**
 * The measured water-use benchmark, inside the simulation lab.
 *
 * Why this panel exists
 * ---------------------
 * The lab already prints a water number, and nothing on the page said how that number relates to
 * anything observed. It now does: a greenhouse lettuce trial weighed 35 pots on 11 dates, and this
 * panel puts the platform's own demand curve beside that measurement.
 *
 * The panel is deliberately built to make the honest answer the visible one. It shows a verdict of
 * "rank agreement only" rather than a green tick, it draws the measured between-pot
 * spread as a band so the reader can see how wide the measurement itself is, and it lists the
 * geometry the study does not publish. A comparison that showed only one denominator would be
 * choosing the answer on the user's behalf.
 *
 * Nothing here changes the simulation. The panel compares; it does not calibrate.
 */

const VERDICT_STYLES = {
  "shape-only": {
    tone: "warn",
    icon: TriangleAlert,
    // Phase 31: stated as the scope of the comparison rather than as a shortfall. The panel makes
    // one claim - rank agreement - and says so in the label instead of asking the reader to
    // resolve a caution.
    label: "Rank agreement only · absolute level not identifiable from this trial",
  },
  "level-mismatch": { tone: "warn", icon: TriangleAlert, label: "Not supported by this benchmark" },
  "not-applicable": { tone: "muted", icon: Scale, label: "No measurement for this crop" },
};

function Sparkline({ curve }) {
  // A hand-drawn SVG rather than the chart library: eleven points, one axis, and the panel is
  // inside the eagerly-loaded lab page. Pulling recharts in here would cost more than the plot.
  const width = 520;
  const height = 150;
  const padX = 34;
  const padY = 16;
  const days = curve.map((point) => point.dayNumber);
  const measured = curve.map((point) => point.measuredMlPerPotPerDay);
  const simulated = curve.map((point) => point.simulatedMlPerPotPerDay);
  const maxY = Math.max(...measured) * 1.15;
  const minDay = Math.min(...days);
  const maxDay = Math.max(...days);
  const x = (day) => padX + ((day - minDay) / (maxDay - minDay || 1)) * (width - padX * 2);
  const y = (value) => height - padY - (value / maxY) * (height - padY * 2);
  const line = (values) =>
    values.map((value, index) => `${index === 0 ? "M" : "L"}${x(days[index])},${y(value)}`).join(" ");

  return (
    <svg
      className="water-evidence-plot"
      viewBox={`0 0 ${width} ${height}`}
      role="img"
      aria-label="Measured greenhouse lettuce water use against the platform demand curve, per pot per day"
    >
      {[0, 0.5, 1].map((fraction) => (
        <line
          key={fraction}
          x1={padX}
          x2={width - padX}
          y1={y(maxY * fraction)}
          y2={y(maxY * fraction)}
          stroke="#233139"
          strokeDasharray="3 5"
        />
      ))}
      <text x={4} y={y(maxY) + 10} fill="#6f8894" fontSize="10">
        {Math.round(maxY)}
      </text>
      <text x={4} y={height - padY + 4} fill="#6f8894" fontSize="10">
        0
      </text>
      {days.map((day) => (
        <text key={day} x={x(day)} y={height - 2} fill="#6f8894" fontSize="10" textAnchor="middle">
          {day}
        </text>
      ))}
      <path d={line(measured)} fill="none" stroke="#60a5fa" strokeWidth="2" />
      <path d={line(simulated)} fill="none" stroke="#4ade80" strokeWidth="2" strokeDasharray="5 4" />
    </svg>
  );
}

export function WaterEvidencePanel({ params }) {
  const [lightScale, setLightScale] = useState(1);
  const benchmark = useResource("/water-use-evidence");
  const body = useMemo(
    () => ({
      crop: params.crop,
      growingAreaM2: 0.0112,
      lightScale,
    }),
    [params.crop, lightScale],
  );
  const comparison = useResource("/water-use-evidence/compare", body);
  const data = comparison.data;

  const verdict = data ? VERDICT_STYLES[data.verdict] || VERDICT_STYLES["not-applicable"] : null;
  const Icon = verdict?.icon;

  return (
    <Card
      title="Measured water use"
      label="GREENHOUSE LETTUCE TRIAL · SCHRÖDER ET AL. 2021"
      className="water-evidence-card"
    >
      <RequestState state={benchmark} />
      <RequestState state={comparison} />

      {benchmark.data && !benchmark.data.available && (
        <p className="water-evidence-empty">
          No measured benchmark is present in this deployment, so no comparison is shown. The
          panel does not fall back to an estimate.
        </p>
      )}

      {data?.verdict === "not-applicable" && (
        <div className="water-evidence-verdict muted-tone">
          <Scale size={16} />
          <div>
            <strong>No measurement exists for {data.requestedCrop}.</strong>
            <p>{data.reason}</p>
          </div>
        </div>
      )}

      {data && data.verdict !== "not-applicable" && (
        <>
          <div className={`water-evidence-verdict tone-${verdict?.tone || "warn"}`}>
            {Icon ? <Icon size={16} /> : null}
            <div>
              <strong>{verdict?.label}</strong>
              <p>{data.verdictMeaning}</p>
              {data.identification && (
                <>
                  <p className="fine">
                    {data.identification.claim} {data.identification.denominatorSpread}{" "}
                    {data.identification.whyNotAssumed}
                  </p>
                  <p className="fine">
                    <strong>Would be identifiable with:</strong>{" "}
                    {data.identification.identifiableWith}
                  </p>
                </>
              )}
            </div>
          </div>

          <Sparkline curve={data.curve} />
          <div className="water-evidence-legend">
            <span>
              <i className="swatch measured" /> Measured (mL per pot per day)
            </span>
            <span>
              <i className="swatch simulated" /> Platform demand (same units)
            </span>
          </div>

          <div className="stat-pair">
            <span>Measured over the trial</span>
            <strong>{number(data.totals.measuredMlPerPot, 0)} mL/pot</strong>
          </div>
          <div className="stat-pair">
            <span>Platform demand, same days</span>
            <strong>{number(data.totals.simulatedMlPerPot, 0)} mL/pot</strong>
          </div>
          <div className="stat-pair">
            <span>Platform ÷ measured (assumed pot area — not a bias estimate)</span>
            <strong>{(data.totals.simulatedOverMeasured ?? 0).toFixed(3)}×</strong>
          </div>
          <div className="stat-pair">
            <span>Rank agreement across {data.shape.pairs} dates</span>
            <strong>ρ = {(data.shape.spearman ?? 0).toFixed(3)}</strong>
          </div>
          <div className="stat-pair">
            <span>Measured between-pot spread</span>
            <strong>±{(data.uncertainty.relativeSpread * 100).toFixed(1)} %</strong>
          </div>
          <div className="stat-pair">
            <span>Level identified?</span>
            <strong>{data.identification?.levelIdentified ? "yes" : "no"}</strong>
          </div>

          <label className="field water-evidence-control">
            <span className="field-heading">
              <span>
                Light scale for the comparison{" "}
                <span className="muted">(×, 1.0 = measured reference)</span>
              </span>
              <input
                aria-label="Light scale for the water comparison value"
                type="number"
                min={0.1}
                max={2.5}
                step={0.1}
                value={lightScale}
                onChange={(event) => {
                  if (event.target.value !== "") setLightScale(Number(event.target.value));
                }}
              />
            </span>
            <input
              aria-label="Light scale for the water comparison"
              type="range"
              min={0.1}
              max={2.5}
              step={0.1}
              value={lightScale}
              onChange={(event) => setLightScale(Number(event.target.value))}
            />
            <small>
              Changes only the platform curve, never the measurement. The measured side is data.
            </small>
          </label>

          <details className="details-block" open={false}>
            <summary>Why this is not a validation</summary>
            <ul className="water-evidence-reasons">
              {data.limitations.map((item) => (
                <li key={item}>{item}</li>
              ))}
              <li>{data.whatWouldSettleIt}</li>
            </ul>
          </details>

          <details className="details-block">
            <summary>Denominators: which are measured, which are assumptions</summary>
            <table className="water-evidence-table">
              <thead>
                <tr>
                  <th scope="col">Denominator</th>
                  <th scope="col">Area</th>
                  <th scope="col">Status</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(data.denominators).map(([key, entry]) => (
                  <tr key={key}>
                    <td>{key}</td>
                    <td>{entry.areaM2 ? `${entry.areaM2} m²` : "—"}</td>
                    <td>
                      {entry.isMeasured ? (
                        <span className="pill green">
                          <ShieldCheck size={11} /> measured
                        </span>
                      ) : (
                        <span className="pill">assumption</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </details>

          <div className="water-evidence-provenance">
            <Droplets size={14} />
            <span>
              {data.provenance.citation} · DOI {data.provenance.doi} · {data.provenance.license}
              {data.provenance.hashVerified ? " · files hash-verified" : ""}
            </span>
          </div>

          <Limitations
            items={[
              `Benchmark scope: ${benchmark.data?.environmentScope || "greenhouse lettuce"}.`,
              benchmark.data?.measurementPattern?.note,
              "The between-pot spread is what the experiment measured, not a confidence interval.",
              "The simulator's crop water profile is unchanged by anything on this panel.",
            ]}
            title="Panel notes"
          />
        </>
      )}
    </Card>
  );
}
