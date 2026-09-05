import {
  formatBytes,
  formatDuration,
  formatNumber,
  formatRelativeTime,
  getSeverityColor,
  getStatusColor,
  truncate,
  parseARN,
  getResourceName,
  DASH,
} from '../utils'

describe('formatRelativeTime', () => {
  // A customer with no agent yet has no heartbeat; a collector or alert that
  // never ran has no last_run. new Date(null) is not an error — it's a
  // valid date, January 1st 1970 UTC — so this used to render a 55-year-old
  // heartbeat next to a status of "Silent" instead of the honest "no
  // heartbeat yet".
  it('renders a dash for null rather than the 1970 epoch', () => {
    expect(formatRelativeTime(null)).toBe(DASH)
  })

  it('renders a dash for undefined', () => {
    expect(formatRelativeTime(undefined)).toBe(DASH)
  })

  it('renders a dash for an empty string rather than "Invalid Date"', () => {
    expect(formatRelativeTime('')).toBe(DASH)
  })

  it('still renders a real recent timestamp normally', () => {
    const oneMinuteAgo = new Date(Date.now() - 60_000).toISOString()
    expect(formatRelativeTime(oneMinuteAgo)).toBe('1 minute ago')
  })
})

describe('formatBytes', () => {
  it('returns "0 Bytes" for zero', () => {
    expect(formatBytes(0)).toBe('0 Bytes')
  })

  it('formats kilobytes', () => {
    expect(formatBytes(1024)).toBe('1 KB')
  })

  it('formats megabytes', () => {
    expect(formatBytes(1024 * 1024, 0)).toBe('1 MB')
  })

  it('formats gigabytes', () => {
    expect(formatBytes(1024 * 1024 * 1024, 0)).toBe('1 GB')
  })
})

describe('formatDuration', () => {
  it('shows seconds under a minute', () => {
    expect(formatDuration(45)).toBe('45s')
  })

  it('shows minutes and seconds', () => {
    expect(formatDuration(90)).toBe('1m 30s')
  })

  it('shows hours and minutes', () => {
    expect(formatDuration(3661)).toBe('1h 1m')
  })

  it('shows days and hours', () => {
    expect(formatDuration(90000)).toBe('1d 1h')
  })
})

describe('formatNumber', () => {
  it('returns a string', () => {
    expect(typeof formatNumber(42)).toBe('string')
  })

  it('formats zero', () => {
    expect(formatNumber(0)).toBe('0')
  })
})

describe('getSeverityColor', () => {
  it('returns red classes for critical', () => {
    expect(getSeverityColor('critical')).toContain('red')
  })

  it('returns orange for high', () => {
    expect(getSeverityColor('high')).toContain('orange')
  })

  it('returns yellow for medium', () => {
    expect(getSeverityColor('medium')).toContain('yellow')
  })

  it('is case-insensitive', () => {
    expect(getSeverityColor('CRITICAL')).toContain('red')
  })

  it('falls back to low color for unknown severity', () => {
    expect(getSeverityColor('unknown-sev')).toContain('blue')
  })
})

describe('getStatusColor', () => {
  it('returns green for healthy', () => {
    expect(getStatusColor('healthy')).toContain('green')
  })

  it('returns green for running', () => {
    expect(getStatusColor('running')).toContain('green')
  })

  it('returns red for offline', () => {
    expect(getStatusColor('offline')).toContain('red')
  })

  it('is case-insensitive', () => {
    expect(getStatusColor('HEALTHY')).toContain('green')
  })

  it('falls back to unknown color for unrecognised status', () => {
    expect(getStatusColor('bizarre-state')).toContain('gray')
  })
})

describe('truncate', () => {
  it('does not truncate strings within the limit', () => {
    expect(truncate('short', 10)).toBe('short')
  })

  it('returns string as-is when exactly at limit', () => {
    expect(truncate('hello', 5)).toBe('hello')
  })

  it('truncates and appends ellipsis', () => {
    expect(truncate('hello world', 5)).toBe('hello...')
  })
})

describe('parseARN', () => {
  it('parses a valid IAM role ARN', () => {
    const result = parseARN('arn:aws:iam::123456789012:role/my-role')
    expect(result).not.toBeNull()
    expect(result?.service).toBe('iam')
    expect(result?.accountId).toBe('123456789012')
    expect(result?.resource).toBe('my-role')
  })

  it('parses a valid ECS ARN', () => {
    const result = parseARN('arn:aws:ecs:eu-west-2:123456789012:cluster/prod')
    expect(result?.region).toBe('eu-west-2')
    expect(result?.service).toBe('ecs')
  })

  it('returns null for strings with fewer than 6 colon-separated parts', () => {
    expect(parseARN('not-an-arn')).toBeNull()
    expect(parseARN('arn:aws:s3')).toBeNull()
  })
})

describe('getResourceName', () => {
  it('extracts the resource segment from an ARN', () => {
    expect(getResourceName('arn:aws:iam::123:role/my-role')).toBe('my-role')
  })

  it('returns the identifier unchanged when it is not an ARN', () => {
    expect(getResourceName('i-1234567890abcdef0')).toBe('i-1234567890abcdef0')
  })
})
