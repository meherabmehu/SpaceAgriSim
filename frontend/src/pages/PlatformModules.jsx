import { Laboratory } from "./modules/Laboratory.jsx";
import { Comparison } from "./modules/Comparison.jsx";
import { Datasets, Predictions, Crops } from "./modules/Evidence.jsx";
import { Analytics } from "./modules/Analytics.jsx";
import { Advisor } from "./modules/Advisor.jsx";
import { Methodology } from "./modules/Methodology.jsx";
export default function PlatformModules(props) {
  const { page } = props;
  if (page === "laboratory") return <Laboratory {...props} />;
  if (page === "comparison") return <Comparison {...props} />;
  if (page === "datasets") return <Datasets {...props} />;
  if (page === "predictions") return <Predictions {...props} />;
  if (page === "crops") return <Crops {...props} />;
  if (page === "analytics") return <Analytics {...props} />;
  if (page === "advisor") return <Advisor {...props} />;
  return <Methodology {...props} />;
}
