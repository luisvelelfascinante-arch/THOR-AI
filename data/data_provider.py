"""
Adquisición de datos de mercado — responsabilidad ÚNICA: pedir velas a MT5
y devolverlas como DataFrame limpio. NO calcula indicadores (eso es
indicators/indicator_bank.py), NO decide estrategia.

Unifica lo que en v1 estaba duplicado entre obtener_indicadores() y
obtener_indicadores_confluencia() (cada una pedía velas y las procesaba por
separado con casi el mismo código).
"""

import logging

import pandas as pd
import MetaTrader5 as mt5

from connectors.mt5_connector import conectar, asegurar_simbolo

log = logging.getLogger("thor.data_provider")

_TIMEFRAMES = {
    "M1": mt5.TIMEFRAME_M1,
    "M5": mt5.TIMEFRAME_M5,
}


def obtener_velas(symbol: str, timeframe: str, cantidad: int) -> pd.DataFrame | None:
    """Devuelve un DataFrame OHLCV o None si no hay datos suficientes.
    Nunca devuelve un DataFrame parcial silenciosamente."""
    if not conectar():
        return None
    if not asegurar_simbolo(symbol):
        return None
    if timeframe not in _TIMEFRAMES:
        raise ValueError(f"Timeframe no soportado: {timeframe}")

    try:
        velas = mt5.copy_rates_from_pos(symbol, _TIMEFRAMES[timeframe], 0, cantidad)
    except Exception as exc:
        log.error("Error leyendo velas de %s (%s): %s", symbol, timeframe, exc)
        return None

    if velas is None or len(velas) == 0:
        log.warning("MT5 no devolvió velas para %s (%s).", symbol, timeframe)
        return None

    df = pd.DataFrame(velas)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    return df


def velas_disponibles(symbol: str, timeframe: str, cantidad: int) -> int:
    """Cuenta cuántas velas entrega MT5 realmente, sin fallar si hay error."""
    df = obtener_velas(symbol, timeframe, cantidad)
    return 0 if df is None else len(df)
