"""Importador del Excel de portfolio (formato 'DATOS INVERSIONES' + 'MOVIMIENTOS').

Diseñado para el Excel personal de seguimiento de inversiones: busca las
columnas por NOMBRE (no por posición), así que si añades/mueves columnas en
tu Excel no rompe el importador — solo falla si renombras una columna clave.

Uso:
    from app.modules.portfolio.importer import parse_portfolio_excel
    result = parse_portfolio_excel(file_bytes)
    # result["positions"] -> list[dict] listas para upsert en DB
    # result["transactions"] -> list[dict] (si hay hoja de movimientos)
    # result["warnings"] -> avisos de filas/columnas que no se pudieron leer
"""

from __future__ import annotations

import io
import logging
from typing import Any, Dict, List

import openpyxl

logger = logging.getLogger("finhub.portfolio.importer")

# Nombre de la hoja con las posiciones actuales. Ajusta aquí si renombras la pestaña.
POSITIONS_SHEET_CANDIDATES = ["DATOS INVERSIONES", "POSICIONES", "PORTFOLIO"]

# Mapeo columna Excel -> campo del modelo Position.
# Se busca por coincidencia flexible (mayúsculas/tildes normalizadas).
POSITION_COLUMN_MAP = {
    "TICKER": "ticker",
    "NOMBRE DEL ACTIVO": "name",
    "CANTIDAD": "quantity",
    "PRECIO DE COMPRA": "avg_price",
    "PRECIO ACTUAL": "current_price",
    "PRECIO OBJETIVO": "target_price",
    "BETA": "beta",
    "DIVIDENDO X ACCION": "dividend_per_share",
    "P/G REALIZADAS": "realized_pl",
}

# Hojas de movimientos: se detectan por prefijo (soporta "MOVIMIENTOS 2025",
# "MOVIMIENTOS 2026", etc. — cualquier año).
TRANSACTIONS_SHEET_PREFIX = "MOVIMIENTOS"


def _normalize(s: Any) -> str:
    """Normaliza un nombre de columna para comparar sin acentos/mayúsculas."""
    if s is None:
        return ""
    s = str(s).strip().upper()
    replacements = {"Á": "A", "É": "E", "Í": "I", "Ó": "O", "Ú": "U", "Ñ": "N"}
    for a, b in replacements.items():
        s = s.replace(a, b)
    return s


def _find_sheet(wb: openpyxl.Workbook, candidates: List[str]) -> str | None:
    normalized_names = {_normalize(n): n for n in wb.sheetnames}
    for cand in candidates:
        norm = _normalize(cand)
        if norm in normalized_names:
            return normalized_names[norm]
    return None


def _is_number(v: Any) -> bool:
    if isinstance(v, (int, float)):
        return True
    return False


def parse_positions_sheet(wb: openpyxl.Workbook, warnings: List[str]) -> List[Dict[str, Any]]:
    sheet_name = _find_sheet(wb, POSITIONS_SHEET_CANDIDATES)
    if sheet_name is None:
        warnings.append(
            f"No se encontró una hoja de posiciones (probé: {POSITIONS_SHEET_CANDIDATES}). "
            "No se importó ninguna posición."
        )
        return []

    ws = wb[sheet_name]
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        return []

    header = rows[0]
    # header_idx: nombre de campo del modelo -> índice de columna
    header_idx: Dict[str, int] = {}
    for col_idx, col_name in enumerate(header):
        norm = _normalize(col_name)
        for excel_col, field in POSITION_COLUMN_MAP.items():
            if _normalize(excel_col) == norm:
                header_idx[field] = col_idx

    if "ticker" not in header_idx:
        warnings.append(
            f"La hoja '{sheet_name}' no tiene columna TICKER. No se importó nada."
        )
        return []

    positions: List[Dict[str, Any]] = []
    for row_num, row in enumerate(rows[1:], start=2):
        ticker = row[header_idx["ticker"]] if header_idx["ticker"] < len(row) else None
        if not ticker or not isinstance(ticker, str):
            continue  # fila vacía o sin ticker válido

        pos: Dict[str, Any] = {"ticker": ticker.strip().upper()}
        for field, col_idx in header_idx.items():
            if field == "ticker" or col_idx >= len(row):
                continue
            value = row[col_idx]
            if field == "name":
                # Algunas plantillas tienen fórmulas VLOOKUP rotas (#VALUE!) en esta
                # columna; si no es texto usable, se deja en None y listo.
                pos[field] = value if isinstance(value, str) and not value.startswith("#") else None
            elif _is_number(value):
                pos[field] = float(value)
            else:
                pos[field] = None

        if pos.get("quantity") is None:
            warnings.append(f"Fila {row_num} ({pos['ticker']}): sin CANTIDAD, se importó como 0.")
            pos["quantity"] = 0.0

        positions.append(pos)

    return positions


def parse_transactions_sheets(wb: openpyxl.Workbook, warnings: List[str]) -> List[Dict[str, Any]]:
    """Lee todas las hojas 'MOVIMIENTOS <año>'. Formato esperado (según tu Excel):
    columna A = P/G realizada, columna B = ticker. Sin fecha ni cantidad explícita
    en tu plantilla actual, así que se importan como venta con solo P/G.
    """
    transactions: List[Dict[str, Any]] = []

    for sheet_name in wb.sheetnames:
        if not _normalize(sheet_name).startswith(TRANSACTIONS_SHEET_PREFIX):
            continue

        ws = wb[sheet_name]
        rows = list(ws.iter_rows(values_only=True))
        if not rows:
            continue

        # La primera fila suele ser un título ("Ventas 2025"), no cabecera real.
        for row_num, row in enumerate(rows, start=1):
            if len(row) < 2:
                continue
            realized_pl_raw, ticker_raw = row[0], row[1]

            if not isinstance(ticker_raw, str) or not ticker_raw.strip():
                continue
            # Filtra la fila de título tipo ('Ventas 2025', None, ...)
            if not _is_number(realized_pl_raw):
                continue

            transactions.append(
                {
                    "ticker": ticker_raw.strip().upper(),
                    "tx_type": "sell",
                    "realized_pl": float(realized_pl_raw),
                    "quantity": None,
                    "price": None,
                    "date": None,
                    "notes": f"Importado de hoja '{sheet_name}', fila {row_num}",
                }
            )

    return transactions


def parse_portfolio_excel(file_bytes: bytes) -> Dict[str, Any]:
    """Parsea el Excel completo. Devuelve positions, transactions y warnings."""
    warnings: List[str] = []

    try:
        wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True)
    except Exception as e:
        return {
            "positions": [],
            "transactions": [],
            "warnings": [],
            "error": f"No se pudo leer el archivo Excel: {e}",
        }

    positions = parse_positions_sheet(wb, warnings)
    transactions = parse_transactions_sheets(wb, warnings)

    logger.info(
        f"Excel parseado: {len(positions)} posiciones, {len(transactions)} transacciones, "
        f"{len(warnings)} avisos."
    )

    return {
        "positions": positions,
        "transactions": transactions,
        "warnings": warnings,
    }
