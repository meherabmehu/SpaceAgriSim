import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

/**
 * SPACE GROWTH CHAMBER — interactive isometric visualization, drawn as plain SVG.
 *
 * Phase 33 replaced the three.js scene with this. The scene it replaces was a real
 * three.js render: `three` alone is ~750 kB minified, and a module importing only
 * `{ WebGLRenderer, Scene }` still bundles above 800 kB, so no code-splitting could bring the
 * chunk under Vite's 500 kB warning without deleting the feature. This view keeps what the 3D
 * scene communicated — the enclosure, the trays and their crop rows, growth stage, the light
 * bars, the water manifold, the sensor points and the environmental indicators — and drops the
 * renderer.
 *
 * What is preserved from the scene it replaces:
 *   chamber structure      frame, glazing, deck, ceiling service panel, back-wall grid
 *   crop placement         rows x per-row grid on the trays, deterministic per-plant jitter
 *   crop archetypes        lettuce/radish rosettes (radish with a bulb), tomato vine with fruit
 *   growth stage           canopy fraction drives leaf count, leaf size and stem height; the
 *                          outer leaves unfurl first, as they did in the instanced version
 *   stress cues            leaf colour follows the space-vs-Earth ratio; water deficit desaturates
 *                          and droops; radiation above 1 mGy/day raises the warning strip
 *   environmental panels   LED bars dimmed by photoperiod, three segmented indicators
 *                          (radiation / CO2 / O2), water manifold with reservoir fill
 *   interaction            drag to orbit, wheel or buttons to zoom, click a system to inspect,
 *                          keyboard arrows/±/Home, and a reset
 *
 * What is different: no WebGL, no render loop, no 750 kB download. Motion is SMIL, only mounted
 * when the caller asks for it, so a scrolled-out or reduced-motion twin costs nothing per frame.
 *
 * Everything here is presentation. Every number comes from `deriveTwinState`, which only rescales
 * values the API already returned; nothing in this file computes growth, water or gas exchange.
 */

// ----------------------------------------------------------------------------- projection

const CHAMBER = { w: 6.4, h: 2.9, d: 4.2 }
const TRAY_Y = -0.85
const VIEW = { width: 560, height: 320, scale: 42, cx: 280, cy: 196 }
const HOME_VIEW = { azimuth: -34, elevation: 24, zoom: 1 }

const clamp = (value, low, high) => Math.max(low, Math.min(high, value))

/**
 * Oblique-parallel projection: rotate about the vertical axis, then tilt.
 *
 * Returns `[x, y, depth]` in viewBox units. `depth` is the distance toward the camera and is used
 * only for painter's-algorithm ordering; it is not part of the drawn coordinate.
 */
function projector(azimuth, elevation, zoom) {
  const a = (azimuth * Math.PI) / 180
  const e = (elevation * Math.PI) / 180
  const ca = Math.cos(a)
  const sa = Math.sin(a)
  const ce = Math.cos(e)
  const se = Math.sin(e)
  const k = VIEW.scale * zoom
  return (x, y, z) => {
    const xr = x * ca - z * sa
    const zr = x * sa + z * ca
    return [VIEW.cx + xr * k, VIEW.cy - (y * ce - zr * se) * k, zr]
  }
}

const points = (list) => list.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(' ')

// ----------------------------------------------------------------------------- palette

const FRAME = '#33415c'
const FRAME_DIM = '#22304a'
const PANEL = '#0b1222'
const PANEL_LIT = '#101c33'
const TRAY = '#1d2c48'
const MEDIUM = '#1f2a3d'
const GLAZING = '#9fd4e6'
const LEAF_HEALTHY = '#4ade80'
const LEAF_STRESSED = '#a3a34a'
const WATER_OK = '#60a5fa'
const WATER_LOW = '#fbbf24'
const RADIATION = '#f87171'
const CO2 = '#c084fc'
const O2 = '#7dd3fc'
const LIGHT_BAR = '#fbeed2'

/** Mix two hex colours; `t` is the weight of the second. Keeps leaf colour continuous. */
function mix(a, b, t) {
  const parse = (hex) => [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16))
  const [r1, g1, b1] = parse(a)
  const [r2, g2, b2] = parse(b)
  const w = clamp(t, 0, 1)
  const channel = (x, y) => Math.round(x + (y - x) * w).toString(16).padStart(2, '0')
  return `#${channel(r1, r2)}${channel(g1, g2)}${channel(b1, b2)}`
}

// ----------------------------------------------------------------------------- plant geometry

/**
 * Plant archetypes, carried over from the scene they replace.
 *   rosette  lettuce / radish — whorls of leaves around a very short stem
 *   vine     tomato — a taller stem with tiers of leaflets and fruit
 * Leaf counts and sizes are presentation choices scaled by the canopy fraction; they are not a
 * growth model.
 */
const ARCHETYPES = {
  lettuce: {
    kind: 'rosette', leaf: '#4cbf6e', whorls: 3,
    rings: [{ n: 7, len: 1.0, spread: 1.0 }, { n: 5, len: 0.78, spread: 0.72 }, { n: 4, len: 0.55, spread: 0.48 }],
  },
  radish: {
    kind: 'rosette', leaf: '#3fae62', whorls: 2, bulb: '#c94a63',
    rings: [{ n: 6, len: 0.92, spread: 0.9 }, { n: 4, len: 0.66, spread: 0.6 }],
  },
  tomato: {
    kind: 'vine', leaf: '#3a9d5c', fruit: '#d9534f', stem: 1.0, tiers: 4, leafletsPerTier: 5,
  },
}

/** Deterministic pseudo-random in [0, 1) so a re-render never reshuffles the chamber. */
const noise = (i) => {
  const x = Math.sin(i * 12.9898) * 43758.5453
  return x - Math.floor(x)
}

// ----------------------------------------------------------------------------- component

export default function GrowthChamberView({ state, reduced = false, paused = false, onInspect, selected }) {
  const [view, setView] = useState(HOME_VIEW)
  const [dragging, setDragging] = useState(false)
  const svgRef = useRef(null)
  const drag = useRef({ active: false, x: 0, y: 0, moved: 0 })

  const animate = !reduced && !paused
  const project = useMemo(() => projector(view.azimuth, view.elevation, view.zoom), [view])

  const orbit = useCallback((dx, dy) => {
    setView((current) => ({
      ...current,
      azimuth: clamp(current.azimuth + dx * 0.45, -80, 80),
      elevation: clamp(current.elevation - dy * 0.3, 10, 55),
    }))
  }, [])

  const zoomBy = useCallback((factor) => {
    setView((current) => ({ ...current, zoom: clamp(current.zoom * factor, 0.72, 1.7) }))
  }, [])

  const reset = useCallback(() => setView(HOME_VIEW), [])

  // Wheel zoom needs a non-passive listener: React's onWheel is passive in Chrome, so
  // preventDefault there would warn and the page would scroll while the view zoomed.
  useEffect(() => {
    const node = svgRef.current
    if (!node) return undefined
    const onWheel = (event) => {
      event.preventDefault()
      zoomBy(event.deltaY < 0 ? 1.08 : 0.926)
    }
    node.addEventListener('wheel', onWheel, { passive: false })
    return () => node.removeEventListener('wheel', onWheel)
  }, [zoomBy])

  const onPointerDown = (event) => {
    drag.current = { active: true, x: event.clientX, y: event.clientY, moved: 0 }
    setDragging(true)
    event.currentTarget.setPointerCapture?.(event.pointerId)
  }

  const onPointerMove = (event) => {
    if (!drag.current.active) return
    const dx = event.clientX - drag.current.x
    const dy = event.clientY - drag.current.y
    drag.current.x = event.clientX
    drag.current.y = event.clientY
    drag.current.moved += Math.abs(dx) + Math.abs(dy)
    orbit(dx, dy)
  }

  const endDrag = (event) => {
    drag.current.active = false
    setDragging(false)
    event.currentTarget.releasePointerCapture?.(event.pointerId)
  }

  /** A click that followed a drag is an orbit, not a selection. */
  const inspect = (key) => (event) => {
    event.stopPropagation()
    if (drag.current.moved > 6) return
    onInspect?.(key)
  }

  const onKeyDown = (event) => {
    const actions = {
      ArrowLeft: () => orbit(-6, 0),
      ArrowRight: () => orbit(6, 0),
      ArrowUp: () => orbit(0, -5),
      ArrowDown: () => orbit(0, 5),
      '+': () => zoomBy(1.1),
      '=': () => zoomBy(1.1),
      '-': () => zoomBy(0.9),
      Home: reset,
    }
    const action = actions[event.key]
    if (!action) return
    event.preventDefault()
    action()
  }

  const geometry = useMemo(() => buildGeometry(state, project), [state, project])
  const leaf = mix(LEAF_HEALTHY, LEAF_STRESSED, (1 - state.health) * 0.9 + (state.waterDeficit ? 0.15 : 0))
  const waterColor = state.waterDeficit ? WATER_LOW : WATER_OK

  return (
    <div className="relative h-full w-full">
      <svg
        ref={svgRef}
        viewBox={`0 0 ${VIEW.width} ${VIEW.height}`}
        className="h-full w-full touch-none select-none"
        style={{ cursor: dragging ? 'grabbing' : 'grab' }}
        role="img"
        aria-label="Isometric view of the growth chamber"
        tabIndex={0}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={endDrag}
        onPointerCancel={endDrag}
        onKeyDown={onKeyDown}
        onDoubleClick={reset}
      >
        <defs>
          <linearGradient id="twin-floor" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#0a1222" />
            <stop offset="100%" stopColor="#070c18" />
          </linearGradient>
          <linearGradient id="twin-light" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={LIGHT_BAR} stopOpacity={0.05 + state.light * 0.35} />
            <stop offset="100%" stopColor={LIGHT_BAR} stopOpacity="0" />
          </linearGradient>
          <radialGradient id="twin-glow" cx="50%" cy="0%" r="80%">
            <stop offset="0%" stopColor={LIGHT_BAR} stopOpacity={0.06 + state.light * 0.14} />
            <stop offset="100%" stopColor={LIGHT_BAR} stopOpacity="0" />
          </radialGradient>
        </defs>

        <rect x="0" y="0" width={VIEW.width} height={VIEW.height} fill="#070c18" />
        <ellipse cx={VIEW.cx} cy={VIEW.cy - 40} rx={210 * view.zoom} ry={120 * view.zoom} fill="url(#twin-glow)" />

        {/* ---------------------------------------------------------------- enclosure */}
        <g aria-hidden="true">
          <polygon points={points(geometry.backPanel)} fill="#0d1730" stroke={FRAME_DIM} strokeWidth="1" />
          {geometry.backGrid.map((line, index) => (
            <line key={`grid-${index}`} {...line} stroke="#16223b" strokeWidth="0.8" />
          ))}
          {/* left and right glazing, then the front pane last so it reads as glass */}
          {geometry.glazing.map((pane, index) => (
            <polygon key={`glazing-${index}`} points={points(pane)} fill={GLAZING} fillOpacity={index === 2 ? 0.05 : 0.09}
              stroke={GLAZING} strokeOpacity="0.18" strokeWidth="0.8" />
          ))}
          <polygon points={points(geometry.deck)} fill="url(#twin-floor)" stroke={FRAME_DIM} strokeWidth="1" />
          {/* chamber frame bars, brightest along the top */}
          {geometry.frame.map((bar, index) => (
            <line key={`frame-${index}`} x1={bar[0]} y1={bar[1]} x2={bar[2]} y2={bar[3]}
              stroke={bar[4]} strokeWidth={bar[5]} strokeLinecap="round" />
          ))}
        </g>

        {/* ---------------------------------------------------------------- backing systems */}
        <g onClick={inspect('sensors')} style={{ cursor: 'pointer' }} aria-hidden="true">
          {geometry.sensors.map((dot, index) => (
            <g key={`sensor-${index}`}>
              <rect x={dot[0] - 2.5} y={dot[1] - 2.5} width="5" height="5" rx="1" fill="#0f2a33" stroke="#22d3ee" strokeWidth="0.9" />
              <rect x={dot[0] - 1.6} y={dot[1] - 1.6} width="3.2" height="3.2" fill="#22d3ee">
                {animate && (
                  <animate attributeName="opacity" values="0.25;0.95;0.25" dur="2.6s" begin={`${index * 0.35}s`} repeatCount="indefinite" />
                )}
              </rect>
            </g>
          ))}
        </g>

        {geometry.indicators.map((strip) => (
          <g key={strip.key} aria-hidden="true">
            <polygon points={points(strip.plate)} fill="#0c1426" stroke={FRAME_DIM} strokeWidth="0.8" />
            {strip.segments.map((segment) => (
              <polygon key={segment.index} points={points(segment.poly)}
                fill={segment.on ? segment.color : '#1b2640'} opacity={segment.on ? 0.95 : 0.75} />
            ))}
          </g>
        ))}

        {/* ---------------------------------------------------------------- light bars */}
        <g onClick={inspect('lighting')} style={{ cursor: 'pointer' }} aria-hidden="true">
          <polygon points={points(geometry.lightBeam)} fill="url(#twin-light)" />
          {geometry.lightBars.map((bar, index) => (
            <g key={`light-${index}`}>
              <polygon points={points(bar.chassis)} fill="#141d33" stroke={FRAME_DIM} strokeWidth="0.7" />
              <polygon points={points(bar.diffuser)} fill={LIGHT_BAR} opacity={0.18 + state.light * 0.7} />
              {bar.diodes.map((diode) => (
                <circle key={diode.index} cx={diode.x} cy={diode.y} r="1.15" fill={diode.tint} opacity={0.35 + state.light * 0.6} />
              ))}
            </g>
          ))}
        </g>

        {/* ---------------------------------------------------------------- trays and crops */}
        <g onClick={inspect('crops')} style={{ cursor: 'pointer' }} aria-hidden="true">
          {geometry.trays.map((tray, index) => (
            <g key={`tray-${index}`}>
              <polygon points={points(tray.top)} fill={TRAY} stroke={FRAME_DIM} strokeWidth="0.7" />
              <polygon points={points(tray.medium)} fill={MEDIUM} />
              <polygon points={points(tray.legs)} fill={FRAME} opacity="0.8" />
            </g>
          ))}
          {geometry.plants.map((plant) => (
            <g key={`plant-${plant.key}`} opacity={plant.visible ? 1 : 0}>
              {plant.stem && (
                <line x1={plant.x} y1={plant.y} x2={plant.x} y2={plant.y - plant.stem} stroke="#5f8a5a" strokeWidth={plant.stemWidth} strokeLinecap="round" />
              )}
              {plant.leaves.map((shape) => (
                <ellipse key={shape.key} cx={shape.cx} cy={shape.cy} rx={shape.rx} ry={shape.ry}
                  transform={`rotate(${shape.angle} ${shape.cx} ${shape.cy})`} fill={leaf} opacity={shape.opacity} />
              ))}
              {plant.fruit && plant.fruit.map((dot) => (
                <circle key={dot.key} cx={dot.cx} cy={dot.cy} r={dot.r} fill={ARCHETYPES[state.crop]?.fruit ?? '#d9534f'} />
              ))}
              {plant.bulb && (
                <ellipse cx={plant.bulb.cx} cy={plant.bulb.cy} rx={plant.bulb.rx} ry={plant.bulb.ry} fill={ARCHETYPES[state.crop]?.bulb ?? '#c94a63'} opacity="0.9" />
              )}
            </g>
          ))}
        </g>

        {/* ---------------------------------------------------------------- water manifold */}
        <g onClick={inspect('water')} style={{ cursor: 'pointer' }} aria-hidden="true">
          {geometry.water.branches.map((branch, index) => (
            <line key={`branch-${index}`} x1={branch[0]} y1={branch[1]} x2={branch[2]} y2={branch[3]}
              stroke={waterColor} strokeWidth="1.4" opacity={0.4 + state.waterSupply * 0.5} />
          ))}
          <line id="twin-water-line" x1={geometry.water.main[0]} y1={geometry.water.main[1]}
            x2={geometry.water.main[2]} y2={geometry.water.main[3]}
            stroke={waterColor} strokeWidth="2.6" strokeLinecap="round" opacity={0.35 + state.waterSupply * 0.6} />
          <polygon points={points(geometry.water.reservoir)} fill="#13203a" stroke={FRAME_DIM} strokeWidth="0.8" />
          <polygon points={points(geometry.water.reservoirFill)} fill={waterColor} opacity="0.75" />
          {state.waterSupply > 0.02 && (
            <circle r="2.4" fill={waterColor}>
              {animate ? (
                <animateMotion dur={`${(2.6 - state.waterSupply * 1.5).toFixed(2)}s`} repeatCount="indefinite">
                  <mpath href="#twin-water-line" />
                </animateMotion>
              ) : (
                <animateMotion dur="0s" fill="freeze">
                  <mpath href="#twin-water-line" />
                </animateMotion>
              )}
            </circle>
          )}
        </g>

        {/* selection outline: which system the legend is describing */}
        {geometry.highlights[selected]?.map((poly, index) => (
          <polygon key={`hl-${index}`} points={points(poly)} fill="#4ade80" fillOpacity="0.07"
            stroke="#4ade80" strokeOpacity="0.5" strokeWidth="1.2" strokeDasharray="4 3" aria-hidden="true" />
        ))}
      </svg>

      {/* overlay controls: real buttons, so the view is reachable without a pointer */}
      <div className="pointer-events-none absolute bottom-2 left-3 flex items-center gap-1">
        <span className="pointer-events-auto inline-flex overflow-hidden rounded border border-line-strong bg-space-950/80">
          <button type="button" onClick={() => orbit(-8, 0)} aria-label="Rotate view left"
            className="px-2 py-0.5 font-mono text-[13px] text-slate-300 hover:bg-space-800 hover:text-accent">←</button>
          <button type="button" onClick={() => orbit(8, 0)} aria-label="Rotate view right"
            className="border-l border-line-strong px-2 py-0.5 font-mono text-[13px] text-slate-300 hover:bg-space-800 hover:text-accent">→</button>
          <button type="button" onClick={() => zoomBy(1.1)} aria-label="Zoom in"
            className="border-l border-line-strong px-2 py-0.5 font-mono text-[13px] text-slate-300 hover:bg-space-800 hover:text-accent">+</button>
          <button type="button" onClick={() => zoomBy(0.9)} aria-label="Zoom out"
            className="border-l border-line-strong px-2 py-0.5 font-mono text-[13px] text-slate-300 hover:bg-space-800 hover:text-accent">−</button>
          <button type="button" onClick={reset} aria-label="Reset view"
            className="border-l border-line-strong px-2 py-0.5 font-mono text-[13px] tracking-wider text-slate-300 hover:bg-space-800 hover:text-accent">RESET</button>
        </span>
      </div>
      <p className="pointer-events-none absolute bottom-2 right-3 font-mono text-[13px] tracking-wider text-slate-500">
        DRAG TO ORBIT · SCROLL TO ZOOM
      </p>
    </div>
  )
}

// ----------------------------------------------------------------------------- geometry

/**
 * Everything drawn, computed once per state change.
 *
 * Painter's order matters: plants are emitted tray by tray from the far row to the near row so a
 * near plant overlaps a far one, exactly as the depth-sorted 3D scene did.
 */
function buildGeometry(state, project) {
  const { w, h, d } = CHAMBER
  const half = { w: w / 2, h: h / 2, d: d / 2 }

  const corner = (sx, sy, sz) => project((sx * half.w), (sy * half.h), (sz * half.d))

  // --------------------------------------------------------------- enclosure
  const backPanel = [
    corner(-1, 1, -1), corner(1, 1, -1), corner(1, -1, -1), corner(-1, -1, -1),
  ].map(([x, y]) => [x, y])

  const deck = [
    corner(-1, -1, -1), corner(1, -1, -1), corner(1, -1, 1), corner(-1, -1, 1),
  ].map(([x, y]) => [x, y])

  const face = (sx, sy, sz) => {
    const [x, y] = corner(sx, sy, sz)
    return [x, y]
  }
  const glazing = [
    // left, right and front panes
    [face(-1, 1, -1), face(-1, 1, 1), face(-1, -1, 1), face(-1, -1, -1)],
    [face(1, 1, -1), face(1, 1, 1), face(1, -1, 1), face(1, -1, -1)],
    [face(-1, 1, 1), face(1, 1, 1), face(1, -1, 1), face(-1, -1, 1)],
  ]

  const bar = (from, to, color, width) => {
    const [x1, y1] = corner(...from)
    const [x2, y2] = corner(...to)
    return [x1, y1, x2, y2, color, width]
  }
  const top = FRAME
  const low = FRAME_DIM
  const frame = [
    // vertical posts
    bar([-1, -1, -1], [-1, 1, -1], top, 3), bar([1, -1, -1], [1, 1, -1], top, 3),
    bar([-1, -1, 1], [-1, 1, 1], top, 3), bar([1, -1, 1], [1, 1, 1], top, 3),
    // top rails
    bar([-1, 1, -1], [1, 1, -1], top, 3), bar([-1, 1, 1], [1, 1, 1], top, 3),
    bar([-1, 1, -1], [-1, 1, 1], top, 3), bar([1, 1, -1], [1, 1, 1], top, 3),
    // floor rails
    bar([-1, -1, -1], [1, -1, -1], low, 2), bar([-1, -1, 1], [1, -1, 1], low, 2),
    bar([-1, -1, -1], [-1, -1, 1], low, 2), bar([1, -1, -1], [1, -1, 1], low, 2),
  ]

  const backGrid = []
  for (let i = -3; i <= 3; i += 1) {
    const x = (i / 7) * w
    const [x1, y1] = project(x, half.h, -half.d)
    const [x2, y2] = project(x, -half.h, -half.d)
    backGrid.push({ x1, y1, x2, y2 })
  }
  for (let i = -1; i <= 1; i += 1) {
    const y = (i / 3) * half.h
    const [x1, y1] = project(-half.w, y, -half.d)
    const [x2, y2] = project(half.w, y, -half.d)
    backGrid.push({ x1, y1, x2, y2 })
  }

  // --------------------------------------------------------------- light bars
  const ceilingY = half.h - 0.14
  const stripXs = [-2.3, -1.15, 0, 1.15, 2.3]
  const stripHalf = (d - 1.2) / 2
  const lightBars = stripXs.map((x) => {
    const chassis = [
      [x - 0.16, 0, -stripHalf], [x + 0.16, 0, -stripHalf],
      [x + 0.16, 0, stripHalf], [x - 0.16, 0, stripHalf],
    ].map(([px, , pz]) => { const [sx, sy] = project(px, ceilingY, pz); return [sx, sy] })
    const diffuser = [
      [x - 0.11, 0, -stripHalf + 0.06], [x + 0.11, 0, -stripHalf + 0.06],
      [x + 0.11, 0, stripHalf - 0.06], [x - 0.11, 0, stripHalf - 0.06],
    ].map(([px, , pz]) => { const [sx, sy] = project(px, ceilingY - 0.035, pz); return [sx, sy] })
    const diodes = Array.from({ length: 7 }).map((_, index) => {
      const z = -stripHalf + ((stripHalf * 2) * (index + 0.5)) / 7
      const [sx, sy] = project(x, ceilingY - 0.04, z)
      return { index, x: sx, y: sy, tint: index % 3 === 1 ? '#6aa0ff' : '#ff6a5a' }
    })
    return { chassis, diffuser, diodes }
  })
  const lightBeam = [
    [-w / 2 + 0.6, 0, -half.d + 0.4], [w / 2 - 0.6, 0, -half.d + 0.4],
    [w / 2 - 0.6, 0, half.d - 0.4], [-w / 2 + 0.6, 0, half.d - 0.4],
  ].map(([px, , pz]) => {
    const [topX, topY] = project(px, ceilingY - 0.06, pz)
    return [topX, topY]
  })
  const beamFloor = [
    [-w / 2 + 0.6, 0, -half.d + 0.4], [w / 2 - 0.6, 0, -half.d + 0.4],
    [w / 2 - 0.6, 0, half.d - 0.4], [-w / 2 + 0.6, 0, half.d - 0.4],
  ].map(([px, , pz]) => { const [sx, sy] = project(px, TRAY_Y, pz); return [sx, sy] })

  // --------------------------------------------------------------- trays
  const rowCount = Math.max(state.rows, 1)
  const rowGap = d / (rowCount + 1)
  const trayHalfW = (w - 1.0) / 2
  const trays = Array.from({ length: rowCount }).map((_, index) => {
    const z = -half.d + rowGap * (index + 1)
    const quad = (y, halfWidth, halfDepth) => [
      [-halfWidth, 0, -halfDepth], [halfWidth, 0, -halfDepth],
      [halfWidth, 0, halfDepth], [-halfWidth, 0, halfDepth],
    ].map(([px, , pz]) => { const [sx, sy] = project(px, y, z + pz); return [sx, sy] })
    return {
      top: quad(TRAY_Y + 0.07, trayHalfW, 0.35),
      medium: quad(TRAY_Y + 0.085, trayHalfW - 0.05, 0.3),
      legs: quad(TRAY_Y - 0.3, trayHalfW - 0.15, 0.28),
    }
  })

  // --------------------------------------------------------------- plants
  const archetype = ARCHETYPES[state.crop] ?? ARCHETYPES.lettuce
  const plants = []
  if (!state.noArea && state.rows > 0) {
    const span = w - 1.4
    const colGap = span / state.perRow
    const scale = Math.max(state.canopyScale, 0.16)
    const droop = state.waterDeficit ? 0.35 : 0
    const rings = archetype.kind === 'rosette' ? archetype.rings : null
    const totalLeaves = rings ? rings.reduce((sum, ring) => sum + ring.n, 0) : archetype.tiers * archetype.leafletsPerTier
    const visibleLeaves = Math.max(2, Math.round(totalLeaves * Math.min(1, 0.25 + scale * 0.85)))

    for (let r = 0; r < state.rows; r += 1) {
      for (let c = 0; c < state.perRow; c += 1) {
        const key = `${r}-${c}`
        const jitterX = (noise(r * 7 + c * 13) - 0.5) * 0.12
        const jitterZ = (noise(r * 5 + c * 11) - 0.5) * 0.16
        const vigor = 0.88 + noise(r * 3 + c * 5) * 0.22
        const s = scale * vigor
        const x = -span / 2 + colGap * (c + 0.5) + jitterX
        const z = -half.d + rowGap * (r + 1) + jitterZ
        const [bx, by] = project(x, TRAY_Y + 0.09, z)

        const leaves = []
        let drawn = 0

        if (archetype.kind === 'rosette') {
          rings.forEach((ring, ringIndex) => {
            for (let i = 0; i < ring.n; i += 1) {
              const slot = drawn
              drawn += 1
              if (slot >= visibleLeaves) continue
              const angle = (i / ring.n) * 360 + ringIndex * 26 + noise(r * 11 + c * 17 + slot) * 18
              const radius = ring.len * s * 15 * (0.86 + noise(slot + r * 3) * 0.28)
              const tilt = clamp(1 - droop * 0.7 - ringIndex * 0.12, 0.25, 1)
              const rad = (angle * Math.PI) / 180
              leaves.push({
                key: `${key}-${slot}`,
                cx: bx + Math.cos(rad) * radius * 0.42,
                cy: by - 3 - Math.sin(rad) * radius * 0.2 - ringIndex * 1.5,
                rx: radius * 0.62,
                ry: Math.max(1.4, radius * 0.3 * tilt),
                angle: Math.sin(rad) * 26,
                opacity: 0.82 + noise(slot) * 0.18,
              })
            }
          })
        } else {
          const stemPx = 26 * s * archetype.stem
          for (let tier = 0; tier < archetype.tiers; tier += 1) {
            const tierY = by - (stemPx * (0.3 + (0.7 * tier) / (archetype.tiers - 1)))
            for (let i = 0; i < archetype.leafletsPerTier; i += 1) {
              const slot = drawn
              drawn += 1
              if (slot >= visibleLeaves) continue
              const angle = (i / archetype.leafletsPerTier) * 360 + tier * 46
              const rad = (angle * Math.PI) / 180
              const len = 11 * s * (1 - tier * 0.1)
              leaves.push({
                key: `${key}-${slot}`,
                cx: bx + Math.cos(rad) * len * 0.5,
                cy: tierY + Math.sin(rad) * len * 0.22,
                rx: len * 0.55,
                ry: Math.max(1.2, len * 0.26),
                angle: Math.sin(rad) * 30,
                opacity: 0.85,
              })
            }
          }
        }

        const fruitVisible = archetype.kind === 'vine' && state.canopyScale > 0.55
        const bulbVisible = archetype.bulb && state.canopyScale > 0.35
        plants.push({
          key,
          x: bx,
          y: by,
          visible: true,
          stem: archetype.kind === 'vine' ? 26 * s * archetype.stem : 3 * s,
          stemWidth: archetype.kind === 'vine' ? Math.max(1, 2.2 * s) : 1.2,
          leaves,
          fruit: fruitVisible
            ? [0, 1].map((n) => ({
                key: `${key}-fruit-${n}`,
                cx: bx + (n === 0 ? 4 : -3.5) * s,
                cy: by - 26 * s * archetype.stem * (n === 0 ? 0.55 : 0.72),
                r: 2.4 * s,
              }))
            : null,
          bulb: bulbVisible
            ? { cx: bx, cy: by + 1.5, rx: 4.6 * s, ry: 3.1 * s }
            : null,
        })
      }
    }
  }

  // --------------------------------------------------------------- water
  const lineY = TRAY_Y - 0.3
  const [mx1, my1] = project(-(w - 1.6) / 2, lineY, half.d - 0.35)
  const [mx2, my2] = project((w - 1.6) / 2, lineY, half.d - 0.35)
  const branches = Array.from({ length: rowCount }).map((_, index) => {
    const z = -half.d + rowGap * (index + 1)
    const [bx, by] = project((w - 1.4) / 2, lineY, z)
    return [mx2, my2, bx, by]
  })
  const reservoirWidth = 0.3
  const reservoirDepth = 0.3
  const reservoirX = -(w - 1.0) / 2
  const reservoirZ = half.d - 0.35
  const reservoir = [
    [reservoirX - reservoirWidth, 0, reservoirZ - reservoirDepth],
    [reservoirX, 0, reservoirZ - reservoirDepth],
    [reservoirX, 0, reservoirZ + reservoirDepth],
    [reservoirX - reservoirWidth, 0, reservoirZ + reservoirDepth],
  ].map(([px, , pz]) => { const [sx, sy] = project(px, lineY - 0.25, pz); return [sx, sy] })
  const fillHeight = 0.5 * clamp(state.waterSupply, 0.02, 1)
  const reservoirFill = [
    [reservoirX - reservoirWidth, 0, reservoirZ - reservoirDepth],
    [reservoirX, 0, reservoirZ - reservoirDepth],
    [reservoirX, 0, reservoirZ + reservoirDepth],
    [reservoirX - reservoirWidth, 0, reservoirZ + reservoirDepth],
  ].map(([px, , pz]) => { const [sx, sy] = project(px, lineY - 0.25 - 0.5 + fillHeight, pz); return [sx, sy] })

  // --------------------------------------------------------------- sensors
  const sensors = [
    [-2.4, -0.4, -half.d + 0.12], [-0.8, -0.4, -half.d + 0.12],
    [0.8, -0.4, -half.d + 0.12], [2.4, -0.4, -half.d + 0.12],
    [(w - 0.4) / 2, 0.7, 0.6], [-(w - 0.4) / 2, 0.7, -0.6],
  ].map(([px, py, pz]) => project(px, py, pz).slice(0, 2))

  // --------------------------------------------------------------- indicators
  const strip = (key, x, level, color, warning) => {
    const segments = 6
    const lit = Math.round(clamp(level, 0, 1) * segments)
    const plateHalfW = 0.11
    const plateHalfH = (0.14 * segments + 0.1) / 2
    const plate = [
      [-plateHalfW, plateHalfH, 0], [plateHalfW, plateHalfH, 0],
      [plateHalfW, -plateHalfH, 0], [-plateHalfW, -plateHalfH, 0],
    ].map(([px, py, pz]) => { const [sx, sy] = project(x + px, 0.35 + py, -half.d + 0.12 + pz); return [sx, sy] })
    const litColor = warning ? '#f0b13a' : color
    return {
      key,
      plate,
      segments: Array.from({ length: segments }).map((_, index) => {
        const y = -((segments - 1) * 0.14) / 2 + index * 0.14
        const poly = [
          [-0.07, y - 0.045, 0.01], [0.07, y - 0.045, 0.01],
          [0.07, y + 0.045, 0.01], [-0.07, y + 0.045, 0.01],
        ].map(([px, py, pz]) => { const [sx, sy] = project(x + px, 0.35 + py, -half.d + 0.12 + pz); return [sx, sy] })
        return { index, on: index < lit, color: litColor, poly }
      }),
    }
  }
  const indicators = [
    strip('radiation', -half.w + 0.45, state.radiation, RADIATION, state.radiationWarning),
    strip('co2', half.w - 0.85, state.co2Level, CO2, false),
    strip('o2', half.w - 0.45, state.gasActivity, O2, false),
  ]

  // --------------------------------------------------------------- selection outlines
  const highlights = {
    crops: trays.map((tray) => tray.top),
    lighting: lightBars.map((bar) => bar.chassis),
    water: [reservoir, beamFloor],
    sensors: [],
  }

  return {
    backPanel, backGrid, deck, glazing, frame, lightBars, lightBeam,
    trays, plants, water: { main: [mx1, my1, mx2, my2], branches, reservoir, reservoirFill },
    sensors, indicators, highlights,
  }
}
