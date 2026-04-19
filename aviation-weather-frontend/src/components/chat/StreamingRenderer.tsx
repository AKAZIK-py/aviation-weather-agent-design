"use client"

import { useState, useEffect, useRef } from "react"
import type { SSEEvent, EvalScores, ToolCallTrace as ToolCallTraceType } from "@/types/api"
import { EvalBadge } from "./EvalBadge"
import { ToolCallTrace } from "./ToolCallTrace"

interface StreamingRendererProps {
  events: SSEEvent[]
  isStreaming: boolean
}

export function StreamingRenderer({ events, isStreaming }: StreamingRendererProps) {
  const [answer, setAnswer] = useState("")
  const [toolCalls, setToolCalls] = useState<ToolCallTraceType[]>([])
  const [evalScores, setEvalScores] = useState<EvalScores | null>(null)
  const [thinking, setThinking] = useState("")
  const [error, setError] = useState("")
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const latest = events[events.length - 1]
    if (!latest) return

    switch (latest.type) {
      case "thinking":
        setThinking(latest.content || "")
        break
      case "tool_call":
        setToolCalls((prev) => [
          ...prev,
          {
            tool: latest.tool || "unknown",
            args: latest.args || {},
            result: "",
          },
        ])
        break
      case "tool_result":
        setToolCalls((prev) => {
          const updated = [...prev]
          for (let i = updated.length - 1; i >= 0; i--) {
            if (updated[i].tool === latest.tool && !updated[i].result) {
              updated[i] = { ...updated[i], result: latest.result || "" }
              break
            }
          }
          return updated
        })
        break
      case "answer":
        setAnswer(latest.content || "")
        break
      case "eval": {
        const raw = latest as unknown as Record<string, unknown>
        setEvalScores({
          task_complete: raw.task_complete as boolean,
          key_info_hit: raw.key_info_hit as string,
          output_usable: raw.output_usable as boolean,
          hallucination_rate: raw.hallucination_rate as number,
        })
        break
      }
      case "error":
        setError(latest.message || "未知错误")
        break
    }
  }, [events])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [answer, toolCalls, events.length])

  return (
    <div className="space-y-3">
      {/* 思考中 */}
      {thinking && !answer && (
        <div className="flex items-center gap-2 text-sm text-muted-foreground animate-pulse">
          <span className="inline-block w-2 h-2 bg-blue-500 rounded-full animate-bounce" />
          <span>{thinking}</span>
        </div>
      )}

      {/* 工具调用过程 */}
      {toolCalls.length > 0 && (
        <ToolCallTrace toolCalls={toolCalls} />
      )}

      {/* 回答内容 */}
      {answer && (
        <div className="text-sm whitespace-pre-wrap leading-relaxed">
          {answer}
        </div>
      )}

      {/* 流式中且还没有回答时的 loading */}
      {isStreaming && !answer && !error && !thinking && (
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <span className="inline-block w-2 h-2 bg-gray-400 rounded-full animate-pulse" />
          <span>连接中...</span>
        </div>
      )}

      {/* 评测 Badge */}
      {evalScores && (
        <EvalBadge scores={evalScores} />
      )}

      {/* 错误 */}
      {error && (
        <div className="text-sm text-red-600 bg-red-50 rounded-lg px-3 py-2">
          {error}
        </div>
      )}

      <div ref={bottomRef} />
    </div>
  )
}
