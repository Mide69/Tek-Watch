import { cn } from '@/lib/utils'

interface BadgeProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: 'default' | 'success' | 'warning' | 'error' | 'info' | 'ai'
}

export function Badge({ className, variant = 'default', children, ...props }: BadgeProps) {
  const variants = {
    default: 'bg-white/[0.07] text-slate-300 border-white/[0.08]',
    success: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/25',
    warning: 'bg-amber-500/15 text-amber-400 border-amber-500/25',
    error:   'bg-red-500/15 text-red-400 border-red-500/25',
    info:    'bg-blue-500/15 text-blue-400 border-blue-500/25',
    ai:      'bg-indigo-500/15 text-indigo-400 border-indigo-500/25',
  }

  return (
    <div
      className={cn(
        'inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors',
        variants[variant],
        className
      )}
      {...props}
    >
      {children}
    </div>
  )
}
