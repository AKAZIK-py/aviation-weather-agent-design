"use client"

import * as React from "react"
import { Card, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import type { WeatherAlert, AlertSeverity } from "@/types/api"
import { cn } from "@/lib/utils"

interface WeatherAlertCardProps {
  alert: WeatherAlert
  className?: string
}

// 严重程度配置
const SEVERITY_CONFIG: Record<AlertSeverity, {
  label: string;
  icon: string;
  bgClass: string;
  borderClass: string;
  textClass: string;
  badgeClass: string;
}> = {
  CRITICAL: {
    label: "严重",
    icon: "🚨",
    bgClass: "bg-red-950/30",
    borderClass: "border-red-500/50",
    textClass: "text-red-100",
    badgeClass: "bg-red-500 text-white",
  },
  HIGH: {
    label: "高",
    icon: "⚠️",
    bgClass: "bg-orange-950/30",
    borderClass: "border-orange-500/50",
    textClass: "text-orange-100",
    badgeClass: "bg-orange-500 text-white",
  },
  MEDIUM: {
    label: "中",
    icon: "⚡",
    bgClass: "bg-yellow-950/30",
    borderClass: "border-yellow-500/50",
    textClass: "text-yellow-100",
    badgeClass: "bg-yellow-500 text-white",
  },
  LOW: {
    label: "低",
    icon: "ℹ️",
    bgClass: "bg-blue-950/30",
    borderClass: "border-blue-500/50",
    textClass: "text-blue-100",
    badgeClass: "bg-blue-500 text-white",
  },
}

export function WeatherAlertCard({ alert, className }: WeatherAlertCardProps) {
  const config = SEVERITY_CONFIG[alert.severity]

  return (
    <Card
      className={cn(
        "overflow-hidden border-2 transition-all duration-300 hover:shadow-lg",
        config.bgClass,
        config.borderClass,
        alert.severity === 'CRITICAL' && "animate-pulse",
        className
      )}
    >
      <CardContent className="p-4">
        {/* 标题和严重程度 */}
        <div className="flex items-start justify-between gap-3 mb-3">
          <div className="flex items-center gap-2 flex-1">
            <span className="text-2xl">{config.icon}</span>
            <h4 className={cn("font-semibold", config.textClass)}>
              {alert.title}
            </h4>
          </div>
          <Badge className={cn("font-semibold", config.badgeClass)}>
            {config.label}
          </Badge>
        </div>

        {/* 描述 */}
        <p className={cn("text-sm mb-3 leading-relaxed", config.textClass, "opacity-90")}>
          {alert.description}
        </p>

        {/* 建议行动 */}
        {alert.recommended_action && (
          <div className={cn(
            "mt-3 pt-3 border-t border-current/20",
            config.textClass
          )}>
            <div className="flex items-start gap-2">
              <span className="text-sm font-semibold opacity-80">建议行动:</span>
              <p className="text-sm opacity-90">{alert.recommended_action}</p>
            </div>
          </div>
        )}

        {/* 时间戳 */}
        <div className="mt-3 flex items-center justify-end">
          <span className="text-xs opacity-60">
            {new Date(alert.timestamp).toLocaleTimeString('zh-CN')}
          </span>
        </div>
      </CardContent>
    </Card>
  )
}

// 告警列表组件
interface WeatherAlertListProps {
  alerts: WeatherAlert[]
  className?: string
}

export function WeatherAlertList({ alerts, className }: WeatherAlertListProps) {
  // 按严重程度排序
  const sortedAlerts = React.useMemo(() => {
    const severityOrder: AlertSeverity[] = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW']
    return [...alerts].sort((a, b) => {
      return severityOrder.indexOf(a.severity) - severityOrder.indexOf(b.severity)
    })
  }, [alerts])

  if (alerts.length === 0) {
    return (
      <Card className={cn("border-dashed border-2", className)}>
        <CardContent className="flex flex-col items-center justify-center py-8 text-center">
          <span className="text-4xl mb-2">✅</span>
          <p className="text-sm text-muted-foreground">当前无告警</p>
        </CardContent>
      </Card>
    )
  }

  return (
    <div className={cn("space-y-3", className)}>
      {/* 统计信息 */}
      <div className="flex items-center justify-between px-2">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold">天气告警</span>
          <Badge variant="secondary">{alerts.length}</Badge>
        </div>
        <div className="flex gap-1">
          {sortedAlerts.filter(a => a.severity === 'CRITICAL').length > 0 && (
            <Badge className="bg-red-500 text-white">
              严重 {sortedAlerts.filter(a => a.severity === 'CRITICAL').length}
            </Badge>
          )}
          {sortedAlerts.filter(a => a.severity === 'HIGH').length > 0 && (
            <Badge className="bg-orange-500 text-white">
              高 {sortedAlerts.filter(a => a.severity === 'HIGH').length}
            </Badge>
          )}
        </div>
      </div>

      {/* 告警列表 */}
      <div className="space-y-3">
        {sortedAlerts.map((alert) => (
          <WeatherAlertCard key={alert.id} alert={alert} />
        ))}
      </div>
    </div>
  )
}
