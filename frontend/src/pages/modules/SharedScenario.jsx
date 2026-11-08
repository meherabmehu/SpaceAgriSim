import { useEffect, useState } from "react";
import { Link2, ShieldQuestion } from "lucide-react";
import { Card, number } from "../missionUI.jsx";
import { fetchSharedScenario } from "../../services/accountApi.ts";

/**
 * Public, read-only view of a shared scenario.
 *
 * It shows the configuration and the numbers that configuration reproduces, and nothing about the
 * account that shared it. The numbers are recomputed by the server from the stored configuration,
 * so this page can never drift from what the model currently produces.
 */
export function SharedScenario({ token }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    fetchSharedScenario(token)
      .then((shared) => active && setData(shared))
      .catch((err) => active && setError(err instanceof Error ? err.message : String(err)))
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
  }, [token]);

  if (loading)
    return <div className="skeleton" role="status">Loading the shared scenario…</div>;

  if (error)
    return (
      <Card title="This share link is not available">
        <p className="muted">{error}</p>
        <p className="muted">
          Share links expire and can be revoked by the account that created them. Ask for a new
          link, or build your own scenario in the simulation lab.
        </p>
        <a className="primary-button" href="#laboratory">
          Open the simulation lab
        </a>
      </Card>
    );

  const result = data.result;
  const harvest = result.harvest || {};
  const metrics = [
    ["Cumulative edible biomass", `${number(result.cropYield)} g`],
    ["Harvested", `${number(harvest.harvestedYield)} g`],
    ["Standing biomass", `${number(harvest.standingBiomass)} g`],
    ["Water supplied", `${number(result.waterUsed, 2)} L`],
    ["Water recovered", `${number(result.waterRecovered, 2)} L`],
    ["CO₂ fixed", `${number(result.co2Removed)} g`],
    ["O₂ produced", `${number(result.estimatedOxygenProduced)} g`],
  ];
  const configuration = data.configuration;

  return (
    <>
      <div className="module-intro">
        <span className="pill">
          <Link2 size={12} /> Shared scenario
        </span>
        <h2>{data.name}</h2>
        <p>{data.disclaimer}</p>
      </div>

      <Card title="Mission estimates">
        <dl className="metric-list">
          {metrics.map(([label, value]) => (
            <div key={label}>
              <dt>{label}</dt>
              <dd>{value}</dd>
            </div>
          ))}
        </dl>
      </Card>

      <Card title="Configuration as shared">
        <dl className="metric-list">
          {Object.entries(configuration).map(([key, value]) => (
            <div key={key}>
              <dt>{key}</dt>
              <dd>{String(value)}</dd>
            </div>
          ))}
        </dl>
        <p className="muted">
          Model {data.modelVersion} · saved {new Date(data.createdAt).toLocaleDateString()} · link
          expires {new Date(data.expiresAt).toLocaleDateString()}
        </p>
      </Card>

      <Card title="What this page does not claim" action={<ShieldQuestion size={16} />}>
        <div className="warning-box">
          {data.limitations.map((line) => (
            <p key={line}>{line}</p>
          ))}
        </div>
        <p className="muted">
          This link is read-only and shows no account information. Recompute the same configuration
          yourself in the simulation lab to check the numbers.
        </p>
      </Card>
    </>
  );
}
