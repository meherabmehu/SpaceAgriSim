# Model evaluation

Evaluation emphasizes leakage control and honest baselines.

- **Mizuna:** sample groups were held out together. Its negative R2 and worse-than-baseline MAE mean it is not useful as a crop-production predictor; the UI and API expose that limitation.
- **Tomato:** plant-grouped validation avoids treating samples from one plant as independent. High discrimination of recorded flight context does not establish causality, stress prediction or yield prediction; confounding may remain.
- **Lettuce:** nested leave-one-experiment-out validation prevents a treatment/plant pattern from leaking across folds. With only four experiments, uncertainty remains large despite R2 0.812. The model rejects outside-domain inputs and labels tip-burn-omitted combinations unsupported.

Metrics are retained in versioned model artifacts and OOF predictions are stored at `ml/evaluation/`. No metric is presented as a spaceflight performance guarantee.

