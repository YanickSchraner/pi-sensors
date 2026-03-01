/**
 * Returns the correct API base URL.
 * - On the server (SSR): uses the internal Docker network URL (container-to-container)
 * - In the browser: uses the public /api path (routed through Caddy)
 */
export function useApiBase(): string {
  const config = useRuntimeConfig()
  if (import.meta.server) {
    return config.apiBaseInternal || config.public.apiBase
  }
  return config.public.apiBase
}
