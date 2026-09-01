'use client'

import { useEffect, useState } from 'react'
import { isFixtureView } from '@/lib/demoMode'

/**
 * Is this view showing the sample estate rather than a real account?
 *
 * Answered in an effect, deliberately, and this is the only correct way to ask
 * it from a component. Two reasons.
 *
 * The answer depends on browser state — a session token and a demo flag in
 * local storage — which does not exist while these pages are being prerendered
 * into a static export. Calling it during render produced markup that
 * disagreed with the server's and threw React hydration errors (#418, #423) on
 * every dashboard page, discarding the server-rendered tree and re-rendering
 * the lot on the client.
 *
 * And the answer changes within a page's life: signing in ends a demo. Reading
 * it once at module load froze whatever was true when the bundle first
 * imported, so a visitor who explored the demo and then signed in kept the
 * demo layout until a full reload.
 *
 * Returns null until the browser has been asked. There is no safe default to
 * guess: assuming a real account flashes a demo badge away from a demo
 * visitor, and assuming a demo flashes "Demo — sample data" at a paying
 * customer. Callers render neither branch while it is null, which costs one
 * frame and tells nobody anything untrue.
 */
export function useFixtureView(): boolean | null {
  const [fixture, setFixture] = useState<boolean | null>(null)
  useEffect(() => { setFixture(isFixtureView()) }, [])
  return fixture
}
