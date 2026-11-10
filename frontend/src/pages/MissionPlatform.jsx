import { lazy, Suspense, useEffect, useState } from "react";
import {
  Activity,
  ArrowDownToLine,
  ArrowRight,
  Atom,
  BookOpen,
  Box,
  ChevronRight,
  CircleHelp,
  Database,
  Droplets,
  GitCompareArrows,
  FlaskConical,
  Globe2,
  Layers3,
  Leaf,
  Menu,
  MessageSquare,
  Orbit,
  Radio,
  Ruler,
  Rocket,
  ShieldCheck,
  Sparkles,
  Sprout,
  Sun,
  Wind,
  UserRound,
  Workflow,
  Waypoints,
  X,
} from "lucide-react";
import { useSimulationConfig } from "../hooks/useSimulationConfig.js";
import { useSimulationParams } from "../hooks/useSimulationParams.js";
import { useSimulation } from "../hooks/useSimulation.js";
import { api, downloadReport } from "../services/platformApi.ts";
import { authenticate, clearSession, logout, readSession } from "../services/auth.ts";
import { confirmVerification, requestPasswordReset, resetPassword } from "../services/accountApi.ts";
import PlatformModules from "./PlatformModules.jsx";
import { Card, number } from "./missionUI.jsx";
// The chart library is 69 kB gzipped and the curve only exists once a simulation has returned,
// so it is fetched with the first result instead of with the shell.
const GrowthPlot = lazy(() =>
  import("../charts/GrowthPlot.jsx").then((module) => ({ default: module.GrowthPlot })),
);

// Keep the greenhouse controls, its WebGL feature check, and Three.js out of
// the mission shell until a researcher actually opens the greenhouse route.
const DigitalTwin3D = lazy(() => import("../components/DigitalTwin3D.jsx"));

const NAV = [
  ["dashboard", "Mission control", Orbit],
  ["laboratory", "Simulation lab", FlaskConical],
  ["predictions", "AI prediction center", Atom],
  ["workflow", "Scientific workflow", Workflow],
  ["workflows", "Guided workflows", Waypoints],
  ["assistant", "Research assistant", MessageSquare],
  ["greenhouse", "3D greenhouse", Box],
  ["comparison", "World comparison", Globe2],
  ["crops", "Crop intelligence", Sprout],
  ["datasets", "NASA data explorer", Database],
  ["analytics", "Mission analytics", Activity],
  ["advisor", "Mission advisor", Sparkles],
  ["benchmarks", "Benchmark transparency", Ruler],
  ["models", "Model comparison", GitCompareArrows],
  ["account", "Account & sharing", UserRound],
  ["methodology", "Methodology", BookOpen],
];
// Phase 30 removed the fractional-gravity response, so a "world" is a radiation environment and
// nothing else. The names stay because the dose rates are the ones those environments are quoted at.
const WORLDS = {
  Earth: { radiation: 0.01 },
  Moon: { radiation: 0.5 },
  Mars: { radiation: 0.2 },
  Orbit: { radiation: 0.3 },
};

export default function MissionPlatform() {
  const { config, status: configStatus, error: configError, retry: retryConfig } = useSimulationConfig();
  const { params, setParam, resetParams } = useSimulationParams(config);
  const { result, error, isLoading, retry } = useSimulation(params);
  const [page, setPage] = useState(() => location.hash.slice(1) || "dashboard");
  const [mobile, setMobile] = useState(false);
  const world = Object.keys(WORLDS).find(name => WORLDS[name].radiation === params.radiation) || 'Custom';
  const [notice, setNotice] = useState("");
  const [registry, setRegistry] = useState(null);
  const [models, setModels] = useState(null);
  const [registryError, setRegistryError] = useState("");
  const [session, setSession] = useState(() => readSession());
  const [authMode, setAuthMode] = useState(null);
  // Account email links arrive as `#reset?token=…` / `#verify?token=…`. The app is static, so the
  // fragment is the only part of the URL that reliably loads it; the token is consumed here and
  // the corresponding dialog opens over whichever page the fragment names.
  const [accountToken, setAccountToken] = useState("");
  useEffect(() => {
    const apply = () => {
      const raw = location.hash.slice(1) || "dashboard";
      const [route, query] = raw.split("?");
      const token = new URLSearchParams(query || "").get("token") || "";
      if (token && (route === "reset" || route === "verify")) {
        setAccountToken(token);
        setAuthMode(route);
        setPage(route);
        return;
      }
      setPage(raw);
    };
    apply();
    window.addEventListener("hashchange", apply);
    return () => window.removeEventListener("hashchange", apply);
  }, []);
  useEffect(() => {
    const controller = new AbortController();
    Promise.all([
      api("/datasets", undefined, controller.signal),
      api("/models", undefined, controller.signal),
    ])
      .then(([data, modelData]) => {
        setRegistry(data);
        setModels(modelData);
      })
      .catch((err) => {
        if (err.name !== "AbortError") setRegistryError(err.message);
      });
    return () => controller.abort();
  }, []);
  const navigate = (next) => {
    location.hash = next;
    setPage(next);
    setMobile(false);
    window.scrollTo({ top: 0, behavior: "instant" });
  };
  const selectWorld = (name) => {
    Object.entries(WORLDS[name]).forEach(([key, value]) =>
      setParam(key, value),
    );
  };
  const exportReport = async (format) => {
    try {
      await downloadReport(format, params);
      setNotice(`${format.toUpperCase()} report downloaded.`);
    } catch (err) {
      setNotice(err.message);
    }
  };
  const saveScenario = async () => {
    if (!session) {
      setAuthMode("login");
      setNotice("Sign in to save a private scenario.");
      return;
    }
    try {
      await api("/scenarios", {
        name: `${world} · ${params.crop} · ${params.simulationDays}d`,
        configuration: params,
      });
      setNotice("Scenario saved to mission history.");
    } catch (err) {
      setNotice(err.message);
    }
  };
  const title = page.startsWith("shared/")
    ? "Shared scenario"
    : page === "reset" || page === "verify"
      ? "Account access"
      : page === "operator"
        ? "Operator console"
      : NAV.find((n) => n[0] === page)?.[1] || "Mission control";
  const shared = {
    session,
    onRequireSignIn: () => setAuthMode("login"),
    params,
    setParam,
    config,
    result,
    registry,
    models,
    registryError,
    navigate,
    exportReport,
    resetParams,
    setNotice,
  };
  return (
    <div className={`platform world-${world.toLowerCase()}`}>
      <a className="skip-link" href="#mission-content">
        Skip to mission content
      </a>
      {mobile && (
        <button
          className="nav-scrim"
          aria-label="Close navigation"
          onClick={() => setMobile(false)}
        />
      )}
      <aside className={`mission-sidebar ${mobile ? "open" : ""}`}>
        <a
          href="#dashboard"
          className="brand"
          onClick={() => navigate("dashboard")}
        >
          <span className="brand-symbol">
            <Orbit size={27} />
          </span>
          <span>
            SpaceAgri<span className="brand-light">Sim</span>
            <small>GROW BEYOND EARTH</small>
          </span>
        </a>
        <div className="workspace">
          <span className="workspace-icon">
            <Rocket size={18} />
          </span>
          <div>
            Research workspace<small>EXPLORATION PROGRAM</small>
          </div>
          <ChevronRight size={14} />
        </div>
        <span className="nav-label">MISSION WORKSPACE</span>
        <nav aria-label="Main navigation">
          {NAV.map(([id, label, Icon]) => (
            <a
              key={id}
              href={`#${id}`}
              onClick={(e) => {
                e.preventDefault();
                navigate(id);
              }}
              aria-current={page === id ? "page" : undefined}
            >
              <Icon size={18} />
              <span>{label}</span>
              {id === "predictions" && <small>ML</small>}
              {id === "assistant" && <small>AI</small>}
            </a>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="source-note">
            <ShieldCheck size={19} />
            <div>
              Science, with context.
              <p>
                Every estimate has a method.
                <br />
                Every dataset has a source.
              </p>
            </div>
          </div>
          <div className="sidebar-footer">
            <span className="avatar">SA</span>
            <div>
              SpaceAgriSim<small>RESEARCH EDITION · V0.2</small>
            </div>
            <CircleHelp size={17} />
          </div>
        </div>
      </aside>
      <div className="mission-workspace">
        <header className="mission-topbar">
          <div className="breadcrumb">
            <button
              className="icon-button mobile-menu"
              aria-label="Open navigation"
              onClick={() => setMobile(true)}
            >
              <Menu size={20} />
            </button>
            <span>Workspace</span>
            <ChevronRight size={13} />
            <strong>{title}</strong>
          </div>
          <div className="topbar-right">
            <span className={`connection ${error || configStatus === "error" ? "offline" : ""}`}>
              <i />
              {error
                ? "API unavailable"
                : configStatus === "error"
                  ? "Configuration unavailable"
                  : isLoading
                    ? "Computing"
                    : configStatus === "live"
                      ? "API connected"
                      : "Connecting"}
            </span>
            <span className="research-tag">RESEARCH PREVIEW</span>
            {session ? (
              <button className="icon-button" title={`Signed in as ${session.user.email}`} onClick={async () => { await logout(); setSession(null); setNotice("Signed out."); }}>
                Sign out
              </button>
            ) : <button className="icon-button" onClick={() => setAuthMode("login")}>Sign in</button>}
            <span className="avatar small">SA</span>
          </div>
        </header>
        <main id="mission-content" className="mission-content">
          <div className="page-title">
            <div>
              <div className="eyebrow">
                <span className="tiny-line" />
                SPACE AGRICULTURE & LIFE SUPPORT
              </div>
              <h1>
                {title}
                <span className="title-dot">.</span>
              </h1>
              <p>
                {page === "dashboard"
                  ? "A new frontier for growing. Explore your habitat, understand the trade-offs."
                  : "Explore the evidence. Configure your mission. Understand every estimate."}
              </p>
            </div>
            <button
              className="secondary-button"
              onClick={() => exportReport("json")}
              disabled={!result || isLoading || !!error}
            >
              <ArrowDownToLine size={16} />
              Export mission
            </button>
          </div>
          {notice && (
            <div className="notice" role="status">
              {notice}
              <button
                className="icon-button"
                onClick={() => setNotice("")}
                aria-label="Dismiss notification"
              >
                <X size={15} />
              </button>
            </div>
          )}
          {error && (
            <div className="error-banner" role="alert">
              <Radio size={18} />
              <span>
                {error.message}{" "}
                {result
                  ? "Results shown are from the last successful run."
                  : ""}
              </span>
              <button onClick={retry}>Retry connection</button>
            </div>
          )}
          {configStatus === "loading" && (
            <p className="fallback-note" role="status">
              Connecting to the simulation API; control ranges load on connection.
            </p>
          )}
          {configStatus === "error" && (
            <div className="error-banner" role="alert">
              <Radio size={18} />
              <span>
                Control ranges could not be loaded
                {configError?.message ? `: ${configError.message}` : "."}{" "}
                The sliders are showing bundled placeholders rather than the API&apos;s
                values, so running and saving are disabled until the API answers.
              </span>
              <button onClick={retryConfig}>Retry</button>
            </div>
          )}
          <div
            className={`simulation-content ${isLoading ? "updating" : ""}`}
            aria-busy={isLoading}
          >
            {page === "dashboard" ? (
              <>
                <section className="mission-hero">
                  <div className="hero-grid" />
                  <div className="orbital-path" />
                  <div className="planet" aria-hidden="true">
                    <div className="planet-shadow" />
                  </div>
                  <div className="hero-copy">
                    <span className="hero-tag">
                      <i />
                      YOUR NEXT HARVEST STARTS HERE
                    </span>
                    <h2>
                      Small seeds.
                      <br />
                      Extraordinary possibilities.
                    </h2>
                    <p>
                      Design a thriving habitat beyond Earth.
                      <br />
                      Simulate crop growth, resources, and the systems that
                      sustain them.
                    </p>
                    <button
                      className="primary-button"
                      onClick={() => navigate("laboratory")}
                    >
                      Open simulation lab
                      <ArrowRight size={16} />
                    </button>
                    <div className="hero-caption">
                      <ShieldCheck size={14} />
                      NASA data informed · Assumptions made visible
                    </div>
                  </div>
                  <div className="orbit-caption">
                    <span className="orbit-cross">+</span>EXPLORING WHAT GROWS
                    NEXT<small><a href="https://www.nasa.gov/image-article/blue-marble-2012/" target="_blank" rel="noreferrer">EARTH IMAGE · NASA/NOAA/GSFC/SUOMI NPP/VIIRS/NORMAN KURING</a></small>
                  </div>
                </section>
                <div className="environment-strip">
                  <span className="eyebrow">YOUR ENVIRONMENT</span>
                  <div className="world-options">
                    {Object.keys(WORLDS).map((name) => (
                      <button
                        key={name}
                        className={world === name ? "selected" : ""}
                        onClick={() => selectWorld(name)}
                      >
                        <span className={`world-orb ${name.toLowerCase()}`} />
                        {name}
                        {world === name && (
                          <span className="selected-check">✓</span>
                        )}
                      </button>
                    ))}
                  </div>
                  <span className="strip-caption">
                    Pressurized habitat · Illustrative exposure presets
                  </span>
                </div>
                <div className="metric-grid">
                  <Metric
                    icon={Sprout}
                    label="Predicted biomass"
                    value={number(result?.cropYield / 1000)}
                    unit="kg"
                    caption="Cumulative edible fresh mass"
                    color="green"
                    hasResult={!!result}
                  />
                  <Metric
                    icon={Droplets}
                    label="Water supplied"
                    value={number(result?.waterUsed)}
                    unit="L"
                    caption={
                      result
                        ? `${number(result.lifeSupport?.water?.netConsumed)} L net make-up water`
                        : "Awaiting simulation"
                    }
                    color="blue"
                    hasResult={!!result}
                  />
                  <Metric
                    icon={Wind}
                    label="Oxygen estimate"
                    value={number(result?.estimatedOxygenProduced)}
                    unit="g"
                    caption="Biomass-derived fixation proxy"
                    color="violet"
                    hasResult={!!result}
                  />
                  <Metric
                    icon={Leaf}
                    label="Harvested yield"
                    value={number(result?.harvest?.harvestedYield / 1000)}
                    unit="kg"
                    caption={
                      result
                        ? `Next harvest · mission day ${result.harvest.nextHarvestDay}`
                        : "Awaiting simulation"
                    }
                    color="amber"
                    hasResult={!!result}
                  />
                </div>
                <div className="dashboard-grid">
                  <Card
                    title="Growth trajectory"
                    label="BIOMASS FORECAST"
                    action={
                      <span className="pill green">
                        <i />
                        Mechanistic estimate
                      </span>
                    }
                  >
                    <div className="chart-summary">
                      <strong>
                        {result ? number(result.cropYield / 1000) : "—"}{" "}
                        <small>kg</small>
                      </strong>
                      <span>
                        total fresh biomass by day {params.simulationDays}
                      </span>
                      <div className="chart-legend">
                        <span>
                          <i />
                          Selected habitat
                        </span>
                        <span>
                          <i />
                          Earth reference
                        </span>
                      </div>
                    </div>
                    <Suspense
                      fallback={
                        <div className="growth-plot" aria-live="polite">
                          <section className="module-loading">Loading growth curve…</section>
                        </div>
                      }
                    >
                      <GrowthPlot result={result} />
                    </Suspense>
                    <div className="chart-footer">
                      <ShieldCheck size={14} />
                      Scenario output · No calibrated confidence interval
                    </div>
                  </Card>
                  <Card
                    title="Mission configuration"
                    label="ACTIVE EXPERIMENT"
                    action={<FlaskConical size={18} className="muted" />}
                  >
                    <label className="crop-field">
                      Growing crop
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
                    <div className="config-summary">
                      <div>
                        <Globe2 size={16} />
                        <span>Environment</span>
                        <strong>{world}</strong>
                      </div>
                      <div>
                        <Sun size={16} />
                        <span>Photoperiod</span>
                        <strong>{params.lightHours} h/day</strong>
                      </div>
                      <div>
                        <Layers3 size={16} />
                        <span>Growing area</span>
                        <strong>{params.growingArea} m²</strong>
                      </div>
                      <div>
                        <Activity size={16} />
                        <span>Mission window</span>
                        <strong>{params.simulationDays} days</strong>
                      </div>
                    </div>
                    <button
                      className="wide-link"
                      onClick={() => navigate("laboratory")}
                    >
                      Adjust mission parameters
                      <ArrowRight size={15} />
                    </button>
                  </Card>
                </div>
                <div className="dashboard-grid lower-grid">
                  <Card
                    title="Your mission, at a glance"
                    label="HARVEST TIMELINE"
                  >
                    <div className="timeline">
                      <span className="timeline-node active" />
                      <div className="timeline-track">
                        <i
                          style={{
                            width: result
                              ? `${Math.min(100, (params.simulationDays / result.crop.growthDurationDays) * 100)}%`
                              : "0%",
                          }}
                        />
                      </div>
                      <span className="timeline-node" />
                      <div className="timeline-labels">
                        <div>
                          <strong>Planting</strong>
                          <small>DAY 0</small>
                        </div>
                        <div>
                          <strong>Current window</strong>
                          <small>DAY {params.simulationDays}</small>
                        </div>
                        <div>
                          <strong>First harvest</strong>
                          <small>
                            DAY {result?.crop.growthDurationDays || "—"}
                          </small>
                        </div>
                      </div>
                    </div>
                    <p className="muted fine">
                      Cycle timing is fixed by the crop profile. Stress reduces
                      yield; delayed maturity is not modeled.
                    </p>
                  </Card>
                  <Card
                    title="Scientific signal"
                    label="MISSION ADVISOR"
                    action={<Sparkles size={18} className="accent" />}
                  >
                    <p className="insight-copy">
                      {result?.lifeSupport?.water?.deficitPercent > 0
                        ? `${number(result.lifeSupport.water.deficitPercent)}% of modeled water demand is unmet. Explore water availability before interpreting biomass estimates.`
                        : "Start with the evidence. Habitat predictions are mathematical scenarios; NASA study data is available separately for inspection."}
                    </p>
                    <button
                      className="wide-link"
                      onClick={() => navigate("advisor")}
                    >
                      Explore mission insights
                      <ArrowRight size={15} />
                    </button>
                  </Card>
                </div>
                <div className="evidence-bar">
                  <Database size={18} />
                  <div>
                    <strong>
                      {registry
                        ? `${registry.datasets?.length || 0} registered NASA studies`
                        : "NASA registry connecting"}
                    </strong>
                    <span>
                      Traceable sources. Separate measurements and estimates.
                    </span>
                  </div>
                  <button onClick={() => navigate("datasets")}>
                    Explore datasets
                    <ArrowRight size={15} />
                  </button>
                </div>
              </>
            ) : page === "greenhouse" ? (
              <>
                <div className="module-intro">
                  <span className="pill green">SIMULATION SYNCHRONIZED</span>
                  <p>
                    Plant scale follows simulated standing biomass. Flow
                    indicators illustrate settings; they are not measured fluid
                    dynamics.
                  </p>
                </div>
                <Suspense fallback={<section className="module-loading" aria-live="polite">Loading growth chamber…</section>}>
                  <DigitalTwin3D result={result} />
                </Suspense>
              </>
            ) : (
              <PlatformModules page={page} {...shared} />
            )}
          </div>
          <footer className="platform-footer">
            <span>
              <Orbit size={14} />
              GROWING THE FUTURE, RESPONSIBLY.
            </span>
            <span>
              Research simulation · Not validated for spacecraft operations
            </span>
            <button
              onClick={saveScenario}
              disabled={!result || isLoading || !!error || configStatus !== "live" || config.capabilities?.historyWritesEnabled === false}
              title={
                configStatus !== "live"
                  ? "The API configuration has not loaded, so scenario saving is unavailable."
                  : config.capabilities?.historyWritesEnabled === false
                    ? "Hosted history is read only. Configure a durable database and enable history writes to save scenarios."
                    : "Save current configuration to shared history"
              }
            >
              {configStatus !== "live"
                ? "Saving unavailable"
                : config.capabilities?.historyWritesEnabled === false
                  ? "History read only"
                  : "Save scenario"}
              <ChevronRight size={13} />
            </button>
          </footer>
          {authMode && <AuthDialog token={accountToken} mode={authMode} onModeChange={setAuthMode} onClose={() => setAuthMode(null)} onAuthenticated={(next) => { setSession(next); setAuthMode(null); setNotice(next.user.emailVerified === false ? "Signed in. Your scenarios are private to your account. Verify your email address from Account & sharing." : "Signed in. Your scenarios are private to your account."); }} />}
        </main>
      </div>
    </div>
  );
}

function AuthDialog({ token: initialToken = "", mode, onModeChange, onClose, onAuthenticated }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [token, setToken] = useState(initialToken);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const credentials = mode === "login" || mode === "register";
  const heading = {
    login: "Sign in",
    register: "Create account",
    forgot: "Reset your password",
    reset: "Choose a new password",
    verify: "Verify your email address",
  }[mode] || "Account access";

  const submit = async (event) => {
    event.preventDefault();
    setBusy(true);
    setError("");
    setMessage("");
    try {
      if (credentials) {
        onAuthenticated(await authenticate(mode, email, password));
        return;
      }
      if (mode === "forgot") {
        const response = await requestPasswordReset(email.trim());
        setMessage(
          response.debugToken
            ? `No mail server is configured on this development server, so here is the reset token directly: ${response.debugToken}`
            : "If that address has an account, a reset link is on its way. The link works once and expires shortly.",
        );
        return;
      }
      if (mode === "reset") {
        const response = await resetPassword(token.trim(), password);
        clearSession();
        setMessage(`${response.note} You can sign in with the new password now.`);
        setPassword("");
        return;
      }
      if (mode === "verify") {
        await confirmVerification(token.trim());
        setMessage("Email address verified. This browser will show the new status after you sign in again.");
        return;
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  return <div className="fixed inset-0 z-50 grid place-items-center bg-slate-950/80 p-4" role="dialog" aria-modal="true" aria-label="Account access">
    <form onSubmit={submit} className="w-full max-w-sm space-y-4 rounded border border-line bg-space-900 p-5 shadow-2xl">
      <div className="flex items-center justify-between"><h2 className="text-lg text-slate-100">{heading}</h2><button type="button" className="icon-button" onClick={onClose}>Close</button></div>
      <p className="text-xs text-slate-400">Public science tools remain available without an account. Accounts protect saved scenarios.</p>
      {(mode === "login" || mode === "register" || mode === "forgot") && (
        <label className="block text-xs text-slate-300">Email<input required type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} className="mt-1 w-full rounded border border-line-strong bg-space-950 p-2" /></label>
      )}
      {(credentials || mode === "reset") && (
        <label className="block text-xs text-slate-300">{mode === "reset" ? "New password" : "Password"}<input required minLength="12" type="password" autoComplete={credentials ? "current-password" : "new-password"} value={password} onChange={(e) => setPassword(e.target.value)} className="mt-1 w-full rounded border border-line-strong bg-space-950 p-2" /></label>
      )}
      {(mode === "reset" || mode === "verify") && (
        <label className="block text-xs text-slate-300">Link token<input required value={token} onChange={(e) => setToken(e.target.value)} className="mt-1 w-full rounded border border-line-strong bg-space-950 p-2 font-mono text-[11px]" placeholder="Paste the token from your email" /></label>
      )}
      {mode === "reset" && <p className="text-xs text-slate-400">Every session signed in with the old password stops working as soon as you submit.</p>}
      {mode === "verify" && <p className="text-xs text-slate-400">Verification records that the address is yours. It does not lock you out of anything.</p>}
      {error && <p className="text-xs text-warn" role="alert">{error}</p>}
      {message && <p className="text-xs text-slate-200" role="status">{message}</p>}
      <button disabled={busy} className="primary-button" type="submit">
        {busy ? "Working…" : heading}
      </button>
      {mode === "login" && (
        <button type="button" className="text-xs text-accent" onClick={() => { setError(""); setMessage(""); onModeChange("forgot"); }}>
          Forgot your password?
        </button>
      )}
      {mode === "forgot" && (
        <button type="button" className="text-xs text-accent" onClick={() => { setError(""); setMessage(""); onModeChange("login"); }}>
          Back to sign in
        </button>
      )}
      {credentials && (
        <button type="button" className="text-xs text-accent" onClick={() => { setError(""); setMessage(""); onModeChange(mode === "login" ? "register" : "login"); }}>
          {mode === "login" ? "Create account" : "I already have an account"}
        </button>
      )}
      <button type="button" className="text-xs text-accent" onClick={() => { setError(""); onClose(); }}>Cancel</button>
    </form>
  </div>;
}
function Metric({ icon: Icon, label, value, unit, caption, color, hasResult }) {
  return (
    <section className={`metric-tile ${color}`}>
      <div className="metric-top">
        <span>{label}</span>
        <span className="metric-icon">
          <Icon size={18} />
        </span>
      </div>
      <div className="metric-value">
        {hasResult ? value : "—"}
        <small>{unit}</small>
      </div>
      <p>
        <span className="metric-dot" />
        {caption}
      </p>
    </section>
  );
}
