'use client'

/**
 * RegionContext — provides the selected AWS region filter across all dashboard pages.
 */
import { createContext, useContext, useState, ReactNode } from 'react'

interface RegionContextValue {
  selectedRegion: string | undefined
  setSelectedRegion: (region: string | undefined) => void
}

const RegionContext = createContext<RegionContextValue>({
  selectedRegion: undefined,
  setSelectedRegion: () => {},
})

export function RegionProvider({ children }: { children: ReactNode }) {
  const [selectedRegion, setSelectedRegion] = useState<string | undefined>(undefined)
  return (
    <RegionContext.Provider value={{ selectedRegion, setSelectedRegion }}>
      {children}
    </RegionContext.Provider>
  )
}

export function useRegion(): RegionContextValue {
  return useContext(RegionContext)
}
