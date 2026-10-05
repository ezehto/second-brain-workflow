import { describe, expect, it } from 'vitest'
import config from './vite.config'

// P1-18: the Compose service depends on these exact settings.
describe('vite config', () => {
  const server = config.server!

  it('proxies /api to the backend service without rewriting the host', () => {
    const proxy = server.proxy as Record<string, { target: string; changeOrigin: boolean }>
    expect(proxy['/api'].target).toBe('http://backend:8000')
    expect(proxy['/api'].changeOrigin).toBe(false)
  })

  it('listens on all interfaces so the container port is reachable', () => {
    expect(server.host).toBe('0.0.0.0')
    expect(server.port).toBe(5173)
  })

  it('polls for changes, because file events do not cross the WSL2 mount', () => {
    expect(server.watch?.usePolling).toBe(true)
  })

  it('accepts requests addressed to localhost', () => {
    expect(server.allowedHosts).toContain('localhost')
  })
})
