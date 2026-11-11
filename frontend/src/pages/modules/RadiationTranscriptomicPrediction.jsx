import { useState } from 'react'
import { api } from '../../services/platformApi.ts'
import { Card } from '../missionUI.jsx'
import { Limitations } from './moduleSupport.jsx'

// Serves the two Phase 9 NASA OSD-46 classifiers through the same generic
// prediction pattern already used for the tomato and lettuce models: load an
// input, post it, show the classifier's own limitations verbatim.
//
// The only input available through the UI is a training-set centroid, which is
// synthetic by construction. It exists so a reviewer can confirm the serving path
// is wired correctly; it is explicitly NOT a measured plant and the component says
// so every time one is loaded. There is no control here for typing arbitrary gene
// expression, because feeding invented numbers into a 150-gene microarray model
// would produce confident output with no scientific meaning.

const MODELS = [
  {
    id: 'radiation-quality-osd46-v1',
    title: 'Radiation quality response',
    label: 'NASA OSD-46 · ARABIDOPSIS MICROARRAY',
    prose: 'Distinguishes non-irradiated controls from 100 Gy gamma and 30 Gy Fe-56 ion radiation by gene expression. Gamma and Fe-56 are balanced across array batches, so array handling cannot explain the separation.',
  },
  {
    id: 'radiation-exposure-osd46-v1',
    title: 'Radiation exposure response',
    label: 'NASA OSD-46 · ARABIDOPSIS MICROARRAY',
    prose: 'Separates irradiated from non-irradiated samples. Controls never appear on one of the three array batches, so the batch-controlled number shown below is the more defensible figure.',
  },
]

function RadiationModelCard({ model }) {
  const [profiles, setProfiles] = useState(null)
  const [result, setResult] = useState(null)
  const [loaded, setLoaded] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  // Explanations are fetched only when a reviewer asks for one, and the panel
  // starts closed. Both choices keep the card's rendered height identical to the
  // pre-Phase-10 baseline, and the visual regression gate measures that.
  const [explanation, setExplanation] = useState(null)
  const [explainBusy, setExplainBusy] = useState(false)
  const [explainError, setExplainError] = useState('')

  const toggleExplanation = async () => {
    if (explanation) { setExplanation(null); return }
    setExplainBusy(true); setExplainError('')
    try {
      setExplanation(await api(`/models/${model.id}/explanation`))
    } catch (err) { setExplainError(err.message) } finally { setExplainBusy(false) }
  }

  const load = async (label) => {
    setBusy(true); setError(''); setResult(null)
    try {
      const data = await api(`/models/${model.id}/reference-profiles`)
      setProfiles(data)
      setLoaded(label)
      setResult(await api(`/predict/${model.id}`,
        { expression: Object.fromEntries(data.features.map((gene, i) => [gene, data.profiles[label][i]])) }))
    } catch (err) { setError(err.message) } finally { setBusy(false) }
  }

  return <Card title={model.title} label={model.label}>
    <p className="prose">{model.prose}</p>
    <p className="prose">
      Choose a class centroid to check the serving path. A centroid is the average
      of the training samples in that class, so it is synthetic and not a measured
      plant.
    </p>
    <div className="module-actions">
      {(profiles?.classLabels || ['control', 'irradiated']).map((label) =>
        <button key={label} className="secondary-button" disabled={busy} onClick={() => load(label)}>
          {busy && loaded === label ? 'Computing…' : `Load ${label} centroid`}
        </button>)}
    </div>
    {error && <div className="error-banner" role="alert">{error}</div>}
    {result && <>
      {profiles?.synthetic && <p className="warning-box">{profiles.label}</p>}
      {result.evidenceVerdict && (
        <p className={`verdict-line ${result.decisionGrade ? 'ok' : 'warn'}`} role="note">
          {result.decisionGrade
            ? 'Decision grade: an independent campaign met every criterion set for this model.'
            : `Not decision grade — ${result.evidenceVerdict.summary}`}
        </p>
      )}
      <div className="comparison-value">{result.prediction}</div>
      <p className="muted fine">
        Class probabilities: {Object.entries(result.probabilities).map(([k, v]) => `${k} ${v.toFixed(3)}`).join(' · ')}.
        Hold-out balanced accuracy {result.validation.balancedAccuracy.toFixed(3)},
        permutation p = {result.validation.permutationPValue.toFixed(4)}
        over {result.validation.biologicalGroups} biological groups.
        The interval is uncalibrated.
      </p>
      {result.batchConfound && <p className="muted fine">
        Array-batch association with the label: Cramér's V {result.batchConfound.cramersV.toFixed(3)}.
        {result.supplementaryEvaluation ? ` Batch-controlled balanced accuracy ${result.supplementaryEvaluation.bestBalancedAccuracy.toFixed(3)} on ${result.supplementaryEvaluation.arraysUsed} arrays from batch ${result.supplementaryEvaluation.batch}.` : ''}
      </p>}
      <Limitations items={result.warnings} />
      <a className="wide-link" href={result.sourceUrl} target="_blank" rel="noreferrer">Read the NASA OSD-46 source dataset</a>
      <div className="module-actions">
        <button className="secondary-button" disabled={explainBusy} onClick={toggleExplanation}>
          {explainBusy ? 'Computing…' : explanation ? 'Hide explanation' : 'Explain this prediction'}
        </button>
      </div>
      {explainError && <div className="error-banner" role="alert">{explainError}</div>}
      {explanation && <>
        <p className="muted fine">
          {explanation.notASurrogate} Method: {explanation.method}; reconstruction
          residual {explanation.identityResidual.toExponential(1)}.
        </p>
        {explanation.binaryEncodingNote && <p className="muted fine">{explanation.binaryEncodingNote}</p>}
        <p className="muted fine">
          Genes selected in every one of {explanation.selectionStability.folds} held-out folds:{' '}
          {explanation.selectionStability.genesSelectedInEveryFold} of{' '}
          {explanation.selectionStability.geneSpace} considered.{' '}
          {explanation.selectionStability.deployedGenesChosenInFewerThanHalfTheFolds} of the{' '}
          {explanation.selectionStability.deployedGeneCount} deployed genes are chosen in
          fewer than half the folds.
        </p>
        <ul className="muted fine">
          {(explanation.perClass.decisionFunction
            ? [{ label: 'decision function', rows: explanation.perClass.decisionFunction.topContributions }]
            : Object.entries(explanation.perClass).map(([label, value]) => ({ label, rows: value.topContributions }))
          ).slice(0, 1).flatMap(({ label, rows }) =>
            rows.slice(0, 6).map((row) => (
              <li key={`${label}-${row.gene}`}>
                {row.gene}: contribution {row.contribution.toFixed(4)} at standardised
                expression {row.standardisedExpression.toFixed(2)}
              </li>
            )))}
        </ul>
        {explanation.singleGeneDependence && <p className="muted fine">
          {explanation.singleGeneDependence.statement} Largest single-gene drop:{' '}
          {explanation.singleGeneDependence.maxMeanDrop.toFixed(4)} balanced accuracy across{' '}
          {explanation.singleGeneDependence.deployedGeneCount} deployed genes.
        </p>}
        <Limitations items={explanation.interpretationLimits} />
      </>}
    </>}
  </Card>
}

export default function RadiationTranscriptomicPrediction() {
  return <>{MODELS.map((model) => <RadiationModelCard key={model.id} model={model} />)}</>
}
