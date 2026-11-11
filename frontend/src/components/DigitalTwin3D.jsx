import { Component, useEffect, useMemo, useRef, useState } from 'react'
import Panel from './Panel.jsx'
import GrowthChamberView from './GrowthChamberView.jsx'
import { deriveTwinState } from '../services/twinState.js'
import { formatDay, formatMass, formatNumber, formatPercent } from '../services/formatters.js'

const STORAGE_KEY = 'spaceagrisim.twin3d'

/** 'on' | 'off' when the user has toggled the view before, otherwise null. */
function readStoredPreference() {
  try {
    const value = window.localStorage.getItem(STORAGE_KEY)
    return value === 'on' || value === 'off' ? value : null
  } catch {
    return null
  }
}

/**
 * The chamber view is on by default; an explicit user choice always wins.
 *
 * The stored value is the same key and the same 'on'/'off' vocabulary the previous 3D view used,
 * so an existing preference survives the Phase 33 redesign instead of resetting.
 */
function initialEnabled() {
  const stored = readStoredPreference()
  return stored ? stored === 'on' : true
}

const LEGEND = [
  { key: 'growth', label: 'Growth', color: '#4ade80', read: (s) => `${formatNumber(s.canopyScale * 100, 0)}% of a full canopy` },
  { key: 'water', label: 'Water', color: '#60a5fa', read: (s) => (s.waterDeficit ? `${formatNumber(s.waterSupply * 100, 0)}% supplied · deficit` : 'demand met') },
  { key: 'radiation', label: 'Radiation', color: '#f87171', read: (s) => `${formatNumber(s.radiationMgy, 2)} mGy/day${s.radiationWarning ? ' · warning' : ''}` },
  { key: 'co2', label: 'CO₂', color: '#c084fc', read: (s) => `${formatNumber(s.co2Ppm, 0)} ppm` },
  { key: 'o2', label: 'O₂', color: '#7dd3fc', read: (s) => `${formatNumber(s.gasActivity * 100, 0)}% exchange activity` },
]

/**
 * SPACE GROWTH CHAMBER - digital-twin visualization of the simulation.
 *
 * - interactive isometric CHAMBER VIEW by default, with a clear CHAMBER VIEW / 2D SCHEMATIC
 *   switch (choice is remembered)
 * - both views are plain SVG: no WebGL, no renderer download, no 3D library
 * - falls back to the 2D schematic if the chamber view throws
 * - reads only from the simulation result (via deriveTwinState)
 *
 * Phase 33 replaced the three.js scene that used to sit behind the switch. The scene needed
 * `three` + `@react-three/fiber` + `@react-three/drei`, and `three` alone is ~750 kB minified
 * (over 800 kB even for a module importing two classes), so it could not pass the bundle budget
 * without either deleting the feature or hiding the warning. The chamber view keeps the same
 * information and interactions at a fraction of the weight.
 */
export default function DigitalTwin3D({ result }) {
  const [enabled, setEnabled] = useState(initialEnabled)
  const [reducedMotion, setReducedMotion] = useState(false)
  const [renderError, setRenderError] = useState(null)
  const [inView, setInView] = useState(true)
  const [selected, setSelected] = useState('crops')
  const viewportRef = useRef(null)
  const state = useMemo(() => deriveTwinState(result), [result])

  useEffect(() => {
    const media = window.matchMedia('(prefers-reduced-motion: reduce)')
    const update = () => setReducedMotion(media.matches)
    update()
    media.addEventListener('change', update)
    return () => media.removeEventListener('change', update)
  }, [])

  // stop the (declarative) animation while the chamber is scrolled out of view
  useEffect(() => {
    const node = viewportRef.current
    if (!node || typeof IntersectionObserver === 'undefined') return undefined
    const observer = new IntersectionObserver(([entry]) => setInView(entry.isIntersecting), { threshold: 0.05 })
    observer.observe(node)
    return () => observer.disconnect()
  }, [])

  const toggle = () => {
    setEnabled((value) => {
      const next = !value
      try {
        window.localStorage.setItem(STORAGE_KEY, next ? 'on' : 'off')
      } catch {
        /* private mode: preference simply is not remembered */
      }
      return next
    })
  }

  const canRenderChamber = !renderError

  return (
    <Panel
      id="digital-twin"
      eyebrow="07"
      title="Space growth chamber"
      subtitle="Digital-twin visualization · driven by the simulation outputs, not by a model of its own"
      padded={false}
      action={
        <button
          type="button"
          role="switch"
          aria-checked={enabled}
          aria-label="Chamber view"
          onClick={toggle}
          className={`rounded border px-2.5 py-1 font-mono text-[14px] tracking-wider transition-colors ${
            enabled ? 'border-accent/60 bg-accent/10 text-accent' : 'border-line-strong text-slate-300 hover:border-accent/60 hover:text-accent'
          }`}
        >
          {enabled ? 'CHAMBER VIEW' : '2D SCHEMATIC'}
        </button>
      }
    >
      <div className="grid lg:grid-cols-[minmax(0,1fr)_15rem]">
        <div ref={viewportRef} className="relative min-h-[16rem] sm:min-h-[20rem] lg:min-h-[22rem]">
          {!state && <Placeholder text="Waiting for simulation…" />}
          {state && !enabled && (
            <Placeholder text="Chamber view is off">
              <SchematicTwin state={state} />
            </Placeholder>
          )}
          {state && enabled && !canRenderChamber && (
            <div className="absolute inset-0 flex flex-col">
              <p className="border-b border-line bg-space-800/60 px-3 py-1.5 font-mono text-[14px] tracking-wider text-warn">
                CHAMBER VIEW FAILED · SHOWING 2D SCHEMATIC
              </p>
              <div className="relative flex-1">
                <SchematicTwin state={state} />
              </div>
            </div>
          )}
          {state && enabled && canRenderChamber && (
            <div className="absolute inset-0">
              <SceneErrorBoundary onError={setRenderError}>
                <GrowthChamberView
                  state={state}
                  reduced={reducedMotion}
                  paused={!inView}
                  onInspect={setSelected}
                  selected={selected}
                />
              </SceneErrorBoundary>
              <div className="pointer-events-none absolute left-3 top-3 rounded border border-line bg-space-950/70 px-2 py-1 font-mono text-[14px] tracking-wider text-slate-300">
                {formatDay(state.day)} · {harvestCaption(state)}
              </div>
              <StatusTags state={state} />
            </div>
          )}
          {state && (
            <p className="pointer-events-none absolute bottom-2 right-3 hidden max-w-[60%] text-right font-mono text-[13px] leading-tight tracking-wider text-slate-500 sm:bottom-9 sm:block">
              VISUALIZATION DRIVEN BY SIMULATION OUTPUTS
            </p>
          )}
        </div>

        <aside className="border-t border-line px-4 py-3 lg:border-l lg:border-t-0" aria-label="Growth chamber legend">
          <p className="label-tech">Legend</p>
          <p className="mt-2 text-xs text-slate-300">Drag to orbit · scroll to zoom · arrow keys and +/− work too.</p>
          <div className="mt-3 flex flex-wrap gap-2" aria-label="Inspect growth chamber components">
            {['crops', 'lighting', 'water', 'sensors'].map((key) => (
              <button
                key={key}
                type="button"
                aria-pressed={selected === key}
                onClick={() => setSelected(key)}
                className={`rounded border px-2 py-1 text-xs ${selected === key ? 'border-accent/60 bg-accent/10 text-accent' : 'border-line-strong text-slate-300 hover:border-accent/60 hover:text-accent'}`}
              >
                {key}
              </button>
            ))}
          </div>
          {result && (
            <p className="mt-3 text-xs leading-relaxed text-slate-300" role="status">
              {selected === 'crops' ? `Standing biomass ${formatMass(result.harvest.standingBiomass)}. Plant shapes are illustrative.`
                : selected === 'lighting' ? `PPFD ${result.inputs.lightIntensity} µmol/m²/s, ${result.inputs.lightHours} h/day. Spectrum: ${result.inputs.lightSpectrum}.`
                  : selected === 'water' ? `Supplied ${formatNumber(result.waterUsed)} L; recovered ${formatNumber(result.waterRecovered)} L. Animated flow is illustrative.`
                    : `Temperature ${result.inputs.temperature} °C; humidity ${result.inputs.humidity}%; CO₂ ${result.inputs.co2Level} ppm. These are configured setpoints, not sensor measurements.`}
            </p>
          )}
          <ul className="mt-2 space-y-2">
            {LEGEND.map((item) => (
              <li key={item.key} className="flex items-start gap-2 text-[13px]">
                <span className="mt-1 h-2 w-2 shrink-0 rounded-sm" style={{ background: item.color }} aria-hidden="true" />
                <span className="min-w-0">
                  <span className="font-mono text-[14px] tracking-wider text-slate-300">{item.label.toUpperCase()}</span>
                  <br />
                  <span className="text-slate-500">{state ? item.read(state) : '–'}</span>
                </span>
              </li>
            ))}
          </ul>
          {state && (
            <p className="mt-3 border-t border-line pt-2 text-[14px] leading-snug text-slate-500">
              Plant size follows standing biomass ({formatMass(result.harvest.standingBiomass)}); leaf colour follows the space-vs-Earth ratio (
              {formatPercent(result.comparison.spaceGrowthPercentage, { digits: 0 })}). Panels, water lines and indicators mirror the control settings.
            </p>
          )}
        </aside>
        {state && (
          <p className="border-t border-line px-3 py-1 font-mono text-[12px] tracking-wider text-slate-500 sm:hidden">
            VISUALIZATION DRIVEN BY SIMULATION OUTPUTS
          </p>
        )}
      </div>
    </Panel>
  )
}

/** Overlay caption: what the chamber is showing in harvest terms. */
function harvestCaption(state) {
  if (!state.harvestWithinWindow) return `NEXT HARVEST ${formatDay(state.nextHarvestDay).toUpperCase()}`
  const cycles = state.cyclesCompleted
  return `${cycles} HARVEST${cycles === 1 ? '' : 'S'} · LAST ${formatDay(state.lastHarvestDay).toUpperCase()} · REGROWING`
}

/** Small amber tags that make the stress cues in the chamber explicit. */
function StatusTags({ state }) {
  const tags = []
  if (state.noArea) tags.push('NO GROWING AREA')
  else if (state.noGrowth) tags.push('NO GROWTH')
  if (state.waterDeficit) tags.push('WATER DEFICIT')
  if (state.radiationWarning) tags.push('HIGH RADIATION')
  if (tags.length === 0) return null
  return (
    <div className="pointer-events-none absolute right-3 top-3 flex flex-col items-end gap-1">
      {tags.map((tag) => (
        <span key={tag} className="rounded border border-warn/50 bg-space-950/70 px-2 py-0.5 font-mono text-[14px] tracking-wider text-warn">
          {tag}
        </span>
      ))}
    </div>
  )
}

function Placeholder({ text, children }) {
  return (
    <div className="absolute inset-0 flex flex-col">
      {children ? <div className="relative flex-1">{children}</div> : null}
      <p className={`${children ? 'border-t border-line bg-space-800/60' : 'm-auto'} px-3 py-1.5 font-mono text-[14px] tracking-wider text-slate-500`}>
        {text}
      </p>
    </div>
  )
}

/** 2D SVG front-elevation schematic of the chamber: the compact alternative to the chamber view. */
function SchematicTwin({ state }) {
  const plants = []
  const rows = state.rows
  const perRow = state.perRow
  for (let r = 0; r < rows; r += 1) {
    for (let c = 0; c < perRow; c += 1) {
      plants.push({ x: 60 + ((c + 0.5) * 280) / perRow, y: 150 - r * 22, r: 4 + state.canopyScale * 9 })
    }
  }
  const leaf = state.health > 0.8 ? '#4ade80' : state.health > 0.5 ? '#86c75a' : '#a3a34a'
  const water = state.waterDeficit ? '#fbbf24' : '#60a5fa'
  return (
    <svg viewBox="0 0 400 200" className="absolute inset-0 h-full w-full" role="img" aria-label="Schematic of the growth chamber">
      <rect x="40" y="20" width="320" height="160" fill="#0c1426" stroke="#27365a" />
      {/* light panels */}
      {[80, 170, 260].map((x) => (
        <rect key={x} x={x} y="26" width="60" height="5" fill="#fbbf24" opacity={0.2 + state.light * 0.8} />
      ))}
      {/* trays */}
      {Array.from({ length: rows }).map((_, r) => (
        <rect key={r} x="60" y={152 - r * 22} width="280" height="4" fill="#1b2a44" />
      ))}
      {/* plants */}
      {plants.map((p, i) => (
        <g key={i}>
          <line x1={p.x} y1={p.y + 2} x2={p.x} y2={p.y - p.r} stroke="#5b8a5b" strokeWidth="1.5" />
          <ellipse cx={p.x} cy={p.y - p.r} rx={p.r} ry={p.r * 0.6} fill={leaf} />
        </g>
      ))}
      {/* water line */}
      <line x1="60" y1="168" x2="340" y2="168" stroke={water} strokeWidth="2" opacity={0.3 + state.waterSupply * 0.7} />
      {/* indicators */}
      <rect x="46" y="60" width="6" height={10 + state.radiation * 30} fill="#f87171" />
      <rect x="338" y="60" width="6" height={10 + state.co2Level * 30} fill="#c084fc" />
      <rect x="348" y="60" width="6" height={10 + state.gasActivity * 30} fill="#7dd3fc" />
      {state.noArea && (
        <text x="200" y="105" textAnchor="middle" fill="#94a3b8" fontSize="11" fontFamily="monospace">
          NO GROWING AREA
        </text>
      )}
    </svg>
  )
}

/**
 * Keeps one unexpected error in the chamber view from blanking the whole panel: the panel falls
 * back to the schematic and says so. The view is plain SVG, so this is defensive only.
 */
class SceneErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { failed: false }
  }

  static getDerivedStateFromError() {
    return { failed: true }
  }

  componentDidCatch(error) {
    this.props.onError?.(error)
  }

  render() {
    return this.state.failed ? null : this.props.children
  }
}
