'use client'

import { useEffect, useRef, useState } from 'react'
import DashboardLayout from '@/components/layout/DashboardLayout'
import { Card, CardContent } from '@/components/ui/Card'
import { CardSkeleton } from '@/components/ui/Skeleton'
import { Building2, Check, Trash2, Upload } from 'lucide-react'
import { useAuth } from '@/hooks/useAuth'
import {
  useProfile, saveProfile, uploadLogo, removeLogo,
  type ProfileEdits,
} from '@/hooks/useProfile'

const EMPTY_EDITS: ProfileEdits = {
  company_name: '', name: '', phone: '', website: '',
  address_line1: '', address_line2: '', city: '', postcode: '', country: '',
}

const FIELDS: { key: keyof ProfileEdits; label: string; placeholder: string; type?: string }[] = [
  { key: 'company_name',  label: 'Company name',  placeholder: 'Acme Ltd' },
  { key: 'name',          label: 'Contact name',  placeholder: 'Ada Lovelace' },
  { key: 'phone',         label: 'Phone number',  placeholder: '+44 20 7946 0958', type: 'tel' },
  { key: 'website',       label: 'Website',       placeholder: 'acme.com' },
  { key: 'address_line1', label: 'Address line 1', placeholder: '12 Example Street' },
  { key: 'address_line2', label: 'Address line 2', placeholder: 'Optional' },
  { key: 'city',          label: 'City',          placeholder: 'London' },
  { key: 'postcode',      label: 'Postcode',      placeholder: 'SW1A 1AA' },
  { key: 'country',       label: 'Country',       placeholder: 'United Kingdom' },
]

const inputCls =
  'w-full px-3.5 py-2.5 rounded-lg border border-border bg-background text-foreground ' +
  'placeholder:text-muted-foreground/60 text-sm focus:outline-none focus:ring-2 ' +
  'focus:ring-primary focus:border-transparent transition'

export default function SettingsPage() {
  const { customerId } = useAuth()
  const { data: profile, isLoading, mutate } = useProfile()

  const [edits, setEdits] = useState<ProfileEdits>(EMPTY_EDITS)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState('')
  const [logoBusy, setLogoBusy] = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)

  // Seed the form once the profile arrives. Keyed on customer_id rather than
  // the whole object so a background revalidation cannot wipe out what the
  // customer is part-way through typing.
  useEffect(() => {
    if (!profile) return
    setEdits({
      company_name: profile.company_name,
      name: profile.name,
      phone: profile.phone,
      website: profile.website,
      address_line1: profile.address_line1,
      address_line2: profile.address_line2,
      city: profile.city,
      postcode: profile.postcode,
      country: profile.country,
    })
  }, [profile?.customer_id]) // eslint-disable-line react-hooks/exhaustive-deps

  const set = (key: keyof ProfileEdits) => (e: React.ChangeEvent<HTMLInputElement>) => {
    setEdits(prev => ({ ...prev, [key]: e.target.value }))
    setSaved(false)
  }

  async function handleSave(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    setSaving(true)
    try {
      const updated = await saveProfile(edits)
      await mutate(updated, { revalidate: false })
      setSaved(true)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not save your profile.')
    } finally {
      setSaving(false)
    }
  }

  async function handleLogo(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    // Clear immediately so picking the same file twice still fires onChange.
    e.target.value = ''
    if (!file) return

    setError('')
    setLogoBusy(true)
    try {
      const updated = await uploadLogo(file)
      await mutate(updated, { revalidate: false })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not upload that logo.')
    } finally {
      setLogoBusy(false)
    }
  }

  async function handleRemoveLogo() {
    setError('')
    setLogoBusy(true)
    try {
      const updated = await removeLogo()
      await mutate(updated, { revalidate: false })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not remove the logo.')
    } finally {
      setLogoBusy(false)
    }
  }

  if (isLoading) {
    return (
      <DashboardLayout customerId={customerId || undefined}>
        <div className="space-y-6">
          <div className="h-8 w-40 bg-muted rounded animate-pulse" />
          <CardSkeleton />
        </div>
      </DashboardLayout>
    )
  }

  return (
    <DashboardLayout customerId={customerId || undefined}>
      <div className="space-y-6 max-w-3xl">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Company profile</h1>
          <p className="text-sm text-muted-foreground mt-1">
            These details appear across your dashboard and on anything Tek Watch
            sends you. Your Customer ID stays{' '}
            <span className="font-mono">{profile?.customer_id || customerId}</span>.
          </p>
        </div>

        {/* Logo */}
        <Card>
          <CardContent className="p-5">
            <h2 className="font-semibold text-foreground mb-1">Company logo</h2>
            <p className="text-sm text-muted-foreground mb-4">
              PNG, JPEG or GIF, up to 2 MB. Shown in the sidebar in place of the
              Tek Watch mark.
            </p>

            <div className="flex items-center gap-5 flex-wrap">
              <div className="w-20 h-20 rounded-xl border border-border bg-muted/40 flex items-center justify-center overflow-hidden flex-shrink-0">
                {profile?.logo_url ? (
                  // Presigned S3 url, so it is remote and time-limited. Plain
                  // <img> rather than next/image: this is a static export with
                  // no optimiser running, and the host changes per signature.
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    src={profile.logo_url}
                    alt={`${profile.display_name} logo`}
                    className="w-full h-full object-contain"
                  />
                ) : (
                  <Building2 className="w-8 h-8 text-muted-foreground/50" />
                )}
              </div>

              <div className="flex items-center gap-2.5">
                <input
                  ref={fileRef}
                  type="file"
                  accept="image/png,image/jpeg,image/gif"
                  onChange={handleLogo}
                  className="hidden"
                />
                <button
                  type="button"
                  onClick={() => fileRef.current?.click()}
                  disabled={logoBusy}
                  className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground text-sm font-semibold rounded-lg disabled:opacity-50 transition-opacity hover:opacity-90"
                >
                  <Upload className="w-4 h-4" />
                  {logoBusy ? 'Working…' : profile?.logo_url ? 'Replace logo' : 'Upload logo'}
                </button>
                {profile?.logo_url && (
                  <button
                    type="button"
                    onClick={handleRemoveLogo}
                    disabled={logoBusy}
                    className="flex items-center gap-2 px-3 py-2 text-sm text-muted-foreground hover:text-foreground border border-border rounded-lg disabled:opacity-50 transition-colors"
                  >
                    <Trash2 className="w-4 h-4" />
                    Remove
                  </button>
                )}
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Details */}
        <Card>
          <CardContent className="p-5">
            <h2 className="font-semibold text-foreground mb-4">Company details</h2>

            <form onSubmit={handleSave} className="space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {FIELDS.map(field => (
                  <div
                    key={field.key}
                    className={field.key.startsWith('address') ? 'sm:col-span-2' : ''}
                  >
                    <label
                      htmlFor={field.key}
                      className="block text-sm font-medium text-foreground mb-1.5"
                    >
                      {field.label}
                    </label>
                    <input
                      id={field.key}
                      type={field.type || 'text'}
                      value={edits[field.key]}
                      onChange={set(field.key)}
                      placeholder={field.placeholder}
                      className={inputCls}
                    />
                  </div>
                ))}
              </div>

              {profile?.email && (
                <p className="text-xs text-muted-foreground">
                  Sign-in email is <span className="font-medium">{profile.email}</span>.
                  Contact support to change it.
                </p>
              )}

              {error && (
                <div
                  role="alert"
                  className="p-3 text-sm text-red-600 dark:text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg"
                >
                  {error}
                </div>
              )}

              <div className="flex items-center gap-3">
                <button
                  type="submit"
                  disabled={saving}
                  className="px-5 py-2.5 bg-primary text-primary-foreground text-sm font-semibold rounded-lg disabled:opacity-50 transition-opacity hover:opacity-90"
                >
                  {saving ? 'Saving…' : 'Save changes'}
                </button>
                {saved && (
                  <span
                    role="status"
                    className="flex items-center gap-1.5 text-sm text-emerald-600 dark:text-emerald-400"
                  >
                    <Check className="w-4 h-4" />
                    Saved
                  </span>
                )}
              </div>
            </form>
          </CardContent>
        </Card>
      </div>
    </DashboardLayout>
  )
}
