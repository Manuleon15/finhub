"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";

const NAV_ITEMS = [
  { href: "/", label: "Dashboard", icon: "📊" },
  { href: "/research", label: "Equity Research", icon: "🔍" },
  { href: "/portfolio", label: "Portfolio", icon: "💼", protected: true },
  { href: "/screener", label: "Screener", icon: "⚙️" },
  { href: "/alerts", label: "Alertas", icon: "🔔" },
  { href: "/earnings", label: "Earnings", icon: "📈" },
  { href: "/copilot", label: "Copiloto", icon: "🤖", protected: true },
  { href: "/settings", label: "Settings", icon: "⚙️", protected: true },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="w-60 min-h-screen bg-bg-card border-r border-bg-border flex flex-col">
      {/* Logo */}
      <div className="p-4 border-b border-bg-border">
        <h1 className="text-xl font-bold text-accent">FinHub</h1>
        <p className="text-xs text-gray-500 mt-1">Equity Research Terminal</p>
      </div>

      {/* Navigation */}
      <nav className="flex-1 p-2">
        {NAV_ITEMS.map((item) => {
          const active = pathname === item.href;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-3 px-3 py-2 rounded-md text-sm transition-colors",
                active
                  ? "bg-bg-hover text-accent"
                  : "text-gray-400 hover:text-white hover:bg-bg-hover"
              )}
            >
              <span className="text-base">{item.icon}</span>
              <span>{item.label}</span>
              {item.protected && (
                <span className="ml-auto text-xs text-gray-600">🔒</span>
              )}
            </Link>
          );
        })}
      </nav>

      {/* Footer */}
      <div className="p-3 border-t border-bg-border text-xs text-gray-600">
        <p>v0.1.0 — Fase 1</p>
      </div>
    </aside>
  );
}

