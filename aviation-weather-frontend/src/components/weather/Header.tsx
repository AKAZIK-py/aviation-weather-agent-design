"use client"

import * as React from "react"

export function Header() {
  return (
    <header className="border-b border-border/50 bg-background/80 backdrop-blur-md sticky top-0 z-50">
      <div className="container mx-auto px-4 h-16 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-primary to-primary/60 flex items-center justify-center text-xl">
            🛩️
          </div>
          <div>
            <h1 className="text-lg font-bold tracking-tight">航空气象分析系统</h1>
            <p className="text-xs text-muted-foreground">Aviation Weather Agent</p>
          </div>
        </div>
        
        <div className="flex items-center gap-4">
          <div className="hidden md:flex items-center gap-2 text-xs text-muted-foreground">
            <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse"></span>
            <span>系统在线</span>
          </div>
          
          <a
            href="https://github.com/AKAZIK-py"
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs text-muted-foreground hover:text-foreground transition-colors"
          >
            Created By AKAZIK-py
          </a>
        </div>
      </div>
    </header>
  )
}
