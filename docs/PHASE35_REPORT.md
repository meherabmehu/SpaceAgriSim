# Phase 35 — Final completion report

One pass over the whole product: what was broken, what was fixed, what is still blocked and what it
costs to load. Every number below was produced by a command in this repository; the commands are
named beside them.

Base `0f01f314e7f9d8b54ab862a34f686b2c1f31bc7c` on branch `phase35/final-completion`.

## 1. Completed and verified

### 1.1 One evidence verdict per model, carried everywhere

`ml/research/phase35_evidence_verdicts.py` derives a verdict per model from committed evaluation
files and model cards (`--check` fails on drift). Result:

| verdict | models |
|---|---|
| passes independent check (decision grade) | mizuna-microbial-relative-load-v2 |
| fails independent check | lettuce-earth-growth-v1, -v2, -v3 |
| no independent check | radiation-quality-osd46-v1, radiation-exposure-osd46-v1, tomato-flight-response-v1 |
| withdrawn, retained | mizuna-harvest-v1, mizuna-microbial-load-v1 |

The verdict is returned by **every prediction route** as `evidenceVerdict` + `decisionGrade`, and for
any non-decision-grade model its measured reason is appended to `warnings`. The registry cards, the
scientific-status panel and the prediction panels all render the same block. 34 new audit checks and
11 new tests keep the surfaces from disagreeing. Details: `docs/PHASE35_SCIENTIFIC_VALIDATION.md`.

### 1.2 A real responsive bug, found and fixed

`/#benchmarks` overflowed its viewport by 83 px at tablet and 114 px at mobile because a 118-character
citation in a grid track with default `min-width: auto` refused to shrink. Fixed with
`min-width: 0` + `overflow-wrap: anywhere` on the row cells (both are required; each alone was
measured to leave the page at 903 px). The defect existed before this phase.

### 1.3 The visual gate covers the two decision-making routes

12 → 18 captures, 18/18 PASS at 0.000 % differing pixels, with the parent commit rebuilt and captured
identically first so every difference is attributable. `docs/PHASE35_VISUAL_REGRESSION.md`.

### 1.4 Deterministic captures

`captureElement()` rounds the screenshot clip at page coordinates, removing a 1-pixel jitter that made
a fractional-height panel produce a 627-pixel image on one run and 628 on the next. The gate's exact
size rule and 2 % budget were not touched.

### 1.5 Accessibility measured, not assumed

Contrast (worst 4.97:1), reduced motion and a keyboard-only journey are now asserted at three
viewports; they pass on both the parent and this branch, i.e. the properties were already true and
simply unmeasured. `docs/PHASE35_ACCESSIBILITY_REPORT.md`.

### 1.6 Documentation corrected to what the code does

* the scientific-status panel's prose asserting “no served model reports calibrated probabilities”
  is now computed from the data it is describing;
* two literal `?` separators that rendered in the registry card are fixed;
* an empty state and a plural were corrected;
* all eight Phase 35 documents, the model cards and the registry are regenerated from the evidence.

## 2. Improved but still limited

| Item | What improved | What did not |
|---|---|---|
| mizuna-microbial-relative-load-v2 | status moved to `validated-exploratory` on its own pre-recorded rule, now that coverage was measured | two campaigns are not a sample of campaigns; the scope still requires a campaign baseline |
| lettuce v3 | reported as failing its holdout while covering 6/6 independent means, both facts visible | accuracy criterion still missed (41.59 % vs 30 %) |
| prediction surfaces | every number arrives with its verdict | the failed models still predict; that is deliberate and disclosed |
| benchmark page | no horizontal scrolling on any viewport | — |

## 3. Blocked by unavailable scientific evidence

No new dataset was acquired; every candidate was rejected with a reason
(`docs/PHASE35_DATA_ACQUISITION.md`). Blocked, with the exact missing evidence:

1. **Measured reference ET / crop water use in a controlled environment.** Needed: a lysimeter or
   gravimetric water-use series with concurrent radiation, temperature, humidity and wind.
2. **Substrate moisture and irrigation time series.** Needed: substrate VWC plus applied-volume
   events per bed for a CEA crop with the same climate series. (The closest public dataset is
   open-field drip irrigation and cannot validate a CEA balance.)
3. **LED spectral response surface.** Needed: per-plant outcomes against spectral composition, PPFD
   and DLI. Papers exist; machine-readable data does not in what was searched.
4. **Fractional-gravity growth response.** Needed: measured edible biomass versus g-level. OSD-480 is
   1.41 TB of root gravitomics and transcriptomics; GLDS-251 is 5-day root RNA-seq.
5. **Independent lettuce campaigns.** Needed: one more campaign outside WUR/PeerJ/Touliatos to test
   the intervals rather than bound them.

Documenting these does not close them, and none was downgraded in severity.

## 4. Intentionally removed or disabled

Nothing was removed in this phase. Previously withdrawn capabilities (mizuna harvest mass, absolute
microbial load, ET0 emulator, gravity input, the harvest workflow) remain absent from every surface:
no route, no catalogue row, no workflow, no nav entry — asserted by the audit's removed-capability
checks, which still pass.

## 5. Not applicable

* No model was trained: no candidate dataset met the volume/grouping/validation bar this phase set.
* No deployment was performed, and none was configured — Render was not touched at any point.

## 6. Gates

| Gate | Result |
|---|---|
| SQLite suite | **1 235 passed, 24 skipped** (every skip is a PostgreSQL-only test with its reason printed) |
| PostgreSQL 17.11 suite | **1 259 passed, 0 skipped, 0 failed** |
| lint / typecheck | clean / clean |
| production build + `build:check` | passed; initial 240 kB / 3 modules, budget unchanged |
| model audit | 9/9 models, **202 checks, 0 failed**, 0 documented gaps, 7 resolved |
| registry verification | **62/62** |
| provenance verification | 9/9 artifacts |
| feature readiness / coverage / gap matrix | 12 / 12 / 14, all `--check` up to date |
| Phase 34 measurement sync | 5 cards, no drift |
| Phase 35 verdict consistency | consistent with the committed measurements |
| visual regression | **18/18 PASS at 0.000 %** |
| Playwright | **150 passed** across desktop 1440×1100, tablet 820×1180, mobile Pixel 7 |

### Test changes, stated rather than hidden

One assertion changed: `test_research.py` asserted the literal string `"experimental"` for
mizuna-microbial-relative-load-v2. It now asserts the derivation — status and verdict agree, and the
passing verdict carries the coverage measurement that earned it. Nothing was loosened: the new
assertions are strictly stronger (they would fail on a status change that the evidence does not
support, which the old literal also happened to catch by accident).

## 7. What a user sees that is new

* a verdict badge on every model card;
* a sentence above every prediction saying whether it is decision grade, and why not;
* a status panel whose claims are computed from the data;
* a benchmark page that fits on a tablet and a phone.

## 8. Repository hygiene after delivery

Two maintenance problems surfaced while verifying the delivered tree, and both are fixed rather than
noted:

**Duplicated evidence.** 115 committed screenshots held only 53 unique images — a capture that does
not change gets copied into the next phase's baseline, candidate and parent directories. That was
46.9 MB of exact duplication. `ml/research/dedupe_screenshots.py` keeps one canonical copy per image,
records every removed path in `docs/screenshots/MANIFEST.json` with the SHA-256 it shares with the
canonical file, and `--check` fails if duplicates reappear. The drift scripts resolve a removed path
through that manifest, so they still compare the same pixels and still report 0.000 % for a capture
that was merely duplicated, marking the row `identicalCopyOf`. `docs/screenshots` is now 25 MB.

**A checkout that loses `.git`.** Some execution environments snapshot a workspace with a size
budget; a repository larger than that budget can come back without its `.git` directory. `scripts/restore_git.sh`
reattaches the tree to the remote without overwriting a file: it clones history into a temporary
directory, moves `.git` into place, resets the index with `--mixed` so local edits appear as
modifications rather than disappearing, strips any credential from the remote URL, and prints what
differs. It was tested against a copy with an injected edit; the edit survived.
