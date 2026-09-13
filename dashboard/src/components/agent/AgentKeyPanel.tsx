'use client'

import { useState } from 'react'
import axios from 'axios'
import { AlertTriangle, Check, Copy, KeyRound } from 'lucide-react'
import apiClient from '@/lib/api'

/**
 * Creates the agent key and shows it once.
 *
 * The key used to be written into the downloaded template as a parameter
 * default. CloudFormation keeps the template body and returns it to anyone in
 * the account who can view the stack, NoEcho or not. Now the template never
 * holds it: the customer copies it from here and pastes it into the hidden
 * APIKey field. Nothing here stores it, and hiding it clears it from memory.
 */
export function AgentKeyPanel() {
  const [key, setKey] = useState('')
  const [confirmReplace, setConfirmReplace] = useState(false)
  const [busy, setBusy] = useState(false)
  const [copied, setCopied] = useState(false)
  const [error, setError] = useState('')

  async function issue(replace: boolean) {
    setError('')
    setBusy(true)
    try {
      const result = await apiClient.issueAgentKey(replace)
      setKey(result.api_key)
      setConfirmReplace(false)
      setCopied(false)
    } catch (err) {
      if (axios.isAxiosError(err) && err.response?.status === 409) {
        setConfirmReplace(true)
      } else {
        setError('Could not create a key right now. Please try again shortly.')
      }
    } finally {
      setBusy(false)
    }
  }

  async function copy() {
    try {
      await navigator.clipboard.writeText(key)
      setCopied(true)
    } catch {
      setError('Copy was blocked by the browser. Select the key and copy it by hand.')
    }
  }

  if (key) {
    return (
      <div className="rounded-lg border border-border bg-card p-4">
        <p className="text-sm font-medium text-foreground mb-2">Your agent key</p>
        <div className="flex gap-2">
          <input
            readOnly
            value={key}
            aria-label="Agent key"
            onFocus={e => e.currentTarget.select()}
            className="min-w-0 flex-1 rounded-md border border-border bg-muted/30 px-3 py-2 font-mono text-xs text-foreground"
          />
          <button
            onClick={copy}
            className="flex items-center gap-1.5 rounded-md border border-border px-3 py-2 text-sm font-medium text-foreground hover:bg-muted/40"
          >
            {copied ? <Check className="w-4 h-4 text-emerald-500" /> : <Copy className="w-4 h-4" />}
            {copied ? 'Copied' : 'Copy'}
          </button>
        </div>
        <p className="text-xs text-muted-foreground mt-2 leading-relaxed">
          Paste it into the <span className="font-mono">APIKey</span> field when you create the stack.
          This is the only time it is shown: we keep a fingerprint of it, not the key.
        </p>
        {error && <p className="text-sm text-red-500 dark:text-red-400 mt-2">{error}</p>}
        <button
          onClick={() => { setKey(''); setCopied(false) }}
          className="mt-3 text-xs font-medium text-muted-foreground hover:text-foreground"
        >
          I have copied it, hide the key
        </button>
      </div>
    )
  }

  if (confirmReplace) {
    return (
      <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-4">
        <div className="flex gap-2.5">
          <AlertTriangle className="w-4 h-4 text-amber-500 flex-shrink-0 mt-0.5" />
          <div>
            <p className="text-sm font-medium text-foreground">You already have an agent key</p>
            <p className="text-sm text-muted-foreground mt-1 leading-relaxed">
              A new key replaces it straight away. Any agent using the old key stops reporting
              until you update its stack with the new one.
            </p>
            <div className="flex gap-2 mt-3">
              <button
                onClick={() => issue(true)}
                disabled={busy}
                className="rounded-md bg-amber-600 px-3 py-1.5 text-sm font-semibold text-white hover:bg-amber-500 disabled:opacity-50"
              >
                {busy ? 'Replacing…' : 'Replace key'}
              </button>
              <button
                onClick={() => setConfirmReplace(false)}
                className="rounded-md border border-border px-3 py-1.5 text-sm font-medium text-foreground hover:bg-muted/40"
              >
                Keep the current key
              </button>
            </div>
            {error && <p className="text-sm text-red-500 dark:text-red-400 mt-2">{error}</p>}
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="flex items-center justify-between flex-wrap gap-3">
      <p className="text-sm text-muted-foreground max-w-xl">
        The stack also needs your agent key. It is not in the template, so it stays out of your
        CloudFormation history. You will see it once.
      </p>
      <button
        onClick={() => issue(false)}
        disabled={busy}
        className="flex items-center gap-2 rounded-lg border border-border px-4 py-2.5 text-sm font-semibold text-foreground hover:bg-muted/40 disabled:opacity-50 flex-shrink-0"
      >
        <KeyRound className="w-4 h-4" />
        {busy ? 'Creating…' : 'Create agent key'}
      </button>
      {error && <p className="w-full text-sm text-red-500 dark:text-red-400">{error}</p>}
    </div>
  )
}
