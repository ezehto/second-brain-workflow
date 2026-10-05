import type { ApiClient } from './client'

/**
 * The real client. It does not exist until the backend does (P1-31); every
 * call fails loudly rather than returning a plausible empty value.
 */
export function createHttpClient(): ApiClient {
  const notImplemented = (): Promise<never> =>
    Promise.reject(new Error('The HTTP API client is not implemented yet. Set VITE_API_MODE=mock.'))
  return {
    csrf: notImplemented,
    login: notImplemented,
    logout: notImplemented,
    me: notImplemented,
    health: notImplemented,
    listNotes: notImplemented,
    lookupNote: notImplemented,
    createNote: notImplemented,
    changeStatus: notImplemented,
    createCapture: notImplemented,
    triageCapture: notImplemented,
    listProjects: notImplemented,
    getProject: notImplemented,
    getStandupToday: notImplemented,
    startStandup: notImplemented,
    appendToStandup: notImplemented,
    getDashboard: notImplemented,
    search: notImplemented,
    getIndexStatus: notImplemented,
    refreshIndex: notImplemented,
  }
}
