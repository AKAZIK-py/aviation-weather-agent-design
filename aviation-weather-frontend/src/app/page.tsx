"use client"

import { useState, useCallback, useEffect } from "react"
import type { Message, SSEEvent, Session, UserRole } from "@/types/api"
import { SessionSidebar } from "@/components/sidebar/SessionSidebar"
import { RoleSwitcher } from "@/components/sidebar/RoleSwitcher"
import { ChatPanel } from "@/components/chat/ChatPanel"
import { MetricsDashboard } from "@/components/metrics/MetricsDashboard"
import { chatStream, listSessions, getSession, deleteSession } from "@/services/api"
import { MessageSquare, BarChart3 } from "lucide-react"

function generateId(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
}

export default function HomePage() {
  const [role, setRole] = useState<UserRole>("pilot")
  const [sessions, setSessions] = useState<Session[]>([])
  const [currentSession, setCurrentSession] = useState<string | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [isStreaming, setIsStreaming] = useState(false)
  const [streamingEvents, setStreamingEvents] = useState<SSEEvent[]>([])
  const [activeTab, setActiveTab] = useState<"chat" | "metrics">("chat")

  // 页面加载时从后端拉会话列表
  useEffect(() => {
    listSessions()
      .then((s) => setSessions(s))
      .catch(() => {/* 静默失败 */})
  }, [])

  const handleSend = useCallback(async (content: string) => {
    // 添加用户消息
    const userMsg: Message = {
      id: generateId(),
      role: "user",
      content,
      timestamp: new Date().toISOString(),
    }
    setMessages((prev) => [...prev, userMsg])
    setIsStreaming(true)
    setStreamingEvents([])

    const toolCallsAccum: Array<{
      tool: string
      args: Record<string, unknown>
      result: string
    }> = []
    let answerContent = ""
    let evalScores = undefined
    let returnedSessionId: string | undefined

    try {
      for await (const event of chatStream(content, role, currentSession || undefined)) {
        setStreamingEvents((prev) => [...prev, event])

        if (event.type === "tool_call") {
          toolCallsAccum.push({
            tool: event.tool || "unknown",
            args: event.args || {},
            result: "",
          })
        } else if (event.type === "tool_result") {
          for (let i = toolCallsAccum.length - 1; i >= 0; i--) {
            if (toolCallsAccum[i].tool === event.tool && !toolCallsAccum[i].result) {
              toolCallsAccum[i].result = event.result || ""
              break
            }
          }
        } else if (event.type === "answer") {
          answerContent = event.content || ""
        } else if (event.type === "eval") {
          evalScores = {
            task_complete: event.task_complete ?? false,
            key_info_hit: event.key_info_hit ?? "0/0",
            output_usable: event.output_usable ?? false,
            hallucination_rate: event.hallucination_rate ?? 0,
          }
        } else if (event.type === "done") {
          if (event.session_id) {
            returnedSessionId = event.session_id
          }
        }
      }
    } catch (err) {
      answerContent = `请求失败: ${err instanceof Error ? err.message : "未知错误"}`
    }

    // 将流式结果转为正式消息
    const assistantMsg: Message = {
      id: generateId(),
      role: "assistant",
      content: answerContent || "未获取到回答",
      toolCalls: toolCallsAccum,
      evalScores,
      timestamp: new Date().toISOString(),
    }
    setMessages((prev) => [...prev, assistantMsg])
    setIsStreaming(false)
    setStreamingEvents([])

    // 处理 session_id：新建或更新会话
    const sid = returnedSessionId || currentSession
    if (sid) {
      setCurrentSession(sid)
      const existing = sessions.find((s) => s.id === sid)
      if (existing) {
        // 更新已有会话
        setSessions((prev) =>
          prev.map((s) =>
            s.id === sid
              ? { ...s, lastMessage: content, updatedAt: new Date().toISOString(), messageCount: s.messageCount + 2 }
              : s
          )
        )
      } else {
        // 新会话：加到列表头
        const newSession: Session = {
          id: sid,
          title: content.slice(0, 20) + (content.length > 20 ? "..." : ""),
          role,
          messageCount: 2,
          lastMessage: answerContent?.slice(0, 30) || content,
          updatedAt: new Date().toISOString(),
        }
        setSessions((prev) => [newSession, ...prev])
      }
    }
  }, [role, currentSession, sessions])

  // 点击历史会话：从后端加载消息
  const handleSelectSession = useCallback(async (sessionId: string | null) => {
    if (!sessionId) {
      handleNewSession()
      return
    }
    setCurrentSession(sessionId)
    try {
      const detail = await getSession(sessionId)
      // detail 应包含 messages 数组
      const msgs: Message[] = (detail.messages || []).map((m: { role: string; content: string }) => ({
        id: generateId(),
        role: m.role as "user" | "assistant",
        content: m.content,
        timestamp: new Date().toISOString(),
      }))
      setMessages(msgs)
    } catch {
      // 加载失败则清空
      setMessages([])
    }
  }, [])

  const handleNewSession = useCallback(() => {
    setCurrentSession(null)
    setMessages([])
    setStreamingEvents([])
    setIsStreaming(false)
  }, [])

  const handleDeleteSession = useCallback(async (sessionId: string) => {
    try {
      await deleteSession(sessionId)
    } catch { /* 静默失败 */ }
    setSessions(prev => prev.filter(s => s.id !== sessionId))
    if (currentSession === sessionId) {
      setCurrentSession(null)
      setMessages([])
    }
  }, [currentSession])

  return (
    <div className="flex h-screen overflow-hidden">
      {/* 左侧栏 */}
      <SessionSidebar
        sessions={sessions}
        currentSession={currentSession}
        onSelect={handleSelectSession}
        onNew={handleNewSession}
        onDelete={handleDeleteSession}
      />

      {/* 右侧主区域 */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Tab 头部 */}
        <div className="flex items-center gap-1 border-b border-gray-200 px-4 py-2">
          <button
            onClick={() => setActiveTab("chat")}
            className={`flex items-center gap-2 px-3 py-1.5 rounded-md text-sm font-medium transition-all ${
              activeTab === "chat"
                ? "bg-background text-foreground shadow-sm"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            <MessageSquare className="w-4 h-4" />
            对话
          </button>
          <button
            onClick={() => setActiveTab("metrics")}
            className={`flex items-center gap-2 px-3 py-1.5 rounded-md text-sm font-medium transition-all ${
              activeTab === "metrics"
                ? "bg-background text-foreground shadow-sm"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            <BarChart3 className="w-4 h-4" />
            指标
          </button>
        </div>

        {/* Tab 内容 */}
        {activeTab === "chat" ? (
          <div className="flex-1 flex flex-col min-h-0">
            <RoleSwitcher role={role} onChange={setRole} />
            <ChatPanel
              messages={messages}
              isStreaming={isStreaming}
              onSend={handleSend}
              streamingEvents={streamingEvents}
              role={role}
            />
          </div>
        ) : (
          <div className="flex-1 min-h-0 overflow-y-auto">
            <MetricsDashboard />
          </div>
        )}
      </div>
    </div>
  )
}
