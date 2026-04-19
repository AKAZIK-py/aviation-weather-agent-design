"use client"

import * as React from "react"

interface KpiCardProps {
  label: string
  value: number
  maxValue: number
  unit?: "%" | "ms" | string
  color?: string
}

export function KpiCard({ label, value, maxValue, unit = "%", color }: KpiCardProps) {
  // 计算百分比
  const percentage = maxValue > 0 ? Math.min((value / maxValue) * 100, 100) : 0

  // 根据百分比确定颜色
  const getColor = () => {
    if (color) return color
    if (percentage >= 90) return "#22c55e" // green
    if (percentage >= 70) return "#eab308" // yellow
    return "#ef4444" // red
  }

  const ringColor = getColor()

  // SVG 环形参数
  const size = 120
  const strokeWidth = 10
  const radius = (size - strokeWidth) / 2
  const circumference = 2 * Math.PI * radius
  const strokeDashoffset = circumference - (percentage / 100) * circumference

  // 显示值
  const displayValue = unit === "%" ? `${Math.round(percentage)}%` : `${value}${unit}`

  return (
    <div className="flex flex-col items-center justify-center p-4 bg-white rounded-xl border border-gray-200 shadow-sm">
      <div className="relative" style={{ width: size, height: size }}>
        <svg
          width={size}
          height={size}
          className="transform -rotate-90"
        >
          {/* 背景圆环 */}
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke="#e5e7eb"
            strokeWidth={strokeWidth}
          />
          {/* 进度圆环 */}
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke={ringColor}
            strokeWidth={strokeWidth}
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={strokeDashoffset}
            className="transition-all duration-500 ease-out"
          />
        </svg>
        {/* 中心数字 */}
        <div className="absolute inset-0 flex items-center justify-center">
          <span className="text-2xl font-bold text-gray-900">
            {displayValue}
          </span>
        </div>
      </div>
      {/* 底部标签 */}
      <span className="mt-2 text-sm font-medium text-gray-600">{label}</span>
    </div>
  )
}
