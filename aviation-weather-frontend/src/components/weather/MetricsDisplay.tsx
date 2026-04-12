"use client"

import * as React from "react"
import { Card, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"

// 动态指标接口
interface LiveMetrics {
  // 累计统计
  total_requests: number
  success_requests: number
  avg_latency_ms: number
  // 最新一次分析
  last_analysis?: {
    flight_rules: string
    risk_level: string
    llm_calls: number
    processing_time_ms: number
    model_used: string
    role: string
    timestamp: string
  }
}

interface MetricsDisplayProps {
  metrics: LiveMetrics
  className?: string
}

// 飞行规则颜色
const FR_COLORS: Record<string, string> = {
  VFR: "text-green-400",
  MVFR: "text-blue-400",
  IFR: "text-amber-400",
  LIFR: "text-red-400",
}

// 风险等级颜色
const RISK_COLORS: Record<string, string> = {
  LOW: "text-green-400 bg-green-500/15",
  MEDIUM: "text-yellow-400 bg-yellow-500/15",
  HIGH: "text-orange-400 bg-orange-500/15",
  CRITICAL: "text-red-400 bg-red-500/15 animate-pulse",
}

export function MetricsDisplay({ metrics, className }: MetricsDisplayProps) {
  const { total_requests, success_requests, avg_latency_ms, last_analysis } = metrics
  const successRate = total_requests > 0 ? ((success_requests / total_requests) * 100).toFixed(1) : "--"

  return (
    <div className={className}>
      {/* 标题栏 */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium">📊 系统状态</span>
          <Badge variant="outline" className="text-xs">
            在线
          </Badge>
        </div>
        <div className="flex items-center gap-3 text-xs text-muted-foreground">
          <span>已处理 <span className="font-mono font-semibold text-foreground">{total_requests}</span> 次</span>
          <span>成功率 <span className="font-mono font-semibold text-green-400">{successRate}%</span></span>
          <span>平均延迟 <span className="font-mono font-semibold text-foreground">{avg_latency_ms}ms</span></span>
        </div>
      </div>

      {/* 核心指标网格 */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
        {/* 总请求数 */}
        <Card className="bg-slate-500/10 border-0">
          <CardContent className="p-3">
            <div className="text-xs text-muted-foreground mb-1">总请求</div>
            <div className="text-2xl font-bold font-mono text-slate-300">
              {total_requests}
            </div>
            <div className="text-xs text-muted-foreground mt-0.5">
              成功 {success_requests}
            </div>
          </CardContent>
        </Card>

        {/* 平均延迟 */}
        <Card className="bg-cyan-500/10 border-0">
          <CardContent className="p-3">
            <div className="text-xs text-muted-foreground mb-1">平均延迟</div>
            <div className="text-2xl font-bold font-mono text-cyan-400">
              {avg_latency_ms}<span className="text-sm">ms</span>
            </div>
            <div className="text-xs text-muted-foreground mt-0.5">
              {avg_latency_ms < 3000 ? "正常" : avg_latency_ms < 10000 ? "较慢" : "超时风险"}
            </div>
          </CardContent>
        </Card>

        {/* 最新飞行规则 */}
        <Card className={cn("border-0", last_analysis ? "bg-indigo-500/10" : "bg-muted/20")}>
          <CardContent className="p-3">
            <div className="text-xs text-muted-foreground mb-1">最新飞行规则</div>
            {last_analysis ? (
              <>
                <div className={cn("text-2xl font-bold font-mono", FR_COLORS[last_analysis.flight_rules] || "text-foreground")}>
                  {last_analysis.flight_rules}
                </div>
                <div className="text-xs text-muted-foreground mt-0.5">
                  {last_analysis.role} · {last_analysis.model_used}
                </div>
              </>
            ) : (
              <div className="text-lg text-muted-foreground">--</div>
            )}
          </CardContent>
        </Card>

        {/* 最新风险等级 */}
        <Card className={cn("border-0", last_analysis ? RISK_COLORS[last_analysis.risk_level]?.split(" ")[1] : "bg-muted/20")}>
          <CardContent className="p-3">
            <div className="text-xs text-muted-foreground mb-1">最新风险</div>
            {last_analysis ? (
              <>
                <div className={cn("text-2xl font-bold font-mono", RISK_COLORS[last_analysis.risk_level]?.split(" ")[0])}>
                  {last_analysis.risk_level}
                </div>
                <div className="text-xs text-muted-foreground mt-0.5">
                  LLM {last_analysis.llm_calls} 次 · {last_analysis.processing_time_ms}ms
                </div>
              </>
            ) : (
              <div className="text-lg text-muted-foreground">--</div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
