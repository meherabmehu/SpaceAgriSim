"""Paired metrics for the ET0 comparison.

Every metric is computed on pairs where **both** sides are present. Missing pairs are dropped
and counted; nothing is zero-filled, because a zero is a plausible ET0 value and would enter
the error statistics as if it were data.
"""
from __future__ import annotations

import math
from typing import Any, Iterable, Sequence


def paired(
    predicted: Sequence[float | None],
    reference: Sequence[float | None],
) -> dict[str, Any] | None:
    """MAE, RMSE, bias, R2, correlation and OLS slope for one pair of series.

    ``bias`` is predicted minus reference, so a negative bias means the first series is
    smaller. ``slope`` is cov/var(reference): 1.0 means the two series move together at the
    same amplitude, and R2 is the squared Pearson correlation, kept separate from the slope so
    a series that tracks perfectly but is scaled by 0.8 does not read as agreement.
    """
    pairs = [
        (float(p), float(r))
        for p, r in zip(predicted, reference)
        if p is not None and r is not None
        and not (math.isnan(p) or math.isnan(r))
    ]
    n = len(pairs)
    if n < 2:
        return None

    diffs = [p - r for p, r in pairs]
    mae = sum(abs(d) for d in diffs) / n
    rmse = math.sqrt(sum(d * d for d in diffs) / n)
    bias = sum(diffs) / n

    mean_p = sum(p for p, _ in pairs) / n
    mean_r = sum(r for _, r in pairs) / n
    cov = sum((p - mean_p) * (r - mean_r) for p, r in pairs) / n
    var_p = sum((p - mean_p) ** 2 for p, _ in pairs) / n
    var_r = sum((r - mean_r) ** 2 for _, r in pairs) / n

    slope = cov / var_r if var_r > 0 else None
    correlation = cov / math.sqrt(var_p * var_r) if var_p > 0 and var_r > 0 else None
    r2 = correlation ** 2 if correlation is not None else None

    return {
        "n": n,
        "mae": mae,
        "rmse": rmse,
        "bias": bias,
        "r2": r2,
        "correlation": correlation,
        "slope": slope,
        "meanPredicted": mean_p,
        "meanReference": mean_r,
        "sdReference": math.sqrt(var_r),
        "p95AbsError": _percentile([abs(d) for d in diffs], 0.95),
        "maxAbsError": max(abs(d) for d in diffs),
    }


def _percentile(values: Iterable[float], q: float) -> float | None:
    ordered = sorted(values)
    if not ordered:
        return None
    index = (len(ordered) - 1) * q
    low = math.floor(index)
    high = math.ceil(index)
    if low == high:
        return ordered[int(index)]
    return ordered[low] + (ordered[high] - ordered[low]) * (index - low)


def mean_error_percent(
    predicted: Sequence[float | None],
    reference: Sequence[float | None],
    *,
    floor_mm: float = 0.1,
) -> float | None:
    """Mean relative error in percent, defined only where the reference is not near zero.

    A percentage error explodes as ET0 approaches zero - Reykjavik produced 19 462 % from a
    denominator of 0.02 mm/d - so pairs at or below ``floor_mm`` are excluded and the absolute
    alternative (``meanErrorMmIfConversionOmitted``) is reported alongside.
    """
    pairs = [
        (float(p), float(r))
        for p, r in zip(predicted, reference)
        if p is not None and r is not None and abs(float(r)) > floor_mm
    ]
    if not pairs:
        return None
    return sum((p - r) / r for p, r in pairs) / len(pairs) * 100.0


def missingness(series: Sequence[float | None]) -> dict[str, Any]:
    """Missing fraction and the longest run of missing values, for the provenance block."""
    total = len(series)
    missing = sum(1 for value in series if value is None)
    longest = current = 0
    for value in series:
        if value is None:
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    return {
        "rows": total,
        "missing": missing,
        "fraction": (missing / total) if total else None,
        "longestRun": longest,
    }
