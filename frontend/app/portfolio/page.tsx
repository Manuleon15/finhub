"use client";

import { useEffect, useState } from "react";
import { apiFetch, apiUpload } from "@/lib/api";
import { formatCurrency, formatPercent, getColor } from "@/lib/format";
import type { Position, PortfolioSummary, ImportResult } from "@/lib/portfolio-types";

export default function PortfolioPage() {
  const [positions, setPositions] = useState<Position[]>([]);
  const [summary, setSummary] = useState<PortfolioSummary | null>(null);
  const [analytics, setAnalytics] = useState<any | null>(null);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [importResult, setImportResult] = useState<ImportResult | null>(null);

  async function loadData() {
    setLoading(true);
    setError(null);
    try {
      const [pos, sum] = await Promise.all([
        apiFetch<Position[]>("/api/portfolio/positions"),
        apiFetch<PortfolioSummary>("/api/portfolio/summary"),
      ]);
      setPositions(pos);
      setSummary(sum);
      try {
        const an = await apiFetch<any>("/api/portfolio/analytics");
        setAnalytics(an);
      } catch (e) { /* analytics no bloquea */ }
    } catch (err: any) {
      setError(err.message || "Error al cargar el portfolio");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadData();
  }, []);

  async function handleFileUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setError(null);
    setImportResult(null);
    try {
      const result = await apiUpload<ImportResult>("/api/portfolio/import", file);
      setImportResult(result);
      await loadData();
    } catch (err: any) {
      setError(err.message || "Error al importar el Excel");
    } finally {
      setUploading(false);
      e.target.value = "";
    }
  }

  return (
    <div className="max-w-6xl mx-auto">
      <div className="flex items-center justify-between mb-1">
        <h1 className="text-2xl font-bold text-white">💼 Portfolio Tracker</h1>
        <label className="px-4 py-2 bg-accent text-black rounded-md font-medium hover:bg-accent-hover cursor-pointer transition-colors text-sm">
          {uploading ? "Importando..." : "📤 Importar Excel"}
          <input
            type="file"
            accept=".xlsx,.xlsm"
            className="hidden"
            onChange={handleFileUpload}
            disabled={uploading}
          />
        </label>
      </div>
      <p className="text-gray-500 mb-6">Tus posiciones reales, importadas desde tu Excel</p>

      {error && (
        <div className="bg-danger/10 border border-danger/30 rounded-md p-4 text-danger mb-6">
          ⚠️ {error}
        </div>
      )}

      {importResult && (
        <div className="bg-success/10 border border-success/30 rounded-md p-4 text-success mb-6">
          ✅ Importadas {importResult.positions_imported} posiciones y {importResult.transactions_imported} transacciones
          {importResult.warnings?.length > 0 && (
            <span className="text-warning"> ({importResult.warnings.length} avisos)</span>
          )}
        </div>
      )}

      {summary && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
          <div className="bg-bg-card border border-bg-border rounded-lg p-4">
            <p className="text-xs text-gray-500">Valor total</p>
            <p className="text-xl font-bold text-white">{formatCurrency(summary.total_value)}</p>
          </div>
          <div className="bg-bg-card border border-bg-border rounded-lg p-4">
            <p className="text-xs text-gray-500">Coste total</p>
            <p className="text-xl font-bold text-white">{formatCurrency(summary.total_cost)}</p>
          </div>
          <div className="bg-bg-card border border-bg-border rounded-lg p-4">
            <p className="text-xs text-gray-500">G/P no realizada</p>
            <p className={`text-xl font-bold ${getColor(summary.total_unrealized_pl)}`}>
              {formatCurrency(summary.total_unrealized_pl)}
              <span className="text-sm"> ({formatPercent(summary.total_unrealized_pl_pct, 1, true)})</span>
            </p>
          </div>
          <div className="bg-bg-card border border-bg-border rounded-lg p-4">
            <p className="text-xs text-gray-500">G/P realizada</p>
            <p className={`text-xl font-bold ${getColor(summary.total_realized_pl)}`}>
              {formatCurrency(summary.total_realized_pl)}
            </p>
          </div>
        </div>
      )}

      {analytics && analytics.has_data && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
          <div className="bg-bg-card border border-bg-border rounded-lg p-5">
            <h3 className="text-white font-semibold mb-3">📊 Métricas de Riesgo</h3>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between"><span className="text-gray-500">Volatilidad anual</span><span className="text-white font-mono">{analytics.risk_metrics?.volatility_label || "N/D"}</span></div>
              <div className="flex justify-between"><span className="text-gray-500">Sharpe ratio</span><span className="text-white font-mono">{analytics.risk_metrics?.sharpe_ratio ?? "N/D"}</span></div>
              <div className="flex justify-between"><span className="text-gray-500">Sortino ratio</span><span className="text-white font-mono">{analytics.risk_metrics?.sortino_ratio ?? "N/D"}</span></div>
              <div className="flex justify-between"><span className="text-gray-500">Max drawdown</span><span className="text-danger font-mono">{analytics.risk_metrics?.max_drawdown_label || "N/D"}</span></div>
            </div>
          </div>

          <div className="bg-bg-card border border-bg-border rounded-lg p-5">
            <h3 className="text-white font-semibold mb-3">📈 vs S&P 500</h3>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between"><span className="text-gray-500">Retorno anual cartera</span><span className="text-white font-mono">{analytics.benchmark?.portfolio_annual_return_label || "N/D"}</span></div>
              <div className="flex justify-between"><span className="text-gray-500">Retorno anual S&P 500</span><span className="text-white font-mono">{analytics.benchmark?.annual_return_label || "N/D"}</span></div>
              <div className="flex justify-between"><span className="text-gray-500">Beta</span><span className="text-white font-mono">{analytics.benchmark?.beta_vs_sp500 ?? "N/D"}</span></div>
              <div className="flex justify-between"><span className="text-gray-500">Alpha</span><span className="text-white font-mono">{analytics.benchmark?.alpha_vs_sp500 ?? "N/D"}</span></div>
            </div>
          </div>

          <div className="bg-bg-card border border-bg-border rounded-lg p-5">
            <h3 className="text-white font-semibold mb-3">🎯 Concentración</h3>
            <p className="text-sm text-gray-400 mb-2">{analytics.concentration?.label}</p>
            <div className="text-xs text-gray-500 space-y-1">
              <p>Nº efectivo de posiciones: <span className="text-white font-mono">{analytics.concentration?.effective_n}</span></p>
              {analytics.concentration?.top_positions?.slice(0, 3).map((tp: any) => (
                <p key={tp.ticker}>{tp.ticker}: <span className="text-white font-mono">{(tp.pct*100).toFixed(1)}%</span></p>
              ))}
            </div>
          </div>

          <div className="bg-bg-card border border-bg-border rounded-lg p-5">
            <h3 className="text-white font-semibold mb-3">💡 Recomendaciones</h3>
            <ul className="text-xs text-gray-400 space-y-2 list-disc pl-4">
              {analytics.recommendations?.map((r: string, i: number) => (
                <li key={i}>{r}</li>
              ))}
            </ul>
          </div>
        </div>
      )}

      {loading && <p className="text-gray-500 text-center py-8">Cargando posiciones...</p>}

      {!loading && positions.length > 0 && (
        <div className="bg-bg-card border border-bg-border rounded-lg overflow-hidden">
          <table className="w-full terminal-table">
            <thead>
              <tr className="text-left text-xs text-gray-500 border-b border-bg-border">
                <th className="p-3">Ticker</th>
                <th className="p-3">Cantidad</th>
                <th className="p-3">P. Compra</th>
                <th className="p-3">P. Actual</th>
                <th className="p-3">Valor</th>
                <th className="p-3">G/P</th>
                <th className="p-3">% G/P</th>
              </tr>
            </thead>
            <tbody>
              {positions.map((p) => (
                <tr key={p.id} className="hover:bg-bg-hover">
                  <td className="p-3 font-mono text-white">{p.ticker}</td>
                  <td className="p-3 text-gray-400">{p.quantity}</td>
                  <td className="p-3 text-gray-400">{formatCurrency(p.avg_price)}</td>
                  <td className="p-3 text-gray-400">{formatCurrency(p.current_price)}</td>
                  <td className="p-3 text-white">{formatCurrency(p.market_value)}</td>
                  <td className={`p-3 ${getColor(p.unrealized_pl)}`}>{formatCurrency(p.unrealized_pl)}</td>
                  <td className={`p-3 ${getColor(p.unrealized_pl_pct)}`}>{formatPercent(p.unrealized_pl_pct, 1, true)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {!loading && positions.length === 0 && (
        <div className="text-center py-12 text-gray-600">
          <p>No hay posiciones. Importa tu Excel para empezar.</p>
        </div>
      )}
    </div>
  );
}
