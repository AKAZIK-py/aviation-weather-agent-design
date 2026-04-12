"use client"

import * as React from "react"
import { Card, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { WORKFLOW_STEPS, type WorkflowStep, type AnalysisProgress as AnalysisProgressType } from "@/types/api"
import { cn } from "@/lib/utils"

interface AnalysisProgressProps {
  currentStep: WorkflowStep
  progress?: AnalysisProgressType
  className?: string
}

// 步骤状态消息映射
const STEP_MESSAGES: Record<WorkflowStep, string> = {
  airport_selection: "正在选择机场...",
  data_fetch: "正在获取METAR数据...",
  analysis: "正在进行大模型分析...",
  report: "正在生成报告...",
}

// 步骤预估时间（秒）
const STEP_ESTIMATED_TIMES: Record<WorkflowStep, number> = {
  airport_selection: 1,
  data_fetch: 3,
  analysis: 5,
  report: 2,
}

export function AnalysisProgress({ currentStep, progress, className }: AnalysisProgressProps) {
  const currentStepIndex = WORKFLOW_STEPS.findIndex(s => s.id === currentStep)

  return (
    <Card className={cn("overflow-hidden", className)}>
      <CardContent className="p-6">
        {/* 步骤指示器 */}
        <div className="flex items-center justify-between mb-6">
          {WORKFLOW_STEPS.map((step, index) => {
            const isCompleted = index < currentStepIndex
            const isCurrent = index === currentStepIndex
            const isPending = index > currentStepIndex

            return (
              <React.Fragment key={step.id}>
                {/* 步骤圆圈 */}
                <div className="flex flex-col items-center gap-2 flex-1">
                  <div
                    className={cn(
                      "w-12 h-12 rounded-full flex items-center justify-center text-lg font-semibold transition-all duration-300",
                      isCompleted && "bg-green-500 text-white",
                      isCurrent && "bg-primary text-primary-foreground ring-4 ring-primary/20 animate-pulse",
                      isPending && "bg-muted text-muted-foreground"
                    )}
                  >
                    {isCompleted ? "✓" : step.icon}
                  </div>
                  <div className="text-center">
                    <div
                      className={cn(
                        "text-xs font-medium transition-colors",
                        isCurrent && "text-primary",
                        isPending && "text-muted-foreground"
                      )}
                    >
                      {step.label}
                    </div>
                    {isCurrent && (
                      <div className="text-xs text-muted-foreground mt-1">
                        预计 {STEP_ESTIMATED_TIMES[step.id]}秒
                      </div>
                    )}
                  </div>
                </div>

                {/* 连接线 */}
                {index < WORKFLOW_STEPS.length - 1 && (
                  <div
                    className={cn(
                      "flex-1 h-1 mx-2 rounded-full transition-all duration-500",
                      index < currentStepIndex ? "bg-green-500" : "bg-muted"
                    )}
                  />
                )}
              </React.Fragment>
            )
          })}
        </div>

        {/* 进度条 */}
        <div className="space-y-2">
          <div className="flex items-center justify-between text-sm">
            <span className="font-medium text-primary">
              {progress?.status_message || STEP_MESSAGES[currentStep]}
            </span>
            {progress?.step_progress && (
              <Badge variant="outline" className="font-mono">
                {progress.step_progress}%
              </Badge>
            )}
          </div>

          <div className="h-2 bg-muted rounded-full overflow-hidden">
            <div
              className="h-full bg-gradient-to-r from-primary to-primary/60 transition-all duration-300"
              style={{ width: progress?.step_progress ? `${progress.step_progress}%` : '30%' }}
            />
          </div>

          {/* 预估剩余时间 */}
          {progress?.estimated_time_remaining && (
            <div className="text-xs text-muted-foreground text-right">
              预计剩余时间: {progress.estimated_time_remaining}秒
            </div>
          )}
        </div>

        {/* 动画提示 */}
        <div className="mt-4 flex items-center justify-center gap-2 text-xs text-muted-foreground">
          <div className="flex gap-1">
            <div className="w-2 h-2 bg-primary rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
            <div className="w-2 h-2 bg-primary rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
            <div className="w-2 h-2 bg-primary rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
          </div>
          <span>处理中，请稍候...</span>
        </div>
      </CardContent>
    </Card>
  )
}
