/** Tipos del módulo Portfolio Tracker.
 * Archivo separado para no tocar lib/types.ts existente — impórtalo donde lo necesites,
 * o copia estas interfaces dentro de lib/types.ts si prefieres tenerlo todo junto.
 */

export interface Position {
  id: number;
  ticker: string;
  name: string | null;
  quantity: number;
  avg_price: number | null;
  current_price: number | null;
  target_price: number | null;
  beta: number | null;
  dividend_per_share: number | null;
  realized_pl: number | null;
  currency: string;
  market_value: number | null;
  cost_basis: number | null;
  unrealized_pl: number | null;
  unrealized_pl_pct: number | null;
}

export interface PortfolioSummary {
  num_positions: number;
  total_value: number;
  total_cost: number;
  total_unrealized_pl: number;
  total_unrealized_pl_pct: number | null;
  total_realized_pl: number;
}

export interface ImportResult {
  positions_imported: number;
  transactions_imported: number;
  warnings: string[];
}
