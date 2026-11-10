import { Card, number } from "../missionUI.jsx";
import { GrowthPlot } from "../../charts/GrowthPlot.jsx";
import { Limitations, JsonDetails } from "./moduleSupport.jsx";
import { WaterEvidencePanel } from "./WaterEvidencePanel.jsx";
import { RefreshCw, FlaskConical } from "lucide-react";
// Gravity and the radiation dose rate are deliberately not user controls here.
//
// Neither has a dataset behind it: a 2026-11-09 search of NASA sources found no crop fresh-weight
// dataset across fractional gravity (the ISS fractional-gravity work is transcriptomic and
// morphological) and no crop-yield dataset at habitat-relevant chronic dose rates. Rather than
// offer a slider whose response curve is invented, the world is chosen from the presets, where
// gravity and dose rate are carried as scenario context.
const CONTROLS = [
  [
    "waterAvailability",
    "Water availability",
    "%",
    "Fraction of estimated crop water demand supplied.",
  ],
  [
    "lightIntensity",
    "Light intensity · PPFD",
    "µmol/m²/s",
    "Simplified saturating response; not a crop-calibrated light-response curve.",
  ],
  [
    "lightHours",
    "Photoperiod",
    "h/day",
    "Daily light duration. Continuous illumination is not a safe crop recommendation.",
  ],
  [
    "co2Level",
    "CO₂ concentration",
    "ppm",
    "Assumed saturating response to cabin carbon dioxide.",
  ],
  [
    "temperature",
    "Air temperature",
    "°C",
    "Illustrative response around crop reference temperature.",
  ],
  [
    "humidity",
    "Relative humidity",
    "%",
    "Affects assumed vapor-pressure deficit and water use.",
  ],
  [
    "growingArea",
    "Cultivated area",
    "m²",
    "Yield and water scale linearly with area.",
  ],
  [
    "simulationDays",
    "Mission duration",
    "days",
    "Fixed crop cycles; no modeled maturity delay under stress.",
  ],
  [
    "waterRecyclingEfficiency",
    "Water recovery",
    "%",
    // The backend caps this at 98 because that is the best the ISS has demonstrated.
    "Fraction of supplied water recovered. The ceiling is 98 %, the ISS figure.",
  ],
];
export function Laboratory({ params, setParam, config, result, resetParams }) {
  return (
    <>
      <div className="module-intro">
        <span className="pill green">
          <FlaskConical size={12} />
          LIVE MATHEMATICAL SCENARIO
        </span>
        <p>
          Change a parameter to recompute growth, water balance, and gas
          exchange. Controls use ranges supplied by the backend. All habitats
          are pressurized and managed.
        </p>
      </div>
      <div className="module-grid">
        <Card title="Habitat parameters" label="SIMULATION LAB">
          <div className="control-grid">
            <label className="field">
              Crop
              <select
                value={params.crop}
                onChange={(e) => setParam("crop", e.target.value)}
              >
                {config.crops.map((c) => (
                  <option key={c.key} value={c.key}>
                    {c.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="field">
              Light spectrum
              <select
                value={params.lightSpectrum}
                onChange={(e) => setParam("lightSpectrum", e.target.value)}
              >
                <option value="balanced">Balanced</option>
                <option value="red-blue">Red + blue</option>
                <option value="white">White</option>
              </select>
              <small>
                Recorded annotation; no quantitative spectrum response is
                inferred.
              </small>
            </label>
            {CONTROLS.map(([key, label, unit, note]) => {
              const range = config.parameters[key];
              return range ? (
                <label key={key} className="field">
                  <span className="field-heading">
                    <span>
                      {label} <span className="muted">({unit})</span>
                    </span>
                    <input
                      aria-label={`${label} value`}
                      type="number"
                      min={range.min}
                      max={range.max}
                      step={range.step}
                      value={params[key]}
                      onChange={(e) => {
                        if (e.target.value !== "")
                          setParam(key, Number(e.target.value));
                      }}
                    />
                  </span>
                  <input
                    aria-label={label}
                    type="range"
                    min={range.min}
                    max={range.max}
                    step={range.step}
                    value={params[key]}
                    onChange={(e) => setParam(key, Number(e.target.value))}
                  />
                  <small>{note}</small>
                </label>
              ) : null;
            })}
          </div>
          <div className="module-actions">
            <button className="secondary-button" onClick={resetParams}>
              <RefreshCw size={14} />
              Reset parameters
            </button>
          </div>
        </Card>
        <div>
          <Card title="Mission response" label="LIVE ESTIMATE">
            <GrowthPlot result={result} />
            <div className="stat-pair">
              <span>Cumulative fresh biomass</span>
              <strong>{number(result?.cropYield)} g</strong>
            </div>
            <div className="stat-pair">
              <span>Net make-up water</span>
              <strong>
                {number(result?.lifeSupport?.water?.netConsumed)} L
              </strong>
            </div>
            <div className="stat-pair">
              <span>Daily light integral</span>
              <strong>
                {number(result?.environment?.dailyLightIntegralMolM2)}{" "}
                mol/m²/day
              </strong>
            </div>
            <div className="stat-pair">
              <span>Vapor-pressure deficit</span>
              <strong>
                {number(result?.environment?.vaporPressureDeficitKpa, 2)} kPa
              </strong>
            </div>
          </Card>
          <WaterEvidencePanel params={params} />
          {result?.warnings?.length > 0 && (
            <Limitations items={result.warnings} />
          )}
          <JsonDetails
            title="Reproducible mission configuration"
            data={params}
          />
        </div>
      </div>
    </>
  );
}
