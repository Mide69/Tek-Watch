'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { Info } from 'lucide-react'
import { useShowingSampleData } from '@/lib/dataSource'
import { isFixtureView } from '@/lib/demoMode'

/**
 * Says, unmistakably, when nothing on screen came from the customer's account.
 *
 * A dashboard that invents plausible numbers is worse than one that shows
 * nothing: nothing is obviously broken, whereas $4,247.80 of estimated spend
 * looks like a fact. This is the one thing standing between a sample figure
 * and a decision made on it, so it sits above the page content rather than
 * tucked into a corner.
 *
 * Hidden for demo visitors — DemoBadge already tells them, and two banners
 * saying the same thing reads as noise.
 */
export function SampleDataBanner() {
  const showingSample = useShowingSampleData()
  const [isDemo, setIsDemo] = useState(true) // assume demo until the browser says otherwise

  useEffect(() => {
    setIsDemo(isFixtureView())
  }, [])

  if (isDemo || !showingSample) return null

  return (
    <div className="mb-4 flex flex-col gap-3 rounded-lg border border-amber-500/30 bg-amber-500/10 px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
      <div className="flex items-start gap-2.5">
        <Info className="mt-0.5 h-4 w-4 flex-shrink-0 text-amber-500" />
        <div className="text-sm">
          <p className="font-semibold text-amber-600 dark:text-amber-300">
            No data yet from your AWS account
          </p>
          <p className="mt-0.5 text-amber-700/80 dark:text-amber-200/70">
            Nothing is reporting in, so every figure below reads zero. Connect the
            Tek Watch agent and this dashboard fills in on its own.
          </p>
        </div>
      </div>
      <Link
        href="/agent"
        className="flex-shrink-0 self-start rounded-md bg-amber-500 px-3 py-1.5 text-xs font-semibold text-amber-950 transition-opacity hover:opacity-90 sm:self-auto"
      >
        Connect AWS account
      </Link>
    </div>
  )
}
