import type { Metadata } from "next"
import { GeistMono } from "geist/font/mono"
import { GeistSans } from "geist/font/sans"
import "./globals.css"

export const metadata: Metadata = {
  title: "航空气象分析系统 | Aviation Weather Agent",
  description: "基于大模型的智能航空气象报文分析系统，支持METAR解析、风险评估和安全决策",
  keywords: ["aviation", "weather", "METAR", "AI", "flight safety"],
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="zh-CN" className="dark">
      <body 
        className={`${GeistSans.variable} ${GeistMono.variable} font-sans antialiased min-h-screen`}
        style={{
          '--font-geist-sans': `var(${GeistSans.variable})`,
          '--font-geist-mono': `var(${GeistMono.variable})`,
        } as React.CSSProperties}
      >
        {children}
      </body>
    </html>
  )
}
