/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE?: string
  readonly VITE_PUBLIC_MODE?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
