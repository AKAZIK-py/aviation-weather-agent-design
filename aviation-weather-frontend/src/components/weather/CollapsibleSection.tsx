"use client"

import * as React from "react"
import { cn } from "@/lib/utils"

interface CollapsibleSectionProps {
  title: string
  summary?: string
  defaultOpen?: boolean
  children: React.ReactNode
  className?: string
}

export function CollapsibleSection({
  title,
  summary,
  defaultOpen = false,
  children,
  className,
}: CollapsibleSectionProps) {
  const [isOpen, setIsOpen] = React.useState(defaultOpen)
  const contentRef = React.useRef<HTMLDivElement>(null)
  const [contentHeight, setContentHeight] = React.useState<number | "auto">(
    defaultOpen ? "auto" : 0
  )

  React.useEffect(() => {
    if (contentRef.current) {
      setContentHeight(isOpen ? contentRef.current.scrollHeight : 0)
    }
  }, [isOpen, children])

  return (
    <div className={cn("border border-border/40 rounded-lg overflow-hidden", className)}>
      {/* Header */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between px-4 py-3 bg-muted/30 hover:bg-muted/50 transition-colors text-left"
      >
        <div className="flex items-center gap-2">
          <span
            className={cn(
              "text-xs transition-transform duration-200",
              isOpen ? "rotate-90" : "rotate-0"
            )}
          >
            ▶
          </span>
          <span className="text-sm font-semibold">{title}</span>
        </div>
        {!isOpen && summary && (
          <span className="text-xs text-muted-foreground">{summary}</span>
        )}
      </button>

      {/* Content with smooth animation */}
      <div
        style={{
          height: contentHeight === "auto" ? "auto" : `${contentHeight}px`,
          overflow: "hidden",
          transition: "height 0.3s ease-in-out",
        }}
      >
        <div ref={contentRef} className="px-4 py-3">
          {children}
        </div>
      </div>
    </div>
  )
}
