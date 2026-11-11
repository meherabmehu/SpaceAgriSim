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
  const external = useResource("/external-validation");
  const closedLoop = useResource("/closed-loop");

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
              <p className="muted">{data.co2.limitation}</p>
              <p className="muted">{data.co2.evidenceStatus}</p>
            </Card>
          )}

          <RequestState state={closedLoop} secondary />
          {closedLoop.data?.available && <ClosedLoop body={closedLoop.data} />}

          <RequestState state={external} secondary />
          {external.data && <ExternalValidation body={external.data} />}

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

const VERDICT_LABEL = {
  "usable-after-transcription": "in domain — waiting on raw data",
  "used-external-check-failed": "scored — the model failed it",
  "out-of-domain": "outside the model's domain",
  "not-usable": "cannot be used",
};

/**
 * Whether anything outside the training data has held the lettuce model to account.
 *
 * The answer today is no, and saying that plainly is the point of the panel. A candidate source
 * that is in domain is shown as waiting on a verbatim transcription rather than quietly scored
 * against a study average, because the average would look like a validation and would not be one.
 */
function ExternalValidation({ body }) {
  const conclusion = body.conclusion || {};
  const check = body.domainCheck || {};
  const external = body.externalCheck || {};
  return (
    <Card title="External validation" label="SOURCES THE LETTUCE MODEL WAS NOT TRAINED ON">
      <div className="stat-pair">
        <span>Independent validation</span>
        <strong>
          {external.available
            ? external.verdict?.passed ? "passed" : "failed"
            : "not yet attempted"}
        </strong>
      </div>
      {external.available && (
        <>
          <p className="muted">
            {external.verdict.headline}. Held against {external.citation}, a greenhouse trial on a
            different continent that the model was never trained on, {external.metrics.observations}{" "}
            transcribed observations were scored at 28 days after transplanting.
          </p>
          <div className="bench-grid">
            {external.rows.map((row) => (
              <div className="bench-row" key={row.id}>
                <span>
                  {row.cultivar} · {row.level} level
                  <small className="muted"> · {number(row.ppfdUmol, 0)} µmol m⁻² s⁻¹</small>
                </span>
                <strong>{number(row.measuredG, 1)} g measured</strong>
                <em>{number(row.predictedG, 1)} g modelled</em>
                <small>×{number(row.ratio, 2)}</small>
              </div>
            ))}
          </div>
          <p className="muted">
            Worst case ×{number(external.metrics.worstRatio, 2)} ({external.metrics.worstObservation}),
            best case ×{number(external.metrics.closestRatio, 2)}. Mean absolute percentage error{" "}
            {number(external.metrics.meanAbsolutePercentageError, 0)} %.
          </p>
          <p className="muted">{external.verdict.consequence}</p>
          <div className="stat-pair">
            <span>Is the gap just the missing root temperature?</span>
            <strong>no</strong>
          </div>
          <p className="muted">
            The study reports air temperature but not root-zone temperature, so root temperature is
            assumed equal to air temperature ({number(external.conditions.airTemperatureC, 1)} °C) and
            flagged as an assumption. Probing it from 20 to 32 °C moves the median ratio only between
            ×{number(Math.min(...external.rootTemperatureSensitivity.map((p) => p.medianRatio)), 2)} and
            ×{number(Math.max(...external.rootTemperatureSensitivity.map((p) => p.medianRatio)), 2)},
            so the assumption cannot explain a median overshoot of ×{number(external.metrics.medianRatio, 2)}.
          </p>
          <ul className="reading-list">
            {external.structuralFindings.map((item) => (
              <li key={item.finding}>
                <strong>{item.finding}</strong> {item.evidence}
              </li>
            ))}
          </ul>
          <p className="muted">
            Provenance: {external.doi} ({external.license}), retrieved {external.retrievedAt},
            transcribed {external.transcribedAt}, source SHA-256 {external.retrievedSha256.slice(0, 12)}…
          </p>
        </>
      )}
      <p className="muted">{conclusion.statement}</p>
      <div className="bench-grid">
        {(body.candidates || []).map((candidate) => (
          <div className="bench-row" key={candidate.id}>
            <span>
              {candidate.title}
              <small className="muted"> · {candidate.publication}</small>
            </span>
            <strong>{VERDICT_LABEL[candidate.verdict] || candidate.verdict}</strong>
            <em>{candidate.doi}</em>
            <small>{candidate.reason}</small>
          </div>
        ))}
      </div>
      <p className="muted">{conclusion.whatThisDoesNotMean}</p>
      {check.available && (
        <p className="muted">{check.means}</p>
      )}
      <p className="muted">{body.scopeNote}</p>
      <JsonDetails title="Inspect the external-validation record" data={body} />
    </Card>
  );
}

/**
 * What NASA measured inside a sealed chamber: ethylene, and the water loop that keeps a crew alive.
 *
 * These are the two questions the simulator used to answer with a caveat instead of a number.
 * Neither is folded into the growth equations: ethylene is a hazard screen beside the simulation,
 * and the water figure bounds a control the simulator already exposes.
 */
function ClosedLoop({ body }) {
  const ethylene = body.ethylene;
  const water = body.water;
  const check = ethylene.chamberCheck;
  return (
    <Card title="Sealed-chamber atmosphere and water" label="NASA CELSS BIOMASS PRODUCTION CHAMBER · ISS ECLSS">
      <div className="stat-pair">
        <span>Ethylene measured in NASA&apos;s closed chamber</span>
        <strong>{ethylene.production.chamberConcentrationPpb.wheat} ppb wheat · {ethylene.production.chamberConcentrationPpb.soybean} ppb soybean</strong>
      </div>
      <div className="bench-grid">
        {ethylene.doseResponse.findings.map((finding) => (
          <div className="bench-row" key={finding.ethyleneNlPerL}>
            <span>Lettuce at {number(finding.ethyleneNlPerL, 0)} nL L⁻¹</span>
            <strong>{finding.dryWeightReductionPct} % dry weight lost</strong>
            <em>{finding.note || "measured in controlled chambers"}</em>
            <small />
          </div>
        ))}
      </div>
      <p className="muted">
        Peak production {ethylene.production.peakProduction.value}{" "}
        {ethylene.production.peakProduction.unit} ({ethylene.production.peakProduction.equivalent}),
        unadjusted for chamber leakage.
      </p>
      <div className="stat-pair">
        <span>No-leak bound for the same chamber volume</span>
        <strong>
          {number(check.boundedPpb, 0)} ppb → ×{number(check.ratioToUpperMeasured, 1)} the highest
          measured value
        </strong>
      </div>
      <p className="muted">{check.explanation}</p>

      <div className="stat-pair">
        <span>ISS water recovery</span>
        <strong>
          {number(water.issRecovery.currentPct, 0)} % now · {water.issRecovery.previousPct} % before
          the brine processor
        </strong>
      </div>
      <p className="muted">
        {water.implication.note} Anything above {number(water.issRecovery.currentPct, 0)} % is not a
        demonstrated capability, so the simulator&apos;s recycling control stops there.
      </p>
      <p className="muted">{body.scopeNote}</p>
      <JsonDetails title="Inspect the closed-loop measurements" data={body} />
    </Card>
  );
}
