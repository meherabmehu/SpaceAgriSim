// Shared formatting helper is pure and does not carry React state.
// eslint-disable-next-line react-refresh/only-export-components
export const number = (value, digits = 1) =>
  value == null || !Number.isFinite(Number(value))
    ? "—"
    : Number(value).toLocaleString(undefined, {
        maximumFractionDigits: digits,
      });
export function Card({ title, label, action, children, className = "" }) {
  return (
    <section className={`mission-card ${className}`}>
      <div className="card-heading">
        <div>
          {label && <span className="eyebrow">{label}</span>}
          <h2>{title}</h2>
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}
