/**
 * Role:   Vitest configuration of the independent QA suite (component and convention tests).
 * Input:  The specs under web/tests/unit; the React plugin needed to compile tsx.
 * Output: A jsdom test environment that never touches the production vite.config.ts.
 * Flow:   Registers the React plugin, restricts the run to tests/unit so the Playwright specs
 *         under tests/e2e stay out of vitest, and enables globals so the specs read like the
 *         rest of the project.
 */
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

export default defineConfig({
  plugins: [react()],
  // tsconfig.app.json only covers src/, so the specs need the automatic runtime spelled out
  esbuild: { jsx: 'automatic' },
  test: {
    globals: true,
    environment: 'jsdom',
    include: ['tests/unit/**/*.test.{ts,tsx}'],
    setupFiles: ['./tests/unit/setup.ts'],
  },
})
