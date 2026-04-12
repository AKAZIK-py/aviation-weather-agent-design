"use client"

import * as React from "react"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Badge } from "@/components/ui/badge"
import { ROLES, type UserRole } from "@/types/api"

interface RoleSelectorProps {
  value: UserRole
  onChange: (role: UserRole) => void
  className?: string
}

export function RoleSelector({ value, onChange, className }: RoleSelectorProps) {
  return (
    <div className={className}>
      <div className="flex items-center gap-2 mb-3">
        <span className="text-sm font-medium">分析视角</span>
        <Badge variant="outline" className="text-xs">
          选择角色获得定制化分析
        </Badge>
      </div>
      <Tabs value={value} onValueChange={(v) => onChange(v as UserRole)} className="w-full">
        <TabsList className="grid grid-cols-4 w-full h-auto p-1">
          {ROLES.map((role) => (
            <TabsTrigger
              key={role.id}
              value={role.id}
              className="flex flex-col items-center gap-1 py-2 data-[state=active]:bg-primary/10"
            >
              <span className="text-lg">{role.icon}</span>
              <span className="text-xs">{role.label}</span>
            </TabsTrigger>
          ))}
        </TabsList>
        {ROLES.map((role) => (
          <TabsContent key={role.id} value={role.id} className="mt-3">
            <div className="bg-muted/30 rounded-lg p-3">
              <p className="text-xs text-muted-foreground mb-2">{role.description}</p>
              <div className="flex flex-wrap gap-1">
                {role.focusAreas.map((area, i) => (
                  <Badge key={i} variant="secondary" className="text-xs">
                    {area}
                  </Badge>
                ))}
              </div>
            </div>
          </TabsContent>
        ))}
      </Tabs>
    </div>
  )
}
