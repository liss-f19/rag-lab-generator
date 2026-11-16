/**
 * Role:   Enforces the project code regulations on every TypeScript file of the web client.
 * Input:  The .ts/.tsx files under web/, read from disk at test time.
 * Output: Failures naming the exact file that breaks a rule.
 * Flow:   Walks the source tree once, then asserts per file that it opens with the mandatory
 *         Role/Input/Output/Flow block comment and that it declares no `any` type, so a
 *         regression is caught before it reaches review.
 */
import { readFileSync, readdirSync, statSync } from 'node:fs'
import { join, relative, resolve } from 'node:path'

import { describe, expect, it } from 'vitest'

const WEB_ROOT = resolve(__dirname, '../..')
const IGNORED = new Set(['node_modules', 'dist', '.vite', 'coverage', 'test-results'])
const HEADER_FIELDS = ['Role:', 'Input:', 'Output:', 'Flow:'] as const
// `: any`, `as any`, `<any>`, `any[]` — the shapes that actually disable type checking.
const ANY_PATTERN = /(:\s*any\b|\bas\s+any\b|<any>|\bany\[\])/

function walk(directory: string): string[] {
  const found: string[] = []
  for (const entry of readdirSync(directory)) {
    if (IGNORED.has(entry)) continue
    const full = join(directory, entry)
    if (statSync(full).isDirectory()) found.push(...walk(full))
    else if (/\.tsx?$/.test(entry)) found.push(full)
  }
  return found
}

const PRODUCTION_FILES = walk(WEB_ROOT)
  .filter((path) => !relative(WEB_ROOT, path).startsWith('tests'))
  .sort()

describe('web source conventions', () => {
  it('finds the source files at all', () => {
    expect(PRODUCTION_FILES.length).toBeGreaterThan(10)
  })

  it.each(PRODUCTION_FILES.map((path) => [relative(WEB_ROOT, path), path]))(
    '%s starts with the Role/Input/Output/Flow header',
    (_name, path) => {
      const text = readFileSync(path, 'utf8')
      expect(text.trimStart().startsWith('/**')).toBe(true)
      const header = text.slice(0, text.indexOf('*/') + 2)
      for (const field of HEADER_FIELDS) {
        expect(header).toContain(field)
      }
    },
  )

  it.each(PRODUCTION_FILES.map((path) => [relative(WEB_ROOT, path), path]))(
    '%s declares no any type',
    (_name, path) => {
      const offenders = readFileSync(path, 'utf8')
        .split('\n')
        .map((line, index) => [index + 1, line] as const)
        .filter(([, line]) => ANY_PATTERN.test(line))
        .map(([number, line]) => `${number}: ${line.trim()}`)
      expect(offenders).toEqual([])
    },
  )
})
