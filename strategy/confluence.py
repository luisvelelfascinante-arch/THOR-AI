"""
Método "Confluencia total" — sin cambios de lógica respecto a v1.
Se mueve aquí (antes engines/confluence.py) porque en la nueva arquitectura
"strategy/" es la capa que decide reglas de entrada, separada de
"indicators/" (cálculo puro) y "scoring/" (el nuevo motor ponderado, Fase 3).

Sigue siendo el modo por defecto en producción
(core.config.estrategia.STRATEGY_MODE == "confluencia_total").
"""

from core.config import estrategia as E


def _tendencia(datos: dict) -> int:
    precio, ema100, ema200, sma200 = (
        datos["precio"], datos["ema100"], datos["ema200"], datos["sma200"]
    )
    if precio > ema100 > ema200 and precio > sma200:
        return 1
    if precio < ema100 < ema200 and precio < sma200:
        return -1
    return 0


def _rsi2(datos: dict) -> int:
    valor = datos["rsi2"]
    if valor <= E.RSI_SOBREVENTA:
        return 1
    if valor >= E.RSI_SOBRECOMPRA:
        return -1
    return 0


def _macd(datos: dict) -> int:
    hist, hist_prev = datos["macd_hist"], datos["macd_hist_prev"]
    if hist > 0 and hist > hist_prev:
        return 1
    if hist < 0 and hist < hist_prev:
        return -1
    return 0


def _stochastic(datos: dict) -> int:
    k, d = datos["stoch_k"], datos["stoch_d"]
    if k < E.STOCH_SOBREVENTA and k > d:
        return 1
    if k > E.STOCH_SOBRECOMPRA and k < d:
        return -1
    return 0


def _bollinger(datos: dict) -> int:
    precio = datos["precio"]
    if precio <= datos["bb_inferior"]:
        return 1
    if precio >= datos["bb_superior"]:
        return -1
    return 0


def _parabolic_sar(datos: dict) -> int:
    if datos["psar"] < datos["precio"]:
        return 1
    if datos["psar"] > datos["precio"]:
        return -1
    return 0


def evaluar_confluencia(datos: dict):
    """Devuelve (score:int 0-100, direccion:str|None, detalle:dict).
    Solo hay dirección si las 6 confirmaciones coinciden (comportamiento v1,
    sin cambios)."""
    senales = {
        "tendencia": _tendencia(datos),
        "rsi2": _rsi2(datos),
        "macd": _macd(datos),
        "stochastic": _stochastic(datos),
        "bollinger": _bollinger(datos),
        "parabolic_sar": _parabolic_sar(datos),
    }

    positivas = sum(1 for v in senales.values() if v == 1)
    negativas = sum(1 for v in senales.values() if v == -1)
    total = len(senales)

    if positivas == total:
        return 100, "CALL", senales
    if negativas == total:
        return 100, "PUT", senales

    mejor = max(positivas, negativas)
    return round(mejor / total * 100), None, senales
