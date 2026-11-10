import { useCallback, useEffect, useRef, useState } from 'react'
import { fetchSimulationConfig } from '../services/simulationApi.js'
import { DEFAULT_CONFIG } from '../services/defaultConfig.js'

/**
 * Loads control ranges / defaults / presets from the backend.
 *
 * Phase 31 rewrote this hook. The previous version had three failure modes that together produced
 * the permanent dashboard note "Loading API configuration; bundled control ranges shown until
 * connected":
 *
 *   1. it swallowed every error (`catch {}`), so a failed request was indistinguishable from a
 *      slow one;
 *   2. it never retried, so one failed request at page load left the bundled ranges in place for
 *      the life of the tab - which is exactly what a cold-starting hosted API produces;
 *   3. it reported `source: 'fallback'` for both states, and the caller rendered that as a
 *      permanent "loading" message even after the request had already failed.
 *
 * The bundled `DEFAULT_CONFIG` remains only as a placeholder so the controls can render while the
 * first attempt is in flight. It is never presented as live configuration: `status` says whether
 * the values on screen came from the API (`live`) or not (`loading` / `error`), and the caller
 * disables the actions that would act on unverified ranges.
 *
 * Retries use a short bounded backoff and then stop, rather than polling forever, so a genuinely
 * offline backend produces one clear error instead of an endless spinner.
 */

const RETRY_DELAYS_MS = [1200, 3000, 6000]

// `/api/config` is static for the life of a deployment, so one successful fetch is enough for the
// whole page. Sharing the in-flight promise (instead of aborting it on unmount) also keeps React
// StrictMode's development double-mount from issuing two requests and aborting the first one -
// that abort was the visible `net::ERR_ABORTED` churn in the console and never populated state.
let cachedConfig = null
let inflightRequest = null

function loadConfigOnce() {
  if (cachedConfig) return Promise.resolve(cachedConfig)
  if (!inflightRequest) {
    inflightRequest = fetchSimulationConfig()
      .then((data) => {
        cachedConfig = data
        inflightRequest = null
        return data
      })
      .catch((err) => {
        inflightRequest = null
        throw err
      })
  }
  return inflightRequest
}

export function resetSimulationConfigCache() {
  cachedConfig = null
  inflightRequest = null
}

export function useSimulationConfig() {
  const [config, setConfig] = useState(DEFAULT_CONFIG)
  const [status, setStatus] = useState('loading') // 'loading' | 'live' | 'error'
  const [error, setError] = useState(null)
  const [attempt, setAttempt] = useState(0)
  const timer = useRef(null)

  const retry = useCallback(() => {
    // A manual retry clears the recorded error and restarts the backoff; it is the only way to
    // recover once the automatic attempts are exhausted.
    setError(null)
    setStatus('loading')
    setAttempt((n) => n + 1)
  }, [])

  useEffect(() => {
    let cancelled = false

    const load = async () => {
      try {
        const data = await loadConfigOnce()
        if (cancelled) return
        if (!data || typeof data !== 'object' || !data.parameters) {
          throw new Error('The API returned a configuration without control ranges.')
        }
        setConfig(data)
        setError(null)
        setStatus('live')
      } catch (err) {
        if (cancelled) return
        if (attempt < RETRY_DELAYS_MS.length) {
          setStatus('loading')
          timer.current = setTimeout(() => {
            if (!cancelled) setAttempt((n) => n + 1)
          }, RETRY_DELAYS_MS[attempt])
          return
        }
        setError(err)
        setStatus('error')
      }
    }

    // The status is set by the state transitions themselves (initial state, manual retry, and
    // the retry branch of the catch) rather than here, so a live configuration is never knocked
    // back to "loading" by a re-render of this effect.
    load()

    return () => {
      cancelled = true
      clearTimeout(timer.current)
    }
  }, [attempt])

  return {
    config,
    status,
    error,
    retry,
    isLive: status === 'live',
  }
}
