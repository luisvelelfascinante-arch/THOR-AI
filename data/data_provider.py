"""
Adquisición de datos de mercado — responsabilidad ÚNICA: pedir velas a la
fuente configurada y devolverlas como DataFrame limpio (mismo formato sin
importar la fuente). NO calcula indicadores (eso es
indicators/indicator_bank.py), NO decide estrategia.

FUENTES SOPORTADAS (core.config.operativa.DATA_SOURCE):
  - "twelve_data" (default desde v4.0): API en la nube, no requiere
    ningún terminal abierto. Ver connectors/twelve_data_connector.py.
  - "mt5": requiere terminal MetaTrader 5 abierto en Windows con sesión
    iniciada. Ver connectors/mt5_connector.py.

Unifica lo que en v1 estaba duplicado entre obtener_indicadores() y
obtener_indicadores_confluencia() (cada una pedía velas y las procesaba por
separado con casi el mismo código).
"""

import logging

import pandas as pd

from core.config import operativa as O, estrategia as E

log = logging.getLogger("thor.data_provider")

_TIMEFRAME_A_TWELVE_DATA = {
    "M1": E.INTERVAL,  # el timeframe "principal" sigue el INTERVAL configurado
    "M5": "5min",
}


def _obtener_velas_mt5(symbol: str, timeframe: str, cantidad: int) -> pd.DataFrame | None:
    from connectors.mt5_connector import conectar, asegurar_simbolo, _cargar_mt5

    if not conectar():
        return None
    if not asegurar_simbolo(symbol):
        return None

    mt5 = _cargar_mt5()
    _timeframes_mt5 = {"M1": mt5.TIMEFRAME_M1, "M5": mt5.TIMEFRAME_M5}
    if timeframe not in _timeframes_mt5:
        raise ValueError(f"Timeframe no soportado: {timeframe}")

    try:
        velas = mt5.copy_rates_from_pos(symbol, _timeframes_mt5[timeframe], 0, cantidad)
    except Exception as exc:
        log.error("Error leyendo velas de %s (%s) vía MT5: %s", symbol, timeframe, exc)
        return None

    if velas is None or len(velas) == 0:
        log.warning("MT5 no devolvió velas para %s (%s).", symbol, timeframe)
        return None

    df = pd.DataFrame(velas)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    return df[["time", "open", "high", "low", "close"]]


def _obtener_velas_twelve_data(symbol: str, timeframe: str, cantidad: int) -> pd.DataFrame | None:
    from connectors.twelve_data_connector import obtener_velas_twelve_data

    interval = _TIMEFRAME_A_TWELVE_DATA.get(timeframe, E.INTERVAL)
    return obtener_velas_twelve_data(symbol, interval, cantidad)


def obtener_velas(symbol: str, timeframe: str, cantidad: int) -> pd.DataFrame | None:
    """Devuelve un DataFrame OHLC (columnas time/open/high/low/close) o
    None si no hay datos suficientes. Nunca devuelve un DataFrame parcial
    silenciosamente. La fuente real la decide
    core.config.operativa.DATA_SOURCE, transparente para quien llama."""
    if O.DATA_SOURCE == "mt5":
        return _obtener_velas_mt5(symbol, timeframe, cantidad)
    elif O.DATA_SOURCE == "twelve_data":
        return _obtener_velas_twelve_data(symbol, timeframe, cantidad)
    else:
        raise ValueError(
            f"DATA_SOURCE='{O.DATA_SOURCE}' no reconocido. Usa 'twelve_data' o 'mt5' en tu .env."
        )


def velas_disponibles(symbol: str, timeframe: str, cantidad: int) -> int:
    """Cuenta cuántas velas entrega la fuente configurada, sin fallar si hay error."""
    df = obtener_velas(symbol, timeframe, cantidad)
    return 0 if df is None else len(df)
