"use client"

import * as React from "react"
import { Card, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { WeatherAlertList } from "./WeatherAlert"
import { CollapsibleSection } from "./CollapsibleSection"
import { parseReportText } from "@/lib/parseReport"
import type { UserRole, RiskLevel, WeatherAlert, AlertSeverity } from "@/types/api"
import { ROLES, RISK_LEVEL_LABELS, RISK_LEVEL_COLORS } from "@/types/api"
import { cn } from "@/lib/utils"

// 后端 role_report 实际返回结构（含新字段）
interface BackendRoleReport {
  role: string
  role_cn?: string
  airport_icao?: string
  observation_time?: string
  risk_level: string
  report_text?: string
  summary?: string
  role_summary?: {
    headlines: string[]
    decision: "GO" | "CAUTION" | "NO-GO"
    confidence: string
  }
  disclaimer?: string
  structured_analysis?: Record<string, any> | null
  alerts?: WeatherAlert[]
  recommendations?: string[]
  generated_at: string
  model_used?: string
}

interface RoleReportCardProps {
  report: BackendRoleReport
  className?: string
}

// GO/NO-GO 决策配置
const DECISION_CONFIG: Record<string, {
  label: string
  color: string
  bgColor: string
  pulse: boolean
}> = {
  GO: {
    label: "GO",
    color: "text-green-400",
    bgColor: "bg-green-500/20 border-green-500/50",
    pulse: false,
  },
  CAUTION: {
    label: "CAUTION",
    color: "text-yellow-400",
    bgColor: "bg-yellow-500/20 border-yellow-500/50",
    pulse: false,
  },
  "NO-GO": {
    label: "NO-GO",
    color: "text-red-400",
    bgColor: "bg-red-500/20 border-red-500/50",
    pulse: true,
  },
}

// 风险等级边框颜色
const RISK_BORDER_COLORS: Record<string, string> = {
  LOW: "border-green-500/40",
  MEDIUM: "border-yellow-500/40",
  HIGH: "border-orange-500/40",
  CRITICAL: "border-red-500/40",
}

// 角色特定主区域配置
const ROLE_PRIMARY_SECTIONS: Record<string, string[]> = {
  pilot: ["天气概况", "能见度", "云底高", "风况", "进近", "DH", "MDA", "建议", "行动"],
  dispatcher: ["飞行规则", "风险", "建议", "行动", "签派"],
  forecaster: ["天气概况", "风险", "建议", "趋势", "预报"],
  ground_crew: ["天气概况", "风险", "建议", "作业", "地面"],
}

export function RoleReportCard({ report, className }: RoleReportCardProps) {
  const roleId = report.role as UserRole
  const riskLevel = (report.risk_level || "MEDIUM") as RiskLevel
  const roleConfig = ROLES.find((r) => r.id === roleId)
  const riskLabel = RISK_LEVEL_LABELS[riskLevel] || riskLevel

  // 兼容两种字段名
  const summaryText = report.report_text || report.summary || "暂无分析报告"

  // 解析报告文本
  const parsed = React.useMemo(() => parseReportText(summaryText), [summaryText])

  // role_summary（新字段）
  const roleSummary = report.role_summary
  const decision = roleSummary?.decision || (riskLevel === "LOW" ? "GO" : riskLevel === "MEDIUM" ? "CAUTION" : "NO-GO")
  const decisionConfig = DECISION_CONFIG[decision] || DECISION_CONFIG.GO
  const headlines = roleSummary?.headlines || []

  // 兼容后端 alert 格式
  const alerts: WeatherAlert[] = (report.alerts || []).map((a: any, i: number) => ({
    id: a.id || `alert-${i}`,
    severity: (a.severity || a.level || "MEDIUM") as AlertSeverity,
    title: a.title || a.factors?.[0] || "天气告警",
    description: a.description || a.content || "",
    recommended_action:
      a.recommended_action ||
      (a.factors?.length > 1 ? a.factors.slice(1).join("; ") : undefined),
    timestamp: a.timestamp || new Date().toISOString(),
  }))

  // 按角色过滤主区域 sections
  const primaryKeywords = ROLE_PRIMARY_SECTIONS[roleId] || ROLE_PRIMARY_SECTIONS.pilot
  const primarySections = parsed.sections.filter((s) =>
    primaryKeywords.some((kw) => s.title.includes(kw))
  )
  const secondarySections = parsed.sections.filter(
    (s) => !primaryKeywords.some((kw) => s.title.includes(kw))
  )

  return (
    <div className={cn("space-y-4", className)}>
      {/* ===== ReportHeader ===== */}
      <Card className={cn("border-2", RISK_BORDER_COLORS[riskLevel])}>
        <CardContent className="pt-4 pb-3">
          <div className="flex items-center justify-between flex-wrap gap-2">
            <div className="flex items-center gap-2">
              <span className="text-xl">{roleConfig?.icon || "✈️"}</span>
              <span className="font-bold">
                {report.airport_icao || "----"}
              </span>
              <span className="text-muted-foreground">·</span>
              <span className="text-sm text-muted-foreground">
                {report.role_cn || roleConfig?.label || roleId}
              </span>
            </div>
            <div className="flex items-center gap-2">
              <Badge className={cn("text-xs", RISK_LEVEL_COLORS[riskLevel])}>
                {riskLabel}
              </Badge>
              {parsed.weatherOverview["飞行规则"] && (
                <Badge variant="outline" className="text-xs">
                  {parsed.weatherOverview["飞行规则"]}
                </Badge>
              )}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* ===== RoleSummary ===== */}
      <Card className="border-2 border-border/50">
        <CardContent className="pt-4 pb-3 space-y-3">
          {/* Headlines */}
          {headlines.length > 0 && (
            <div className="space-y-1">
              {headlines.map((h, i) => (
                <div key={i} className="flex items-center gap-2 text-sm">
                  <span className="w-1.5 h-1.5 rounded-full bg-primary flex-shrink-0" />
                  <span>{h}</span>
                </div>
              ))}
            </div>
          )}

          {/* GO/NO-GO Decision */}
          <div
            className={cn(
              "flex items-center justify-center py-3 rounded-lg border-2",
              decisionConfig.bgColor,
              decisionConfig.pulse && "animate-pulse"
            )}
          >
            <span className={cn("text-2xl font-black tracking-wider", decisionConfig.color)}>
              {decisionConfig.label}
            </span>
            {roleSummary?.confidence && (
              <span className="ml-3 text-xs text-muted-foreground">
                置信度: {roleSummary.confidence}
              </span>
            )}
          </div>
        </CardContent>
      </Card>

      {/* ===== PrimarySection (按角色渲染) ===== */}
      {primarySections.length > 0 ? (
        primarySections.map((section, i) => (
          <Card key={i} className="border border-border/40">
            <CardContent className="pt-3 pb-3">
              <div className="text-sm font-semibold mb-2 flex items-center gap-2">
                <span className="text-primary">●</span>
                {section.title}
              </div>
              <div className="space-y-1">
                {section.lines.map((line, j) => (
                  <div key={j} className="text-sm text-muted-foreground leading-relaxed">
                    {line}
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        ))
      ) : (
        // 降级: 直接显示报告文本
        <Card className="border border-border/40">
          <CardContent className="pt-3 pb-3">
            <div className="text-sm leading-relaxed whitespace-pre-wrap font-mono bg-muted/30 rounded-lg p-4">
              {summaryText}
            </div>
          </CardContent>
        </Card>
      )}

      {/* ===== CollapsibleSection: 补充信息 ===== */}
      {secondarySections.length > 0 && (
        <CollapsibleSection
          title="补充信息"
          summary={`${secondarySections.length} 个区块`}
          defaultOpen={false}
        >
          <div className="space-y-3">
            {secondarySections.map((section, i) => (
              <div key={i}>
                <div className="text-xs font-semibold text-muted-foreground mb-1">
                  {section.title}
                </div>
                <div className="space-y-1">
                  {section.lines.map((line, j) => (
                    <div key={j} className="text-xs text-muted-foreground">
                      {line}
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </CollapsibleSection>
      )}

      {/* 动态评分 + 结构化数据 */}
      {report.structured_analysis && Object.keys(report.structured_analysis).length > 0 && (
        <CollapsibleSection
          title="结构化分析"
          summary="JSON"
          defaultOpen={false}
        >
          <pre className="text-xs whitespace-pre-wrap font-mono bg-muted/30 rounded-lg p-3 overflow-x-auto">
            {JSON.stringify(report.structured_analysis, null, 2)}
          </pre>
        </CollapsibleSection>
      )}

      {/* ===== CollapsibleSection: 原始数据 ===== */}
      <CollapsibleSection
        title="原始数据"
        summary="METAR / JSON"
        defaultOpen={false}
      >
        <div className="space-y-3">
          {summaryText && (
            <div>
              <div className="text-xs font-semibold text-muted-foreground mb-1">报告原文</div>
              <pre className="text-xs whitespace-pre-wrap font-mono bg-muted/30 rounded-lg p-3 max-h-[300px] overflow-y-auto">
                {summaryText}
              </pre>
            </div>
          )}
          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <span>模型: {report.model_used || "N/A"}</span>
            <span>
              生成时间:{" "}
              {report.generated_at
                ? new Date(report.generated_at).toLocaleString("zh-CN")
                : "N/A"}
            </span>
          </div>
        </div>
      </CollapsibleSection>

      {/* ===== AlertList ===== */}
      {alerts.length > 0 && (
        <div>
          <div className="text-sm font-semibold mb-3 flex items-center gap-2">
            <span>⚠️</span>
            天气告警 ({alerts.length})
          </div>
          <WeatherAlertList alerts={alerts} />
        </div>
      )}

      {/* ===== PageFooter ===== */}
      {report.disclaimer && (
        <Card className="border border-border/30 bg-muted/10">
          <CardContent className="py-3 px-4">
            <p className="text-xs text-muted-foreground leading-relaxed">
              {report.disclaimer}
            </p>
            <p className="text-xs text-muted-foreground/60 mt-2">
              航空气象分析系统 v2.0 · ICAO Annex 3 标准
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
