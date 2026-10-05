import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'

interface ToastApi {
  /** Shows a message for a few seconds. A new message replaces the old one. */
  show: (message: string) => void
}

const ToastContext = createContext<ToastApi | null>(null)

const VISIBLE_MS = 4000

export function ToastProvider({ children }: { children: ReactNode }) {
  const [message, setMessage] = useState('')
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)

  const show = useCallback((next: string) => {
    setMessage(next)
    clearTimeout(timer.current)
    timer.current = setTimeout(() => setMessage(''), VISIBLE_MS)
  }, [])
  useEffect(() => () => clearTimeout(timer.current), [])

  const api = useMemo(() => ({ show }), [show])
  return (
    <ToastContext.Provider value={api}>
      {children}
      {/* The live region is always mounted so a screen reader announces the text when it appears. */}
      <div role="status" aria-live="polite" className="pointer-events-none fixed right-5 bottom-5 left-5 z-[60] flex justify-end sm:left-auto">
        {message && (
          <p className="pointer-events-auto m-0 max-w-[420px] rounded-tile bg-ink px-3.5 py-2.5 text-[13px] font-medium break-words text-ground">
            {message}
          </p>
        )}
      </div>
    </ToastContext.Provider>
  )
}

export function useToast(): ToastApi {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error('useToast must be used inside <ToastProvider>')
  return ctx
}
