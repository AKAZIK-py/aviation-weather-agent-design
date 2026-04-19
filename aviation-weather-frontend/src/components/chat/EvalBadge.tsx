"use client"

import type { EvalScores } from "@/types/api"
import { Badge } from "@/components/ui/badge"

interface EvalBadgeProps {
  scores: EvalScores
}

function statusColor(passed: boolean): string {
  return passed ? "bg-green-100 text-green-800 border-green-200" : "bg-red-100 text-red-800 border-red-200"
}

function hallucinationColor(rate: number): string {
  if (rate <= 0.05) return "bg-green-100 text-green-800 border-green-200"
  if (rate <= 0.2) return "bg-yellow-100 text-yellow-800 border-yellow-200"
  return "bg-red-100 text-red-800 border-red-200"
}

export function EvalBadge({ scores }: EvalBadgeProps) {
  return (
    <div className="flex flex-wrap gap-1.5 mt-2">
      <Badge variant="outline" className={`text-xs ${statusColor(scores.task_complete)}`}>
        {scores.task_complete ? "✓ 任务完成" : "✗ 未完成"}
      </Badge>
      <Badge variant="outline" className={`text-xs ${statusColor(scores.output_usable)}`}>
        {scores.output_usable ? "✓ 输出可用" : "✗ 输出异常"}
      </Badge>
      <Badge variant="outline" className="text-xs bg-blue-50 text-blue-800 border-blue-200">
        关键信息 {scores.key_info_hit}
      </Badge>
      <Badge variant="outline" className={`text-xs ${hallucinationColor(scores.hallucination_rate)}`}>
        幻觉率 {(scores.hallucination_rate * 100).toFixed(0)}%
      </Badge>
    </div>
  )
}
