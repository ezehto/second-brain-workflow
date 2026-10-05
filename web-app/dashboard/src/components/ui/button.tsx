import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "cn"
import { Slot } from "radix-ui"

const buttonVariants = cva(
  "group/button inline-flex shrink-0 cursor-pointer items-center justify-center gap-2 rounded-btn border border-transparent text-sm font-semibold whitespace-nowrap no-underline transition-colors outline-none select-none focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand disabled:pointer-events-none disabled:opacity-45 [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-4 max-rail:min-h-11",
  {
    variants: {
      variant: {
        default:
          "bg-brand-fill text-white hover:bg-brand-fill-hover hover:text-white",
        secondary:
          "border-line bg-inset text-ink hover:bg-line hover:text-ink",
        outline:
          "border-line bg-transparent text-ink hover:bg-inset hover:text-ink",
        ghost: "text-muted-ink hover:bg-inset hover:text-ink",
        onAccent:
          "bg-white/15 text-white hover:bg-white/25 hover:text-white",
        destructive:
          "bg-tint-blocked text-status-blocked hover:bg-status-blocked/25",
        link: "text-brand underline-offset-4 hover:underline",
      },
      size: {
        default: "h-[38px] px-3.5",
        sm: "h-8 px-3 text-[13px]",
        icon: "size-[38px]",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
)

function Button({
  className,
  variant = "default",
  size = "default",
  asChild = false,
  ...props
}: React.ComponentProps<"button"> &
  VariantProps<typeof buttonVariants> & {
    asChild?: boolean
  }) {
  const Comp = asChild ? Slot.Root : "button"

  return (
    <Comp
      data-slot="button"
      data-variant={variant}
      data-size={size}
      className={cn(buttonVariants({ variant, size, className }))}
      {...props}
    />
  )
}

export { Button, buttonVariants }
