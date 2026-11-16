/**
 * Role:   Interactive force-directed rendering of a knowledge-graph neighbourhood.
 * Input:  A Subgraph (nodes + edges), the selected node id and a selection callback.
 * Output: An SVG canvas with pan and zoom, colored node kinds and a legend.
 * Flow:   Copies the nodes and edges into mutable datums, runs a d3-force simulation to
 *         convergence in one synchronous pass (so no animation frame loop is needed), then
 *         draws the edges and the nodes at the resulting coordinates; wheel zooms, drag pans.
 */
import {
  forceCenter,
  forceCollide,
  forceLink,
  forceManyBody,
  forceSimulation,
  type SimulationLinkDatum,
  type SimulationNodeDatum,
} from 'd3-force'
import { useMemo, useRef, useState } from 'react'

import type { Subgraph } from '../api/types'
import { KIND_COLORS } from './graphKinds'

const WIDTH = 900
const HEIGHT = 560
const TICKS = 260

interface Datum extends SimulationNodeDatum {
  id: string
  kind: string
  label: string
  degree: number
}

interface Edge extends SimulationLinkDatum<Datum> {
  kind: string
}

function layout(graph: Subgraph): { nodes: Datum[]; edges: Edge[] } {
  const nodes: Datum[] = graph.nodes.map((node) => ({
    id: node.id,
    kind: node.kind,
    label: node.label,
    degree: node.degree,
  }))
  const known = new Set(nodes.map((node) => node.id))
  const edges: Edge[] = graph.edges
    .filter((edge) => known.has(edge.src) && known.has(edge.dst))
    .map((edge) => ({ source: edge.src, target: edge.dst, kind: edge.kind }))

  const simulation = forceSimulation(nodes)
    .force(
      'link',
      forceLink<Datum, Edge>(edges)
        .id((node) => node.id)
        .distance(90)
        .strength(0.35),
    )
    .force('charge', forceManyBody<Datum>().strength(-260))
    .force('center', forceCenter(WIDTH / 2, HEIGHT / 2))
    .force('collide', forceCollide<Datum>(28))
    .stop()
  simulation.tick(TICKS)
  return { nodes, edges }
}

function radius(node: Datum): number {
  return Math.min(18, 7 + Math.sqrt(node.degree) * 2.2)
}

export function GraphView({
  graph,
  selected,
  onSelect,
}: {
  graph: Subgraph
  selected: string | null
  onSelect: (nodeId: string) => void
}) {
  const { nodes, edges } = useMemo(() => layout(graph), [graph])
  const [view, setView] = useState({ x: 0, y: 0, k: 1 })
  const dragging = useRef<{ x: number; y: number } | null>(null)
  const kinds = useMemo(() => [...new Set(nodes.map((node) => node.kind))].sort(), [nodes])

  return (
    <div className="relative">
      <svg
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        className="h-[560px] w-full touch-none rounded-lg border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-950"
        onWheel={(event) => {
          const factor = event.deltaY < 0 ? 1.12 : 1 / 1.12
          setView((previous) => ({
            ...previous,
            k: Math.max(0.3, Math.min(4, previous.k * factor)),
          }))
        }}
        onPointerDown={(event) => {
          dragging.current = { x: event.clientX - view.x, y: event.clientY - view.y }
        }}
        onPointerMove={(event) => {
          if (!dragging.current) return
          setView((previous) => ({
            ...previous,
            x: event.clientX - (dragging.current?.x ?? 0),
            y: event.clientY - (dragging.current?.y ?? 0),
          }))
        }}
        onPointerUp={() => {
          dragging.current = null
        }}
        onPointerLeave={() => {
          dragging.current = null
        }}
      >
        <g transform={`translate(${view.x},${view.y}) scale(${view.k})`}>
          {edges.map((edge, index) => {
            const source = edge.source as Datum
            const target = edge.target as Datum
            return (
              <line
                key={index}
                x1={source.x ?? 0}
                y1={source.y ?? 0}
                x2={target.x ?? 0}
                y2={target.y ?? 0}
                stroke="currentColor"
                className="text-slate-300 dark:text-slate-700"
                strokeWidth={1}
              />
            )
          })}
          {nodes.map((node) => (
            <g
              key={node.id}
              transform={`translate(${node.x ?? 0},${node.y ?? 0})`}
              className="cursor-pointer"
              onClick={() => onSelect(node.id)}
            >
              <circle
                r={radius(node)}
                fill={KIND_COLORS[node.kind] ?? '#94a3b8'}
                stroke={selected === node.id ? '#111827' : 'white'}
                strokeWidth={selected === node.id ? 3 : 1.5}
                opacity={0.9}
              />
              <text
                y={radius(node) + 11}
                textAnchor="middle"
                className="fill-slate-600 dark:fill-slate-300"
                style={{ fontSize: 10 }}
              >
                {node.label.length > 22 ? `${node.label.slice(0, 22)}…` : node.label}
              </text>
            </g>
          ))}
        </g>
      </svg>

      <div className="pointer-events-none absolute top-2 left-2 flex flex-wrap gap-2 rounded-lg bg-white/80 p-2 text-[11px] backdrop-blur dark:bg-slate-900/80">
        {kinds.map((kind) => (
          <span key={kind} className="flex items-center gap-1">
            <span
              className="inline-block size-2.5 rounded-full"
              style={{ background: KIND_COLORS[kind] ?? '#94a3b8' }}
            />
            {kind}
          </span>
        ))}
      </div>
      <p className="absolute right-2 bottom-2 text-[11px] text-slate-400">
        scroll to zoom · drag to pan · click a node to expand
      </p>
    </div>
  )
}
