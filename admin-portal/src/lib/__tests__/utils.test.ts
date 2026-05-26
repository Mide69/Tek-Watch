import { formatRelativeTime, formatDate } from '../utils'

describe('formatRelativeTime', () => {
  it('returns "Never" for null', () => {
    expect(formatRelativeTime(null)).toBe('Never')
  })

  it('returns "Never" for undefined', () => {
    expect(formatRelativeTime(undefined)).toBe('Never')
  })

  it('returns "just now" for a date less than one minute ago', () => {
    const recent = new Date(Date.now() - 10_000).toISOString()
    expect(formatRelativeTime(recent)).toBe('just now')
  })

  it('returns minutes-ago label for a date ~5 minutes ago', () => {
    const fiveMin = new Date(Date.now() - 5 * 60_000).toISOString()
    expect(formatRelativeTime(fiveMin)).toBe('5m ago')
  })

  it('returns hours-ago label for a date ~2 hours ago', () => {
    const twoHours = new Date(Date.now() - 2 * 60 * 60_000).toISOString()
    expect(formatRelativeTime(twoHours)).toBe('2h ago')
  })

  it('returns days-ago label for a date ~3 days ago', () => {
    const threeDays = new Date(Date.now() - 3 * 24 * 60 * 60_000).toISOString()
    expect(formatRelativeTime(threeDays)).toBe('3d ago')
  })

  it('accepts a Date object', () => {
    const recent = new Date(Date.now() - 10_000)
    expect(formatRelativeTime(recent)).toBe('just now')
  })
})

describe('formatDate', () => {
  it('returns "—" for null', () => {
    expect(formatDate(null)).toBe('—')
  })

  it('returns "—" for undefined', () => {
    expect(formatDate(undefined)).toBe('—')
  })

  it('returns a non-empty string for a valid ISO date', () => {
    const result = formatDate('2024-06-15T10:00:00Z')
    expect(result).toBeTruthy()
    expect(result).not.toBe('—')
  })
})
