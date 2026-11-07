# Phase 2 telemetry status

## Decision

No “live ISS telemetry” feature was added. The Phase 2 NASA audit did not verify an openly accessible, real-time, plant-specific telemetry feed that can be safely joined to a crop experiment. Presenting unrelated ISS environmental or radiation values as live crop telemetry would be scientifically misleading.

## What the product supports today

- Timestamped **simulation** series, clearly labelled as scenario estimates.
- Historical OSDR study metadata and acquired measurement previews, each with source/provenance.
- Separate simulation controls and measured-study views; no synthetic join between them.

## Requirements before a telemetry connector is enabled

1. A verified source URL and terms of use.
2. Source identifier, timestamp, unit and documented measurement method.
3. Freshness/last-success indicator and missing-data handling.
4. Proof that telemetry and plant observations belong to the same experiment before joint analysis.
5. A historical-only label unless an official live feed is verified.

This is intentionally recorded as a data-availability constraint, not an unfinished fake integration.

