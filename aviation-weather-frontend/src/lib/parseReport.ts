/**
 * 解析后端返回的 report_text 纯文本，提取结构化数据
 */

export interface ParsedSection {
  title: string
  lines: string[]
}

export interface ParsedReport {
  weatherOverview: Record<string, string>
  riskFactors: string[]
  recommendations: string[]
  approachStandards: string[]
  sections: ParsedSection[]
}

export function parseReportText(reportText: string): ParsedReport {
  const result: ParsedReport = {
    weatherOverview: {},
    riskFactors: [],
    recommendations: [],
    approachStandards: [],
    sections: [],
  }

  if (!reportText) return result

  const lines = reportText.split("\n")
  let currentSection = ""
  let currentLines: string[] = []

  for (const line of lines) {
    const trimmed = line.trim()

    // 检测段落标题: 【xxx】
    const sectionMatch = trimmed.match(/^【(.+?)】/)
    if (sectionMatch) {
      // 保存上一个段落
      if (currentSection && currentLines.length > 0) {
        result.sections.push({ title: currentSection, lines: currentLines })
      }
      currentSection = sectionMatch[1]
      currentLines = []
      continue
    }

    if (trimmed) {
      currentLines.push(trimmed)
    }
  }
  // 保存最后一个段落
  if (currentSection && currentLines.length > 0) {
    result.sections.push({ title: currentSection, lines: currentLines })
  }

  // 从 sections 中提取具体数据
  for (const section of result.sections) {
    const title = section.title

    // 天气概况
    if (title.includes("天气概况") || title.includes("气象概况")) {
      for (const line of section.lines) {
        const kvMatch = line.match(/^[-•]\s*(.+?)：(.+)$/) || line.match(/^[-•]\s*(.+?):\s*(.+)$/)
        if (kvMatch) {
          result.weatherOverview[kvMatch[1].trim()] = kvMatch[2].trim()
        }
      }
    }

    // 风险因素
    if (title.includes("风险因素") || title.includes("风险")) {
      result.riskFactors = section.lines
        .filter((l) => l.startsWith("-") || l.startsWith("•"))
        .map((l) => l.replace(/^[-•]\s*/, "").trim())
        .filter(Boolean)
    }

    // 建议
    if (title.includes("建议") || title.includes("行动")) {
      result.recommendations = section.lines
        .filter((l) => l.startsWith("-") || l.startsWith("•") || /^\d+\./.test(l))
        .map((l) => l.replace(/^[-•]\s*/, "").replace(/^\d+\.\s*/, "").trim())
        .filter(Boolean)
    }

    // 进近标准
    if (title.includes("进近") || title.includes("DH") || title.includes("MDA")) {
      result.approachStandards = section.lines.filter(Boolean)
    }
  }

  return result
}
