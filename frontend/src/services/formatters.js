/**
 * Number formatting helpers shared by cards, charts and controls.
 * Keeping them here avoids each component re-implementing unit logic.
 * These only format values the API already computed - no simulation maths.
 */

const formatters = new Map()

function withDigits(digits) {
  if (!formatters.has(digits)) {
    formatters.set(digits, new Intl.NumberFormat('en-US', { maximumFractionDigits: digits }))
  }
  return formatters.get(digits)
}

export function formatNumber(value, digits = 1) {
  if (value == null || Number.isNaN(value)) return '–'
  return withDigits(digits).format(Number(Number(value).toFixed(digits)))
}

/** Grams -> "850 g", "1.24 kg" or "18.3 kg" depending on size. */
export function formatMass(grams) {
  if (grams == null || Number.isNaN(grams)) return '–'
  const abs = Math.abs(grams)
  if (abs >= 10000) return `${formatNumber(grams / 1000, 1)} kg`
  if (abs >= 1000) return `${formatNumber(grams / 1000, 2)} kg`
  return `${formatNumber(grams, 0)} g`
}

/** Litres -> "12.5 L" or "1.2 m³". */
export function formatVolume(litres) {
  if (litres == null || Number.isNaN(litres)) return '–'
  if (Math.abs(litres) >= 1000) return `${formatNumber(litres / 1000, 2)} m³`
  return `${formatNumber(litres, 1)} L`
}

export function formatPercent(value, { signed = false, digits = 1 } = {}) {
  if (value == null || Number.isNaN(value)) return '–'
  const sign = signed && value > 0 ? '+' : ''
  return `${sign}${formatNumber(value, digits)}%`
}

/** Signed percentage points, e.g. "-15.0 pts". */
export function formatPoints(value, digits = 1) {
  if (value == null || Number.isNaN(value)) return '–'
  const sign = value > 0 ? '+' : ''
  return `${sign}${formatNumber(value, digits)} pts`
}

export function formatDays(value, digits = 0) {
  if (value == null || Number.isNaN(value)) return '–'
  const n = formatNumber(value, digits)
  return `${n} ${Number(n) === 1 ? 'day' : 'days'}`
}

/** "Day 35" */
export function formatDay(day) {
  if (day == null) return '–'
  return `Day ${formatNumber(day, 0)}`
}

/** Growth factor -> "×0.85" */
export function formatFactor(value) {
  if (value == null || Number.isNaN(value)) return '–'
  return `×${Number(value).toFixed(2)}`
}

/** Value with its unit, respecting the slider step for decimals. */
export function formatWithUnit(value, unit, step = 1) {
  const decimals = step >= 1 ? 0 : step >= 0.1 ? 1 : 2
  return `${formatNumber(value, decimals)} ${unit}`.trim()
}

/** Relative change between two API values, as a signed percent (presentation only). */
export function relativeChangePercent(before, after) {
  if (before == null || after == null) return null
  if (Math.abs(before) < 1e-9) return Math.abs(after) < 1e-9 ? 0 : null
  return ((after - before) / Math.abs(before)) * 100
}

/**
 * A model's validation text, whatever shape the artifact records it in.
 *
 * Older artifacts store a sentence; models with an independent holdout store a structured object
 * (internal folds, independent study, development set). The object is what lets the API carry a
 * verdict it cannot misrepresent, so it stays - but React cannot render it as a child, and a
 * dashboard error is not a scientific disclosure. This flattens either shape to one sentence, and
 * prefers the API's own `validationSummary` when a newer artifact supplies one.
 */
export function validationText(model) {
  if (!model) return ''
  if (typeof model.validationSummary === 'string' && model.validationSummary) {
    return model.validationSummary
  }
  const validation = model.validation
  if (validation == null) return ''
  if (typeof validation === 'string') return validation
  if (typeof validation !== 'object') return String(validation)

  const parts = []
  const internal = validation.internal
  if (internal && internal.metrics) {
    const mape = internal.metrics.MAPE
    parts.push(
      `${internal.protocol || 'held-out'}: ` +
        (mape != null ? `MAPE ${formatNumber(mape, 1)} %` : 'see metrics'),
    )
  }
  const independent = validation.independent
  if (independent) {
    const mape = (independent.metrics || {}).MAPE
    parts.push(
      `independent holdout ${independent.study ? independent.study.split(',')[0] : 'unnamed'}: ` +
        (mape != null ? `MAPE ${formatNumber(mape, 1)} % ` : '') +
        `criterion ${formatNumber(independent.acceptanceCriterionPct ?? 0, 0)} %, ` +
        `${independent.passed ? 'passed' : 'FAILED'}`.replace('  ', ' ').trim(),
    )
  }
  const development = validation.development
  if (development && development.metrics) {
    parts.push(
      `development set (not validation): MAPE ${formatNumber(development.metrics.MAPE, 1)} %`,
    )
  }
  return parts.filter(Boolean).join(' · ')
}
