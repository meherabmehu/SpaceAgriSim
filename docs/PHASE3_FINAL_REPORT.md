# Phase 3 final report — production readiness and scientific ML advancement

Phase 3 was completed on branch `feat/phase3-production-ml`. The branch is pushed and preview-deployed, but has deliberately not been merged to `main`.

## Completed work

- Established a reproducible baseline (`dfece0f` ancestor): backend tests, frontend static checks, bundle sizes and clean-worktree state.
- Hardened persistence for SQLite and PostgreSQL: allowed-DSN guard, connection pre-ping, dialect-aware `/api/ready`, and an isolated opt-in PostgreSQL integration test.
- Added the PostgreSQL configuration, backup, restore and recovery runbook. No managed database or paid resource was created.
- Performed an independent-validation evidence audit for all three scientific ML artifacts. No compatible independent study was found, so no performance claims, model weights or model status were inflated.
- Reviewed NASA OSD-766, OSD-59, NTRS sources and the Zenodo Piikkio lettuce set. They were not ingested because they do not form an independent, compatible target/predictor validation set.
- Preserved honest uncertainty semantics: reported model ranges are descriptive residual ranges, not calibrated coverage intervals. Out-of-domain and experimental/baseline-only labels remain explicit.
- Deferred the whole greenhouse route until selected. The initial frontend JavaScript is now 595.10 kB minified (previously 606.11 kB); the 922.21 kB Three.js scene is still a separate on-demand chunk and already pauses while off-screen.
- Updated Render's Blueprint branch to `main`, refreshed deployment guidance, and verified a live Vercel branch preview.

## Verification evidence

| Check | Result |
| --- | --- |
| Backend tests | 97 passed, 1 skipped optional PostgreSQL integration test |
| Frontend lint/typecheck/build | passed |
| Playwright workflows | 15 passed across desktop, tablet and mobile |
| Local POST endpoint smoke | `/simulate`, `/compare`, `/optimize`: 200 |
| Vercel preview GET smoke | `/ready`, `/datasets`, `/models`, `/scenarios`: 200 |
| npm production dependency audit | 0 vulnerabilities |
| Docker Compose configuration | passed; Docker daemon runtime test remains unavailable locally |

## Deliberate limits and next production gate

1. Provision a PostgreSQL service, place its secret DSN in the host configuration, run the opt-in database integration test, then verify save/read and backup/restore against that deployment.
2. Add authentication, authorization, rate limiting at the edge, monitoring and retention policy before enabling public scenario writes.
3. Obtain a genuinely independent, compatible crop outcome dataset before recalibrating intervals or promoting any ML model beyond its current exploratory/baseline-only status.
4. Review this branch and merge only after those deployment decisions are approved.

This remains a research simulator, not an operational spacecraft crop-control or crew-safety system.
