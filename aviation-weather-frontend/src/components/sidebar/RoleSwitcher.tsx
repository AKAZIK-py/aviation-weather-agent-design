"use client"

import type { UserRole } from "@/types/api"
import { ROLES } from "@/types/api"

interface RoleSwitcherProps {
  role: UserRole
  onChange: (role: UserRole) => void
}

export function RoleSwitcher({ role, onChange }: RoleSwitcherProps) {
  return (
    <div className="flex items-center gap-1 px-4 py-2 border-b border-border/50 bg-background/50">
      {ROLES.map((r) => (
        <button
          key={r.id}
          type="button"
          onClick={() => onChange(r.id)}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium transition-all ${
            role === r.id
              ? "bg-primary text-primary-foreground shadow-sm"
              : "text-muted-foreground hover:bg-muted hover:text-foreground"
          }`}
        >
          <span>{r.icon}</span>
          <span>{r.label}</span>
        </button>
      ))}
    </div>
  )
}
