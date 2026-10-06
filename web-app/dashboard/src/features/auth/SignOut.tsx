import { Button } from '@/components/ui/button'
import { DropdownMenuItem } from '@/components/ui/dropdown-menu'
import { useToast } from '@/components/Toast'
import { useSession } from './SessionProvider'

/** Ends the session; the route guard then sends the person to the login page. */
function useSignOut() {
  const { logout } = useSession()
  const toast = useToast()
  return async () => {
    try {
      await logout()
    } catch {
      toast.show('The server did not confirm the sign-out, so your session may still be open. Try again, or close this browser.')
    }
  }
}

export function SignOutMenuItem() {
  const signOut = useSignOut()
  return (
    <DropdownMenuItem onSelect={() => void signOut()} className="min-h-8 max-rail:min-h-11">
      Sign out
    </DropdownMenuItem>
  )
}

export function SignOutButton({ className }: { className?: string }) {
  const signOut = useSignOut()
  return (
    <Button variant="secondary" className={className} onClick={() => void signOut()}>
      Sign out
    </Button>
  )
}
