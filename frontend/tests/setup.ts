import '@testing-library/jest-dom/vitest'

// jsdom does not implement ResizeObserver; Radix UI (Switch, etc.) requires it.
global.ResizeObserver = class ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
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
