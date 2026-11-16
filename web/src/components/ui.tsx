/**
 * Role:   Small presentational primitives shared by every page.
 * Input:  Props describing a panel, a badge, a select, a score or an error.
 * Output: Styled React elements; no data fetching and no application state.
 * Flow:   Each component is a thin wrapper over Tailwind classes so the pages stay readable and
 *         the light/dark palette is defined in exactly one place.
 */
import type { ReactNode } from 'react'

export function Panel({
  title,
  actions,
  children,
  className = '',
}: {
  title?: ReactNode
  actions?: ReactNode
  children: ReactNode
  className?: string
}) {
  return (
    <section
      className={`rounded-xl border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-900 ${className}`}
    >
      {(title || actions) && (
        <header className="flex items-center justify-between gap-3 border-b border-slate-200 px-4 py-2.5 dark:border-slate-800">
          <h2 className="text-sm font-semibold tracking-tight">{title}</h2>
          {actions}
        </header>
      )}
      <div className="p-4">{children}</div>
    </section>
  )
}

const TONES: Record<string, string> = {
  neutral: 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300',
  ok: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/50 dark:text-emerald-300',
  warn: 'bg-amber-100 text-amber-800 dark:bg-amber-900/50 dark:text-amber-300',
  bad: 'bg-rose-100 text-rose-800 dark:bg-rose-900/50 dark:text-rose-300',
  info: 'bg-indigo-100 text-indigo-800 dark:bg-indigo-900/50 dark:text-indigo-300',
}

export function Badge({
  children,
  tone = 'neutral',
  title,
}: {
  children: ReactNode
  tone?: keyof typeof TONES | string
  title?: string
}) {
  return (
    <span
      title={title}
      className={`inline-flex items-center rounded-md px-1.5 py-0.5 font-mono text-[11px] leading-4 ${TONES[tone] ?? TONES.neutral}`}
    >
      {children}
    </span>
  )
}

export function Spinner({ label = 'loading' }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 text-sm text-slate-500">
      <span className="size-3 animate-spin rounded-full border-2 border-slate-400 border-t-transparent" />
      {label}
    </div>
  )
}

export function ErrorBox({ title = 'Request failed', error }: { title?: string; error: unknown }) {
  const message = error instanceof Error ? error.message : String(error)
  return (
    <div className="rounded-lg border border-rose-300 bg-rose-50 p-3 text-sm text-rose-900 dark:border-rose-900 dark:bg-rose-950/50 dark:text-rose-200">
      <p className="font-semibold">{title}</p>
      <p className="mt-1 font-mono text-xs break-words">{message}</p>
    </div>
  )
}

export function EmptyState({ title, hint }: { title: string; hint?: ReactNode }) {
  return (
    <div className="rounded-lg border border-dashed border-slate-300 p-6 text-center dark:border-slate-700">
      <p className="text-sm font-medium text-slate-600 dark:text-slate-300">{title}</p>
      {hint && <div className="mt-2 text-xs text-slate-500 dark:text-slate-400">{hint}</div>}
    </div>
  )
}

export function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="flex flex-col gap-1 text-xs">
      <span className="font-medium text-slate-500 dark:text-slate-400">{label}</span>
      {children}
    </label>
  )
}

const CONTROL =
  'rounded-md border border-slate-300 bg-white px-2 py-1.5 text-sm outline-none focus:border-indigo-500 dark:border-slate-700 dark:bg-slate-900'

export function Select({
  value,
  onChange,
  options,
  allowEmpty,
  emptyLabel = 'any',
}: {
  value: string
  onChange: (value: string) => void
  options: string[]
  allowEmpty?: boolean
  emptyLabel?: string
}) {
  return (
    <select
      className={CONTROL}
      value={value}
      onChange={(event) => onChange(event.target.value)}
    >
      {allowEmpty && <option value="">{emptyLabel}</option>}
      {options.map((option) => (
        <option key={option} value={option}>
          {option}
        </option>
      ))}
    </select>
  )
}

export function TextInput({
  value,
  onChange,
  placeholder,
  type = 'text',
  className = '',
}: {
  value: string
  onChange: (value: string) => void
  placeholder?: string
  type?: string
  className?: string
}) {
  return (
    <input
      type={type}
      className={`${CONTROL} ${className}`}
      value={value}
      placeholder={placeholder}
      onChange={(event) => onChange(event.target.value)}
    />
  )
}

export function Button({
  children,
  onClick,
  variant = 'primary',
  disabled,
  type = 'button',
  title,
}: {
  children: ReactNode
  onClick?: () => void
  variant?: 'primary' | 'ghost' | 'danger'
  disabled?: boolean
  type?: 'button' | 'submit'
  title?: string
}) {
  const styles = {
    primary: 'bg-indigo-600 text-white hover:bg-indigo-500 disabled:bg-slate-400',
    ghost:
      'border border-slate-300 text-slate-700 hover:bg-slate-100 dark:border-slate-700 dark:text-slate-200 dark:hover:bg-slate-800',
    danger: 'text-rose-600 hover:bg-rose-50 dark:text-rose-400 dark:hover:bg-rose-950/50',
  }[variant]
  return (
    <button
      type={type}
      title={title}
      disabled={disabled}
      onClick={onClick}
      className={`rounded-md px-3 py-1.5 text-sm font-medium transition disabled:cursor-not-allowed disabled:opacity-60 ${styles}`}
    >
      {children}
    </button>
  )
}

export function ScoreBar({ score, max }: { score: number; max: number }) {
  const ratio = max > 0 ? Math.max(0, Math.min(1, score / max)) : 0
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-24 overflow-hidden rounded-full bg-slate-200 dark:bg-slate-800">
        <div className="h-full rounded-full bg-indigo-500" style={{ width: `${ratio * 100}%` }} />
      </div>
      <span className="font-mono text-[11px] text-slate-500">{score.toFixed(4)}</span>
    </div>
  )
}
