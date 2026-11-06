import { Card } from "../missionUI.jsx";
import { JsonDetails } from "./moduleSupport.jsx";
import { ShieldCheck } from "lucide-react";
export function Methodology({ config, result }) {
  return (
    <Card
      title="Science you can inspect"
      label="METHODS & RESPONSIBLE USE"
      action={<ShieldCheck size={19} className="accent" />}
    >
      <div className="prose">
        <p>
          SpaceAgriSim is a research demonstration for exploring controlled
          agriculture in hypothetical space habitats. The simulator uses
          explicit mathematical assumptions; the NASA dataset registry and
          artifact-backed learning experiments are separate evidence streams.
        </p>
        <h3>Growth, water, and gas exchange</h3>
        <p>
          Crop-specific logistic curves repeat on fixed harvest cycles.
          Environment response factors scale fresh edible biomass. Water demand
          follows canopy development; supply equals demand multiplied by
          availability, and recovered water equals supply multiplied by recovery
          efficiency. Gas exchange is derived from dry-matter carbon
          accumulation and photosynthetic stoichiometry. It is not a measured
          cabin atmosphere forecast.
        </p>
        <h3>What a trained model can tell you</h3>
        <p>
          A NASA study can support a model only when actual paired features and
          target measurements exist. Omics files are not interchangeable with
          yield measurements. The mizuna experiment is crop- and study-specific.
          Sparse grouped validation and uncalibrated residual ranges do not
          establish operational reliability.
        </p>
        <h3>Uncertainty and coverage</h3>
        <p>
          Habitat simulations have no empirically calibrated prediction
          interval. Radiation quality, chronic stress, nutrient deficiencies,
          disease, power budgets, maturity delays, and engineered water delivery
          are incompletely represented. Partial-gravity yield curves are
          assumptions. The interface reports methods and missing coverage rather
          than an invented confidence percentage.
        </p>
        <h3>Official sources and reproducibility</h3>
        <p>
          <a
            href="https://osdr.nasa.gov/bio/repo/"
            target="_blank"
            rel="noreferrer"
          >
            NASA Open Science Data Repository
          </a>{" "}
          provides study metadata and source files. Downloads, checksums,
          transformations, grouping and model evaluation are recorded in the
          repository.{" "}
          <a
            href="https://github.com/meherabmehu/SpaceAgriSim/tree/feat/scientific-mission-platform/docs"
            target="_blank"
            rel="noreferrer"
          >
            Read the project documentation
          </a>{" "}
          for exact commands, sources, validation results, and limitations.
        </p>
        <h3>Responsible use</h3>
        <p>
          These outputs are educational and research-oriented. They are not
          NASA-certified, spacecraft life-support engineering, or flight
          operations advice. Shared scenario history is intended for
          demonstration configurations.
        </p>
      </div>
      <JsonDetails
        title="Backend formulas and constants"
        data={config.assumptions}
      />
      <JsonDetails
        title="Current output provenance"
        data={result?.provenance}
      />
    </Card>
  );
}
