/**
 * TekWatch brand mark: a radar/scan glyph (concentric rings + a sweep arc
 * + a center contact dot) rather than a stock icon. Reads as "watching,
 * detecting, live" — the same signal/pulse language already used
 * throughout the product (LIVE indicators, heartbeat animations).
 *
 * Colour comes from `currentColor`, so it inherits whatever text-* class
 * the parent sets (white on a solid brand-colour square, or a tinted
 * colour on a transparent circle) — same usage pattern the old Radio
 * icon had, drop-in replacement.
 */
export function LogoMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" fill="none" className={className} aria-hidden="true">
      <circle cx="16" cy="16" r="13" stroke="currentColor" strokeWidth="1.75" opacity="0.3" />
      <circle cx="16" cy="16" r="9" stroke="currentColor" strokeWidth="1.75" opacity="0.6" />
      <path d="M16 3 A13 13 0 0 1 29 16" stroke="currentColor" strokeWidth="2.25" strokeLinecap="round" />
      <circle cx="16" cy="16" r="4" fill="currentColor" />
    </svg>
  )
}
