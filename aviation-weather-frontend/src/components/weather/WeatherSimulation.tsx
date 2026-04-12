"use client"

import * as React from "react"
import { Card, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"
import type { RiskLevel, UserRole } from "@/types/api"

// 天气场景定义
export interface WeatherScenario {
  id: string
  name: string
  icon: string
  riskLevel: RiskLevel
  description: string
  metar: string
}

// 预设天气场景
export const WEATHER_SCENARIOS: WeatherScenario[] = [
  {
    id: "vfr",
    name: "正常天气",
    icon: "☀️",
    riskLevel: "LOW",
    description: "目视飞行条件良好，能见度佳，云层较高",
    metar: "METAR ZSPD 120300Z 18008KT 9999 SCT040 25/18 Q1012",
  },
  {
    id: "cold-wave",
    name: "寒潮降温",
    icon: "🥶",
    riskLevel: "HIGH",
    description: "强冷空气南下，气温骤降，可能伴有积冰",
    metar: "METAR ZSNJ 120300Z 35020G32KT 9999 SCT025 M08/M12 Q1035",
  },
  {
    id: "ifr",
    name: "低能见度",
    icon: "🌫️",
    riskLevel: "MEDIUM",
    description: "大雾导致能见度降低，需仪表飞行",
    metar: "METAR ZSPD 120300Z 00000KT 0800 FG BKN002 15/14 Q1020",
  },
  {
    id: "thunderstorm",
    name: "雷暴大风",
    icon: "⛈️",
    riskLevel: "CRITICAL",
    description: "雷暴伴随强阵风，严重影响飞行安全",
    metar: "METAR ZSPD 120300Z 27025G40KT 3000 +TSRA BKN010CB 28/24 Q0998",
  },
  {
    id: "freezing-fog",
    name: "冻雾结冰",
    icon: "❄️",
    riskLevel: "HIGH",
    description: "冻雾导致飞机积冰风险，影响操作性能",
    metar: "METAR ZSPD 120300Z 05010KT 0400 FZFG OVC003 M02/M04 Q1025",
  },
  {
    id: "heavy-snow",
    name: "大雪天气",
    icon: "🌨️",
    riskLevel: "HIGH",
    description: "强降雪降低能见度，跑道可能积雪",
    metar: "METAR ZSSS 120300Z 36015G25KT 1000 +SN BKN008 OVC015 M05/M07 Q1018",
  },
  {
    id: "crosswind",
    name: "强侧风",
    icon: "💨",
    riskLevel: "MEDIUM",
    description: "强侧风影响起降安全，需评估侧风标准",
    metar: "METAR ZSHC 120300Z 28022G35KT 9999 SCT030 30/20 Q1005",
  },
  {
    id: "typhoon-approach",
    name: "台风外围",
    icon: "🌀",
    riskLevel: "CRITICAL",
    description: "台风外围环流影响，强风暴雨，风切变严重",
    metar: "METAR ZSAM 120300Z 12040G55KT 1500 +RA BKN008 OVC015 26/24 Q0985",
  },
  {
    id: "sandstorm",
    name: "沙尘暴",
    icon: "🌪️",
    riskLevel: "CRITICAL",
    description: "强沙尘暴严重影响能见度和发动机安全",
    metar: "METAR ZWWW 120300Z 24030G45KT 0500 SS OVC020 35/10 Q0995",
  },
  {
    id: "freezing-rain",
    name: "冻雨积冰",
    icon: "🧊",
    riskLevel: "CRITICAL",
    description: "冻雨导致严重积冰，对飞行安全构成最大威胁",
    metar: "METAR ZYTX 120300Z 02012KT 2000 FZRA OVC005 M03/M05 Q1022",
  },
]

// 风险等级对应的边框颜色
const RISK_BORDER_COLORS: Record<RiskLevel, string> = {
  LOW: "border-l-green-500 hover:border-green-400",
  MEDIUM: "border-l-amber-500 hover:border-amber-400",
  HIGH: "border-l-orange-500 hover:border-orange-400",
  CRITICAL: "border-l-red-500 hover:border-red-400",
}

// 风险等级对应的背景色
const RISK_BG_COLORS: Record<RiskLevel, string> = {
  LOW: "bg-green-500/5",
  MEDIUM: "bg-amber-500/5",
  HIGH: "bg-orange-500/5",
  CRITICAL: "bg-red-500/5",
}

// 风险等级中文
const RISK_LABELS: Record<RiskLevel, string> = {
  LOW: "低风险",
  MEDIUM: "中风险",
  HIGH: "高风险",
  CRITICAL: "极高风险",
}

interface WeatherSimulationProps {
  onSelectScenario: (metar: string, role: UserRole) => void
  selectedRole: UserRole
  disabled?: boolean
}

export function WeatherSimulation({
  onSelectScenario,
  selectedRole,
  disabled = false,
}: WeatherSimulationProps) {
  const [customMetar, setCustomMetar] = React.useState("")
  const [activeScenario, setActiveScenario] = React.useState<string | null>(null)

  const handleScenarioClick = (scenario: WeatherScenario) => {
    if (disabled) return
    setActiveScenario(scenario.id)
    onSelectScenario(scenario.metar, selectedRole)
  }

  const handleCustomSubmit = () => {
    if (disabled || !customMetar.trim()) return
    setActiveScenario("custom")
    onSelectScenario(customMetar.trim(), selectedRole)
  }

  return (
    <Card className="bg-card/50 backdrop-blur-sm border-border/50 rounded-2xl">
      <div className="p-6">
        <h3 className="text-lg font-semibold mb-1 flex items-center gap-2">
          <span className="text-xl">🎮</span>
          天气模拟器
        </h3>
        <p className="text-sm text-muted-foreground mb-4">
          选择预设天气场景或输入自定义METAR进行模拟分析
        </p>

        {/* 预设场景网格 */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-4">
          {WEATHER_SCENARIOS.map((scenario) => (
            <button
              key={scenario.id}
              onClick={() => handleScenarioClick(scenario)}
              disabled={disabled}
              className={cn(
                "text-left p-3 rounded-xl border-l-4 border border-border/50 transition-all",
                RISK_BORDER_COLORS[scenario.riskLevel],
                RISK_BG_COLORS[scenario.riskLevel],
                disabled && "opacity-50 cursor-not-allowed",
                activeScenario === scenario.id && "ring-2 ring-primary/50"
              )}
            >
              <div className="flex items-start justify-between mb-1">
                <div className="flex items-center gap-2">
                  <span className="text-xl">{scenario.icon}</span>
                  <span className="font-medium text-sm">{scenario.name}</span>
                </div>
                <Badge
                  variant={
                    scenario.riskLevel === "LOW"
                      ? "low"
                      : scenario.riskLevel === "MEDIUM"
                      ? "medium"
                      : "high"
                  }
                  className="text-xs"
                >
                  {RISK_LABELS[scenario.riskLevel]}
                </Badge>
              </div>
              <p className="text-xs text-muted-foreground leading-relaxed">
                {scenario.description}
              </p>
            </button>
          ))}
        </div>

        {/* 自定义METAR输入 */}
        <div className="border-t border-border/50 pt-4">
          <label className="text-sm font-medium mb-2 block">
            自定义METAR报文
          </label>
          <div className="flex gap-2">
            <input
              type="text"
              value={customMetar}
              onChange={(e) => setCustomMetar(e.target.value)}
              placeholder="输入METAR报文，如: METAR ZSPD 120300Z..."
              disabled={disabled}
              className="flex-1 px-3 py-2 text-sm bg-muted/30 border border-border/50 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary/50 disabled:opacity-50"
            />
            <button
              onClick={handleCustomSubmit}
              disabled={disabled || !customMetar.trim()}
              className="px-4 py-2 bg-primary text-primary-foreground text-sm font-medium rounded-lg hover:bg-primary/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              分析
            </button>
          </div>
          <p className="text-xs text-muted-foreground mt-2">
            输入任意有效的METAR报文进行模拟分析
          </p>
        </div>
      </div>
    </Card>
  )
}
