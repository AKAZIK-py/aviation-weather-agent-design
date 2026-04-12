'use client';

import * as React from 'react';
import { useMemo } from 'react';

interface ReportDiffProps {
  previous_report: any;
  current_report: any;
  title?: string;
}

interface DiffItem {
  field: string;
  previous: any;
  current: any;
  changed: boolean;
  riskChange?: 'up' | 'down' | 'same';
}

export default function ReportDiff({ 
  previous_report, 
  current_report, 
  title = "报告对比" 
}: ReportDiffProps) {
  
  const diffItems = useMemo(() => {
    if (!previous_report || !current_report) return [];
    
    const items: DiffItem[] = [];
    const allKeys = new Set([
      ...Object.keys(previous_report),
      ...Object.keys(current_report)
    ]);
    
    allKeys.forEach(key => {
      const prev = previous_report[key];
      const curr = current_report[key];
      const changed = JSON.stringify(prev) !== JSON.stringify(curr);
      
      let riskChange: 'up' | 'down' | 'same' = 'same';
      
      // 检查风险等级变化
      if (key === 'risk_level' && changed) {
        const riskOrder = ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'];
        const prevIndex = riskOrder.indexOf(prev);
        const currIndex = riskOrder.indexOf(curr);
        
        if (currIndex > prevIndex) {
          riskChange = 'up';
        } else if (currIndex < prevIndex) {
          riskChange = 'down';
        }
      }
      
      items.push({
        field: key,
        previous: prev,
        current: curr,
        changed,
        riskChange
      });
    });
    
    return items;
  }, [previous_report, current_report]);
  
  const changedCount = diffItems.filter(item => item.changed).length;
  
  if (!previous_report || !current_report) {
    return (
      <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
        <p className="text-gray-500 text-sm">没有可用的对比数据</p>
      </div>
    );
  }
  
  const formatValue = (value: any): string => {
    if (value === null || value === undefined) return 'N/A';
    if (typeof value === 'object') return JSON.stringify(value, null, 2);
    return String(value);
  };
  
  const getRiskColor = (riskChange?: 'up' | 'down' | 'same'): string => {
    switch (riskChange) {
      case 'up': return 'bg-red-100 border-red-300';
      case 'down': return 'bg-green-100 border-green-300';
      default: return '';
    }
  };
  
  const getFieldLabel = (field: string): string => {
    const labels: Record<string, string> = {
      'icao_code': 'ICAO代码',
      'observation_time': '观测时间',
      'wind_direction': '风向',
      'wind_speed': '风速',
      'wind_gust': '阵风',
      'visibility': '能见度',
      'clouds': '云层',
      'temperature': '温度',
      'dewpoint': '露点',
      'qnh': '气压',
      'flight_rules': '飞行规则',
      'risk_level': '风险等级',
      'risk_factors': '风险因素',
      'explanation': '分析说明'
    };
    return labels[field] || field;
  };
  
  return (
    <div className="bg-white border border-gray-200 rounded-lg shadow-sm">
      <div className="px-4 py-3 border-b border-gray-200 bg-gray-50 rounded-t-lg">
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-semibold text-gray-800">{title}</h3>
          <span className="text-sm text-gray-500">
            {changedCount} 项变化
          </span>
        </div>
      </div>
      
      <div className="divide-y divide-gray-100">
        {diffItems.map((item, index) => (
          <div 
            key={index}
            className={`px-4 py-3 ${item.changed ? getRiskColor(item.riskChange) : ''}`}
          >
            <div className="flex items-start justify-between">
              <div className="flex-1">
                <div className="text-sm font-medium text-gray-700 mb-1">
                  {getFieldLabel(item.field)}
                </div>
                
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <div className="text-xs text-gray-500 mb-1">之前</div>
                    <div className={`text-sm p-2 rounded ${
                      item.changed ? 'bg-red-50 line-through text-red-600' : 'bg-gray-50 text-gray-700'
                    }`}>
                      <pre className="whitespace-pre-wrap font-mono text-xs">
                        {formatValue(item.previous)}
                      </pre>
                    </div>
                  </div>
                  
                  <div>
                    <div className="text-xs text-gray-500 mb-1">当前</div>
                    <div className={`text-sm p-2 rounded ${
                      item.changed ? 'bg-green-50 text-green-700 font-medium' : 'bg-gray-50 text-gray-700'
                    }`}>
                      <pre className="whitespace-pre-wrap font-mono text-xs">
                        {formatValue(item.current)}
                      </pre>
                    </div>
                  </div>
                </div>
                
                {item.changed && item.riskChange && item.riskChange !== 'same' && (
                  <div className={`mt-2 text-xs px-2 py-1 rounded ${
                    item.riskChange === 'up' 
                      ? 'bg-red-200 text-red-800' 
                      : 'bg-green-200 text-green-800'
                  }`}>
                    风险等级{item.riskChange === 'up' ? '升高' : '降低'}
                  </div>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>
      
      {changedCount === 0 && (
        <div className="px-4 py-6 text-center text-gray-500">
          两次报告完全相同，没有变化
        </div>
      )}
    </div>
  );
}

/**
 * 简单的diff算法，比较两个对象并返回差异
 */
export function computeDiff(previous: any, current: any): DiffItem[] {
  if (!previous || !current) return [];
  
  const items: DiffItem[] = [];
  const allKeys = new Set([
    ...Object.keys(previous),
    ...Object.keys(current)
  ]);
  
  allKeys.forEach(key => {
    const prev = previous[key];
    const curr = current[key];
    const changed = JSON.stringify(prev) !== JSON.stringify(curr);
    
    let riskChange: 'up' | 'down' | 'same' = 'same';
    
    if (key === 'risk_level' && changed) {
      const riskOrder = ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'];
      const prevIndex = riskOrder.indexOf(prev);
      const currIndex = riskOrder.indexOf(curr);
      
      if (currIndex > prevIndex) {
        riskChange = 'up';
      } else if (currIndex < prevIndex) {
        riskChange = 'down';
      }
    }
    
    items.push({
      field: key,
      previous: prev,
      current: curr,
      changed,
      riskChange
    });
  });
  
  return items;
}