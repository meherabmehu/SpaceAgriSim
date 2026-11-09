import { useState } from 'react'
import { api } from '../../services/platformApi.ts'
import { Card, number } from '../missionUI.jsx'
import { Limitations } from './moduleSupport.jsx'

export default function EarthLettucePrediction(){
  const [inputs,setInputs]=useState({crop:'lettuce',daysAfterTransplant:20,airTemperature:24,rootTemperature:28,ppfd:400})
  const [result,setResult]=useState(null)
  const [error,setError]=useState('')
  const [busy,setBusy]=useState(false)
  const fields=[['daysAfterTransplant','Days after transplant',0,60,1],['airTemperature','Air temperature (°C)',5,40,1],['rootTemperature','Root temperature (°C)',5,40,1],['ppfd','PPFD (µmol/m²/s)',0,1000,10]]
  const predict=async()=>{setBusy(true);setError('');setResult(null);try{setResult(await api('/predict/lettuce-earth-growth-v1',inputs))}catch(err){setError(err.message)}finally{setBusy(false)}}
  return <Card title="Earth lettuce growth experiment" label="WAGENINGEN / 4TU · EXTERNAL DATA, NOT NASA">
    <p className="prose">Predict fresh shoot mass per plant for Batavia Othilie lettuce in Earth growth chambers. The source uses a 16-hour photoperiod and non-limiting water, nutrients and CO₂. This model cannot estimate spaceflight yield or area-level production.</p>
    <div className="warning-box"><p>The current v2 lettuce model failed an independent check: scored against a Thai greenhouse trial it was never trained on, it overpredicted fresh weight by ×1.7 to ×5.4. This v1 model shares the same four inputs and no cultivar input, so treat any value below as exploratory, not as a harvest forecast. See the benchmarks page for the per-observation numbers.</p></div>
    <div className="control-grid">{fields.map(([key,label,min,max,step])=><label className="field" key={key}>{label}<input type="number" min={min} max={max} step={step} value={inputs[key]} onChange={e=>{setInputs({...inputs,[key]:Number(e.target.value)});setResult(null)}}/></label>)}</div>
    <div className="module-actions"><button className="primary-button" disabled={busy} onClick={predict}>{busy?'Computing…':'Predict Earth lettuce mass'}</button></div>
    {error&&<div className="error-banner" role="alert">{error}</div>}
    {result&&<><div className="comparison-value">{number(result.prediction)} <small>{result.unit}</small></div><p className="muted fine">Descriptive residual range: {number(result.interval.low)}–{number(result.interval.high)} g, uncalibrated. {result.outOfDistribution?'Outside supported data coverage.':'Within marginal training ranges; experimental combinations are sparse.'}</p><Limitations items={result.warnings}/><a className="wide-link" href={result.sourceUrl} target="_blank" rel="noreferrer">Read the CC-BY-4.0 source dataset</a></>}
  </Card>
}
