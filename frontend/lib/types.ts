/** Tipos compartidos entre frontend y backend. */

export interface BusinessOverview {
  name: string;
  ticker: string;
  sector: string;
  industry: string;
  description: string;
  country: string;
  website: string;
  employees: number | null;
  market_cap: number | null;
  price: number | null;
  currency: string;
}

export interface FinancialQuality {
  roic: number | null;
  roic_label: string;
  fcf_margin: number | null;
  fcf_margin_label: string;
  debt_to_equity: number | null;
  debt_label: string;
  gross_margin: number | null;
  gross_margin_label: string;
  revenue_growth: number | null;
  revenue_growth_label: string;
  fcf_growth: number | null;
  fcf_growth_label: string;
  current_ratio: number | null;
  operating_margin: number | null;
  profit_margin: number | null;
  return_on_equity: number | null;
}

export interface Valuation {
  pe_ratio: number | null;
  forward_pe: number | null;
  pb_ratio: number | null;
  ev_to_revenue: number | null;
  ev_to_ebitda: number | null;
  peg_ratio: number | null;
  earnings_yield: number | null;
  fcf_yield: number | null;
  dividend_yield: number | null;
  target_mean_price: number | null;
  analyst_recommendation: string | null;
}

export interface DCFScenario {
  price_per_share: number;
  wacc: number;
  wacc_label: string;
  terminal_growth: number;
  terminal_growth_label: string;
  projected_fcfs: number[];
  terminal_value: number;
  pv_fcf: number;
  pv_terminal: number;
  enterprise_value: number;
  equity_value: number;
  net_debt: number;
  upside_vs_current: number | null;
  upside_label: string;
}

export interface DCFResult {
  ticker: string;
  current_price: number | null;
  base_fcf: number;
  shares_outstanding: number;
  fcf_growth_historical: number | null;
  revenue_growth: number | null;
  scenarios: {
    bear: DCFScenario;
    base: DCFScenario;
    bull: DCFScenario;
  };
  model_assumptions: {
    risk_free_rate: number;
    market_risk_premium: number;
    tax_rate: number;
    projection_years: number;
  };
  error?: string;
}

export interface ScoreBreakdown {
  [key: string]: {
    points: number;
    max: number;
    label: string;
  };
}

export interface Scoring {
  quality_score: { score: number; max: number; breakdown: ScoreBreakdown };
  valuation_score: { score: number; max: number; breakdown: ScoreBreakdown };
  total_score: number;
  max_score: number;
  recommendation: {
    action: string;
    label: string;
    color: string;
    description: string;
  };
}

export interface AnalysisResult {
  ticker: string;
  business_overview: BusinessOverview;
  financial_quality: FinancialQuality;
  valuation: Valuation;
  dcf: DCFResult;
  scoring: Scoring;
}

