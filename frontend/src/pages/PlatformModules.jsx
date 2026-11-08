import { lazy, Suspense } from "react";

const lazyExport = (loader, name) => lazy(() => loader().then((module) => ({ default: module[name] })));
const Laboratory = lazyExport(() => import("./modules/Laboratory.jsx"), "Laboratory");
const Comparison = lazyExport(() => import("./modules/Comparison.jsx"), "Comparison");
const Datasets = lazyExport(() => import("./modules/Evidence.jsx"), "Datasets");
const Predictions = lazyExport(() => import("./modules/Evidence.jsx"), "Predictions");
const Crops = lazyExport(() => import("./modules/Evidence.jsx"), "Crops");
const Analytics = lazyExport(() => import("./modules/Analytics.jsx"), "Analytics");
const Advisor = lazyExport(() => import("./modules/Advisor.jsx"), "Advisor");
const Methodology = lazyExport(() => import("./modules/Methodology.jsx"), "Methodology");
const ResearchAssistant = lazyExport(() => import("./modules/ResearchAssistant.jsx"), "ResearchAssistant");
const ScientificWorkflow = lazyExport(() => import("./modules/ScientificWorkflow.jsx"), "ScientificWorkflow");
const Account = lazyExport(() => import("./modules/Account.jsx"), "Account");
const SharedScenario = lazyExport(() => import("./modules/SharedScenario.jsx"), "SharedScenario");

const modules = { laboratory: Laboratory, comparison: Comparison, datasets: Datasets, predictions: Predictions, crops: Crops, analytics: Analytics, advisor: Advisor, assistant: ResearchAssistant, workflow: ScientificWorkflow, account: Account, methodology: Methodology };

export default function PlatformModules(props) {
  // A share link is a public read-only route (`#shared/<token>`), not a signed-in workspace page.
  if (typeof props.page === "string" && props.page.startsWith("shared/"))
    return <Suspense fallback={<section className="module-loading" aria-live="polite">Loading shared scenario…</section>}><SharedScenario token={props.page.slice("shared/".length)} /></Suspense>;
  const Module = modules[props.page] || Methodology;
  return <Suspense fallback={<section className="module-loading" aria-live="polite">Loading mission workspace…</section>}><Module {...props} /></Suspense>;
}
