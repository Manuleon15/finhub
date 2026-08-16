"use client";

import { useEffect, useState } from "react";
import { apiFetch, apiUpload } from "@/lib/api";
import { formatCurrency, formatPercent, getColor } from "@/lib/format";
import type { Position, PortfolioSummary, ImportResult } from "@/lib/portfolio-types";

export default function PortfolioPage() {
  const [positions, setPositions] = useState<Position[]>([]);
  const [summary, setSummary] = useState<PortfolioSummary | null>(null);
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
      e.target.value = ""; // permite re-subir el mismo archivo si hace falta
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
        <div className="bg-success/10 border border-success/30 rounded-md p-4 text-success mb-6 text-sm">
          ✓ Importadas {importResult.positions_imported} posiciones y{" "}
          {importResult.transactions_imported} transacciones nuevas.
          {importResult.warnings.length > 0 && (
            <ul className="mt-2 text-warning list-disc list-inside">
              {importResult.warnings.map((w, i) => (
                <li key={i}>{w}</li>
              ))}
            </ul>
          )}
        </div>
      )}

      {loading ? (
        <div className="text-center py-12">
          <div className="inline-block w-8 h-8 border-2 border-accent border-t-transparent rounded-full animate-spin" />
        </div>
      ) : positions.length === 0 ? (
        <div className="text-center py-12 text-gray-600">
          <p className="text-lg">Todavía no tienes posiciones importadas</p>
          <p className="text-sm mt-2">Pulsa "Importar Excel" arriba para subir tu archivo</p>
        </div>
      ) : (
        <>
          {/* Summary KPIs */}
          {summary && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
              <div className="bg-bg-card border border-bg-border rounded-lg p-5">
                <p className="text-sm text-gray-500">Valor del portfolio</p>
                <p className="text-2xl font-bold text-white mt-1">
                  {formatCurrency(summary.total_value)}
                </p>
              </div>
              <div className="bg-bg-card border border-bg-border rounded-lg p-5">
                <p className="text-sm text-gray-500">Ganancia/pérdida no realizada</p>
                <p className={`text-2xl font-bold mt-1 ${getColor(summary.total_unrealized_pl)}`}>
                  {formatCurrency(summary.total_unrealized_pl)}
                </p>
                <p className={`text-xs mt-1 ${getColor(summary.total_unrealized_pl_pct)}`}>
                  {formatPercent(summary.total_unrealized_pl_pct, 1, true)}
                </p>
              </div>
              <div className="bg-bg-card border border-bg-border rounded-lg p-5">
                <p className="text-sm text-gray-500">Ganancia realizada</p>
                <p className={`text-2xl font-bold mt-1 ${getColor(summary.total_realized_pl)}`}>
                  {formatCurrency(summary.total_realized_pl)}
                </p>
              </div>
              <div className="bg-bg-card border border-bg-border rounded-lg p-5">
                <p className="text-sm text-gray-500">Nº posiciones</p>
                <p className="text-2xl font-bold text-white mt-1">{summary.num_positions}</p>
              </div>
            </div>
          )}

          {/* Positions table */}
          <div className="bg-bg-card border border-bg-border rounded-lg overflow-x-auto">
            <table className="w-full terminal-table text-sm">
              <thead>
                <tr className="text-left text-gray-500 border-b border-bg-border">
                  <th className="p-3">Ticker</th>
                  <th className="p-3 text-right">Cantidad</th>
                  <th className="p-3 text-right">Precio compra</th>
                  <th className="p-3 text-right">Precio actual</th>
                  <th className="p-3 text-right">Valor</th>
                  <th className="p-3 text-right">P/G no realizada</th>
                  <th className="p-3 text-right">P. objetivo</th>
                </tr>
              </thead>
              <tbody>
                {positions
                  .sort((a, b) => (b.market_value ?? 0) - (a.market_value ?? 0))
                  .map((p) => (
                    <tr key={p.id} className="hover:bg-bg-hover">
                      <td className="p-3 font-mono text-white">{p.ticker}</td>
                      <td className="p-3 text-right font-mono text-gray-300">
                        {p.quantity.toFixed(2)}
                      </td>
                      <td className="p-3 text-right font-mono text-gray-300">
                        {formatCurrency(p.avg_price)}
                      </td>
                      <td className="p-3 text-right font-mono text-white">
                        {formatCurrency(p.current_price)}
                      </td>
                      <td className="p-3 text-right font-mono text-white">
                        {formatCurrency(p.market_value)}
                      </td>
                      <td className={`p-3 text-right font-mono ${getColor(p.unrealized_pl)}`}>
                        {formatCurrency(p.unrealized_pl)}{" "}
                        <span className="text-xs">
                          ({formatPercent(p.unrealized_pl_pct, 1, true)})
                        </span>
                      </td>
                      <td className="p-3 text-right font-mono text-gray-400">
                        {formatCurrency(p.target_price)}
                      </td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
