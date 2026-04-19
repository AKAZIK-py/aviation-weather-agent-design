"use client"

import { useState, useRef, useEffect } from "react"
import type { Message, SSEEvent, UserRole } from "@/types/api"
import { MessageBubble } from "./MessageBubble"
import { StreamingRenderer } from "./StreamingRenderer"
import { chatStream } from "@/services/api"

interface ChatPanelProps {
  messages: Message[]
  isStreaming: boolean
  onSend: (content: string) => void
  streamingEvents: SSEEvent[]
  role: UserRole
}

export function ChatPanel({ messages, isStreaming, onSend, streamingEvents, role }: ChatPanelProps) {
  const [input, setInput] = useState("")
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages, streamingEvents.length])

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    const trimmed = input.trim()
    if (!trimmed || isStreaming) return
    onSend(trimmed)
    setInput("")
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto"
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      handleSubmit(e)
    }
  }

  function handleTextareaChange(e: React.ChangeEvent<HTMLTextAreaElement>) {
    setInput(e.target.value)
    // Auto-resize
    const el = e.target
    el.style.height = "auto"
    el.style.height = Math.min(el.scrollHeight, 120) + "px"
  }

  return (
    <div className="flex flex-col flex-1 min-h-0">
      {/* 消息列表 */}
      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-1">
        {messages.length === 0 && streamingEvents.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-center text-muted-foreground">
            <div className="text-4xl mb-3 opacity-30">✈️</div>
            <p className="text-sm">输入天气相关问题开始对话</p>
            <p className="text-xs mt-1">例如：ZBAA 能降落吗？</p>
          </div>
        )}

        {messages.map((msg) => (
          <MessageBubble key={msg.id} message={msg} />
        ))}

        {/* 流式渲染中的 AI 回复 */}
        {isStreaming && streamingEvents.length > 0 && (
          <div className="flex justify-start mb-4">
            <div className="max-w-[75%] rounded-2xl rounded-bl-md px-4 py-3 bg-muted/60">
              <StreamingRenderer events={streamingEvents} isStreaming={isStreaming} />
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* 输入框 */}
      <div className="border-t border-border/50 px-4 py-3 bg-background/80 backdrop-blur-sm">
        <form onSubmit={handleSubmit} className="flex items-end gap-2">
          <textarea
            ref={textareaRef}
            value={input}
            onChange={handleTextareaChange}
            onKeyDown={handleKeyDown}
            placeholder={isStreaming ? "正在回复中..." : "输入天气相关问题... (Enter 发送, Shift+Enter 换行)"}
            disabled={isStreaming}
            rows={1}
            className="flex-1 resize-none rounded-xl border border-input bg-background px-4 py-2.5 text-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50 min-h-[44px] max-h-[120px]"
          />
          <button
            type="submit"
            disabled={isStreaming || !input.trim()}
            className="h-11 px-5 rounded-xl bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            发送
          </button>
        </form>
      </div>
    </div>
  )
}
