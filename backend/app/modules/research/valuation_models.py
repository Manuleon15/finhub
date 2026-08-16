"""Modelos de value investing — Graham, Magic Formula, Piotroski, Altman, Buffett.

Cada modelo da:
- score numérico
- verdict (STRONG_BUY / BUY / HOLD / SELL / STRONG_SELL)
- detalle explicativo
- weight por defecto para el scoring combinado
"""

from __future__ import annotations

import logging
import math
from typing import Any, Dict, List, Optional

from app.core.data_providers.yahoo import get_financials, get_ticker_info
from app.modules.research.analyzer import (
    FIELD_CANDIDATES,
    _find_field,
    _find_field_any_year,
    get_fcf,
    get_operating_cf,
    get_total_assets,
    get_total_debt,
    get_total_equity,
)

logger = logging.getLogger("finhub.valuation_models")

DEFAULT_WEIGHTS = {
    "graham": 0.15,
    "magic_formula": 0.20,
    "piotroski": 0.15,
    "altman_z": 0.10,
    "owner_earnings": 0.20,
    "dcf": 0.20,
}


# ========================== GRAHAM NUMBER ==========================

def graham_number(
    eps: Optional[float],
    bvps: Optional[float],
    current_price: Optional[float],
) -> Dict[str, Any]:
    """Graham Number = sqrt(22.5 × EPS × BVPS). Precio máximo a pagar."""
    if eps is None or bvps is None or eps <= 0 or bvps <= 0:
        return {
            "model": "graham_number",
            "error": "EPS o BVPS no disponible / negativo",
            "verdict": "HOLD",
        }

    graham = math.sqrt(22.5 * eps * bvps)

    upside = None
    if current_price and current_price > 0:
        upside = round((graham - current_price) / current_price, 4)

    if upside is not None and upside > 0.30:
        verdict = "STRONG_BUY"
    elif upside is not None and upside > 0.10:
        verdict = "BUY"
    elif upside is not None and upside > -0.10:
        verdict = "HOLD"
    elif upside is not None and upside > -0.30:
        verdict = "SELL"
    else:
        verdict = "STRONG_SELL"

    return {
        "model": "graham_number",
        "graham_number": round(graham, 2),
        "eps": eps,
        "bvps": bvps,
        "current_price": current_price,
        "upside_vs_current": upside,
        "upside_label": f"{upside * 100:+.1f}%" if upside is not None else "N/D",
        "verdict": verdict,
        "weight": DEFAULT_WEIGHTS["graham"],
        "explanation": (
            "Graham Number es el precio máximo que Benjamin Graham pagaría. "
            "sqrt(22.5 × EPS × BVPS). Stock > Graham = sobrevalorada según Graham."
        ),
    }


# ========================== MAGIC FORMULA ==========================

def magic_formula(info: Dict[str, Any], roic: Optional[float]) -> Dict[str, Any]:
    """Joel Greenblatt: high earnings yield + high ROIC.

    Earnings yield = E/P
    ROIC = Return on Invested Capital
    Rank: percentile sobre universo (sin cálculo complejo: heurístico).
    """
    pe = info.get("pe_ratio") or info.get("trailingPE")
    if pe is None or pe <= 0:
        return {
            "model": "magic_formula",
            "error": "P/E no disponible",
            "verdict": "HOLD",
        }

    earnings_yield = round(1 / pe, 4)
    roic_value = roic if roic is not None else 0

    # Heurística ojo verdeblattt: ambos > 0.05 es bueno
    if roic_value > 0.15 and earnings_yield > 0.07:
        verdict = "STRONG_BUY"
        confidence = "high"
    elif roic_value > 0.10 and earnings_yield > 0.05:
        verdict = "BUY"
        confidence = "good"
    elif roic_value > 0.05 and earnings_yield > 0.03:
        verdict = "HOLD"
        confidence = "fair"
    elif roic_value > 0:
        verdict = "HOLD"
        confidence = "below_average"
    else:
        verdict = "SELL"
        confidence = "low"

    return {
        "model": "magic_formula",
        "earnings_yield": earnings_yield,
        "earnings_yield_label": f"{earnings_yield * 100:.1f}%",
        "roic": roic_value,
        "roic_label": f"{roic_value * 100:.1f}%" if roic_value is not None else "N/D",
        "verdict": verdict,
        "confidence": confidence,
        "weight": DEFAULT_WEIGHTS["magic_formula"],
        "explanation": (
            "Magic Formula (Joel Greenblatt): combina earnings yield alto "
            "(acción barata vs earnings) con ROIC alto (empresa rentable sobre capital)."
        ),
    }


# ========================== PIOTROSKI F-SCORE ==========================

def _fcf_positive(financials: Dict[str, Any]) -> Optional[bool]:
    fcf = get_fcf(financials, 0)
    if fcf is None:
        return None
    return fcf > 0


def _roa_positive(financials: Dict[str, Any]) -> Optional[bool]:
    ni = _find_field_any_year(financials, "income_statement", FIELD_CANDIDATES["net_income"])
    assets = get_total_assets(financials, 0)
    if ni is None or assets is None or assets == 0:
        return None
    return (ni / assets) > 0


def _roa_improving(
    financials: Dict[str, Any],
    info: Dict[str, Any],
) -> Optional[bool]:
    current_fq = info.get("financial_quality") or {}
    rg = current_fq.get("return_on_assets")
    if rg is None:
        info_roa = info.get("returnOnAssets")
        if info_roa is not None:
            return info_roa > 0  # heurística simple
        return None
    return rg > 0  # heurística: ROA positivo ya indica mejora


def _cfo_positive(financials: Dict[str, Any]) -> Optional[bool]:
    ocf = get_operating_cf(financials, 0)
    if ocf is None:
        return None
    return ocf > 0


def _cfo_gt_ni(financials: Dict[str, Any]) -> Optional[bool]:
    ocf = get_operating_cf(financials, 0)
    ni = _find_field_any_year(financials, "income_statement", FIELD_CANDIDATES["net_income"])
    if ocf is None or ni is None:
        return None
    return ocf > ni


def _debt_decreasing(financials: Dict[str, Any]) -> Optional[bool]:
    """Detecta si la deuda está bajando vs año anterior."""
    debt_curr = get_total_debt(financials, 0)
    debt_prev = get_total_debt(financials, 1)
    if debt_curr is None or debt_prev is None:
        return None
    return debt_curr <= debt_prev


def _current_ratio_improving(financials: Dict[str, Any]) -> Optional[bool]:
    """Detecta si el current ratio mejora."""
    ca_curr = _find_field_any_year(financials, "balance_sheet", FIELD_CANDIDATES["current_assets"])
    cl_curr = _find_field(financials, "balance_sheet", FIELD_CANDIDATES["current_liabilities"], 0)
    ca_prev = _find_field(financials, "balance_sheet", FIELD_CANDIDATES["current_assets"], 1)
    cl_prev = _find_field(financials, "balance_sheet", FIELD_CANDIDATES["current_liabilities"], 1)
    if ca_curr is None or cl_curr is None or cl_curr == 0:
        return None
    if ca_prev is None or cl_prev is None or cl_prev == 0:
        return None
    return (ca_curr / cl_curr) >= (ca_prev / cl_prev)


def _shares_dilution_check(financials: Dict[str, Any]) -> Optional[bool]:
    """Detecta si se están emitiendo nuevas acciones."""
    shares_curr = _find_field_any_year(
        financials, "income_statement", FIELD_CANDIDATES["shares_outstanding"]
    )
    shares_prev = _find_field(
        financials, "income_statement", FIELD_CANDIDATES["shares_outstanding"], 1
    )
    if shares_curr is None or shares_prev is None:
        return None
    return shares_curr <= shares_prev


def _gross_margin_improving(financials: Dict[str, Any]) -> Optional[bool]:
    """Detecta si el gross margin mejora."""
    gp_curr = _find_field_any_year(
        financials, "income_statement", FIELD_CANDIDATES["gross_profit"]
    )
    rev_curr = _find_field(financials, "income_statement", FIELD_CANDIDATES["revenue"], 0)
    gp_prev = _find_field(
        financials, "income_statement", FIELD_CANDIDATES["gross_profit"], 1
    )
    rev_prev = _find_field(financials, "income_statement", FIELD_CANDIDATES["revenue"], 1)
    if gp_curr is None or rev_curr is None or rev_curr == 0:
        return None
    if gp_prev is None or rev_prev is None or rev_prev == 0:
        return None
    return (gp_curr / rev_curr) >= (gp_prev / rev_prev)


def _asset_turnover_improving(financials: Dict[str, Any]) -> Optional[bool]:
    """Asset turnover = Revenue / Total Assets. Compara año a año."""
    rev_curr = _find_field(financials, "income_statement", FIELD_CANDIDATES["revenue"], 0)
    assets_curr = get_total_assets(financials, 0)
    rev_prev = _find_field(financials, "income_statement", FIELD_CANDIDATES["revenue"], 1)
    assets_prev = get_total_assets(financials, 1)
    if rev_curr is None or assets_curr is None or assets_curr == 0:
        return None
    if rev_prev is None or assets_prev is None or assets_prev == 0:
        return None
    return (rev_curr / assets_curr) >= (rev_prev / assets_prev)


def piotroski_f_score(
    financials: Dict[str, Any], info: Dict[str, Any]
) -> Dict[str, Any]:
    """Piotroski F-Score (0-9): 9 criterios de fortaleza financiera."""
    tests = [
        ("fcf_positive", _fcf_positive(financials)),
        ("roa_positive", _roa_positive(financials)),
        ("roa_improving", _roa_improving(financials, info)),
        ("cfo_positive", _cfo_positive(financials)),
        ("cfo_gt_ni", _cfo_gt_ni(financials)),
        ("debt_decreasing", _debt_decreasing(financials)),
        ("current_ratio_improving", _current_ratio_improving(financials)),
        ("no_share_dilution", _shares_dilution_check(financials)),
        ("gross_margin_improving", _gross_margin_improving(financials)),
    ]
    # Asset turnover requiere año anterior y actual — añadimos si hay datos
    at = _asset_turnover_improving(financials)
    if at is not None:
        tests.append(("asset_turnover_improving", at))

    score = sum(1 for _, val in tests if val is True)
    max_score = len(tests)
    available = sum(1 for _, val in tests if val is not None)

    if score >= 8 and available >= 8:
        verdict = "STRONG_BUY"
    elif score >= 6:
        verdict = "BUY"
    elif score >= 4:
        verdict = "HOLD"
    elif score >= 2:
        verdict = "SELL"
    else:
        verdict = "STRONG_SELL"

    breakdown = {
        name: "PASS" if val is True else ("FAIL" if val is False else "N/D")
        for name, val in tests
    }

    return {
        "model": "piotroski_f_score",
        "score": score,
        "max_score": max_score,
        "available": available,
        "verdict": verdict,
        "weight": DEFAULT_WEIGHTS["piotroski"],
        "breakdown": breakdown,
        "explanation": (
            "Piotroski F-Score: 9 criterios de fortaleza financiera. "
            "Cada uno PASS = 1 punto. 8-9 = empresa muy fuerte, "
            "0-2 = empresa débil (probablemente distressed)."
        ),
    }


# ========================== ALTMAN Z-SCORE ==========================

def altman_z_score(
    financials: Dict[str, Any], info: Dict[str, Any]
) -> Dict[str, Any]:
    """Altman Z-Score: probabilidad de bancarrota en 2 años.

    Z = 1.2*A + 1.4*B + 3.3*C + 0.6*D + 1.0*E

    A = Working Capital / Total Assets
    B = Retained Earnings / Total Assets
    C = EBIT / Total Assets
    D = Market Cap / Total Liabilities
    E = Sales / Total Assets
    """
    try:
        current_assets = _find_field_any_year(
            financials, "balance_sheet", FIELD_CANDIDATES["current_assets"]
        )
        current_liabilities = _find_field_any_year(
            financials, "balance_sheet", FIELD_CANDIDATES["current_liabilities"]
        )
        if current_assets is None or current_liabilities is None:
            return {
                "model": "altman_z",
                "error": "Datos insufficient",
                "verdict": "HOLD",
            }

        wc = current_assets - current_liabilities
        total_assets = get_total_assets(financials, 0)
        if total_assets is None or total_assets == 0:
            return {
                "model": "altman_z",
                "error": "Total assets no disponible",
                "verdict": "HOLD",
            }

        retained_earnings = _find_field_any_year(
            financials, "balance_sheet", ["Retained Earnings", "RetainedEarnings"]
        )
        if retained_earnings is None:
            total_equity = get_total_equity(financials, 0) or 0
            retained_earnings = total_equity * 0.5  # Heurística: 50% del equity es retained earnings

        ebit = _find_field_any_year(
            financials, "income_statement", FIELD_CANDIDATES["ebit"]
        )
        if ebit is None:
            op_margin = info.get("operatingMargins")
            revenue = get_revenue_safe(info, financials)
            if op_margin is not None and revenue is not None:
                ebit = op_margin * revenue

        if ebit is None:
            return {
                "model": "altman_z",
                "error": "EBIT no disponible",
                "verdict": "HOLD",
            }

        market_cap = info.get("market_cap") or 0
        # Total liabilities = Total assets - equity
        total_equity = get_total_equity(financials, 0) or 0
        total_liabilities = total_assets - total_equity

        if total_liabilities == 0:
            return {
                "model": "altman_z",
                "error": "Liabilities no disponible",
                "verdict": "HOLD",
            }

        revenue = get_revenue_safe(info, financials) or 0

        A = wc / total_assets
        B = retained_earnings / total_assets
        C = ebit / total_assets
        D = market_cap / total_liabilities
        E = revenue / total_assets

        z = 1.2 * A + 1.4 * B + 3.3 * C + 0.6 * D + 1.0 * E

        if z > 2.99:
            verdict = "STRONG_BUY"
            zone = "Safe Zone"
        elif z > 1.81:
            verdict = "HOLD"
            zone = "Grey Zone"
        else:
            verdict = "STRONG_SELL"
            zone = "Distress Zone"

        return {
            "model": "altman_z",
            "z_score": round(z, 2),
            "components": {
                "working_capital_to_assets": round(A, 4),
                "retained_earnings_to_assets": round(B, 4),
                "ebit_to_assets": round(C, 4),
                "market_cap_to_liabilities": round(D, 4),
                "sales_to_assets": round(E, 4),
            },
            "zone": zone,
            "verdict": verdict,
            "weight": DEFAULT_WEIGHTS["altman_z"],
            "explanation": (
                "Altman Z-Score predice bancarrota a 2 años. Z>2.99 seguro, "
                "1.81-2.99 grey zone, <1.81 distress zone (probable bancarrota)."
            ),
        }
    except Exception as e:
        return {
            "model": "altman_z",
            "error": str(e),
            "verdict": "HOLD",
        }


def get_revenue_safe(info: Dict[str, Any], financials: Dict[str, Any]) -> Optional[float]:
    from app.modules.research.analyzer import get_revenue
    rev = get_revenue(financials, 0)
    if rev is None:
        rev = info.get("totalRevenue")
    return rev


# ========================== OWNER EARNINGS (Buffett) ==========================

def owner_earnings(
    financials: Dict[str, Any], info: Dict[str, Any]
) -> Dict[str, Any]:
    """Owner Earnings = Net Income + D&A - capex - working capital increases.

    Aproximación práctica: OCF - mantenimiento capex (sin working capital changes precisos).
    """
    ocf = get_operating_cf(financials, 0)
    capex = None
    from app.modules.research.analyzer import get_capex
    capex = get_capex(financials, 0)

    if ocf is None:
        # Fallback: net income proxy
        ni = _find_field_any_year(
            financials, "income_statement", FIELD_CANDIDATES["net_income"]
        )
        if ni is None or ni <= 0:
            return {
                "model": "owner_earnings",
                "error": "OCF y Net Income no disponibles",
                "verdict": "HOLD",
            }
        owner_earnings_value = ni * 0.75
        source = "estimated_75pct_net_income"
    else:
        if capex is None:
            owner_earnings_value = ocf
            source = "ocf_no_capex"
        else:
            owner_earnings_value = ocf - capex
            source = "ocf_minus_capex"

    market_cap = info.get("market_cap")
    if not market_cap or market_cap == 0:
        yield_pct = None
    else:
        yield_pct = round(owner_earnings_value / market_cap, 4)

    if yield_pct is not None and yield_pct > 0.08:
        verdict = "STRONG_BUY"
    elif yield_pct is not None and yield_pct > 0.05:
        verdict = "BUY"
    elif yield_pct is not None and yield_pct > 0.03:
        verdict = "HOLD"
    else:
        verdict = "SELL"

    return {
        "model": "owner_earnings",
        "owner_earnings": round(owner_earnings_value, 0),
        "source": source,
        "yield_pct": yield_pct,
        "yield_label": f"{yield_pct * 100:.1f}%" if yield_pct is not None else "N/D",
        "verdict": verdict,
        "weight": DEFAULT_WEIGHTS["owner_earnings"],
        "explanation": (
            "Owner Earnings (Buffett): dinero que el dueño podría llevarse "
            "sin afectar la operación del negocio = OCF - mantenimiento capex."
        ),
    }


# ========================== COMBINADOR ==========================

def run_all_valuation_models(
    ticker: str,
    analyzer_data: Dict[str, Any],
    dcf_data: Optional[Dict[str, Any]] = None,
    enabled_models: Optional[List[str]] = None,
    custom_weights: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    """Ejecuta todos los modelos y devuelve veredicto combinado.

    enabled_models: lista de modelos a usar. Si None, usa todos.
    custom_weights: pesos custom por modelo (deben sumar 1.0).
    """
    info = analyzer_data.get("raw_info", {}) or {}
    financials = analyzer_data.get("raw_financials", {}) or {}
    eps = info.get("eps")
    bvps = info.get("book_value_per_share")
    current_price = info.get("current_price") or info.get("price")
    roic = analyzer_data.get("financial_quality", {}).get("roic")

    all_models = ["graham", "magic_formula", "piotroski", "altman_z", "owner_earnings", "dcf"]
    enabled = enabled_models if enabled_models else all_models

    results = {}

    if "graham" in enabled:
        results["graham"] = graham_number(eps, bvps, current_price)
    if "magic_formula" in enabled:
        results["magic_formula"] = magic_formula(info, roic)
    if "piotroski" in enabled:
        results["piotroski"] = piotroski_f_score(financials, info)
    if "altman_z" in enabled:
        results["altman_z"] = altman_z_score(financials, info)
    if "owner_earnings" in enabled:
        results["owner_earnings"] = owner_earnings(financials, info)
    if "dcf" in enabled and dcf_data:
        # Convertir DCF al formato de modelo
        prob_value = dcf_data.get("probabilistic_value")
        upside = None
        if prob_value and current_price and current_price > 0:
            upside = round((prob_value - current_price) / current_price, 4)
        if upside is not None and upside > 0.25:
            verdict = "STRONG_BUY"
        elif upside is not None and upside > 0.10:
            verdict = "BUY"
        elif upside is not None and upside > -0.10:
            verdict = "HOLD"
        elif upside is not None and upside > -0.25:
            verdict = "SELL"
        else:
            verdict = "STRONG_SELL"
        results["dcf"] = {
            "model": "dcf_intrinsic",
            "intrinsic_value": prob_value,
            "current_price": current_price,
            "upside_vs_current": upside,
            "upside_label": f"{upside * 100:+.1f}%" if upside is not None else "N/D",
            "margin_of_safety_price": dcf_data.get("margin_of_safety_price"),
            "verdict": verdict,
            "weight": DEFAULT_WEIGHTS["dcf"],
        }

    # Pesos
    weights = {m: DEFAULT_WEIGHTS.get(m, 0.0) for m in results}
    if custom_weights:
        weights.update(custom_weights)

    # Normalizar para que sumen 1
    total_w = sum(weights.values())
    if total_w > 0:
        weights = {k: v / total_w for k, v in weights.items()}

    # Score combinado ponderado
    verdict_scores = {
        "STRONG_BUY": 5,
        "BUY": 4,
        "HOLD": 3,
        "SELL": 2,
        "STRONG_SELL": 1,
    }
    composite = 0.0
    for model_name, r in results.items():
        verdict = r.get("verdict", "HOLD")
        w = weights.get(model_name, 0)
        composite += verdict_scores.get(verdict, 3) * w

    # Convertir a score 0-100 y verdict final
    composite_score = round((composite - 1) / 4 * 100, 1)

    if composite_score >= 80:
        final_verdict = "STRONG_BUY"
        action = "STRONG_BUY"
        label = "Compra fuerte"
        color = "green"
    elif composite_score >= 65:
        final_verdict = "BUY"
        action = "BUY"
        label = "Comprar"
        color = "green"
    elif composite_score >= 50:
        final_verdict = "HOLD"
        action = "HOLD"
        label = "Mantener"
        color = "yellow"
    elif composite_score >= 35:
        final_verdict = "SELL"
        action = "SELL"
        label = "Vender"
        color = "red"
    else:
        final_verdict = "STRONG_SELL"
        action = "STRONG_SELL"
        label = "Vender / Evitar"
        color = "red"

    # Explicación resumida
    model_verdicts = {m: r["verdict"] for m, r in results.items()}
    buy_count = sum(1 for v in model_verdicts.values() if v in ("BUY", "STRONG_BUY"))
    sell_count = sum(1 for v in model_verdicts.values() if v in ("SELL", "STRONG_SELL"))

    return {
        "models": results,
        "weights": weights,
        "composite_score": composite_score,
        "composite_verdict": {
            "action": action,
            "label": label,
            "color": color,
            "verdict": final_verdict,
            "buy_signals": buy_count,
            "sell_signals": sell_count,
            "explanation": (
                f"{buy_count} modelos dan BUY, {sell_count} dan SELL. "
                f"Score combinado {composite_score:.0f}/100."
            ),
        },
    }
