# Phase 12 — competition demo

Five minutes, one command, and the last four demonstrations are refusals on purpose. The
demo is built for someone with a healthy suspicion of an AI claim.

```bash
./scripts/demo_phase9.sh          # full: verifies sources, retrains, checks checksums, Phase 12, live API
./scripts/demo_phase9.sh --fast   # skips retraining, reads the committed state
python3 scripts/demo_phase12.py   # the Phase 12 step on its own (~1.2 s, no server needed)
```

The script keeps its Phase 9 name because earlier documents reference that command line; its
content is now Phase 12. Nothing here deploys anything.

---

## 1. Measured timing

| Run | Wall clock | What it does |
| --- | --- | --- |
| `demo_phase12.py` alone | **~1.2 s** | the whole Phase 12 story, in-process, no server |
| `--fast --no-server` | **~2.3 s** | checksums, metric assertions, targeted tests, Phase 10/11/12 evidence |
| `--fast` | **~3.8 s** | the above plus the live API section |
| full | **~11 min** | the above plus a deterministic refit of both radiation models from the pinned NASA matrices |

Only the refit is slow, and it is there to prove the numbers are reproducible rather than
memorised.

---

## 2. What each step proves

| Step | Proves |
| --- | --- |
| 1. Checksums | Every NASA source file is the file the docs claim |
| 2. Retrain (full only) | Both served models refit deterministically; only timestamps and checksums change |
| 3. Metrics | The documented balanced accuracies and permutation p-values still hold |
| 4. Registry + suite | 40/40 registry checks, then the targeted tests |
| 5. Calibration and transfer | Interval coverage on held-out groups; the cross-study negative; recovered dose and gravity signals |
| 6. Phase 11 evidence | The four negatives: OSD-346 replication failure, dataset sweep finding zero new harvest candidates, the OSD-320 duplicate proof, OOD threshold unvalidated |
| **7. Phase 12** | The AI layer, its citation trail, and its four refusals |
| 8. Live API | A real prediction over HTTP, a partial-vector refusal, an exact explanation, and a 404 where no explanation method exists |

---

## 3. The Phase 12 step, verbatim

```
  the research assistant answers from retrieved evidence, and cites it
    Q: Is OSD-320 an independent replication of OSD-46?
    status: grounded  intent: dataset_suitability
      [1] Phase 11 compared all 44 arrays across 22,810 probesets ...
      [2] Title: Gamma radiation and HZE treatment of seedlings in Arabidopsis.
      cite phase11-duplicate-osd320  model or estimate, not a measurement
      cite OSD-46                    measured data   data/metadata/dataset_manifest#OSD-46
      measured data: ['OSD-46']
      model/estimate: ['phase11-duplicate-osd320']

  refusal 1: a question the corpus cannot answer is refused, not invented
    status: insufficient  refusal: insufficient-evidence  claims: 0  citations: 0

  refusal 2: a molecular classifier will not run on environmental inputs
    POST /workflow/run radiation-quality-osd46-v1 with temperature and light
      -> HTTP 422 (family-mismatch)
      expected gene-expression inputs, received environment inputs, 20 gene features missing

  refusal 3: a physically impossible value is rejected, not clamped
    900 C air temperature -> HTTP 422 (physically-impossible)

  refusal 4: a retired model still refuses to answer with a number
    mizuna-microbial-load-v1 -> HTTP 410 (retired-model)

  a valid run returns the number, its domain check, limitations and provenance
    prediction: 191.4 g fresh shoot mass/plant
    kind: regression  isMeasurement: False  calibrated: False
    inside training domain: True
    provenance: WUR-lettuce (sha256 9931f375baf5…)
      limit: Only Batavia Othilie lettuce on Earth; not calibrated for partial gravity or radiation.

  saved analyses belong to one account, and only that account
    alice saved 06f15672… (Demo: lettuce at 20 days)
    bob sees 0 analyses; GET alice's id -> HTTP 404
    export row: prediction,191.3595763661245

  the dataset explorer never counts a duplicate deposit twice
    26 accessions -> 25 independent studies; 1 duplicate, 1 shared material, 31 unverified pairs
    requested 4 -> independent 2: ['OSD-46', 'OSD-655']
      drop OSD-320: duplicate-measurement (conflicts with OSD-46)
      drop OSD-780: shared-sample-different-assay (conflicts with OSD-655)

  every model states its scientific category and calibration status
    lettuce-earth-growth-v2            cat 3  environment      runnable   calibrated=False
    mizuna-microbial-load-v1           cat 6  microbial        retired    calibrated=False
    ...
```

Every line is a real API response. The script prints `FAILED: …` and exits non-zero if any of
its assertions stops holding, so this is a gate, not a transcript.

---

## 4. The three things to click in the UI

1. **Research assistant** (`#assistant`) — ask *"Is OSD-320 an independent replication of
   OSD-46?"*. The answer arrives with a citation card listing the accession, the evidence
   class, the local file, and that passage's limitations. Then ask *"How do I bake sourdough
   bread?"*: the panel says **Refused** and shows no citations.
2. **NASA data explorer** (`#datasets`) — the first panel reads "26 accessions are 25
   independent studies", with the OSD-320 proof quoted. Select OSD-46 and OSD-320, press
   *Check independence*, and watch the count come back as 1.
3. **AI prediction center** (`#predictions`) — every model with its category, training source,
   calibration status and retirement reason. Four are NASA-trained; the panel says so instead
   of implying eight are.

No layout, typography or navigation was redesigned; the new panels use the workspace's
existing card and pill components, and the assistant is one added sidebar entry.

---

## 5. What a judge should try to break

| Try this | Expected |
| --- | --- |
| Ask the assistant for a Moon crop yield | Refused or partial, with the model's Earth-only limitation quoted |
| Feed 900 °C air to the lettuce model | 422 `physically-impossible` |
| Feed temperature and light to the OSD-46 classifier | 422 `family-mismatch`, naming the missing genes |
| Ask for a prediction from the retired microbial model | 410 with the finding that retired it |
| Save an analysis, log out, log in as another account | The analysis is not listed, and its id returns 404 |
| Export an analysis and check the number | Identical to the API response, with the "not a measurement" line inside the file |
| Count the datasets yourself | The explorer's independent count is lower, and it explains every exclusion |
