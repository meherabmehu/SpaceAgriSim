import { Ruler, Scale, Wind } from "lucide-react";
import { Card, number } from "../missionUI.jsx";
import { useResource, RequestState, JsonDetails, Limitations } from "./moduleSupport.jsx";

/**
 * The measured-versus-modelled numbers, in one place.
 *
 * The three panels answer three different questions and are kept visibly separate:
 *   · BPC  — a real closed chamber's gas and water exchange, held against the simulator;
 *   · leafy anchor — a NASA planning figure for microgreen productivity;
 *   · CO2  — the response curve the model applies, with the measured optimum beside it.
 *
 * Nothing is sorted into a ranking: the sources are not interchangeable, and a league table
 * would say they were.
 */
export function Benchmarks() {
  const state = useResource("/benchmarks");
  const data = state.data?.benchmarks;

  return (
    <>
      <div className="module-intro">
        <span className="pill">
          <Ruler size={12} /> Benchmark transparency
        </span>
        <h2>What NASA measured, what the simulator says, and the gap between them</h2>
        <p>
          Every number below is read from a pinned artifact. None of them was used to tune the
          model: they are held against it, which is the only way the gap stays visible.
        </p>
      </div>

      <RequestState state={state} />

      {data && (
        <>
          {data.bpc && (
            <Card title="Closed-chamber gas and water exchange" label="NASA TM 102788 · BIOMASS PRODUCTION CHAMBER">
              <div className="bench-grid">
                {[
                  ["CO₂ fixed, net (g m⁻² d⁻¹)", data.bpc.measured.co2_g_per_m2_day_net, data.bpc.simulated.lettuce?.co2_g_per_m2_day_mean],
                  ["Water transpired (L m⁻² d⁻¹)", data.bpc.measured.water_l_per_m2_day_mean, data.bpc.simulated.lettuce?.water_l_per_m2_day_mean],
                  ["Dry biomass (g m⁻² d⁻¹)", data.bpc.measured.dry_biomass_g_per_m2_day, data.bpc.simulated.lettuce?.dry_biomass_g_per_m2_day],
                  ["O₂ released (g m⁻² d⁻¹)", data.bpc.measured.o2_g_per_m2_day_mean, data.bpc.simulated.lettuce?.o2_g_per_m2_day_mean],
                ].map(([label, measured, modelled]) => (
                  <div className="bench-row" key={label}>
                    <span>{label}</span>
                    <strong>{number(measured, 2)}</strong>
                    <em>{number(modelled, 2)}</em>
                    <small>×{number(measured ? modelled / measured : 0, 2)}</small>
                  </div>
                ))}
              </div>
              <div className="bench-legend">
                <span>measured (wheat, 20 m² stand)</span>
                <span>simulator (lettuce, 1 m²)</span>
                <span>model ÷ measured</span>
              </div>
              <p className="muted">
                The simulator fixes and transpires roughly a seventh of what the chamber did per
                square metre. That is the honest headline: the per-area magnitude is the same
                order, and the crop models are not calibrated to this chamber.
              </p>
              <Limitations items={data.bpc.caveats} />
            </Card>
          )}

          {data.leafyAnchor && (
            <Card title="Leafy-green planning anchor" label="NTRS 20250001897 · NASA SPACE CROP REFERENCE">
              <div className="stat-pair">
                <span>Anchor productivity</span>
                <strong>{number(data.leafyAnchor.g_per_m2_day_from_tray, 1)} g m⁻² day⁻¹</strong>
              </div>
              <p className="muted">
                Two independent routes to the same figure: {number(data.leafyAnchor.serving_g, 0)} g
                per {number(data.leafyAnchor.tray_area_m2, 3)} m² tray over{" "}
                {number(data.leafyAnchor.cycle_days, 0)} days, and{" "}
                {number(data.leafyAnchor.crew_daily_g, 0)} g/day over{" "}
                {number(data.leafyAnchor.crew_area_m2, 2)} m² of crew area.
              </p>
              <div className="bench-grid">
                {Object.entries(data.freshProductivity || {}).map(([crop, row]) => (
                  <div className="bench-row" key={crop}>
                    <span>{crop}</span>
                    <strong>{number(row.fresh_g_per_m2_day, 1)}</strong>
                    <em>{number(row.cycle_days, 0)} d cycle</em>
                    <small>×{number(row.ratio_to_nasa_leafy_anchor, 2)}</small>
                  </div>
                ))}
              </div>
              <p className="muted">{data.leafyAnchor.note}</p>
            </Card>
          )}

          {data.co2 && (
            <Card title="CO₂ response factor" label="MODEL ASSUMPTION vs MEASURED OPTIMUM" action={<Wind size={16} />}>
              <div className="bench-grid">
                {data.co2.points.map((point) => (
                  <div className="bench-row" key={point.ppm}>
                    <span>{number(point.ppm, 0)} ppm</span>
                    <strong>×{number(point.factor, 2)}</strong>
                    <em>{point.ppm === data.co2.measuredOptimumPpm ? "measured optimum" : " "}</em>
                    <small>{point.ppm === data.co2.ambientPpm ? "reference" : ""}</small>
                  </div>
                ))}
              </div>
              <p className="muted">{data.co2.form}</p>
              <div className="warning-box">
                <p>{data.co2.limitation}</p>
              </div>
              <p className="muted">{data.co2.evidenceStatus}</p>
            </Card>
          )}

          <Card title="How to read these tables" action={<Scale size={16} />}>
            <ul className="reading-list">
              {(data.reading || []).map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
            <JsonDetails title="Inspect the benchmark payload" data={data} />
          </Card>
        </>
      )}
    </>
  );
}
