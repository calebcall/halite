import '@testing-library/jest-dom/vitest'

// jsdom does not implement ResizeObserver; Radix UI (Switch, etc.) requires it.
global.ResizeObserver = class ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
}

// jsdom does not implement pointer capture APIs; Radix UI Select requires them.
if (typeof window !== 'undefined' && typeof window.Element !== 'undefined') {
  if (!window.Element.prototype.hasPointerCapture) {
    window.Element.prototype.hasPointerCapture = () => false
  }
  if (!window.Element.prototype.setPointerCapture) {
    window.Element.prototype.setPointerCapture = () => {}
  }
  if (!window.Element.prototype.releasePointerCapture) {
    window.Element.prototype.releasePointerCapture = () => {}
  }
  // jsdom does not implement scrollIntoView; Radix UI Select requires it.
  if (!window.Element.prototype.scrollIntoView) {
    window.Element.prototype.scrollIntoView = () => {}
  }
}

// Node 22+ exposes a file-backed localStorage global that requires --localstorage-file.
// Replace it with a simple in-memory implementation so tests can use it freely.
if (typeof globalThis.localStorage === 'undefined' || typeof globalThis.localStorage.clear !== 'function') {
  const store: Record<string, string> = {}
  const memoryStorage: Storage = {
    get length() { return Object.keys(store).length },
    key(n: number) { return Object.keys(store)[n] ?? null },
    getItem(k: string) { return Object.prototype.hasOwnProperty.call(store, k) ? store[k] : null },
    setItem(k: string, v: string) { store[k] = String(v) },
    removeItem(k: string) { delete store[k] },
    clear() { Object.keys(store).forEach(k => delete store[k]) },
  }
  Object.defineProperty(globalThis, 'localStorage', { value: memoryStorage, writable: true })
}
