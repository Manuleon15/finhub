"use client";

import { useEffect, useState } from "react";
import { apiFetch, apiUpload } from "@/lib/api";
import { formatCurrency, formatPercent } from "@/lib/format";
import type { ImportResult } from "@/lib/portfolio-types";

export default function PortfolioPage() {
  const [overview, setOverview] = useState<any>(null);
  const [analytics, setAnalytics] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [importResult, setImportResult] = useState<ImportResult | null>(null);

  async function load() {
    try {
      const [ov, an] = await Promise.all([
        apiFetch<any>("/api/portfolio/overview"),
        apiFetch<any>("/api/portfolio/analytics"),
      ]);
      setOverview(ov);
      setAnalytics(an);
    } catch (e: any) {
      setError(e.message || "Error al cargar");
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

  const k = overview?.kpis;
  const irpf = overview?.irpf;
  const perf = overview?.performance;
  const ac = analytics?.analyst_comment;

  const SectorBar = ({ s }: any) => (
    <div key={s.sector}>
      <div className="flex justify-between text-sm mb-1">
        <span className="text-gray-400">{s.sector}</span>
        <span className="text-white font-mono">{(s.pct*100).toFixed(1)}%</span>
      </div>
      <div className="h-2 bg-bg-border rounded-full overflow-hidden">
        <div className="h-full bg-accent rounded-full" style={{ width: `${Math.min(100, s.pct*100)}%` }} />
      </div>
    </div>
  );

  const KPICard = ({ label, value, color }: any) => (
    <div className="bg-bg-card border border-bg-border rounded-lg p-4">
      <p className="text-xs text-gray-500">{label}</p>
      <p className={`text-2xl font-bold ${color || "text-white"}`}>{value}</p>
    </div>
  );

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">📊 Análisis de Cartera</h1>
          <p className="text-xs text-gray-500 mt-1">Complementa tu Excel · {analytics?.updated_at}</p>
        </div>
        <label className="px-4 py-2 bg-accent text-black rounded-md font-medium cursor-pointer text-sm">
          {uploading ? "Importando..." : "↻ Actualizar"}
          <input type="file" accept=".xlsx,.xlsm" className="hidden" onChange={handleUpload} disabled={uploading} />
        </label>
      </div>

      {error && <div className="bg-danger/10 border border-danger/30 rounded-md p-4 text-danger">{error}</div>}
      {importResult && (
        <div className="bg-success/10 border border-success/30 rounded-md p-4 text-success">
          ✅ {importResult.positions_imported} posiciones, {importResult.transactions_imported} transacciones
          {importResult.monthly_snapshots_saved ? `, ${importResult.monthly_snapshots_saved} snapshots` : ""}
        </div>
      )}

      {/* Comentario de analista */}
      {ac && (
        <div className="bg-gradient-to-br from-bg-card to-bg border border-accent/30 rounded-lg p-6">
          <p className="text-accent font-bold mb-3">💬 Nota de investigación</p>
          <p className="text-white font-medium mb-4">{ac.resumen}</p>
          <div className="grid md:grid-cols-3 gap-4 text-sm">
            <div><p className="text-success font-semibold mb-2">✓ Fortalezas</p><ul className="text-gray-300 space-y-1 list-disc pl-4">{ac.fortalezas.map((f: string, i: number) => <li key={i}>{f}</li>)}</ul></div>
            <div><p className="text-warning font-semibold mb-2">⚠ Riesgos</p><ul className="text-gray-300 space-y-1 list-disc pl-4">{ac.riesgos.map((f: string, i: number) => <li key={i}>{f}</li>)}</ul></div>
            <div><p className="text-accent font-semibold mb-2">🎯 Recomendaciones</p><ul className="text-gray-300 space-y-1 list-disc pl-4">{ac.recomendaciones.map((f: string, i: number) => <li key={i}>{f}</li>)}</ul></div>
          </div>
        </div>
      )}

      {/* KPIs */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <KPICard label="Valor total" value={formatCurrency(k?.total_value)} />
        <KPICard label="G/P no realizada" value={`${formatCurrency(k?.total_unrealized_pl)} (${formatPercent(k?.total_unrealized_pl_pct, 1, true)})`} color={k?.total_unrealized_pl >= 0 ? "text-success" : "text-danger"} />
        <KPICard label="Dividend yield" value={formatPercent(analytics?.excel_metrics?.dividend_yield, 1)} />
        <KPICard label="Beta ponderada" value={analytics?.excel_metrics?.beta_ponderada ?? "N/D"} />
      </div>

      {/* IRPF */}
      {irpf && (
        <div className="bg-bg-card border border-bg-border rounded-lg p-5">
          <h3 className="text-white font-semibold mb-4">💸 Preview IRPF (si vendieras hoy)</h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
            <div><p className="text-gray-500">Plusvalía no realizada</p><p className="text-white font-mono">{formatCurrency(irpf.unrealized_pnl)}</p></div>
            <div><p className="text-gray-500">IRPF estimado</p><p className="text-danger font-mono">{formatCurrency(irpf.estimated_unrealized_tax)}</p></div>
            <div><p className="text-gray-500">Dividendos esperados</p><p className="text-white font-mono">{formatCurrency(irpf.expected_dividends)}</p></div>
            <div><p className="text-gray-500">IRPF dividendos (19%)</p><p className="text-danger font-mono">{formatCurrency(irpf.estimated_dividend_tax)}</p></div>
          </div>
          <div className="mt-4 pt-4 border-t border-bg-border">
            <div className="flex justify-between items-center">
              <p className="text-gray-400">Total IRPF si vendieras hoy</p>
              <p className="text-2xl font-bold text-danger">{formatCurrency(irpf.if_sold_today_total_tax)}</p>
            </div>
            <p className="text-[10px] text-gray-600 mt-2">{irpf.disclaimer}</p>
          </div>
        </div>
      )}

      {/* Métricas de riesgo */}
      <div className="bg-bg-card border border-bg-border rounded-lg p-5">
        <h3 className="text-white font-semibold mb-4">📉 Métricas de riesgo</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-center">
          {[
            ["Volatilidad", analytics?.risk_metrics?.volatility_label || "N/D"],
            ["Sharpe", analytics?.risk_metrics?.sharpe_ratio?.toFixed(2) ?? "N/D"],
            ["Sortino", analytics?.risk_metrics?.sortino_ratio?.toFixed(2) ?? "N/D"],
            ["Max drawdown", analytics?.risk_metrics?.max_drawdown_label || "N/D"],
          ].map(([l, v]) => (
            <div key={String(l)} className="border border-bg-border rounded-md p-3">
              <p className="text-xs text-gray-500">{l}</p>
              <p className="text-xl font-bold text-white">{String(v)}</p>
            </div>
          ))}
        </div>
        <p className="text-[10px] text-gray-600 mt-3">Se calculan con 12 meses de histórico diario de Yahoo Finance. Se actualizan cuando Yahoo responde.</p>
      </div>

      {/* vs S&P 500 */}
      <div className="bg-bg-card border border-bg-border rounded-lg p-5">
        <h3 className="text-white font-semibold mb-4">📈 vs S&P 500 (12m)</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-center">
          {[
            ["Cartera", analytics?.benchmark?.portfolio_annual_label || "N/D"],
            ["S&P 500", analytics?.benchmark?.sp500_annual_label || "N/D"],
            ["Beta", analytics?.benchmark?.beta_vs_sp500 ?? "N/D"],
            ["Correlación", analytics?.benchmark?.correlation ?? "N/D"],
          ].map(([l, v]) => (
            <div key={String(l)} className="border border-bg-border rounded-md p-3">
              <p className="text-xs text-gray-500">{l}</p>
              <p className="text-xl font-bold text-white">{String(v)}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Exposición sectorial */}
      <div className="bg-bg-card border border-bg-border rounded-lg p-5">
        <h3 className="text-white font-semibold mb-4">🏭 Exposición sectorial</h3>
        <div className="space-y-3">
          {overview?.allocation?.by_sector?.map((s: any) => <SectorBar key={s.sector} s={s} />)}
        </div>
      </div>

      {/* Histórico mensual */}
      {perf?.series?.length > 0 && (
        <div className="bg-bg-card border border-bg-border rounded-lg p-5">
          <h3 className="text-white font-semibold mb-4">📅 Histórico mensual (vs S&P 500)</h3>
          <div className="space-y-2">
            {perf.series.map((m: any) => (
              <div key={`${m.period}`} className="flex items-center gap-4 text-sm">
                <span className="text-gray-500 w-16">{m.period}</span>
                <div className="flex-1">
                  <div className="flex justify-between text-xs mb-1">
                    <span className="text-gray-400">Cartera</span>
                    <span className={m.portfolio >= m.sp500 ? "text-success" : "text-danger"}>{formatPercent(m.portfolio, 1, true)}</span>
                  </div>
                  <div className="flex h-2 gap-0.5">
                    <div className="bg-accent rounded-l" style={{ width: `${Math.min(50, Math.max(0, 50 + m.portfolio * 50))}%` }} />
                    <div className="bg-gray-600 rounded-r" style={{ width: `${Math.min(50, Math.max(0, 50 + m.sp500 * 50))}%` }} />
                  </div>
                  <div className="flex justify-between text-xs mt-1">
                    <span className="text-gray-500">S&P 500</span>
                    <span className="text-gray-500">{formatPercent(m.sp500, 1, true)}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
