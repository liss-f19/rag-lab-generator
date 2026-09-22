/**
 * Role:   Markdown renderer used for agent answers, lab tutorials and summaries.
 * Input:  A markdown string.
 * Output: Styled React elements with highlighted code and rendered mermaid diagrams.
 * Flow:   react-markdown with remark-gfm and rehype-highlight; the `pre` renderer is a
 *         pass-through so the `code` renderer decides between an inline span, a mermaid figure
 *         and a highlighted block, and links always open in a new tab.
 */
import type { ReactNode } from 'react'
import ReactMarkdown from 'react-markdown'
import rehypeHighlight from 'rehype-highlight'
import remarkGfm from 'remark-gfm'

import { Mermaid } from './Mermaid'

function textOf(node: ReactNode): string {
  if (node === null || node === undefined || typeof node === 'boolean') return ''
  if (typeof node === 'string' || typeof node === 'number') return String(node)
  if (Array.isArray(node)) return node.map(textOf).join('')
  if (typeof node === 'object' && 'props' in node) {
    const props = (node as { props?: { children?: ReactNode } }).props
    return textOf(props?.children)
  }
  return ''
}

export function Markdown({ content }: { content: string }) {
  return (
    <div className="prose-tight text-sm leading-relaxed break-words">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[[rehypeHighlight, { ignoreMissing: true, detect: true }]]}
        components={{
          pre: ({ children }) => <>{children}</>,
          code: ({ className, children }) => {
            const language = /language-(\w+)/.exec(className ?? '')?.[1]
            const raw = textOf(children)
            if (language === 'mermaid') return <Mermaid chart={raw.trimEnd()} />
            if (!language && !raw.includes('\n')) {
              return (
                <code className="rounded bg-slate-200/70 px-1 py-0.5 font-mono text-[12px] dark:bg-slate-800">
                  {children}
                </code>
              )
            }
            return (
              <pre className="my-3 overflow-x-auto rounded-lg border border-slate-200 bg-slate-50 p-3 text-xs dark:border-slate-800 dark:bg-slate-950">
                <code className={className}>{children}</code>
              </pre>
            )
          },
          a: ({ href, children }) => (
            <a
              href={href}
              target="_blank"
              rel="noreferrer"
              className="text-indigo-600 underline underline-offset-2 dark:text-indigo-400"
            >
              {children}
            </a>
          ),
          h1: ({ children }) => <h1 className="mt-4 mb-2 text-lg font-semibold">{children}</h1>,
          h2: ({ children }) => <h2 className="mt-4 mb-2 text-base font-semibold">{children}</h2>,
          h3: ({ children }) => <h3 className="mt-3 mb-1 text-sm font-semibold">{children}</h3>,
          ul: ({ children }) => <ul className="list-disc pl-5">{children}</ul>,
          ol: ({ children }) => <ol className="list-decimal pl-5">{children}</ol>,
          table: ({ children }) => (
            <div className="my-3 overflow-x-auto">
              <table className="w-full border-collapse text-xs">{children}</table>
            </div>
          ),
          th: ({ children }) => (
            <th className="border border-slate-300 px-2 py-1 text-left font-semibold dark:border-slate-700">
              {children}
            </th>
          ),
          td: ({ children }) => (
            <td className="border border-slate-200 px-2 py-1 align-top dark:border-slate-800">
              {children}
            </td>
          ),
          blockquote: ({ children }) => (
            <blockquote className="border-l-2 border-indigo-400 pl-3 text-slate-600 dark:text-slate-300">
              {children}
            </blockquote>
          ),
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  )
}
