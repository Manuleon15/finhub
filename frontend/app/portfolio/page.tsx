"use client";

import { useEffect, useState } from "react";
import { apiFetch, apiUpload } from "@/lib/api";
import { formatCurrency, formatPercent } from "@/lib/format";
import type { ImportResult } from "@/lib/portfolio-types";

export default function PortfolioPage() {
  const [analytics, setAnalytics] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [importResult, setImportResult] = useState<ImportResult | null>(null);

  async function load() {
    try {
      const an = await apiFetch<any>("/api/portfolio/analytics");
      setAnalytics(an);
    } catch (e: any) {
      setError(e.message || "Error al cargar análisis");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  async function handleUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true); setError(null);
    try {
      const r = await apiUpload<ImportResult>("/api/portfolio/import", file);
      setImportResult(r);
      await load();
    } catch (e: any) {
      setError(e.message || "Error al importar");
    } finally { setUploading(false); e.target.value = ""; }
  }

  if (loading) return <p className="text-gray-500 text-center py-12">Analizando cartera...</p>;
  if (!analytics?.has_data) return (
    <div className="max-w-6xl mx-auto text-center py-12">
      <p className="text-gray-500 mb-4">Importa tu Excel para ver el análisis premium.</p>
      <label className="px-4 py-2 bg-accent text-black rounded-md font-medium cursor-pointer">
        📤 Importar Excel
        <input type="file" accept=".xlsx,.xlsm" className="hidden" onChange={handleUpload} disabled={uploading} />
      </label>
    </div>
  );

  const em = analytics.excel_metrics;
  const rm = analytics.risk_metrics;
  const bm = analytics.benchmark;
  const ac = analytics.analyst_comment;

  const Card = ({ title, children }: any) => (
    <div className="bg-bg-card border border-bg-border rounded-lg p-5">
      <h3 className="text-white font-semibold mb-3">{title}</h3>
      {children}
    </div>
  );

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">📊 Análisis de Cartera</h1>
          <p className="text-xs text-gray-500 mt-1">Complementa tu Excel · {analytics.updated_at}</p>
        </div>
        <label className="px-4 py-2 bg-accent text-black rounded-md font-medium cursor-pointer text-sm">
          {uploading ? "Importando..." : "↻ Actualizar"}
          <input type="file" accept=".xlsx,.xlsm" className="hidden" onChange={handleUpload} disabled={uploading} />
        </label>
      </div>

      {error && <div className="bg-danger/10 border border-danger/30 rounded-md p-4 text-danger">{error}</div>}
      {importResult && (
        <div className="bg-success/10 border border-success/30 rounded-md p-4 text-success">
          ✅ Importadas {importResult.positions_imported} posiciones, {importResult.transactions_imported} transacciones
        </div>
      )}

      {/* Comentario de analista */}
      <div className="bg-gradient-to-br from-bg-card to-bg border border-accent/30 rounded-lg p-6">
        <div className="flex items-center gap-2 mb-3">
          <span className="text-accent font-bold">💬 Nota de investigación</span>
          <span className="text-xs text-gray-500">generada por FinHub</span>
        </div>
        <p className="text-white font-medium mb-4">{ac.resumen}</p>
        <div className="grid md:grid-cols-3 gap-4 text-sm">
          <div>
            <p className="text-success font-semibold mb-2">✓ Fortalezas</p>
            <ul className="text-gray-300 space-y-1 list-disc pl-4">{ac.fortalezas.map((f: string, i: number) => <li key={i}>{f}</li>)}</ul>
          </div>
          <div>
            <p className="text-warning font-semibold mb-2">⚠ Riesgos</p>
            <ul className="text-gray-300 space-y-1 list-disc pl-4">{ac.riesgos.map((f: string, i: number) => <li key={i}>{f}</li>)}</ul>
          </div>
          <div>
            <p className="text-accent font-semibold mb-2">🎯 Recomendaciones</p>
            <ul className="text-gray-300 space-y-1 list-disc pl-4">{ac.recomendaciones.map((f: string, i: number) => <li key={i}>{f}</li>)}</ul>
          </div>
        </div>
        <p className="text-[10px] text-gray-600 mt-4">{ac.nota}</p>
      </div>

      {/* KPIs clave */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card title="Beta ponderada"><p className="text-2xl font-bold text-white">{em.beta_ponderada ?? "N/D"}</p></Card>
        <Card title="Dividend yield"><p className="text-2xl font-bold text-success">{em.dividend_yield_label}</p></Card>
        <Card title="Retorno s/ coste"><p className="text-2xl font-bold text-white">{em.retorno_sobre_coste_label}</p></Card>
        <Card title="G/P realizada"><p className="text-2xl font-bold text-white">{formatCurrency(em.realized_pl)}</p></Card>
      </div>

      {/* Métricas de riesgo */}
      <Card title="📉 Métricas de riesgo (12m)">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-center">
          {[
            ["Volatilidad anual", rm.volatility_label],
            ["Sharpe", rm.sharpe_ratio?.toFixed(2) ?? "N/D"],
            ["Sortino", rm.sortino_ratio?.toFixed(2) ?? "N/D"],
            ["Max drawdown", rm.max_drawdown_label],
          ].map(([l, v]) => (
            <div key={String(l)} className="border border-bg-border rounded-md p-3">
              <p className="text-xs text-gray-500">{l}</p>
              <p className="text-xl font-bold text-white">{String(v)}</p>
            </div>
          ))}
        </div>
      </Card>

      {/* vs S&P 500 */}
      <Card title="📈 vs S&P 500 (12m)">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-center">
          {[
            ["Cartera", bm.portfolio_annual_label],
            ["S&P 500", bm.sp500_annual_label],
            ["Beta", bm.beta_vs_sp500 ?? "N/D"],
            ["Correlación", bm.correlation ?? "N/D"],
          ].map(([l, v]) => (
            <div key={String(l)} className="border border-bg-border rounded-md p-3">
              <p className="text-xs text-gray-500">{l}</p>
              <p className="text-xl font-bold text-white">{String(v)}</p>
            </div>
          ))}
        </div>
      </Card>

      {/* Exposición sectorial */}
      <Card title="🏭 Exposición sectorial">
        <div className="space-y-2">
          {em.sector_exposure.map((s: any) => (
            <div key={s.sector}>
              <div className="flex justify-between text-sm mb-1">
                <span className="text-gray-400">{s.sector}</span>
                <span className="text-white font-mono">{(s.pct*100).toFixed(1)}% · {formatCurrency(s.value)}</span>
              </div>
              <div className="h-2 bg-bg-border rounded-full overflow-hidden">
                <div className="h-full bg-accent rounded-full" style={{ width: `${Math.min(100, s.pct*100)}%` }} />
              </div>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
