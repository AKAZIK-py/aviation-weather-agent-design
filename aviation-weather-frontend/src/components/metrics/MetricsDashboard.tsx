"use client"

import * as React from "react"
import type { SystemMetrics } from "@/types/api"
import { getSystemMetrics } from "@/services/api"
import { KpiCard } from "./KpiCard"
import { TrendChart } from "./TrendChart"
import { BadcaseTable } from "./BadcaseTable"
import { RefreshCw, AlertCircle } from "lucide-react"

export function MetricsDashboard() {
  const [metrics, setMetrics] = React.useState<SystemMetrics | null>(null)
  const [loading, setLoading] = React.useState(true)
  const [error, setError] = React.useState<string | null>(null)

  const fetchMetrics = React.useCallback(async () => {
    try {
      setLoading(true)
      const data = await getSystemMetrics(7)
      setMetrics(data)
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载失败")
    } finally {
      setLoading(false)
    }
  }, [])

  React.useEffect(() => {
    fetchMetrics()
  }, [fetchMetrics])

  if (loading && !metrics) {
    return (
      <div className="flex items-center justify-center h-full text-gray-400">
        加载中...
      </div>
    )
  }

  if (error && !metrics) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-4">
        <AlertCircle className="w-12 h-12 text-red-400" />
        <p className="text-red-500">{error}</p>
        <button
          onClick={fetchMetrics}
          className="px-4 py-2 text-sm bg-blue-500 text-white rounded-lg hover:bg-blue-600"
        >
          重试
        </button>
      </div>
    )
  }

  const data = metrics!

  // 转换百分比值用于 KPI 卡片
  const taskCompletionPercent = Math.round(data.task_completion_rate * 100)
  const outputUsabilityPercent = Math.round(data.output_usability_rate * 100)
  const successRatePercent = Math.round(data.success_rate * 100)
  const badcaseCount = data.badcase_count

  return (
    <div className="p-6 space-y-6">
      {/* 顶部操作栏 */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-gray-900">系统指标</h2>
          <p className="text-sm text-gray-500 mt-1">
            最近 7 天 · 共 {data.total_requests} 次请求
          </p>
        </div>
        <button
          onClick={fetchMetrics}
          className="flex items-center gap-2 px-3 py-2 text-sm bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition-colors"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
          刷新
        </button>
      </div>

      {/* KPI 卡片 */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <KpiCard
          label="任务完成率"
          value={taskCompletionPercent}
          maxValue={100}
          unit="%"
        />
        <KpiCard
          label="关键信息命中"
          value={Math.round(data.key_info_avg_hits * 100)}
          maxValue={100}
          unit="%"
        />
        <KpiCard
          label="输出可用率"
          value={outputUsabilityPercent}
          maxValue={100}
          unit="%"
        />
        <KpiCard
          label="Badcase 数"
          value={badcaseCount}
          maxValue={Math.max(badcaseCount, 10)}
          unit=""
        />
      </div>

      {/* Token 消耗 */}
      <div className="bg-white rounded-xl border border-gray-200 p-4">
        <div className="flex items-center gap-2 mb-3">
          <span className="text-sm font-semibold text-gray-700">🪙 Token 消耗</span>
        </div>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <div>
            <div className="text-xs text-gray-500">总 Token</div>
            <div className="text-xl font-bold text-gray-900">{(data.total_tokens || 0).toLocaleString()}</div>
          </div>
          <div>
            <div className="text-xs text-gray-500">输入 Token</div>
            <div className="text-xl font-bold text-blue-600">{(data.total_prompt_tokens || 0).toLocaleString()}</div>
          </div>
          <div>
            <div className="text-xs text-gray-500">输出 Token</div>
            <div className="text-xl font-bold text-green-600">{(data.total_completion_tokens || 0).toLocaleString()}</div>
          </div>
          <div>
            <div className="text-xs text-gray-500">每次请求平均</div>
            <div className="text-xl font-bold text-gray-700">{(data.avg_tokens_per_request || 0).toLocaleString()}</div>
          </div>
        </div>
        {/* Provider 分布 */}
        {data.provider_distribution && Object.keys(data.provider_distribution).length > 0 && (
          <div className="mt-3 pt-3 border-t border-gray-100">
            <div className="text-xs text-gray-500 mb-1">Provider 分布</div>
            <div className="flex flex-wrap gap-2">
              {Object.entries(data.provider_distribution).map(([provider, count]) => (
                <span key={provider} className="inline-flex px-2 py-0.5 rounded-full text-xs bg-purple-100 text-purple-700">
                  {provider}: {count}次
                </span>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* 其他指标 */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <div className="text-sm text-gray-500">成功请求率</div>
          <div className="text-2xl font-bold text-gray-900 mt-1">
            {successRatePercent}%
          </div>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <div className="text-sm text-gray-500">平均延迟</div>
          <div className="text-2xl font-bold text-gray-900 mt-1">
            {Math.round(data.avg_latency_ms)}ms
          </div>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <div className="text-sm text-gray-500">幻觉率</div>
          <div className="text-2xl font-bold text-gray-900 mt-1">
            {(data.hallucination_rate * 100).toFixed(1)}%
          </div>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <div className="text-sm text-gray-500">角色分布</div>
          <div className="mt-1 flex flex-wrap gap-1">
            {Object.entries(data.role_distribution).map(([role, count]) => (
              <span
                key={role}
                className="inline-flex px-2 py-0.5 rounded-full text-xs bg-blue-100 text-blue-700"
              >
                {role}: {count}
              </span>
            ))}
            {Object.keys(data.role_distribution).length === 0 && (
              <span className="text-gray-400 text-sm">暂无数据</span>
            )}
          </div>
        </div>
      </div>

      {/* 趋势图 */}
      <TrendChart data={data.daily_trend} />

      {/* Badcase 表格 */}
      <BadcaseTable limit={20} />
    </div>
  )
}
