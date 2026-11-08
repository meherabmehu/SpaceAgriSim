# Phase 13 — The End-to-End Scientific Workflow

One path, seven steps, from a published NASA dataset to a file a researcher can cite — with every
step showing what it knows and what it does not.

Open the application, choose **Scientific workflow** in the sidebar (or `/#workflow`).

| Step | What the reader sees | Where it comes from |
|---|---|---|
| 1 Evidence | Each served model with its study, source type, science category and calibration status; retired models shown disabled **with the reason** | `GET /api/workflow/models` |
| 2 Model selection | The model's exact feature list and units; nothing else can be sent | same catalogue |
| 3 Validation | Every check the API runs, pass or fail, before anything executes | `POST /api/workflow/validate` |
| 4 Inference | The prediction, its kind, and whether an interval is calibrated | `POST /api/workflow/run` |
| 5 Interpretation | The model's own statements plus the evidence claims behind them | same response |
| 6 Saved analysis | The stored record id and title, private to the account | `POST /api/workflow/run-and-save` |
| 7 Export | JSON, CSV or Markdown, generated from the stored payload unmodified | `GET /api/analyses/{id}/export/{fmt}` |

## The decisions the workflow makes for the reader

**A retired model cannot be run.** `mizuna-microbial-load-v1` is category 6 (unsupported scientific
prediction) and is rendered disabled, with the reason it was retired and the numbers behind it:
leave-one-experiment-out R² of −0.55 and −0.58, worse than predicting the training mean. The
interface does not offer a "run anyway".

**An uncalibrated output is named as one.** The page prints "uncalibrated point estimate" next to
any model without a measured interval, and a classifier's probabilities are captioned as model
outputs rather than probabilities of a biological outcome. No confidence interval is drawn that
the model does not have.

**Input validation is not duplicated.** The page could check ranges itself, and that is exactly how
a UI drifts from the API. It sends the inputs and shows the backend's verdict, so the two cannot
disagree.

**Running needs no account; saving does.** The empty state says which, and the save path opens the
existing sign-in dialog rather than failing with a 401 the reader cannot act on.

**Nothing is replayed.** No stored example output stands in for a live inference. An empty session
is an empty session.

## Loading, empty and error states

Every step has all three, using the components that already existed
(`RequestState`, `.skeleton`, `.empty-state`, `.error-banner`, `.warning-box`):

* **Loading** — "Loading verified API output…" while the catalogue is fetched; buttons show
  "Validating…", "Running…", "Saving…" and are disabled while a request is in flight, so a second
  click cannot start a second inference.
* **Empty** — "No inference has been run in this session", "Nothing saved from this session yet",
  "Select a model to see the inputs it requires". Each says what to do next rather than leaving a
  blank panel.
* **Error** — the backend's own message in a `role="alert"` region: the out-of-domain input, the
  retired model, the quota refusal (with count and limit), the missing sign-in.

## State handling

Selection, draft inputs and results are **keyed by model id** rather than reset by effects. A
validation verdict produced for one model can therefore never be displayed under another model's
inputs, and switching models does not trigger a cascade of renders. The consequence a reader sees:
switch models mid-workflow and the panel is honestly empty rather than showing a stale pass.

## Verified by tests

`frontend/e2e/workflow.spec.js`, five tests across desktop, tablet and mobile:

1. a retired model cannot be selected (`disabled`, `aria-disabled`);
2. valid inputs produce a labelled model output — the words "uncalibrated point estimate" must be
   present;
3. an out-of-domain input surfaces an alert carrying the backend's rejection;
4. an incomplete form is caught before any request is sent;
5. saving without an account is refused with guidance, and a saved analysis exports to a file
   whose name and contents identify it as model output.

Backend behaviour behind those steps is covered by `backend/tests/test_phase12_workflow.py`,
`test_phase13_account_limits.py` and `test_phase13_security.py` — cross-account isolation, quota
enforcement under concurrency, and export paths that return 404 for another account's id.

## What the workflow does not do

It does not calibrate anything, does not extend a model's domain, and does not make a model output
into a measurement. A CSV exported from step 7 begins with a header stating that the numbers are
model output and not a measurement, because a file outlives the interface that produced it.
