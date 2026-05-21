import '@testing-library/jest-dom/vitest'

// jsdom does not implement ResizeObserver; Radix UI (Switch, etc.) requires it.
global.ResizeObserver = class ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
}
