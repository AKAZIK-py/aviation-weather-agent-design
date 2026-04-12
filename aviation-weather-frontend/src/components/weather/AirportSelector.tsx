"use client"

import * as React from "react"
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { AIRPORTS, getAirportsGroupedByRegion } from "@/lib/airports"
import { cn } from "@/lib/utils"

interface AirportSelectorProps {
  value?: string
  onChange: (icao: string) => void
  disabled?: boolean
  showSearch?: boolean
  className?: string
}

export function AirportSelector({
  value,
  onChange,
  disabled,
  showSearch = true,
  className,
}: AirportSelectorProps) {
  const [searchQuery, setSearchQuery] = React.useState("")
  const groupedAirports = React.useMemo(() => getAirportsGroupedByRegion(), [])

  // 过滤机场
  const filteredAirports = React.useMemo(() => {
    if (!searchQuery.trim()) return groupedAirports

    const query = searchQuery.toLowerCase()
    const filtered: Record<string, typeof AIRPORTS> = {}

    Object.entries(groupedAirports).forEach(([region, airports]) => {
      const matched = airports.filter(
        (airport) =>
          airport.icao.toLowerCase().includes(query) ||
          airport.iata.toLowerCase().includes(query) ||
          airport.name_cn.includes(query) ||
          airport.name_en.toLowerCase().includes(query) ||
          airport.city_cn.includes(query) ||
          airport.city_en.toLowerCase().includes(query)
      )
      if (matched.length > 0) {
        filtered[region] = matched
      }
    })

    return filtered
  }, [searchQuery, groupedAirports])

  const selectedAirport = AIRPORTS.find((a) => a.icao === value)

  return (
    <div className={cn("space-y-3", className)}>
      <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
        选择机场
      </label>

      {/* 搜索框 */}
      {showSearch && (
        <div className="relative">
          <Input
            type="text"
            placeholder="搜索机场 (ICAO/IATA/名称/城市)"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full"
            disabled={disabled}
          />
          {searchQuery && (
            <button
              onClick={() => setSearchQuery("")}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-xs text-muted-foreground hover:text-foreground"
            >
              ✕
            </button>
          )}
        </div>
      )}

      {/* 机场选择下拉 */}
      <Select value={value} onValueChange={onChange} disabled={disabled}>
        <SelectTrigger className="w-full">
          <SelectValue placeholder="请选择机场" />
        </SelectTrigger>
        <SelectContent>
          {Object.entries(filteredAirports).map(([region, airports]) => (
            <SelectGroup key={region}>
              <SelectLabel className="font-semibold">{region}</SelectLabel>
              {airports
                .sort((a, b) => (b.is_major ? 1 : 0) - (a.is_major ? 1 : 0))
                .map((airport) => (
                  <SelectItem key={airport.icao} value={airport.icao}>
                    <div className="flex items-center justify-between gap-2">
                      <div className="flex items-center gap-2 flex-1">
                        <span className="font-medium">{airport.name_cn}</span>
                        {airport.is_major && (
                          <Badge variant="secondary" className="text-xs">
                            主要
                          </Badge>
                        )}
                      </div>
                      <div className="flex items-center gap-1 text-xs text-muted-foreground">
                        <span className="font-mono">{airport.icao}</span>
                        <span>/</span>
                        <span className="font-mono">{airport.iata}</span>
                      </div>
                    </div>
                  </SelectItem>
                ))}
            </SelectGroup>
          ))}
        </SelectContent>
      </Select>

      {/* 已选机场信息 */}
      {value && selectedAirport && (
        <div className="bg-accent/10 border border-accent/30 rounded-lg p-3">
          <div className="flex items-start justify-between gap-3">
            <div className="flex items-start gap-3 flex-1">
              <span className="text-2xl">✈️</span>
              <div className="flex-1">
                <div className="font-semibold text-sm">{selectedAirport.name_cn}</div>
                <div className="text-xs text-muted-foreground mt-1">
                  {selectedAirport.name_en}
                </div>
                <div className="flex items-center gap-3 mt-2 text-xs text-muted-foreground">
                  <span>📍 {selectedAirport.city_cn}</span>
                  <span>🔢 {selectedAirport.icao}/{selectedAirport.iata}</span>
                </div>
                <div className="flex items-center gap-3 mt-1 text-xs text-muted-foreground">
                  <span>🌐 {selectedAirport.latitude.toFixed(4)}°, {selectedAirport.longitude.toFixed(4)}°</span>
                  <span>⛰️ {selectedAirport.elevation}m</span>
                </div>
              </div>
            </div>
            <button
              onClick={() => onChange("")}
              className="text-xs text-muted-foreground hover:text-foreground transition-colors px-2 py-1 rounded hover:bg-background/50"
            >
              清除
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
