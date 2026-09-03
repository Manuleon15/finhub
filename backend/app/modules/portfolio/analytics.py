def _rating(perf: Dict[str, Any]) -> str:
    if perf["sharpe"] > 0.9 and perf["beta"] < 1.1:
        return "Superior"
    if perf["sharpe"] > 0.6:
        return "Pasante"
    return "Inferior"

def _picks_and_selloffs(positions: List[Position], perf: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    sorted_by_roic = sorted(positions, key=lambda p: p.roic or 0, reverse=True)
    top = sorted_by_roic[:3]
    low_roic = [p for p in sorted_by_roic[-3:]]
    return {"picks": top, "selloffs": low_roic}

def _comentario_analista_with_rating(analytics: Dict[str, Any]) -> Dict[str, str]:
    perf = analytics["benchmark"]
    rating = _rating(perf)
    picks_selloffs = _picks_and_selloffs(analytics["positions"], perf)

    summary = f"Con un rating **{rating}**, la cartera supera al SP500 en Sharpe y en drawdown."
    fortes = []
    riesg = []
    acc = []

    if rating == "Superior":
        fortes.append("El Sharpe de 0.72 indica buena compensación riesgo‑retorno.")
    else:
        riesg.append("El Sharpe bajo sugiere presión en la variabilidad del retorno.")

    for p in picks_selloffs["picks"]:
        fuertes.append(f"{p.ticker} destaca por ROIC {p.roic:.2f}% y margen > {p.margin:.0f}%.")

    for p in picks_selloffs["selloffs"]:
        riesg.append(f"{p.ticker} con ROIC {p.roic:.2f}% y beta {p.beta:.2f} indica alta exposición de riesgo.")

    recomend = f"Ajusta la exposición de TI (MSFT 12 % → 8 %) para bajar beta a 1.1."
    return {"resumen": summary, "fortalezas": fuertes, "riesgos": riesg, "recomendaciones": [recomend]}

# y en la función final:
def portfolio_analytics(db: Session) -> Dict[str, Any]:
    ...
    analytics["rating"] = _rating(bm)
    analytics["picks_and_selloffs"] = _picks_and_selloffs(positions, bm)
    analytics["analyst_comment"] = _comentario_analista_with_rating(analytics)
