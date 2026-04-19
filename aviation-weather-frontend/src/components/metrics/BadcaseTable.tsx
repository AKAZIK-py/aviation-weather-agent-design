"use client"

import * as React from "react"
import type { Badcase } from "@/types/api"
import { getBadcases } from "@/services/api"

interface BadcaseTableProps {
  limit?: number
}

export function BadcaseTable({ limit = 20 }: BadcaseTableProps) {
  const [badcases, setBadcases] = React.useState<Badcase[]>([])
  const [loading, setLoading] = React.useState(true)
  const [error, setError] = React.useState<string | null>(null)

  React.useEffect(() => {
    const fetchBadcases = async () => {
      try {
        setLoading(true)
        const data = await getBadcases(limit)
        setBadcases(data)
        setError(null)
      } catch (err) {
        setError(err instanceof Error ? err.message : "加载失败")
      } finally {
        setLoading(false)
      }
    }
    fetchBadcases()
  }, [limit])

  if (loading) {
    return (
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Badcase 列表</h3>
        <div className="flex items-center justify-center h-32 text-gray-400">
          加载中...
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Badcase 列表</h3>
        <div className="flex items-center justify-center h-32 text-red-400">
          {error}
        </div>
      </div>
    )
  }

  if (badcases.length === 0) {
    return (
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Badcase 列表</h3>
        <div className="flex items-center justify-center h-32 text-gray-400">
          暂无 badcase
        </div>
      </div>
    )
  }

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-6">
      <h3 className="text-lg font-semibold text-gray-900 mb-4">Badcase 列表</h3>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-200">
              <th className="text-left py-3 px-4 font-medium text-gray-600">ID</th>
              <th className="text-left py-3 px-4 font-medium text-gray-600">查询</th>
              <th className="text-left py-3 px-4 font-medium text-gray-600">角色</th>
              <th className="text-left py-3 px-4 font-medium text-gray-600">失败分类</th>
              <th className="text-left py-3 px-4 font-medium text-gray-600">状态</th>
              <th className="text-left py-3 px-4 font-medium text-gray-600">时间</th>
            </tr>
          </thead>
          <tbody>
            {badcases.map((badcase) => (
              <tr key={badcase.case_id} className="border-b border-gray-100 hover:bg-gray-50">
                <td className="py-3 px-4 font-mono text-xs text-gray-500">
                  {badcase.case_id}
                </td>
                <td className="py-3 px-4 text-gray-900 max-w-[200px] truncate">
                  {badcase.query || "-"}
                </td>
                <td className="py-3 px-4 text-gray-600">
                  {badcase.role || "-"}
                </td>
                <td className="py-3 px-4">
                  <span className={`inline-flex px-2 py-0.5 rounded-full text-xs font-medium ${
                    badcase.failure_category === "hallucination"
                      ? "bg-red-100 text-red-700"
                      : "bg-amber-100 text-amber-700"
                  }`}>
                    {badcase.failure_category}
                  </span>
                </td>
                <td className="py-3 px-4">
                  <span className={`inline-flex px-2 py-0.5 rounded-full text-xs font-medium ${
                    badcase.status === "已修复"
                      ? "bg-green-100 text-green-700"
                      : "bg-gray-100 text-gray-700"
                  }`}>
                    {badcase.status}
                  </span>
                </td>
                <td className="py-3 px-4 text-gray-500 text-xs">
                  {badcase.timestamp ? badcase.timestamp.slice(0, 10) : "-"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
