"use client";

import { useState } from "react";
import { apiFetch, buildQuery } from "@/lib/api";
import { formatCurrency, formatPercent, formatNumber, getColor } from "@/lib/format";
import type { AnalysisResult } from "@/lib/types";

export default function ResearchPage() {
  const [ticker, setTicker] = useState("");
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<AnalysisResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function analyze(e: React.FormEvent) {
    e.preventDefault();
    if (!ticker.trim()) return;

    setLoading(true);
    setError(null);
    setData(null);

    try {
      const result = await apiFetch<AnalysisResult>(
        `/api/research/analyze${buildQuery({ ticker: ticker.toUpperCase() })}`
      );
      setData(result);
    } catch (err: any) {
      setError(err.message || "Error al analizar el ticker");
    } finally {
      setLoading(false);
    }
  }

  const recColor = (color: string) => {
    if (color === "green") return "text-success bg-success/10 border-success/30";
    if (color === "yellow") return "text-warning bg-warning/10 border-warning/30";
    return "text-danger bg-danger/10 border-danger/30";
  };

  return (
    <div className="max-w-6xl mx-auto">
      <h1 className="text-2xl font-bold text-white mb-1">🔍 Equity Research Terminal</h1>
      <p className="text-gray-500 mb-6">Análisis completo con DCF y scoring BUY/HOLD/SELL</p>

      {/* Search bar */}
      <form onSubmit={analyze} className="flex gap-3 mb-6">
        <input
          type="text"
          value={ticker}
          onChange={(e) => setTicker(e.target.value)}
          placeholder="Ticker (ej. MSFT, AAPL, NVDA)"
          className="flex-1 px-4 py-3 bg-bg-card border border-bg-border rounded-md text-white placeholder-gray-600 focus:outline-none focus:border-accent font-mono uppercase"
        />
        <button
          type="submit"
          disabled={loading || !ticker.trim()}
          className="px-6 py-3 bg-accent text-black rounded-md font-medium hover:bg-accent-hover disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {loading ? "Analizando..." : "Analizar"}
        </button>
      </form>

      {error && (
        <div className="bg-danger/10 border border-danger/30 rounded-md p-4 text-danger mb-6">
          ⚠️ {error}
        </div>
      )}

      {loading && (
        <div className="text-center py-12">
          <div className="inline-block w-8 h-8 border-2 border-accent border-t-transparent rounded-full animate-spin" />
          <p className="text-gray-500 mt-3">Obteniendo datos financieros y calculando DCF...</p>
        </div>
      )}

      {data && !loading && (
        <div className="space-y-6">
          {/* Business Overview */}
          <section className="bg-bg-card border border-bg-border rounded-lg p-6">
            <div className="flex items-start justify-between mb-4">
              <div>
                <h2 className="text-xl font-bold text-white">{data.business_overview.name}</h2>
                <p className="text-gray-500 text-sm">
                  {data.ticker} · {data.business_overview.sector} · {data.business_overview.industry}
                </p>
              </div>
              <div className="text-right">
                <p className="text-2xl font-bold text-white">
                  {formatCurrency(data.business_overview.price)}
                </p>
                <p className="text-xs text-gray-500">Market Cap: {formatNumber(data.business_overview.market_cap)}</p>
              </div>
            </div>
            <p className="text-sm text-gray-400 leading-relaxed line-clamp-3">
              {data.business_overview.description}
            </p>
          </section>

          {/* Financial Quality */}
          <section className="bg-bg-card border border-bg-border rounded-lg p-6">
            <h3 className="text-lg font-semibold text-white mb-4">📊 Calidad Financiera</h3>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
              {[
                { label: "ROIC", value: data.financial_quality.roic_label, good: (data.financial_quality.roic ?? 0) > 0.15 },
                { label: "FCF Margin", value: data.financial_quality.fcf_margin_label, good: (data.financial_quality.fcf_margin ?? 0) > 0.10 },
                { label: "Deuda", value: data.financial_quality.debt_label, good: (data.financial_quality.debt_to_equity ?? 1) < 0.5 },
                { label: "Gross Margin", value: data.financial_quality.gross_margin_label, good: (data.financial_quality.gross_margin ?? 0) > 0.30 },
                { label: "Revenue Growth", value: data.financial_quality.revenue_growth_label, good: (data.financial_quality.revenue_growth ?? 0) > 0.05 },
                { label: "FCF Growth", value: data.financial_quality.fcf_growth_label, good: (data.financial_quality.fcf_growth ?? 0) > 0.05 },
              ].map((m) => (
                <div key={m.label} className="border border-bg-border rounded-md p-3">
                  <p className="text-xs text-gray-500">{m.label}</p>
                  <p className={`text-lg font-bold mt-1 ${m.good ? "text-success" : "text-white"}`}>
                    {m.value}
                  </p>
                </div>
              ))}
            </div>
          </section>

          {/* DCF Valuation */}
          <section className="bg-bg-card border border-bg-border rounded-lg p-6">
            <h3 className="text-lg font-semibold text-white mb-4">💰 Valoración DCF (3 escenarios)</h3>

            {data.dcf.error ? (
              <div className="text-gray-500 text-sm p-4 bg-bg rounded-md">
                ⚠️ {data.dcf.error}
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {(["bear", "base", "bull"] as const).map((scenario) => {
                  const s = data.dcf.scenarios[scenario];
                  if (!s) return null;
                  const labels = { bear: "🐻 Bear", base: "📊 Base", bull: "🐂 Bull" };
                  const colors = { bear: "text-danger", base: "text-warning", bull: "text-success" };
                  return (
                    <div key={scenario} className="border border-bg-border rounded-md p-4">
                      <p className="text-sm text-gray-500 mb-2">{labels[scenario]}</p>
                      <p className={`text-2xl font-bold ${colors[scenario]}`}>
                        {formatCurrency(s.price_per_share)}
                      </p>
                      <p className={`text-sm mt-1 ${getColor(s.upside_vs_current)}`}>
                        {s.upside_label} vs precio actual
                      </p>
                      <div className="mt-3 text-xs text-gray-500 space-y-1">
                        <p>WACC: {s.wacc_label}</p>
                        <p>Terminal Growth: {s.terminal_growth_label}</p>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}

            {/* Valuation metrics */}
            <div className="mt-4 grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
              {[
                { label: "P/E Ratio", value: data.valuation.pe_ratio?.toFixed(1) },
                { label: "Forward P/E", value: data.valuation.forward_pe?.toFixed(1) },
                { label: "PEG", value: data.valuation.peg_ratio?.toFixed(2) },
                { label: "P/B", value: data.valuation.pb_ratio?.toFixed(2) },
                { label: "EV/Revenue", value: data.valuation.ev_to_revenue?.toFixed(2) },
                { label: "EV/EBITDA", value: data.valuation.ev_to_ebitda?.toFixed(2) },
                { label: "FCF Yield", value: data.valuation.fcf_yield ? formatPercent(data.valuation.fcf_yield) : "N/A" },
                { label: "Div Yield", value: data.valuation.dividend_yield ? formatPercent(data.valuation.dividend_yield) : "N/A" },
              ].map((m) => (
                <div key={m.label} className="flex justify-between border-b border-bg-border pb-1">
                  <span className="text-gray-500">{m.label}</span>
                  <span className="text-white font-mono">{m.value ?? "N/A"}</span>
                </div>
              ))}
            </div>
          </section>

          {/* Scoring & Recommendation */}
          <section className="bg-bg-card border border-bg-border rounded-lg p-6">
            <h3 className="text-lg font-semibold text-white mb-4">🎯 Scoring y Recomendación</h3>

            {/* Recommendation badge */}
            <div className="flex items-center gap-4 mb-6">
              <div className={`px-6 py-3 rounded-md border ${recColor(data.scoring.recommendation.color)}`}>
                <p className="text-2xl font-bold">{data.scoring.recommendation.action}</p>
                <p className="text-xs opacity-80">{data.scoring.recommendation.description}</p>
              </div>
              <div>
                <p className="text-4xl font-bold text-white">{data.scoring.total_score}</p>
                <p className="text-xs text-gray-500">de {data.scoring.max_score}</p>
              </div>
            </div>

            {/* Score breakdown */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Quality */}
              <div>
                <p className="text-sm text-gray-400 mb-2">
                  Calidad: {data.scoring.quality_score.score}/{data.scoring.quality_score.max}
                </p>
                <div className="space-y-1">
                  {Object.entries(data.scoring.quality_score.breakdown).map(([key, val]) => (
                    <div key={key} className="flex justify-between text-xs">
                      <span className="text-gray-500">{val.label}</span>
                      <span className="text-white">{val.points}/{val.max}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Valuation */}
              <div>
                <p className="text-sm text-gray-400 mb-2">
                  Valoración: {data.scoring.valuation_score.score}/{data.scoring.valuation_score.max}
                </p>
                <div className="space-y-1">
                  {Object.entries(data.scoring.valuation_score.breakdown).map(([key, val]) => (
                    <div key={key} className="flex justify-between text-xs">
                      <span className="text-gray-500">{val.label}</span>
                      <span className="text-white">{val.points}/{val.max}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </section>
        </div>
      )}

      {!data && !loading && !error && (
        <div className="text-center py-12 text-gray-600">
          <p className="text-lg">Introduce un ticker para empezar el análisis</p>
          <p className="text-sm mt-2">Ejemplos: MSFT, AAPL, NVDA, GOOG, AMZN, META</p>
        </div>
      )}
    </div>
  );
}

