"use client"

import type { Session } from "@/types/api"
import { Button } from "@/components/ui/button"
import { Trash2 } from "lucide-react"

interface SessionSidebarProps {
  sessions: Session[]
  currentSession: string | null
  onSelect: (sessionId: string | null) => void
  onNew: () => void
  onDelete: (sessionId: string) => void
}

export function SessionSidebar({ sessions, currentSession, onSelect, onNew, onDelete }: SessionSidebarProps) {
  return (
    <aside className="w-[280px] bg-slate-900 text-slate-200 flex flex-col shrink-0">
      {/* 头部 */}
      <div className="p-4 border-b border-slate-700">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-sm font-semibold text-slate-100">对话历史</h2>
          <span className="text-[10px] text-slate-500 bg-slate-800 px-1.5 py-0.5 rounded">
            {sessions.length}
          </span>
        </div>
        <Button
          onClick={onNew}
          variant="outline"
          size="sm"
          className="w-full bg-slate-800 border-slate-600 text-slate-200 hover:bg-slate-700 hover:text-white"
        >
          + 新对话
        </Button>
      </div>

      {/* 会话列表 */}
      <div className="flex-1 overflow-y-auto">
        {sessions.length === 0 && (
          <div className="p-4 text-center text-xs text-slate-500">
            暂无对话记录
          </div>
        )}
        {sessions.map((session) => (
          <div
            key={session.id}
            className="group relative"
          >
            <button
              type="button"
              onClick={() => onSelect(session.id)}
              className={`w-full text-left px-4 py-3 border-b border-slate-800 hover:bg-slate-800 transition-colors ${
                currentSession === session.id ? "bg-slate-800" : ""
              }`}
            >
              <div className="text-sm font-medium text-slate-200 truncate pr-6">
                {session.title || "未命名对话"}
              </div>
              <div className="text-xs text-slate-500 mt-0.5 truncate">
                {session.lastMessage?.slice(0, 30) || "暂无消息"}
              </div>
              <div className="flex items-center gap-2 mt-1">
                <span className="text-[10px] text-slate-600">
                  {session.messageCount} 条消息
                </span>
                <span className="text-[10px] text-slate-600">
                  {session.updatedAt
                    ? new Date(session.updatedAt).toLocaleDateString("zh-CN")
                    : ""}
                </span>
              </div>
            </button>
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation()
                onDelete(session.id)
              }}
              className="absolute right-2 top-3 p-1 rounded hover:bg-slate-700 text-slate-500 hover:text-red-400 opacity-0 group-hover:opacity-100 transition-opacity"
              title="删除会话"
            >
              <Trash2 className="h-3.5 w-3.5" />
            </button>
          </div>
        ))}
      </div>

      {/* 底部 */}
      <div className="p-3 border-t border-slate-700 text-[10px] text-slate-600 text-center">
        航空气象 Agent v3.0
      </div>
    </aside>
  )
}
