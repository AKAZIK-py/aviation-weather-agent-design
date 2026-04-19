"use client"

import { useState } from "react"
import type { ToolCallTrace as ToolCallTraceType } from "@/types/api"

interface ToolCallTraceProps {
  toolCalls: ToolCallTraceType[]
}

function formatJson(value: unknown): string {
  if (typeof value === "string") return value
  try {
    return JSON.stringify(value, null, 2)
  } catch {
    return String(value)
  }
}

export function ToolCallTrace({ toolCalls }: ToolCallTraceProps) {
  const [expanded, setExpanded] = useState(false)

  if (toolCalls.length === 0) return null

  return (
    <div className="mt-2">
      <button
        type="button"
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors"
      >
        <span>{expanded ? "▾" : "▸"}</span>
        <span>工具调用 ({toolCalls.length})</span>
      </button>

      {expanded && (
        <div className="mt-1.5 space-y-1.5 pl-3 border-l-2 border-muted">
          {toolCalls.map((tc, i) => (
            <div key={`${tc.tool}-${i}`} className="text-xs">
              <div className="flex items-center gap-1.5">
                <span className={tc.result ? "text-green-600" : "text-red-500"}>
                  {tc.result ? "●" : "○"}
                </span>
                <span className="font-mono font-medium">{tc.tool}</span>
                {tc.durationMs !== undefined && (
                  <span className="text-muted-foreground">({tc.durationMs}ms)</span>
                )}
              </div>
              <div className="ml-4 mt-0.5 space-y-0.5">
                <div className="text-muted-foreground">
                  <span className="font-mono text-[10px]">args:</span>{" "}
                  <code className="bg-muted/50 rounded px-1">{formatJson(tc.args)}</code>
                </div>
                {tc.result && (
                  <div className="text-muted-foreground">
                    <span className="font-mono text-[10px]">result:</span>{" "}
                    <code className="bg-muted/50 rounded px-1 max-h-20 overflow-auto block whitespace-pre-wrap">
                      {tc.result.length > 200 ? tc.result.slice(0, 200) + "..." : tc.result}
                    </code>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
