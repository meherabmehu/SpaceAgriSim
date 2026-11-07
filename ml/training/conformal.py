"""Conformal prediction for the platform's regression models.

Why this module exists
----------------------
Phase 9 shipped prediction intervals that were honest about being uncalibrated,
and the honesty exposed a defect: the two microbial models state a 90 % interval
and deliver 81 % and 85 % coverage on held-out groups. A stated 90 % interval
covering 85 % of held-out points is not a caveat to repeat, it is a bug to fix.

The cause is arithmetic, not bad luck. Split conformal calibrates the interval on
one held-out slice of the *training* data — here 17 of 35 pillows, giving 70
residuals — and then a finite-sample quantile of 70 residuals is a noisy estimate
of the 90th percentile. Two things make it worse:

  * the calibration slice is small, and
  * with grouped data the effective sample size is the number of *groups*, not the
    number of rows, so 70 residuals from 17 pillows behave more like 17.

Cross-conformal (CV+) uses every training point for calibration instead of a
slice, at the cost of fitting K models instead of two. For a dataset this small
that trade is obviously correct.

What is implemented
-------------------
`split`      the Phase 9 method, kept so the comparison is measured not asserted
`cv_plus`    grouped cross-conformal: out-of-fold absolute residuals, all rows used
`mondrian`   grouped cross-conformal, with the quantile taken within each stratum
             (bacterial campaign for the microbial task, experiment for lettuce)

Everything is evaluated under the same outer leave-group-out protocol, so the
methods see identical held-out data. No calibration data ever comes from a held-
out group, and the inner folds are group-aware, so a pillow never contributes to
its own calibration residual.

What this module does NOT claim
-------------------------------
Conformal coverage is a marginal guarantee under exchangeability. Multiple tissues
from one pillow are not exchangeable with a new pillow, and two campaigns are not a
sample of campaigns. Coverage measured here is therefore *empirical held-out
coverage on the groups available*, which is the strongest statement this data can
support. It is reported as such, and nothing here is described as a guarantee.
"""
from __future__ import annotations

import numpy as np
from sklearn.model_selection import GroupKFold


def _quantile(residuals: np.ndarray, alpha: float) -> float:
    """Finite-sample conformal quantile of absolute residuals.

    Uses the ``ceil((n + 1)(1 - alpha)) / n`` order statistic, which is what gives
    split conformal its coverage property; taking a plain ``np.quantile`` throws
    that away at small ``n`` and is a common way to silently undercover.

    When the required order statistic falls past the end of the sample — which
    happens below ``(2 - alpha) / alpha`` residuals, i.e. under 19 at 90 % — the
    textbook answer is an infinite interval. That is unshippable, so the maximum
    observed residual is used instead. It is the most conservative *finite* choice
    available from the calibration data and can only widen the interval, so it
    cannot manufacture coverage that is not there.
    """
    n = len(residuals)
    if n == 0:
        return float("inf")
    level = np.ceil((n + 1) * (1 - alpha)) / n
    if level >= 1.0:
        return float(np.max(residuals))
    return float(np.sort(residuals)[min(int(np.ceil(level * n)) - 1, n - 1)])


def _group_folds(groups: np.ndarray, n_splits: int, seed: int) -> list[tuple]:
    unique = np.unique(groups)
    n_splits = max(2, min(n_splits, len(unique)))
    return list(GroupKFold(n_splits=n_splits).split(np.zeros(len(groups)), groups=groups))


def out_of_fold_residuals(fit_predict, x, y, groups, n_splits=5, seed=0):
    """Group-aware out-of-fold absolute residuals.

    The inner folds keep whole groups together, so a pillow's calibration residual
    comes from a model that never saw that pillow.
    """
    residuals = np.full(len(y), np.nan)
    for train, test in _group_folds(groups, n_splits, seed):
        assert not set(groups[train]) & set(groups[test]), "group leakage in inner folds"
        prediction = fit_predict(x[train], y[train], x[test])
        residuals[test] = np.abs(y[test] - prediction)
    assert not np.isnan(residuals).any(), "uncovered rows in out-of-fold residuals"
    return residuals


def split_conformal(fit_predict, x_train, y_train, groups_train, x_test,
                    alpha=0.10, calibration_fraction=0.4, seed=0):
    """The Phase 9 method: fit on part of the training groups, calibrate on the rest."""
    folds = _group_folds(groups_train, max(2, int(round(1 / calibration_fraction))), seed)
    proper, calibration = folds[0]
    prediction = fit_predict(x_train[proper], y_train[proper], x_test)
    calibration_prediction = fit_predict(x_train[proper], y_train[proper], x_train[calibration])
    residuals = np.abs(y_train[calibration] - calibration_prediction)
    radius = _quantile(residuals, alpha)
    return prediction, radius, radius, {"calibrationResiduals": int(len(residuals)),
                                        "calibrationGroups": int(len(np.unique(groups_train[calibration])))}


def cv_plus_conformal(fit_predict, x_train, y_train, groups_train, x_test,
                      alpha=0.10, inner_folds=5, seed=0, strata_train=None):
    """Grouped cross-conformal. Every training row calibrates the interval."""
    residuals = out_of_fold_residuals(fit_predict, x_train, y_train, groups_train,
                                      n_splits=inner_folds, seed=seed)
    prediction = fit_predict(x_train, y_train, x_test)
    radius = _quantile(residuals, alpha)
    detail = {"calibrationResiduals": int(len(residuals)),
              "calibrationGroups": int(len(np.unique(groups_train)))}

    if strata_train is None:
        return prediction, radius, radius, detail

    # Mondrian: a separate quantile inside each stratum, falling back to the pooled
    # quantile when a stratum cannot support one. The fallback is recorded rather
    # than hidden, because a silently pooled stratum is not a conditional interval.
    pooled = radius
    strata = np.asarray(strata_train)
    # ceil((n+1)(1-alpha))/n reaches 1 — the point where a stratum needs the
    # maximum-residual fallback above — exactly when n <= (2-alpha)/alpha, i.e. below
    # 19 residuals at 90 %. Strata that small get the pooled radius, which has more
    # calibration data, and the fallback is recorded so a reader can see it.
    minimum = int(np.ceil((2 - alpha) / alpha)) + 1
    per_stratum, fallbacks = {}, []
    for value in sorted(set(strata.tolist())):
        mask = strata == value
        if mask.sum() < minimum:
            per_stratum[value] = {"radius": pooled, "n": int(mask.sum()),
                                  "fallback": f"pooled (stratum has {int(mask.sum())} "
                                              f"residuals, {minimum} needed)"}
            fallbacks.append(value)
            continue
        per_stratum[value] = {"radius": _quantile(residuals[mask], alpha),
                              "n": int(mask.sum()), "fallback": None}
    detail.update({"perStratum": per_stratum, "pooledFallbackFor": fallbacks})
    return prediction, radius, per_stratum, detail


def group_level_conformal(fit_predict, x_train, y_train, groups_train, x_test,
                          alpha=0.10, inner_folds=5, seed=0):
    """Cross-conformal whose exchangeability unit is the biological group.

    A row-level interval answers "will this row be covered?", which is the wrong
    question when the rows are tissues from the same plant: a user predicting a new
    pillow needs an interval that covers *that pillow*. Conformal exchangeability
    holds for groups, not for rows within a group, so the calibration statistic here
    is the group's worst residual rather than each row's residual.

    This yields wider intervals by construction. It is not a trick to reach the
    nominal number — it is the same method applied at the unit the claim is about,
    and it is reported next to the row-level figures so the cost is visible.
    """
    residuals = out_of_fold_residuals(fit_predict, x_train, y_train, groups_train,
                                      n_splits=inner_folds, seed=seed)
    group_worst = np.array([residuals[groups_train == group].max()
                            for group in np.unique(groups_train)])
    prediction = fit_predict(x_train, y_train, x_test)
    radius = _quantile(group_worst, alpha)
    return prediction, radius, radius, {"calibrationGroups": int(len(group_worst)),
                                        "calibrationResiduals": int(len(group_worst)),
                                        "unit": "group (worst residual within group)"}


def evaluate(fit_predict, x, y, groups, alpha=0.10, outer_folds=5, inner_folds=5,
             strata=None, seed=0) -> dict:
    """Compare the three methods under one shared leave-group-out protocol.

    For every outer fold the training groups are used for everything the method
    needs (fitting and calibration) and the held-out groups are used only to score
    coverage. Identical outer folds for every method, so the comparison is paired.
    """
    methods = {"split": [], "cv_plus": [], "mondrian": [], "group_level": []}
    detail = {"split": {}, "cv_plus": {}, "mondrian": {}, "group_level": {}}
    n_covered = {name: 0 for name in methods}
    width = {name: [] for name in methods}
    total = 0

    for train, test in _group_folds(groups, outer_folds, seed):
        assert not set(groups[train]) & set(groups[test]), "group leakage in outer folds"
        strata_train = None if strata is None else np.asarray(strata)[train]
        strata_test = None if strata is None else np.asarray(strata)[test]
        total += len(test)

        prediction, radius, _, info = split_conformal(
            fit_predict, x[train], y[train], groups[train], x[test], alpha, seed=seed)
        residual = np.abs(y[test] - prediction)
        n_covered["split"] += int((residual <= radius).sum())
        width["split"].extend([2 * radius] * len(test))
        detail["split"].setdefault("lastFold", info)

        prediction, radius, _, info = cv_plus_conformal(
            fit_predict, x[train], y[train], groups[train], x[test], alpha,
            inner_folds=inner_folds, seed=seed)
        residual = np.abs(y[test] - prediction)
        n_covered["cv_plus"] += int((residual <= radius).sum())
        width["cv_plus"].extend([2 * radius] * len(test))
        detail["cv_plus"].setdefault("lastFold", info)

        prediction, radius, _, info = group_level_conformal(
            fit_predict, x[train], y[train], groups[train], x[test], alpha,
            inner_folds=inner_folds, seed=seed)
        residual = np.abs(y[test] - prediction)
        n_covered["group_level"] += int((residual <= radius).sum())
        width["group_level"].extend([2 * radius] * len(test))
        detail["group_level"].setdefault("lastFold", info)

        if strata is None:
            # No strata were supplied, so there is nothing to condition on. Mondrian
            # is then identical to cv_plus by definition and is reported as such
            # rather than silently duplicated under a different name.
            prediction, radius, per_stratum, info = cv_plus_conformal(
                fit_predict, x[train], y[train], groups[train], x[test], alpha,
                inner_folds=inner_folds, seed=seed)
            per_stratum = None
        else:
            prediction, radius, per_stratum, info = cv_plus_conformal(
                fit_predict, x[train], y[train], groups[train], x[test], alpha,
                inner_folds=inner_folds, seed=seed, strata_train=strata_train)
        residual = np.abs(y[test] - prediction)
        # A stratum absent from the training data cannot have its own quantile; the
        # pooled radius is used and the fact is recorded.
        if per_stratum is None:
            radii = np.full(len(test), radius, dtype=float)
        else:
            radii = np.array([per_stratum.get(value, {}).get("radius", radius)
                              if value in per_stratum else radius
                              for value in strata_test], dtype=float)
        covered = int((residual <= radii).sum())
        n_covered["mondrian"] += covered
        width["mondrian"].extend((2 * radii).tolist())
        detail["mondrian"].setdefault("lastFold", info)
        methods["mondrian"].append({"covered": covered, "n": int(len(test))})

    summary = {}
    for name in methods:
        summary[name] = {
            "nominalCoverage": 1 - alpha,
            "empiricalCoverage": round(n_covered[name] / total, 4),
            "meanIntervalWidth": round(float(np.mean(width[name])), 4),
            "covered": n_covered[name],
            "total": total,
        }
    return {"summary": summary, "detail": detail,
            "protocol": (f"{outer_folds}-fold group-held-out outer evaluation; each method "
                         f"calibrates only on training groups; identical outer folds for "
                         f"every method")}
