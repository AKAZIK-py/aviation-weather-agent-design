"use client"

import * as React from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import type { AnalyzeResponse, RiskLevel, UserRole } from "@/types/api"
import { RISK_LEVEL_LABELS, RISK_LEVEL_COLORS } from "@/types/api"
import { cn } from "@/lib/utils"

interface AnalysisResultProps {
  result: AnalyzeResponse | null
  isLoading?: boolean
  className?: string
}

// 角色映射
const ROLE_LABELS: Record<UserRole, string> = {
  pilot: "飞行员",
  dispatcher: "签派管制",
  forecaster: "预报员",
  ground_crew: "地勤",
}

// 风险等级图标
const RISK_ICONS: Record<RiskLevel, string> = {
  LOW: "✓",
  MEDIUM: "⚠",
  HIGH: "⚡",
  CRITICAL: "🚨",
}

// 风险等级边框样式
const RISK_BORDER_COLORS: Record<RiskLevel, string> = {
  LOW: "border-green-500/40",
  MEDIUM: "border-yellow-500/40",
  HIGH: "border-orange-500/40",
  CRITICAL: "border-red-500/40",
}

// 飞行规则映射
const FLIGHT_RULES_LABELS: Record<string, { label: string; color: string }> = {
  VFR: { label: "目视飞行规则", color: "text-green-500" },
  MVFR: { label: "边缘目视飞行规则", color: "text-blue-500" },
  IFR: { label: "仪表飞行规则", color: "text-amber-500" },
  LIFR: { label: "低仪表飞行规则", color: "text-red-500" },
}

export function AnalysisResult({ result, isLoading, className }: AnalysisResultProps) {
  if (isLoading) {
    return (
      <div className={cn("space-y-4", className)}>
        <Card className="animate-pulse">
          <CardHeader>
            <div className="h-7 w-32 bg-muted/30 rounded-lg" />
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="h-20 bg-muted/30 rounded-xl" />
            <div className="h-16 bg-muted/30 rounded-xl" />
            <div className="h-24 bg-muted/30 rounded-xl" />
          </CardContent>
        </Card>
      </div>
    )
  }

  if (!result || !result.success) {
    return (
      <Card className={cn("border-dashed border-2 border-muted/30", className)}>
        <CardContent className="flex flex-col items-center justify-center py-12 text-center">
          <div className="text-5xl mb-4 opacity-20">🛫</div>
          <p className="text-muted-foreground text-sm">
            输入METAR报文后点击分析，结果将在此显示
          </p>
          {result?.error && (
            <p className="text-destructive text-sm mt-2">{result.error}</p>
          )}
        </CardContent>
      </Card>
    )
  }

  const metar = result.metar_parsed!
  const riskLevel = result.risk_level ?? 'LOW'
  const riskLabel = RISK_LEVEL_LABELS[riskLevel]
  const riskIcon = RISK_ICONS[riskLevel]
  const flightRuleInfo = metar.flight_rules ? FLIGHT_RULES_LABELS[metar.flight_rules] : null

  // 获取结构化输出或使用基础解释
  const displayContent = result.structured_output || result.basic_explanation

  return (
    <div className={cn("space-y-4", className)}>
      {/* 解析报文 */}
      <Card className="overflow-hidden">
        <CardHeader className="bg-gradient-to-r from-primary/10 to-transparent border-b border-border/50">
          <CardTitle className="text-lg flex items-center gap-2">
            <span className="text-2xl">📊</span>
            报文解析
            {result.airport_name && (
              <Badge variant="secondary" className="ml-2">
                {result.airport_name}
              </Badge>
            )}
            {metar.icao_code && (
              <Badge variant="outline" className="font-mono">
                {metar.icao_code}
              </Badge>
            )}
          </CardTitle>
        </CardHeader>
        <CardContent className="pt-4 space-y-3">
          {/* 机场和时间 */}
          <div className="flex items-center gap-4 text-sm flex-wrap">
            {metar.observation_time && (
              <div>
                <span className="text-muted-foreground">观测时间:</span>
                <span className="ml-2 font-mono">{metar.observation_time}</span>
              </div>
            )}
            {metar.flight_rules && flightRuleInfo && (
              <div>
                <span className="text-muted-foreground">飞行规则:</span>
                <span className={cn("ml-2 font-semibold", flightRuleInfo.color)}>
                  {flightRuleInfo.label}
                </span>
              </div>
            )}
            {result.detected_role && (
              <div>
                <span className="text-muted-foreground">分析视角:</span>
                <span className="ml-2 font-semibold text-primary">
                  {ROLE_LABELS[result.detected_role] || result.detected_role}
                </span>
              </div>
            )}
          </div>

          {/* 气象数据网格 */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {metar.wind_direction !== null && metar.wind_direction !== undefined && (
              <div className="bg-muted/30 rounded-lg p-3">
                <div className="text-xs text-muted-foreground mb-1">风向风速</div>
                <div className="font-mono font-semibold">
                  {metar.wind_direction}° / {metar.wind_speed}kt
                  {metar.wind_gust && ` G${metar.wind_gust}kt`}
                </div>
              </div>
            )}
            {metar.visibility !== undefined && metar.visibility !== null && (
              <div className="bg-muted/30 rounded-lg p-3">
                <div className="text-xs text-muted-foreground mb-1">能见度</div>
                <div className="font-mono font-semibold">
                  {metar.visibility >= 1000 
                    ? `${(metar.visibility / 1000).toFixed(1)} km` 
                    : `${metar.visibility} m`}
                </div>
              </div>
            )}
            {metar.temperature !== undefined && metar.dewpoint !== undefined && (
              <div className="bg-muted/30 rounded-lg p-3">
                <div className="text-xs text-muted-foreground mb-1">温度/露点</div>
                <div className="font-mono font-semibold">
                  {metar.temperature}°C / {metar.dewpoint}°C
                </div>
              </div>
            )}
            {metar.altimeter && (
              <div className="bg-muted/30 rounded-lg p-3">
                <div className="text-xs text-muted-foreground mb-1">高度表</div>
                <div className="font-mono font-semibold">{metar.altimeter.toFixed(1)} hPa</div>
              </div>
            )}
          </div>

          {/* 天气现象 */}
          {metar.present_weather && metar.present_weather.length > 0 && (
            <div className="flex flex-wrap gap-2 items-center">
              <span className="text-xs text-muted-foreground">天气现象:</span>
              {metar.present_weather.map((w, i) => (
                <Badge key={i} variant="secondary" className="font-mono">
                  {typeof w === 'string' ? w : w.description}
                </Badge>
              ))}
            </div>
          )}

          {/* 云况 */}
          {metar.cloud_layers && metar.cloud_layers.length > 0 && (
            <div className="flex flex-wrap gap-2 items-center">
              <span className="text-xs text-muted-foreground">云况:</span>
              {metar.cloud_layers.map((cloud, i) => (
                <Badge key={i} variant="outline" className="font-mono">
                  {cloud.cover} {cloud.height_feet}ft
                  {cloud.cloud_type && ` (${cloud.cloud_type})`}
                </Badge>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* 风险评估 */}
      <Card className={cn("border-2", RISK_BORDER_COLORS[riskLevel])}>
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-3">
            <span className={cn("text-2xl", riskLevel === 'CRITICAL' && 'animate-pulse')}>{riskIcon}</span>
            风险评估
            <Badge className={cn("ml-2", RISK_LEVEL_COLORS[riskLevel])}>
              {riskLabel}
            </Badge>
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {/* 风险因素 */}
          {result.risk_factors && result.risk_factors.length > 0 && (
            <div>
              <div className="text-xs text-muted-foreground mb-2">风险因素:</div>
              <ul className="space-y-1">
                {result.risk_factors.map((factor, i) => (
                  <li key={i} className="text-sm flex items-start gap-2">
                    <span className="text-muted-foreground">•</span>
                    {factor}
                  </li>
                ))}
              </ul>
            </div>
          )}
          
          {/* 风险推理 */}
          {result.risk_reasoning && (
            <div className="mt-3 pt-3 border-t border-border/30">
              <div className="text-xs text-muted-foreground mb-1">风险分析:</div>
              <p className="text-sm leading-relaxed whitespace-pre-wrap">{result.risk_reasoning}</p>
            </div>
          )}

          {/* 结构化输出 */}
          {displayContent && (
            <div className="mt-3 pt-3 border-t border-border/30">
              <div className="text-xs text-muted-foreground mb-1">
                {result.structured_output ? '详细分析:' : '分析说明:'}
              </div>
              <div className="text-sm leading-relaxed whitespace-pre-wrap">
                {typeof displayContent === 'string' ? displayContent : JSON.stringify(displayContent, null, 2)}
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* 安全检查 */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <span className="text-2xl">{result.intervention_required ? "🚫" : "✅"}</span>
            安全检查
            <Badge variant={result.intervention_required ? "destructive" : "default"} className="ml-2">
              {result.intervention_required ? "需要干预" : "通过"}
            </Badge>
          </CardTitle>
        </CardHeader>
        <CardContent>
          {result.intervention_reason && (
            <div className="mb-3 p-3 bg-destructive/10 rounded-lg border border-destructive/20">
              <p className="text-sm text-destructive font-medium">{result.intervention_reason}</p>
            </div>
          )}
          {result.reasoning_trace && result.reasoning_trace.length > 0 ? (
            <ul className="space-y-1">
              {result.reasoning_trace.map((trace, i) => (
                <li key={i} className={cn(
                  "text-sm flex items-start gap-2",
                  result.intervention_required ? "text-destructive" : "text-muted-foreground"
                )}>
                  <span>•</span>
                  {trace}
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-muted-foreground">所有安全检查项目均已通过</p>
          )}
        </CardContent>
      </Card>

      {/* 处理统计 */}
      <Card className="bg-muted/30">
        <CardContent className="py-3 flex items-center justify-between text-xs text-muted-foreground">
          <div className="flex items-center gap-4">
            <span>LLM调用: <Badge variant="outline" className="ml-1">{result.llm_calls}</Badge></span>
            <span>处理时间: <Badge variant="outline" className="ml-1">{result.processing_time_ms}ms</Badge></span>
          </div>
          <div>
            Created By <a href="https://github.com/bytedance/deer-flow" target="_blank" rel="noopener noreferrer" className="text-primary hover:underline font-semibold">DeerFlow</a>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
