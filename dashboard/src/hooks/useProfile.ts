'use client'

/**
 * The signed-in customer's company profile.
 *
 * Exists so the dashboard has a human name to show. Before this, every page
 * could only display the raw Customer ID — the signup form asked for a company
 * name and then threw it away.
 */

import useSWR from 'swr'
import apiClient from '@/lib/api'

const API = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000'

export interface CompanyProfile {
  customer_id: string
  company_name: string
  name: string
  email: string
  phone: string
  website: string
  address_line1: string
  address_line2: string
  city: string
  postcode: string
  country: string
  subscription_tier: string
  logo_url: string
  display_name: string
}

export const EMPTY_PROFILE: CompanyProfile = {
  customer_id: '', company_name: '', name: '', email: '', phone: '', website: '',
  address_line1: '', address_line2: '', city: '', postcode: '', country: '',
  subscription_tier: '', logo_url: '', display_name: '',
}

/** Editable subset — mirrors PROFILE_FIELDS on the API. */
export type ProfileEdits = Pick<
  CompanyProfile,
  'company_name' | 'name' | 'phone' | 'website'
  | 'address_line1' | 'address_line2' | 'city' | 'postcode' | 'country'
>

async function readError(res: Response, fallback: string): Promise<string> {
  // FastAPI puts the human-readable reason in `detail`. Surfacing it matters
  // here: "that logo is larger than 2 MB" is actionable, "request failed" is not.
  try {
    const body = await res.json()
    if (typeof body?.detail === 'string') return body.detail
  } catch {
    /* not json — fall through */
  }
  return fallback
}

export function useProfile() {
  return useSWR<CompanyProfile | null>(
    'company-profile',
    async () => {
      const token = apiClient.getToken()
      if (!token) return null
      const res = await fetch(`${API}/api/v1/profile`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (!res.ok) return null
      return res.json()
    },
    { revalidateOnFocus: false },
  )
}

export async function saveProfile(edits: Partial<ProfileEdits>): Promise<CompanyProfile> {
  const token = apiClient.getToken()
  if (!token) throw new Error('Your session has expired. Please sign in again.')

  const res = await fetch(`${API}/api/v1/profile`, {
    method: 'PUT',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(edits),
  })
  if (!res.ok) throw new Error(await readError(res, 'Could not save your profile.'))
  return res.json()
}

export async function uploadLogo(file: File): Promise<CompanyProfile> {
  const token = apiClient.getToken()
  if (!token) throw new Error('Your session has expired. Please sign in again.')

  const form = new FormData()
  form.append('file', file)

  // No Content-Type header on purpose — the browser has to set the multipart
  // boundary itself, and setting it by hand produces a body the API cannot parse.
  const res = await fetch(`${API}/api/v1/profile/logo`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
    body: form,
  })
  if (!res.ok) throw new Error(await readError(res, 'Could not upload that logo.'))
  return res.json()
}

export async function removeLogo(): Promise<CompanyProfile> {
  const token = apiClient.getToken()
  if (!token) throw new Error('Your session has expired. Please sign in again.')

  const res = await fetch(`${API}/api/v1/profile/logo`, {
    method: 'DELETE',
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) throw new Error(await readError(res, 'Could not remove the logo.'))
  return res.json()
}
