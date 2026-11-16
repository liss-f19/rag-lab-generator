/**
 * Role:   Global setup of the vitest QA suite.
 * Input:  none
 * Output: jest-dom matchers on expect and the browser APIs jsdom does not implement.
 * Flow:   Imports the jest-dom matchers, then stubs matchMedia and ResizeObserver so the
 *         components that read the color scheme or measure themselves render under jsdom.
 */
import '@testing-library/jest-dom/vitest'

if (!window.matchMedia) {
  window.matchMedia = ((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  })) as unknown as typeof window.matchMedia
}

// jsdom implements no SVG layout; mermaid measures every label, so give it plausible boxes.
interface SvgLayoutStubs {
  getBBox?: () => { x: number; y: number; width: number; height: number }
  getScreenCTM?: () => DOMMatrix | null
  getComputedTextLength?: () => number
}

const svgPrototype = globalThis.SVGElement?.prototype as (SVGElement & SvgLayoutStubs) | undefined
if (svgPrototype && !svgPrototype.getBBox) {
  svgPrototype.getBBox = () => ({ x: 0, y: 0, width: 120, height: 20 })
  svgPrototype.getScreenCTM = () => null
  svgPrototype.getComputedTextLength = () => 120
}

if (!globalThis.ResizeObserver) {
  globalThis.ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  } as unknown as typeof ResizeObserver
}
