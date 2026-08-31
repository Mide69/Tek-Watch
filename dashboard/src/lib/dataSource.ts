'use client'

/**
 * Tracks whether what is on screen is the customer's real AWS data or sample data.
 *
 * Why this exists: useData's apiFetch falls back to mock data whenever a request
 * fails, and it used to do so silently. Combined with a second bug — it sent no
 * Authorization header, so every request 401'd — a signed-in customer was shown
 * a fully populated dashboard of invented resources, alarms and costs, with
 * nothing to say the figures were not theirs. Someone could have acted on them.
 *
 * The fallback itself is worth keeping: it guarantees every page has a
 * well-formed shape to render and so never blanks out on a transient failure.
 * What it must not do is stay quiet. Every fetch now reports which kind of data
 * it returned, and the banner in the dashboard layout says so plainly.
 */

import { useSyncExternalStore } from 'react'

const samplePaths = new Set<string>()
const listeners = new Set<() => void>()

// Cached so getSnapshot returns a referentially stable value; recomputing a
// boolean is cheap, but useSyncExternalStore re-reads it constantly.
let showingSample = false

function emit(): void {
  const next = samplePaths.size > 0
  if (next === showingSample) return
  showingSample = next
  listeners.forEach(listener => listener())
}

export function markDataSource(path: string, isSample: boolean): void {
  if (isSample) samplePaths.add(path)
  else samplePaths.delete(path)
  emit()
}

/** Forget every recorded path. Used by tests to isolate cases. */
export function resetDataSource(): void {
  samplePaths.clear()
  emit()
}

/** Non-React read of the same flag, for tests and for imperative callers. */
export function isShowingSampleData(): boolean {
  return showingSample
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener)
  return () => { listeners.delete(listener) }
}

/** True when any panel currently on screen is showing sample data. */
export function useShowingSampleData(): boolean {
  // Server snapshot is false: this is a static export, and the server has no
  // idea what the browser managed to fetch. Starting false keeps hydration
  // consistent; the first fetch flips it.
  return useSyncExternalStore(subscribe, () => showingSample, () => false)
}
