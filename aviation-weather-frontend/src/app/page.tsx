"use client"

import * as React from "react"
import { Header } from "@/components/weather/Header"
import { AirportSelector } from "@/components/weather/AirportSelector"
import { RoleSelector } from "@/components/weather/RoleSelector"
import { AnalysisProgress } from "@/components/weather/AnalysisProgress"
import { RoleReportCard } from "@/components/weather/RoleReport"
import { MetricsDisplay } from "@/components/weather/MetricsDisplay"
import { WeatherSimulation } from "@/components/weather/WeatherSimulation"
import { analyzeV2, analyzeMetarWithRaw } from "@/services/api"
import type { WorkflowStep, UserRole, AnalyzeV2Response } from "@/types/api"
import ReportDiff from "@/components/weather/ReportDiff"
import { WORKFLOW_STEPS } from "@/types/api"
import { Card, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"

export default function HomePage() {
  // 工作流状态
  const [currentStep, setCurrentStep] = React.useState<WorkflowStep>('airport_selection')
  const [selectedAirport, setSelectedAirport] = React.useState<string>("")
  const [selectedRole, setSelectedRole] = React.useState<UserRole>("pilot")
  const [metarRaw, setMetarRaw] = React.useState<string>("")
  const [isAnalyzing, setIsAnalyzing] = React.useState(false)
  const [result, setResult] = React.useState<AnalyzeV2Response | null>(null)
  const [error, setError] = React.useState<string | null>(null)
  const [previousResult, setPreviousResult] = React.useState<AnalyzeV2Response | null>(null)
  const [showDiff, setShowDiff] = React.useState(false)

  // 动态指标 — 每次分析后更新
  const [metrics, setMetrics] = React.useState({
    total_requests: 0,
    success_requests: 0,
    avg_latency_ms: 0,
    last_analysis: undefined as {
      flight_rules: string
      risk_level: string
      llm_calls: number
      processing_time_ms: number
      model_used: string
      role: string
      timestamp: string
    } | undefined,
  })

  // 累计延迟追踪
  const latencySumRef = React.useRef(0)

  // 处理天气模拟分析
  const handleSimulationSelect = async (metar: string, role: UserRole) => {
    setIsAnalyzing(true)
    setError(null)
    
    // 保存当前结果作为历史对比
    if (result) {
      setPreviousResult(result)
    }
    
    setResult(null)
    setMetarRaw(metar)
    setShowDiff(false)

    try {
      // 步骤 1: 数据获取
      setCurrentStep('data_fetch')
      await new Promise(resolve => setTimeout(resolve, 500))

      // 步骤 2: 大模型分析
      setCurrentStep('analysis')
      const response = await analyzeMetarWithRaw(metar, role)
      setResult(response)

      // 更新动态指标
      const latency = response.processing_time_ms || 0
      latencySumRef.current += latency
      setMetrics(prev => {
        const newTotal = prev.total_requests + 1
        const newSuccess = prev.success_requests + (response.success ? 1 : 0)
        return {
          total_requests: newTotal,
          success_requests: newSuccess,
          avg_latency_ms: Math.round(latencySumRef.current / newTotal),
          last_analysis: response.success ? {
            flight_rules: response.metar_parsed?.flight_rules || "--",
            risk_level: response.risk_level || "--",
            llm_calls: response.llm_calls || 0,
            processing_time_ms: Math.round(latency),
            model_used: response.role_report?.model_used || "rule-engine",
            role: response.detected_role || role,
            timestamp: new Date().toLocaleTimeString('zh-CN'),
          } : prev.last_analysis,
        }
      })

      // 步骤 3: 报告分发
      setCurrentStep('report')
      await new Promise(resolve => setTimeout(resolve, 500))

    } catch (err) {
      setError(err instanceof Error ? err.message : "分析失败，请重试")
      setCurrentStep('airport_selection')
    } finally {
      setIsAnalyzing(false)
    }
  }

  // 步骤进度
  const currentStepIndex = WORKFLOW_STEPS.findIndex(s => s.id === currentStep)

  // 处理分析流程
  const handleStartAnalysis = async () => {
    if (!selectedAirport) return

    setIsAnalyzing(true)
    setError(null)
    
    // 保存当前结果作为历史对比
    if (result) {
      setPreviousResult(result)
    }
    
    setResult(null)
    setShowDiff(false)

    try {
      // 步骤 1: 机场选择已完成
      setCurrentStep('data_fetch')
      await new Promise(resolve => setTimeout(resolve, 1000))

      // 步骤 2: 数据获取
      setCurrentStep('analysis')
      await new Promise(resolve => setTimeout(resolve, 1000))

      // 步骤 3: 大模型分析
      const response = await analyzeV2(selectedAirport, selectedRole)
      setMetarRaw(response.metar_raw || "")
      setResult(response)

      // 更新动态指标
      const latency = response.processing_time_ms || 0
      latencySumRef.current += latency
      setMetrics(prev => {
        const newTotal = prev.total_requests + 1
        const newSuccess = prev.success_requests + (response.success ? 1 : 0)
        return {
          total_requests: newTotal,
          success_requests: newSuccess,
          avg_latency_ms: Math.round(latencySumRef.current / newTotal),
          last_analysis: response.success ? {
            flight_rules: response.metar_parsed?.flight_rules || "--",
            risk_level: response.risk_level || "--",
            llm_calls: response.llm_calls || 0,
            processing_time_ms: Math.round(latency),
            model_used: response.role_report?.model_used || "rule-engine",
            role: response.detected_role || selectedRole,
            timestamp: new Date().toLocaleTimeString('zh-CN'),
          } : prev.last_analysis,
        }
      })

      // 步骤 4: 报告分发
      setCurrentStep('report')
      await new Promise(resolve => setTimeout(resolve, 500))

    } catch (err) {
      setError(err instanceof Error ? err.message : "分析失败，请重试")
      setCurrentStep('airport_selection')
    } finally {
      setIsAnalyzing(false)
    }
  }

  // 重置流程
  const handleReset = () => {
    setCurrentStep('airport_selection')
    setSelectedAirport("")
    setSelectedRole("pilot")
    setMetarRaw("")
    setResult(null)
    setError(null)
    setIsAnalyzing(false)
    setShowDiff(false)
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-background via-background to-muted/20">
      <Header />

      <main className="container mx-auto px-4 py-8">
        {/* Hero Section */}
        <div className="text-center mb-8">
          <h2 className="text-3xl md:text-4xl font-bold mb-3 bg-gradient-to-r from-primary via-primary/80 to-primary/60 bg-clip-text text-transparent">
            智能航空气象分析
          </h2>
          <p className="text-muted-foreground max-w-2xl mx-auto">
            基于大语言模型的METAR报文解析系统，提供风险评估、安全检查和决策建议
          </p>
        </div>

        {/* Workflow Steps Indicator */}
        <div className="mb-8">
          <Card className="bg-card/50 backdrop-blur-sm border-border/50">
            <CardContent className="py-4 px-6">
              <div className="flex items-center justify-between">
                {WORKFLOW_STEPS.map((step, index) => {
                  const isCompleted = index < currentStepIndex
                  const isCurrent = index === currentStepIndex
                  const isPending = index > currentStepIndex

                  return (
                    <React.Fragment key={step.id}>
                      <div className="flex items-center gap-2 flex-1">
                        <div
                          className={cn(
                            "w-8 h-8 rounded-full flex items-center justify-center text-sm font-semibold transition-all",
                            isCompleted && "bg-green-500 text-white",
                            isCurrent && "bg-primary text-primary-foreground",
                            isPending && "bg-muted text-muted-foreground"
                          )}
                        >
                          {isCompleted ? "✓" : index + 1}
                        </div>
                        <div className="flex-1">
                          <div
                            className={cn(
                              "text-xs font-medium",
                              isCurrent && "text-primary",
                              isPending && "text-muted-foreground"
                            )}
                          >
                            {step.label}
                          </div>
                          <div className="text-xs text-muted-foreground">
                            {step.icon}
                          </div>
                        </div>
                      </div>

                      {index < WORKFLOW_STEPS.length - 1 && (
                        <div
                          className={cn(
                            "w-12 h-0.5 mx-2",
                            index < currentStepIndex ? "bg-green-500" : "bg-muted"
                          )}
                        />
                      )}
                    </React.Fragment>
                  )
                })}
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Metrics Display */}
        <div className="mb-8">
          <MetricsDisplay metrics={metrics} />
        </div>

        {/* Main Content */}
        <div className="grid lg:grid-cols-2 gap-6">
          {/* Left Column: Input & Progress */}
          <div className="space-y-6">
            {/* Step 1: Airport Selection */}
            {(currentStep === 'airport_selection' || currentStep === 'data_fetch') && (
              <Card className="bg-card/50 backdrop-blur-sm border-border/50 rounded-2xl p-6">
                <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
                  <span className="text-xl">✈️</span>
                  步骤 1: 机场选择
                  {selectedAirport && <Badge variant="secondary">已选择</Badge>}
                </h3>
                <AirportSelector
                  value={selectedAirport}
                  onChange={setSelectedAirport}
                  disabled={isAnalyzing}
                />
              </Card>
            )}

            {/* Step 1: Role Selection */}
            {currentStep === 'airport_selection' && (
              <Card className="bg-card/50 backdrop-blur-sm border-border/50 rounded-2xl p-6">
                <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
                  <span className="text-xl">👤</span>
                  分析角色选择
                </h3>
                <RoleSelector
                  value={selectedRole}
                  onChange={setSelectedRole}
                />
              </Card>
            )}

            {/* Weather Simulation */}
            {currentStep === 'airport_selection' && (
              <WeatherSimulation
                onSelectScenario={handleSimulationSelect}
                selectedRole={selectedRole}
                disabled={isAnalyzing}
              />
            )}

            {/* Start Analysis Button */}
            {currentStep === 'airport_selection' && selectedAirport && (
              <button
                onClick={handleStartAnalysis}
                disabled={isAnalyzing}
                className="w-full h-14 bg-primary text-primary-foreground font-semibold rounded-xl hover:bg-primary/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                开始分析
              </button>
            )}

            {/* Step 2: METAR Data Display */}
            {(currentStep === 'data_fetch' || currentStep === 'analysis') && metarRaw && (
              <Card className="bg-card/50 backdrop-blur-sm border-border/50 rounded-2xl p-6">
                <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
                  <span className="text-xl">📡</span>
                  步骤 2: METAR数据
                  <Badge variant="outline">实时获取</Badge>
                </h3>
                <div className="bg-muted/30 rounded-lg p-4">
                  <pre className="text-sm font-mono whitespace-pre-wrap">{metarRaw}</pre>
                </div>
              </Card>
            )}

            {/* Progress Indicator */}
            {isAnalyzing && (
              <AnalysisProgress currentStep={currentStep} />
            )}

            {/* Error Display */}
            {error && (
              <Card className="bg-destructive/10 border-destructive/30 rounded-xl p-4">
                <p className="text-sm text-destructive">{error}</p>
              </Card>
            )}
          </div>

          {/* Right Column: Results */}
          <div className="space-y-6">
            {currentStep === 'report' && result && result.success ? (
              <>
                {/* 对比按钮 */}
                {previousResult && (
                  <div className="flex justify-end">
                    <button
                      onClick={() => setShowDiff(!showDiff)}
                      className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                        showDiff 
                          ? 'bg-blue-500 text-white' 
                          : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                      }`}
                    >
                      {showDiff ? '隐藏对比' : '查看历史对比'}
                    </button>
                  </div>
                )}
                
                {/* 对比结果 */}
                {showDiff && previousResult && (
                  <ReportDiff 
                    previous_report={previousResult.metar_parsed || previousResult}
                    current_report={result.metar_parsed || result}
                    title="METAR数据对比"
                  />
                )}
                
                {/* 分析结果 */}
                {result.role_report ? (
                  <RoleReportCard report={result.role_report} />
                ) : (
                  /* 降级显示: 没有role_report时用基础数据 */
                  <RoleReportCard report={{
                    role: result.detected_role || 'pilot',
                    risk_level: result.risk_level || 'MEDIUM',
                    report_text: `天气分析完成\n\n机场: ${result.metar_raw?.substring(0, 40) || 'N/A'}\n风险等级: ${result.risk_level || 'N/A'}\n角色: ${result.detected_role || 'N/A'}`,
                    alerts: [],
                    generated_at: result.timestamp || new Date().toISOString(),
                  }} />
                )}
              </>
            ) : (
              <Card className="border-dashed border-2 border-muted/30 h-full min-h-[400px]">
                <CardContent className="flex flex-col items-center justify-center h-full text-center py-12">
                  <div className="text-5xl mb-4 opacity-20">🛫</div>
                  <p className="text-muted-foreground text-sm">
                    {isAnalyzing
                      ? "正在分析中..."
                      : "选择机场并点击开始分析，结果将在此显示"}
                  </p>
                </CardContent>
              </Card>
            )}
          </div>
        </div>

        {/* Reset Button */}
        {currentStep === 'report' && (
          <div className="mt-8 flex justify-center">
            <button
              onClick={handleReset}
              className="px-6 py-2 bg-muted text-muted-foreground rounded-lg hover:bg-muted/80 transition-colors"
            >
              重新开始
            </button>
          </div>
        )}

        {/* Footer */}
        <footer className="mt-12 pt-6 border-t border-border/50 text-center">
          <p className="text-xs text-muted-foreground">
            航空气象分析系统 v2.0 · 支持多模型切换 (DeepSeek / Qwen / GPT-4 / Claude)
          </p>
        </footer>
      </main>
    </div>
  )
}
