/** Utilidades de formateo: moneda, porcentajes, números grandes. */

export function formatCurrency(
  value: number | null | undefined,
  currency: string = "USD",
  decimals: number = 2
): string {
  if (value === null || value === undefined) return "N/A";
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency,
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(value);
}

export function formatPercent(
  value: number | null | undefined,
  decimals: number = 1,
  withSign: boolean = false
): string {
  if (value === null || value === undefined) return "N/A";
  const pct = (value * 100).toFixed(decimals);
  const sign = withSign && value > 0 ? "+" : "";
  return `${sign}${pct}%`;
}

export function formatNumber(value: number | null | undefined): string {
  if (value === null || value === undefined) return "N/A";
  if (Math.abs(value) >= 1e12) return `${(value / 1e12).toFixed(2)}T`;
  if (Math.abs(value) >= 1e9) return `${(value / 1e9).toFixed(2)}B`;
  if (Math.abs(value) >= 1e6) return `${(value / 1e6).toFixed(2)}M`;
  if (Math.abs(value) >= 1e3) return `${(value / 1e3).toFixed(2)}K`;
  return value.toFixed(2);
}

export function formatPrice(value: number | null | undefined): string {
  return formatCurrency(value, "USD", 2);
}

export function getColor(value: number | null | undefined): string {
  if (value === null || value === undefined) return "text-gray-400";
  return value >= 0 ? "text-success" : "text-danger";
}

