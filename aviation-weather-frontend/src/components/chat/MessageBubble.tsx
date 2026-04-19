"use client"

import type { Message } from "@/types/api"
import { EvalBadge } from "./EvalBadge"
import { ToolCallTrace } from "./ToolCallTrace"

interface MessageBubbleProps {
  message: Message
}

export function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === "user"

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"} mb-4`}>
      <div
        className={`max-w-[75%] rounded-2xl px-4 py-3 ${
          isUser
            ? "bg-blue-600 text-white rounded-br-md"
            : "bg-muted/60 text-foreground rounded-bl-md"
        }`}
      >
        {/* 消息内容 */}
        <div className="text-sm whitespace-pre-wrap leading-relaxed">
          {message.content}
        </div>

        {/* AI 消息下的工具调用 */}
        {!isUser && message.toolCalls && message.toolCalls.length > 0 && (
          <ToolCallTrace toolCalls={message.toolCalls} />
        )}

        {/* AI 消息下的评测 Badge */}
        {!isUser && message.evalScores && (
          <EvalBadge scores={message.evalScores} />
        )}

        {/* 时间戳 */}
        <div
          className={`text-[10px] mt-1.5 ${
            isUser ? "text-blue-200" : "text-muted-foreground"
          }`}
        >
          {new Date(message.timestamp).toLocaleTimeString("zh-CN", {
            hour: "2-digit",
            minute: "2-digit",
          })}
        </div>
      </div>
    </div>
  )
}
