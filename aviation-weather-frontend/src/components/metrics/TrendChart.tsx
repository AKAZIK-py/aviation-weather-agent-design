"use client"

import * as React from "react"
import type { DailyTrend } from "@/types/api"

interface TrendChartProps {
  data: DailyTrend[]
}

type MetricType = "task_completion" | "hallucination" | "avg_latency_ms"

const METRIC_LABELS: Record<MetricType, string> = {
  task_completion: "任务完成率",
  hallucination: "幻觉率",
  avg_latency_ms: "平均延迟(ms)",
}

const METRIC_COLORS: Record<MetricType, string> = {
  task_completion: "bg-blue-500",
  hallucination: "bg-red-500",
  avg_latency_ms: "bg-amber-500",
}

export function TrendChart({ data }: TrendChartProps) {
  const [activeMetric, setActiveMetric] = React.useState<MetricType>("task_completion")

  if (!data || data.length === 0) {
    return (
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">7天趋势</h3>
        <div className="flex items-center justify-center h-48 text-gray-400">
          暂无趋势数据
        </div>
      </div>
    )
  }

  // 按日期升序排列
  const sortedData = [...data].sort((a, b) => a.date.localeCompare(b.date))

  // 计算最大值用于归一化
  const values = sortedData.map((d) => {
    if (activeMetric === "task_completion") return d.task_completion
    if (activeMetric === "hallucination") return d.hallucination
    return d.avg_latency_ms
  })
  const maxValue = Math.max(...values, 0.01)

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-gray-900">7天趋势</h3>
        <div className="flex gap-2">
          {(Object.keys(METRIC_LABELS) as MetricType[]).map((metric) => (
            <button
              key={metric}
              onClick={() => setActiveMetric(metric)}
              className={`px-3 py-1 text-xs rounded-full transition-colors ${
                activeMetric === metric
                  ? "bg-blue-100 text-blue-700 font-medium"
                  : "bg-gray-100 text-gray-600 hover:bg-gray-200"
              }`}
            >
              {METRIC_LABELS[metric]}
            </button>
          ))}
        </div>
      </div>

      <div className="flex items-end gap-2 h-48">
        {sortedData.map((item) => {
          const value =
            activeMetric === "task_completion"
              ? item.task_completion
              : activeMetric === "hallucination"
              ? item.hallucination
              : item.avg_latency_ms

          // 归一化高度 (最小 4px)
          const heightPercent = maxValue > 0 ? (value / maxValue) * 100 : 0
          const barHeight = Math.max(heightPercent, 2)

          // 格式化显示值
          const displayValue =
            activeMetric === "avg_latency_ms"
              ? `${Math.round(value)}ms`
              : `${(value * 100).toFixed(1)}%`

          // 格式化日期为 MM-DD
          const dateLabel = item.date.slice(5)

          return (
            <div
              key={item.date}
              className="flex-1 flex flex-col items-center group"
            >
              {/* 悬浮提示 */}
              <div className="mb-1 opacity-0 group-hover:opacity-100 transition-opacity">
                <span className="text-xs font-medium text-gray-900 bg-gray-100 px-2 py-0.5 rounded">
                  {displayValue}
                </span>
              </div>

              {/* 柱子 */}
              <div className="w-full flex justify-center">
                <div
                  className={`w-full max-w-[40px] rounded-t-md transition-all duration-300 ${METRIC_COLORS[activeMetric]}`}
                  style={{ height: `${barHeight}%` }}
                />
              </div>

              {/* 日期标签 */}
              <span className="mt-2 text-xs text-gray-500">{dateLabel}</span>
            </div>
          )
        })}
      </div>
    </div>
  )
}
