import { useSearchParams } from 'react-router'
import type { NoteSummary } from '@/api/types'
import { NoteReader } from '@/features/notes/NoteReader'
import { useSplitLayout } from '@/lib/viewport'
import { withParam, type ListView } from './filters'

/**
 * The reader pane both pages share. From 1024 up a row opens the note in the
 * pane (`?note=`); below that `onOpen` is undefined and the row's link goes to
 * the `/notes?path=` route instead.
 */
export function useReaderPane(view: ListView) {
  const [params, setParams] = useSearchParams()
  const split = useSplitLayout()
  const setNote = (note: string | undefined) => setParams(withParam(params, 'note', note))
  return {
    setParam: (key: keyof ListView, value: string | undefined) => setParams(withParam(params, key, value)),
    onOpen: split ? (note: NoteSummary) => setNote(note.path) : undefined,
    reader: split && view.note ? <NoteReader path={view.note} onClose={() => setNote(undefined)} /> : undefined,
  }
}
