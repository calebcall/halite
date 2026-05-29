/// <reference types="vite/client" />

/**
 * Git/build hash injected by Vite's `define` (see vite.config.ts). Set at build
 * time via the Dockerfile's BUILD_HASH arg; an empty string in local dev, which
 * the sidebar footer renders as "Dev".
 */
declare const __BUILD_HASH__: string
