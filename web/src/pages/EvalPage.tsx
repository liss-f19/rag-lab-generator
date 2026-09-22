/**
 * Role:   Evaluation page: benchmark runs as a sortable table and a comparison bar chart.
 * Input:  /api/eval/runs (results/*.csv parsed generically plus the eval_runs table).
 * Output: One selectable source at a time, its rows sorted on demand and one metric charted.
 * Flow:   Normalises every source into {columns, rows} of strings, detects which columns are
 *         numeric, sorts numerically when possible, and feeds the selected metric to recharts
 *         with a label built from the configuration columns.
 */
import { useMemo, useState } from 'react'
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

import { useEvalRuns } from '../api/hooks'
import type { EvalRuns } from '../api/types'
import { Badge, EmptyState, ErrorBox, Field, Panel, Select, Spinner } from '../components/ui'

interface Source {
  name: string
  columns: string[]
  rows: Record<string, string>[]
}

const BAR_COLORS = ['#6366f1', '#14b8a6', '#f59e0b', '#ec4899', '#0ea5e9', '#22c55e']

function flattenDbRuns(data: EvalRuns): Source | null {
  if (data.db_runs.length === 0) return null
  const rows = data.db_runs.map((run) => {
    const row: Record<string, string> = { id: String(run.id), created_at: run.created_at }
    for (const [key, value] of Object.entries(run.config)) row[key] = String(value)
    for (const [key, value] of Object.entries(run.metrics)) row[key] = String(value)
    return row
  })
  const columns = [...new Set(rows.flatMap((row) => Object.keys(row)))]
  return { name: 'eval_runs (database)', columns, rows }
}

function isNumeric(rows: Record<string, string>[], column: string): boolean {
  const values = rows.map((row) => row[column]).filter((value) => value !== undefined && value !== '')
  return values.length > 0 && values.every((value) => Number.isFinite(Number(value)))
}

function labelOf(row: Record<string, string>, columns: string[]): string {
  const parts = columns.map((column) => row[column]).filter(Boolean)
  return parts.length > 0 ? parts.join(' / ') : '—'
}

export function EvalPage() {
  const { data, isLoading, isError, error } = useEvalRuns()
  const [sourceName, setSourceName] = useState('')
  const [sortColumn, setSortColumn] = useState('')
  const [descending, setDescending] = useState(true)
  const [metric, setMetric] = useState('')

  const sources = useMemo<Source[]>(() => {
    if (!data) return []
    const fromFiles = data.files.map((file) => ({
      name: file.name,
      columns: file.columns,
      rows: file.rows,
    }))
    const fromDb = flattenDbRuns(data)
    return fromDb ? [...fromFiles, fromDb] : fromFiles
  }, [data])

  const source = sources.find((entry) => entry.name === sourceName) ?? sources[0]

  const numericColumns = useMemo(
    () => (source ? source.columns.filter((column) => isNumeric(source.rows, column)) : []),
    [source],
  )
  const labelColumns = useMemo(
    () => (source ? source.columns.filter((column) => !numericColumns.includes(column)) : []),
    [source, numericColumns],
  )

  const activeMetric = metric && numericColumns.includes(metric) ? metric : (numericColumns[0] ?? '')

  const sortedRows = useMemo(() => {
    if (!source) return []
    const column = sortColumn || activeMetric || source.columns[0]
    if (!column) return source.rows
    const numeric = numericColumns.includes(column)
    return [...source.rows].sort((left, right) => {
      const a = left[column] ?? ''
      const b = right[column] ?? ''
      const order = numeric ? Number(a) - Number(b) : a.localeCompare(b)
      return descending ? -order : order
    })
  }, [source, sortColumn, activeMetric, descending, numericColumns])

  const chartData = useMemo(
    () =>
      activeMetric
        ? sortedRows.slice(0, 12).map((row) => ({
            label: labelOf(row, labelColumns.slice(0, 2)),
            value: Number(row[activeMetric] ?? 0),
          }))
        : [],
    [sortedRows, activeMetric, labelColumns],
  )

  if (isLoading) return <Spinner label="reading results/" />
  if (isError || !data) return <ErrorBox error={error} />

  if (sources.length === 0) {
    return (
      <EmptyState
        title="No evaluation runs yet"
        hint={
          <>
            <p>
              Nothing in <code>{data.results_dir}</code> and no rows in <code>eval_runs</code>.
            </p>
            <pre className="mt-2 inline-block rounded bg-slate-200 px-3 py-2 text-left text-[11px] dark:bg-slate-800">
              uv run rag-lab eval --matrix
            </pre>
          </>
        }
      />
    )
  }

  return (
    <div className="space-y-4">
      <Panel
        title="Benchmark runs"
        actions={
          <span className="flex gap-1.5">
            <Badge tone={data.db_reachable ? 'ok' : 'warn'}>
              db {data.db_reachable ? 'up' : 'down'}
            </Badge>
            <Badge>{source?.rows.length ?? 0} rows</Badge>
          </span>
        }
      >
        <div className="flex flex-wrap gap-3">
          <Field label="source">
            <Select
              value={source?.name ?? ''}
              onChange={setSourceName}
              options={sources.map((entry) => entry.name)}
            />
          </Field>
          <Field label="metric">
            <Select value={activeMetric} onChange={setMetric} options={numericColumns} />
          </Field>
        </div>

        {chartData.length > 0 && (
          <div className="mt-4 h-72">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData} margin={{ top: 8, right: 8, bottom: 40, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgb(148 163 184 / 0.3)" />
                <XAxis
                  dataKey="label"
                  angle={-25}
                  textAnchor="end"
                  interval={0}
                  height={60}
                  tick={{ fontSize: 11 }}
                />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip />
                <Bar dataKey="value" name={activeMetric} radius={[4, 4, 0, 0]}>
                  {chartData.map((entry, index) => (
                    <Cell key={entry.label} fill={BAR_COLORS[index % BAR_COLORS.length]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </Panel>

      {source && (
        <Panel title={source.name}>
          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-xs">
              <thead>
                <tr>
                  {source.columns.map((column) => (
                    <th
                      key={column}
                      onClick={() => {
                        if (sortColumn === column) setDescending((previous) => !previous)
                        else {
                          setSortColumn(column)
                          setDescending(true)
                        }
                      }}
                      className="cursor-pointer border-b border-slate-200 px-2 py-1.5 text-left font-semibold whitespace-nowrap select-none hover:text-indigo-600 dark:border-slate-800"
                    >
                      {column}
                      {(sortColumn || activeMetric) === column && (descending ? ' ▼' : ' ▲')}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {sortedRows.map((row, index) => (
                  <tr
                    key={index}
                    className="odd:bg-slate-50 dark:odd:bg-slate-950/60"
                  >
                    {source.columns.map((column) => (
                      <td
                        key={column}
                        className={`border-b border-slate-100 px-2 py-1 whitespace-nowrap dark:border-slate-800 ${
                          numericColumns.includes(column) ? 'text-right font-mono' : ''
                        }`}
                      >
                        {row[column] ?? ''}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>
      )}
    </div>
  )
}
