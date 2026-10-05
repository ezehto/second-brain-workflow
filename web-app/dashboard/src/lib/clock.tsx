import { createContext, useContext, type ReactNode } from 'react'

/** A calendar date, `YYYY-MM-DD`, in the vault's time zone (Asia/Manila). */
export type IsoDate = string

/** Returns today's date. Injected so no component reads the system clock. */
export type Clock = () => IsoDate

export const VAULT_TIME_ZONE = 'Asia/Manila'

/** The real clock: today in the vault's time zone, not the browser's. */
export const systemClock: Clock = () =>
  new Intl.DateTimeFormat('en-CA', {
    timeZone: VAULT_TIME_ZONE,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(new Date())

export const fixedClock =
  (date: IsoDate): Clock =>
  () =>
    date

const ClockContext = createContext<Clock>(systemClock)

export function ClockProvider({ clock, children }: { clock: Clock; children: ReactNode }) {
  return <ClockContext.Provider value={clock}>{children}</ClockContext.Provider>
}

/** The injected clock itself, for a provider that may override it. */
export function useClock(): Clock {
  return useContext(ClockContext)
}

/** Today's date from the injected clock. */
export function useToday(): IsoDate {
  return useContext(ClockContext)()
}
