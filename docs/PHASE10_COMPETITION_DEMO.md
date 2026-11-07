# Phase 10 — competition demo

One command, six steps, no network beyond the local API. It is written for someone with
five minutes and a healthy suspicion: every step shows a number, and several numbers are
negative on purpose.

```bash
./scripts/demo_phase9.sh          # includes the live API step
./scripts/demo_phase9.sh --fast   # skips the server, reads artifacts directly (~6 s)
```

The script is still named `demo_phase9.sh` because renaming it would break the command
line in earlier documents; its content is Phase 10.

## Measured timing

| Run | Wall clock |
| --- | --- |
| `--fast` (artifacts only) | **5.9 s** |
| full, including server start and live prediction | **6.4 s** |

The demo is fast because it runs 47 targeted tests and reads committed artifacts rather
than re-training. Nothing in it takes long enough to lose an audience.

## What it shows, in order

**1–2. The catalogue and the registry.** 19 studies through the API (18 NASA + one
external), 8 models, with the two excluded candidates named.

**3–4. Tests.** 47 passing fast tests plus the scientific-claims checks.

**5. The audit trail**, which is the part worth demoing:

```
interval coverage, nominal 0.90 (split was the Phase 9 method):
  mizuna-microbial-relative-load-v2  split 0.870 -> group_level 0.992
  mizuna-microbial-load-v1           split 0.886 -> group_level 0.992
  lettuce-earth-growth-v2            split 0.907 -> cv_plus 0.961
  lettuce-earth-growth-v1            split 0.908 -> cv_plus 0.939
cross-study: transfer-failed-under-every-harmonisation; the target's own contrast is
  0.438 with cells held out (95% CI 0.30-0.59) and 0.812 with timepoints held out,
  so the negative is about transfer, not about the absence of signal
dose labels: valid ([0.0, 10.0, 100.0] Gy), and the answer depends on the split:
  hold out (dose,timepoint) cell -> balanced 0.111
  hold out whole timepoint       -> 0.611 (p=0.0005)
partial gravity, OSD-314 at [0.0, 0.34, 1.0] g in orbit:
  uG vs 0.34 g inside flight -> balanced 1.000 (p=0.0055),
  corroborated by 8478 DE genes; not served, because n=17 in one mission
```

That block is the whole phase in twelve lines: two intervals that now cover what they
claim, a transfer negative that has been scoped honestly, a dose exclusion whose
reasoning was corrected without promoting anything, and a genuine partial-gravity
signal that is deliberately not served.

**6. The live API**, including the two refusals that matter more than the successes:

```
control  centroid -> control  (control 0.99, hze 0.00, gamma 0.00)
gamma    centroid -> gamma    (gamma 1.00, control 0.00, hze 0.00)
hze      centroid -> hze      (hze 1.00, control 0.00, gamma 0.00)
partial vector -> HTTP 422 (expression-feature-mismatch, missing 149 genes)
explanation: exact linear attribution of the served linear-softmax evaluator
  identity residual 8.88e-16, 75 genes chosen in all 22 folds
  largest single-gene permutation drop: 0.0037 -> signal is distributed
lettuce explanation -> HTTP 404 (no valid method, no stub)
```

A 422 for a partial gene vector, a 404 for a surrogate explanation, and an explanation
that reconstructs the served logits to 1e-16 — those are the demonstrations a reviewer
should poke at.

## What a five-minute live run should do

For a live audience with the frontend running:

1. `./scripts/demo_phase9.sh --fast` — 6 s, the whole audit trail above.
2. Open the radiation card, click **control centroid**, then **Explain this
   prediction**. The explanation appears at the end of the card with its identity
   residual, its fold-stability counts and its limits. Nothing above it moves.
3. Predict a class centroid and the confidence interval, which reports a **measured**
   0.992 coverage for the microbial models beside its nominal 0.90.
4. Show the two excluded candidates in the model list are absent, and that
   `/api/models/radiation-dose-osd782-v1` returns 404.

## What not to claim while demoing

- Do not say "the platform predicts radiation damage". It classifies three radiation
  qualities in two genotypes on one platform.
- Do not say "partial gravity is predicted". It is *detectable* in one 17-library
  experiment and is not served.
- Do not present the intervals as guarantees. They are measured coverages over 35
  pillows in two campaigns and four lettuce experiments.
- Do not call any gene a biomarker. Removing any single one changes balanced accuracy
  by at most 0.0037.
