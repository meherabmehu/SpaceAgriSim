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
    </>}
  </Card>
}

export default function RadiationTranscriptomicPrediction() {
  return <>{MODELS.map((model) => <RadiationModelCard key={model.id} model={model} />)}</>
}
