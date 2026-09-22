/**
 * Role:   Application shell: left navigation, top bar and the routed page area.
 * Input:  The routed children through <Outlet/>; the health query for the top bar.
 * Output: The full-height two-column layout used by every page.
 * Flow:   Declares the navigation entries once, renders them as a sidebar on wide screens and
 *         as a scrolling strip on narrow ones, and keeps the page area independently scrollable.
 */
import { NavLink, Outlet } from 'react-router'

import { HealthBadge } from './HealthBadge'

const NAV = [
  { to: '/chat', label: 'Chat', hint: 'ask the agent' },
  { to: '/corpus', label: 'Corpus', hint: 'labs and files' },
  { to: '/retrieval', label: 'Retrieval Lab', hint: 'compare strategies' },
  { to: '/graph', label: 'Graph', hint: 'knowledge graph' },
  { to: '/eval', label: 'Eval', hint: 'benchmark runs' },
  { to: '/status', label: 'Status', hint: 'configuration' },
]

function navClass({ isActive }: { isActive: boolean }): string {
  return [
    'block rounded-lg px-3 py-2 text-sm transition',
    isActive
      ? 'bg-indigo-600 text-white'
      : 'text-slate-600 hover:bg-slate-200 dark:text-slate-300 dark:hover:bg-slate-800',
  ].join(' ')
}

export function Layout() {
  return (
    <div className="flex h-full flex-col md:flex-row">
      <nav className="shrink-0 border-b border-slate-200 bg-white px-3 py-3 md:w-56 md:border-r md:border-b-0 dark:border-slate-800 dark:bg-slate-900">
        <div className="mb-4 hidden px-2 md:block">
          <p className="text-sm font-semibold tracking-tight">SOP Lab Assistant</p>
          <p className="text-[11px] text-slate-500">RAG + LangGraph, MiNI PW</p>
        </div>
        <ul className="flex gap-1 overflow-x-auto md:flex-col md:overflow-visible">
          {NAV.map((entry) => (
            <li key={entry.to} className="shrink-0 md:shrink">
              <NavLink to={entry.to} className={navClass} title={entry.hint}>
                {entry.label}
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex shrink-0 items-center justify-between gap-4 border-b border-slate-200 bg-white px-4 py-2.5 dark:border-slate-800 dark:bg-slate-900">
          <p className="text-sm font-medium text-slate-500">Operating Systems lab assistant</p>
          <HealthBadge />
        </header>
        <main className="min-h-0 flex-1 overflow-y-auto bg-slate-100 p-4 dark:bg-slate-950">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
