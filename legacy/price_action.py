"""
Confirmación de Price Action.

*** IMPORTANTE ***
El material del curso del profesor Juan Fernández no llegó adjunto (solo
llegó el código). Los patrones de esta versión son las 3 confirmaciones de
price action más estándar de la industria (envolvente, pin bar/rechazo,
vela de momentum por tamaño de cuerpo). Esto es un placeholder funcional,
NO una transcripción de la metodología oficial del curso.

Cuando tengas el material del profesor, dime exactamente qué patrón(es) usa
y en qué vela(s) se confirma, y reemplazo esta función sin tocar el resto
del sistema (scanner y strategy solo esperan +1 / -1 / 0 de aquí).
"""

import pandas as pd

from core import config


def _cuerpo(vela) -> float:
    return abs(vela["close"] - vela["open"])


def _rango(vela) -> float:
    return vela["high"] - vela["low"]


def _es_alcista(vela) -> bool:
    return vela["close"] > vela["open"]


def _envolvente(anterior, actual) -> int:
    """Vela envolvente alcista (+1) o bajista (-1)."""
    if _es_alcista(actual) and not _es_alcista(anterior):
        if actual["close"] >= anterior["open"] and actual["open"] <= anterior["close"]:
            return 1
    if not _es_alcista(actual) and _es_alcista(anterior):
        if actual["open"] >= anterior["close"] and actual["close"] <= anterior["open"]:
            return -1
    return 0


def _pin_bar(vela) -> int:
    """Rechazo con mecha larga: alcista (+1) o bajista (-1)."""
    rango = _rango(vela)
    if rango <= 0:
        return 0

    cuerpo = _cuerpo(vela)
    mecha_inferior = min(vela["open"], vela["close"]) - vela["low"]
    mecha_superior = vela["high"] - max(vela["open"], vela["close"])

    if mecha_inferior >= rango * 0.6 and cuerpo <= rango * 0.35:
        return 1
    if mecha_superior >= rango * 0.6 and cuerpo <= rango * 0.35:
        return -1
    return 0


def _momentum(vela) -> int:
    """Vela de cuerpo dominante (>=70% del rango): a favor de su dirección."""
    rango = _rango(vela)
    if rango <= 0:
        return 0
    if _cuerpo(vela) / rango >= 0.7:
        return 1 if _es_alcista(vela) else -1
    return 0


def confirmar_price_action(df_m1: pd.DataFrame) -> int:
    """
    Devuelve:
        1  -> price action confirma dirección alcista (CALL)
       -1  -> price action confirma dirección bajista (PUT)
        0  -> sin confirmación clara
    Usa las 2 últimas velas M1 cerradas.
    """
    if df_m1 is None or len(df_m1) < 2:
        return 0

    anterior = df_m1.iloc[-2]
    actual = df_m1.iloc[-1]

    señales = [
        _envolvente(anterior, actual),
        _pin_bar(actual),
        _momentum(actual),
    ]

    positivas = señales.count(1)
    negativas = señales.count(-1)

    if positivas > negativas:
        return 1
    if negativas > positivas:
        return -1
    return 0

# --- NOTA v2 ---
# Movido aquí por la auditoría Fase 1: no lo importa ningún módulo activo.
# Sigue pendiente la Decisión 1 del README original (material real del
# curso de Juan Fernández para price action). Se conserva sin cambios.
