"use client"

import * as React from "react"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

interface METARInputProps {
  value: string
  onChange: (value: string) => void
  onAnalyze: () => void
  isLoading?: boolean
  disabled?: boolean
  placeholder?: string
  className?: string
}

// 预设示例报文
const EXAMPLE_METARS = [
  {
    label: "标准报文",
    value: "METAR ZBAA 111800Z 24008MPS 9999 SCT030 12/08 Q1018 NOSIG",
  },
  {
    label: "恶劣天气",
    value: "METAR ZSSS 111800Z 18015G28MPS 3000 TSRA SCT010 BKN020CB 15/14 Q1008 TEMPO TL1950 2000 TSRA",
  },
  {
    label: "低能见度",
    value: "METAR ZGGG 111800Z 00000KT 0800 FG VV002 18/17 Q1014 BECMG TL1900 2000 BR",
  },
]

export function METARInput({
  value,
  onChange,
  onAnalyze,
  isLoading = false,
  disabled = false,
  placeholder = "输入METAR报文或选择示例...",
  className,
}: METARInputProps) {
  const handleExampleSelect = (metar: string) => {
    onChange(metar)
  }

  return (
    <div className={cn("space-y-4", className)}>
      {/* 主输入区 */}
      <div className="relative">
        <textarea
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          rows={3}
          disabled={disabled}
          className="w-full rounded-xl border border-input bg-background/50 backdrop-blur-sm px-4 py-3 text-sm font-mono ring-offset-background placeholder:text-muted-foreground/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 transition-all duration-200 resize-none"
          spellCheck={false}
        />
        <div className="absolute bottom-3 right-3 flex items-center gap-2">
          <span className="text-xs text-muted-foreground/50 font-mono">
            {value.length} chars
          </span>
        </div>
      </div>

      {/* 快速示例选择器 */}
      <div className="flex flex-wrap gap-2 items-center">
        <span className="text-xs text-muted-foreground">快速示例:</span>
        {EXAMPLE_METARS.map((example) => (
          <Button
            key={example.label}
            variant="outline"
            size="sm"
            onClick={() => handleExampleSelect(example.value)}
            className="h-7 text-xs bg-muted/30 hover:bg-muted/50 border-muted/50"
          >
            {example.label}
          </Button>
        ))}
      </div>

      {/* 分析按钮 */}
      <Button
        onClick={onAnalyze}
        disabled={disabled || !value.trim() || isLoading}
        className="w-full h-12 text-base font-medium relative overflow-hidden group"
      >
        <span className={cn(
          "transition-opacity duration-200",
          isLoading ? "opacity-0" : "opacity-100"
        )}>
          分析气象报文
        </span>
        {isLoading && (
          <div className="absolute inset-0 flex items-center justify-center">
            <svg
              className="animate-spin h-5 w-5 text-primary-foreground"
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
            >
              <circle
                className="opacity-25"
                cx="12"
                cy="12"
                r="10"
                stroke="currentColor"
                strokeWidth="4"
              />
              <path
                className="opacity-75"
                fill="currentColor"
                d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
              />
            </svg>
          </div>
        )}
      </Button>
    </div>
  )
}
