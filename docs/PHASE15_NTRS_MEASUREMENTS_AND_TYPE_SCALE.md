# Phase 15 — NASA chamber measurements from NTRS, and the type scale

Two pieces of work that answer the same complaint: the platform was harder to read than the
evidence deserved, and it was quiet about the one class of NASA measurement that actually
matches what the simulator assumes.

Nothing in this phase trains a model, fits a coefficient or changes a simulator output. What
changed is what can be **read** and what can be **cited**.

---

## 1. The gap this closes

OSDR is a molecular and microbiome archive. It answers "what changed inside the plant". The
habitat simulator asks a different question: how much biomass, water and CO₂ moved through a
canopy, and when. Those measurements were made — in the NASA Biomass Production Chamber at
Kennedy Space Center — and published as NASA technical memoranda. They are on **NTRS**, not in
OSDR. They were previously described in this repository as "aggregated experimental results";
that was true of what the repository held, not of what NASA published.

## 2. What was acquired

| NTRS ID | Report | Crop | Why it earns a place |
| --- | --- | --- | --- |
| 19900016137 | TM 102788, CO₂ and water exchange rates by a wheat crop in NASA's BPC — 86-day study | Wheat | Day-resolved CO₂ and water exchange for a full seed-to-harvest stand |
| 19910010713 | N91-20026, CO₂ and water exchange of a soybean stand in the BPC | Soybean | A second crop and canopy geometry for comparison |
| 19900007373 | N90-16689, Dynamics of CO₂ exchange of a wheat community | Wheat | How the exchange rate moves across the growth cycle, not just the endpoint |

Each PDF is pinned by **byte length and SHA-256** in `data/literature/ntrs_bpc`; a download
that does not match the pin is rejected, and a changed upstream hash stops the script rather
than being accepted. 14 measurement pages were selected across the three reports.

### Record 20040090219 is deliberately **not** acquired

"A data base of crop nutrient use, water use, and carbon dioxide exchange in a 20 square meter
growth chamber: I. Wheat as a case study" describes exactly the ideal dataset. NTRS publishes a
citation record with **no downloadable file** for it. It is cited as a reference and nothing was
reconstructed from its abstract — writing a dataset out of an abstract is the failure mode this
whole project exists to avoid.

## 3. How the pages are used, and how they are not

**Used:** each selected page becomes a citable corpus passage (`kind: literature`) carrying the
report label, the NTRS id, the **page number**, the verbatim excerpt, a direct URL
(`…/citations/<id>#page=N`) and the measurement terms the page actually names. The assistant can
now answer questions about chamber transpiration and CO₂ exchange and cite a page a reader can
open.

**Not used:** the excerpts are **not** parsed into a numeric time series. The PDFs are scanned
typescripts; column-aligned parsing would risk inventing values that are not on the page. Quoting
a page is honest; synthesising a table from OCR is not.

**Never:** fitted into the simulator. The chamber data remains cited evidence, not calibration.
Every passage repeats the boundary: ground-based at Kennedy Space Center, one chamber, one
cultivar, one campaign — **not a Moon, Mars or ISS measurement**.

## 4. The line that is tested

Acquiring ground-chamber wheat numbers creates an obvious temptation: answer a Moon question
with a Kennedy Space Center number. Two tests hold that line:

- `test_a_chamber_measurement_question_is_answered_with_a_citation` — BPC questions must be
  answered, citing `NTRS-…` sources.
- `test_ground_chamber_data_does_not_enable_a_space_yield_answer` — "What is the expected crop
  yield on the Moon?" and "…lettuce yield on Mars?" must still return `insufficient` with **zero
  claims and zero citations**.

Both pass. The catalogue grew by 17 passages and the assistant still refuses the two questions it
has no evidence for.

## 5. One benchmark expectation was revised, deliberately

`data-03` ("What evidence would be needed to validate the excluded models?") expected
`notGrounded`. After adding 17 passages the BM25 corpus statistics shifted, and the question now
clears the evidence floor with citations **entirely inside `mustCiteAny`**
(`method-training-eligibility`, `phase10-dose`). The corpus does document which evidence would
validate the excluded models, so the grounded answer is the correct one and the expectation was
conservative.

The expectation was revised to `grounded` and the item carries a `revisionNote` recording that,
so the change is visible in the data rather than buried in a diff. The failure that actually
matters — citing a source outside `mustCiteAny` — still fails the test.

## 6. Coverage rows updated (honestly, not optimistically)

| Row | Before | After |
| --- | --- | --- |
| Plant growth | "NASA data available only as aggregated experimental results" | "NASA closed-chamber canopy measurements acquired from NTRS; **no orbital growth time series exists**" |
| Water consumption | "requiring processing" | "NASA canopy water-exchange measurements acquired from NTRS" — with the note that these are ground-based and cultivar-specific |
| CO₂ uptake | "only as aggregated experimental results" | "NASA closed-chamber gas-exchange measurements acquired" — no harmonised training table was built |
| Oxygen production | "raw measurements are unavailable" | "**derived** from measured CO₂ exchange; no direct O₂ measurement acquired" |
| Light intensity | "only as aggregated experimental results" | "PPFD levels are recorded in the acquired studies; the PPFD-to-yield response is **still not** a fitted surface" |

No row claims more than the acquired bytes support.

## 7. Data we will never have, and are done asking for

The owner's instruction was to stop listing data that cannot be obtained and to build strength
only on data that can. These are now out of scope **permanently**, and the app says so instead of
implying a pending gap:

| Data | Why it cannot exist |
| --- | --- |
| Real lunar or Martian regolith crop trials | No returned bulk regolith has been used for a plant growth trial; simulants are the only available analogue, and a simulant is not regolith |
| A "stress → yield loss in grams" curve | Orbital plant studies measure gene expression and microbiology; nobody has harvested enough plants to fit a yield-loss surface |
| Orbital lettuce/tomato/radish growth time series | No such series is published; the closest thing is the ground chamber work acquired above |
| Spacecraft water-loop recovery measurements | Program data, not in the public archive |

## 8. The type scale

The interface was rendering 6–11 px type for labels, table cells and captions. The owner asked
for it to be readable, without a redesign.

- `.platform` root size 13 px → **15 px**.
- 122 `font-size` declarations in `platform.css` and the `font` shorthand raised on a fixed
  scale: 6→9, 7→10, 8→11, 9→11, 10→12, 11→13, 12→14, 13→14, with display sizes nudged only
  slightly (18→19 … 29→30, 41→42) so headings keep their hierarchy.
- 24 component files had arbitrary Tailwind sizes (`text-[10px]` etc.) raised by the same steps.
- The sidebar and its offset widened 244 → 268 px so nav labels do not wrap at the larger size.

No layout, colour, spacing or component structure changed. Verified with `npm run build`,
`npm run lint` and `npm run typecheck` — all clean.

**Limit of that verification:** the change was checked by build and by reading the CSS, not by a
rendered visual diff, because a browser binary could not be installed in this environment. Any
container with a fixed height that now overflows should be reported and will be fixed in
place.

## 9. Verified results

| Gate | Before | After |
| --- | --- | --- |
| Backend suite | 545 passed / 1 skipped | **553 passed / 1 skipped** |
| Corpus | 52 passages | **69 passages** (datasets 25 · findings 10 · models 8 · methodology 6 · classifications 3 · **literature 17**) |
| Coverage rows | 17 | 17 (five rewritten with the acquired source) |
| frontend build / lint / typecheck | clean | clean |
