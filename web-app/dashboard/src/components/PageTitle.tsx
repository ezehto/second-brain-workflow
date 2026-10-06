import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'

interface PageTitleState {
  title: string | null
  setTitle: (title: string | null) => void
}

const PageTitleContext = createContext<PageTitleState | null>(null)

/**
 * Lets a page that loads its own name (a project, a note) put it in the top
 * bar. The route `handle` gives the fallback ("Project"); while a page is
 * mounted and has called `usePageTitle`, the header shows that name instead.
 */
export function PageTitleProvider({ children }: { children: ReactNode }) {
  const [title, setTitle] = useState<string | null>(null)
  return <PageTitleContext.Provider value={{ title, setTitle }}>{children}</PageTitleContext.Provider>
}

/** The name a page published, or null. For the header. */
export function usePublishedTitle(): string | null {
  return useContext(PageTitleContext)?.title ?? null
}

/** Publish the page's loaded name to the header; cleared when the page unmounts or the name goes away. */
export function usePageTitle(title: string | undefined): void {
  const setTitle = useContext(PageTitleContext)?.setTitle
  useEffect(() => {
    if (!setTitle || !title) return
    setTitle(title)
    return () => setTitle(null)
  }, [setTitle, title])
}
