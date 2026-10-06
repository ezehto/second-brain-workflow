import { useNavigate, useSearchParams } from 'react-router'
import { EmptyState } from '@/components/EmptyState'
import { Icon } from '@/components/Icon'
import { Button } from '@/components/ui/button'
import { NoteReader } from './NoteReader'

/** The `/notes?path=` route: one note on its own page, for narrow screens and for links from anywhere. */
export function NotePage() {
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const path = params.get('path')
  return (
    <div className="flex flex-col gap-3">
      <div>
        <Button variant="ghost" size="sm" onClick={() => navigate(-1)}>
          <Icon name="chevron" className="size-3.5 rotate-90" />
          Back
        </Button>
      </div>
      {path ? <NoteReader path={path} /> : <EmptyState>No note is selected. Open one from a list.</EmptyState>}
    </div>
  )
}
