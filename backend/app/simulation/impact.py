"""
Impact decomposition: why is the space scenario different from Earth?

Growth is linear in the combined environment factor, and that factor is a
product of one factor per driver:

    combined = light x water x radiation x co2

so the space / Earth yield ratio is the product of the per-driver ratios

    spaceYield / earthYield = PROD_i (spaceFactor_i / earthFactor_i)

That product is unpacked into a waterfall: start at the Earth reference
(100 %), apply one driver at a time in a fixed order and record how many
percentage points each step adds or removes. The steps add up exactly to the
combined difference, which is what makes the chart honest.

Two different percentages are reported for every driver:

    percent             the driver's own effect relative to Earth for the
                        SAME driver, e.g. radiation 0.3 mGy/day -> -7 %
    contributionPoints  how many percentage points of the final gap that
                        driver accounts for once the earlier steps are applied

In "matched" mode water, light and CO2 are identical in both runs, so their
ratio is 1 and they contribute 0 points even when the absolute response is
large (CO2 enrichment boosts both runs alike). `responsePercent` keeps that
absolute response visible: the factor relative to the crop's reference
conditions (background radiation, 100 % water, optimal light, ambient CO2).

Gravity has no factor any more: Phase 30 removed the fractional-gravity response rather than keep a
coefficient no dataset supports, so it can neither appear in the waterfall nor move a yield.
"""

from __future__ import annotations

from dataclasses import dataclass

# Fixed presentation order: the space-specific drivers first, then resources.
FACTOR_ORDER = ["radiation", "water", "light", "co2"]

FACTOR_LABELS = {
    "radiation": "Radiation",
    "water": "Water",
    "light": "Light",
    "co2": "CO2",
}


@dataclass(frozen=True)
class ImpactStep:
    key: str
    label: str
    space_factor: float
    earth_factor: float
    ratio: float  # space_factor / earth_factor
    percent: float  # (ratio - 1) x 100
    response_percent: float  # (space_factor - 1) x 100, relative to the reference conditions
    contribution_points: float  # percentage points of the final gap this driver accounts for
    running_percent: float  # yield as % of Earth after applying this and all earlier steps


@dataclass(frozen=True)
class ImpactBreakdown:
    steps: list[ImpactStep]
    combined_percent: float  # sum of the contribution points (= signed yield difference)
    limiting_factor: str | None  # driver with the most negative contribution, if any
    boosting_factor: str | None  # driver with the most positive contribution, if any


def _ratio(space_factor: float, earth_factor: float) -> float:
    if earth_factor <= 0.0:
        # Both zero (e.g. no water in matched mode): the driver does not
        # separate the two runs, so it contributes nothing.
        return 1.0 if space_factor <= 0.0 else float("inf")
    return space_factor / earth_factor


def decompose_impact(space_factors: dict[str, float], earth_factors: dict[str, float]) -> ImpactBreakdown:
    running = 100.0
    steps: list[ImpactStep] = []

    extra = [key for key in ("intensity", "temperature", "humidity")
             if space_factors.get(key, 1.0) != 1.0 or earth_factors.get(key, 1.0) != 1.0]
    for key in FACTOR_ORDER + extra:
        space_factor = space_factors[key]
        earth_factor = earth_factors[key]
        ratio = _ratio(space_factor, earth_factor)
        before = running
        running = running * ratio if ratio != float("inf") else running
        steps.append(
            ImpactStep(
                key=key,
                label=FACTOR_LABELS.get(key, key.title()),
                space_factor=space_factor,
                earth_factor=earth_factor,
                ratio=ratio if ratio != float("inf") else 1.0,
                percent=(ratio - 1.0) * 100.0 if ratio != float("inf") else 0.0,
                response_percent=(space_factor - 1.0) * 100.0,
                contribution_points=running - before,
                running_percent=running,
            )
        )

    negatives = [s for s in steps if s.contribution_points < -1e-9]
    positives = [s for s in steps if s.contribution_points > 1e-9]
    limiting = min(negatives, key=lambda s: s.contribution_points).key if negatives else None
    boosting = max(positives, key=lambda s: s.contribution_points).key if positives else None

    return ImpactBreakdown(
        steps=steps,
        combined_percent=running - 100.0,
        limiting_factor=limiting,
        boosting_factor=boosting,
    )
