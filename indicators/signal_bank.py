"""
Banco de señales vectorizado — calcula las 6 confirmaciones técnicas
(tendencia, RSI(2), MACD, Stochastic, Bollinger, Parabolic SAR) para TODA
la serie histórica de una sola vez con NumPy, en vez de llamar 6 funciones
de Python por cada fila en un bucle.

Es la MISMA lógica exacta que strategy/confluence.py (_tendencia, _rsi2,
etc.) — cada condición fue traducida 1:1 a su equivalente vectorizado con
np.where. No cambia ningún umbral ni ninguna regla, solo la forma de
calcularla. strategy/confluence.py y scoring/score_engine.py siguen
existiendo tal cual para el modo en vivo (una vela a la vez, donde un
bucle de Python no importa) — este módulo es la versión para
backtesting/optimización, donde sí importa.
"""

import numpy as np
import pandas as pd

from core.config import estrategia as E


def calcular_senales_vectorizadas(serie: pd.DataFrame) -> dict:
    """serie: salida de indicators.indicator_bank.calcular_confluencia_serie
    (una fila por vela). Devuelve un dict de arrays NumPy (int8: 1, -1, 0),
    uno por confirmación, alineados con `serie`."""
    precio = serie["precio"].to_numpy()
    ema100 = serie["ema100"].to_numpy()
    ema200 = serie["ema200"].to_numpy()
    sma200 = serie["sma200"].to_numpy()
    rsi2 = serie["rsi2"].to_numpy()
    macd_hist = serie["macd_hist"].to_numpy()
    macd_hist_prev = serie["macd_hist_prev"].to_numpy()
    stoch_k = serie["stoch_k"].to_numpy()
    stoch_d = serie["stoch_d"].to_numpy()
    bb_superior = serie["bb_superior"].to_numpy()
    bb_inferior = serie["bb_inferior"].to_numpy()
    psar = serie["psar"].to_numpy()

    # Misma lógica que strategy/confluence.py::_tendencia, vectorizada
    tendencia = np.where(
        (precio > ema100) & (ema100 > ema200) & (precio > sma200), 1,
        np.where((precio < ema100) & (ema100 < ema200) & (precio < sma200), -1, 0)
    )

    # _rsi2
    rsi2_s = np.where(rsi2 <= E.RSI_SOBREVENTA, 1,
                       np.where(rsi2 >= E.RSI_SOBRECOMPRA, -1, 0))

    # _macd
    macd_s = np.where((macd_hist > 0) & (macd_hist > macd_hist_prev), 1,
                       np.where((macd_hist < 0) & (macd_hist < macd_hist_prev), -1, 0))

    # _stochastic
    stoch_s = np.where((stoch_k < E.STOCH_SOBREVENTA) & (stoch_k > stoch_d), 1,
                        np.where((stoch_k > E.STOCH_SOBRECOMPRA) & (stoch_k < stoch_d), -1, 0))

    # _bollinger
    bollinger_s = np.where(precio <= bb_inferior, 1,
                            np.where(precio >= bb_superior, -1, 0))

    # _parabolic_sar
    psar_s = np.where(psar < precio, 1, np.where(psar > precio, -1, 0))

    return {
        "tendencia": tendencia.astype(np.int8),
        "rsi2": rsi2_s.astype(np.int8),
        "macd": macd_s.astype(np.int8),
        "stochastic": stoch_s.astype(np.int8),
        "bollinger": bollinger_s.astype(np.int8),
        "parabolic_sar": psar_s.astype(np.int8),
    }


def evaluar_confluencia_vectorizado(senales: dict) -> tuple:
    """Misma lógica que strategy.confluence.evaluar_confluencia(), para
    TODA la serie a la vez. Devuelve (scores: np.ndarray[int],
    direcciones: np.ndarray[object] con 'CALL'/'PUT'/None)."""
    claves = ["tendencia", "rsi2", "macd", "stochastic", "bollinger", "parabolic_sar"]
    stack = np.stack([senales[k] for k in claves], axis=0)
    total = stack.shape[0]

    positivas = (stack == 1).sum(axis=0)
    negativas = (stack == -1).sum(axis=0)

    direcciones = np.full(stack.shape[1], None, dtype=object)
    direcciones[positivas == total] = "CALL"
    direcciones[negativas == total] = "PUT"

    scores = np.round(np.maximum(positivas, negativas) / total * 100).astype(int)
    scores[direcciones != None] = 100  # noqa: E711 (comparación con None en array de NumPy, no en escalar)

    return scores, direcciones


def calcular_score_vectorizado(senales: dict) -> tuple:
    """Misma lógica que scoring.score_engine.calcular_score(), para TODA
    la serie a la vez. Devuelve (scores, direcciones) igual que la
    función anterior."""
    from scoring.score_engine import PESOS

    tendencia = senales["tendencia"]
    rsi2 = senales["rsi2"]
    macd = senales["macd"]
    stoch = senales["stochastic"]
    bollinger = senales["bollinger"]
    psar = senales["parabolic_sar"]

    votos = np.stack([rsi2, macd, stoch], axis=0)
    votos_pos = (votos == 1).sum(axis=0)
    votos_neg = (votos == -1).sum(axis=0)
    momentum = np.where(votos_pos >= 2, 1, np.where(votos_neg >= 2, -1, 0))

    valido = (tendencia != 0) & (momentum != 0) & (tendencia == momentum)
    direccion_base = tendencia  # solo tiene sentido donde `valido` es True

    score = np.zeros(len(tendencia))
    score += np.where(bollinger == direccion_base, PESOS["bollinger"],
                       np.where(bollinger == -direccion_base, -PESOS["bollinger"], 0))
    score += np.where(psar == direccion_base, PESOS["parabolic_sar"],
                       np.where(psar == -direccion_base, -PESOS["parabolic_sar"], 0))
    score = np.clip(score, 0, 100)

    direcciones = np.full(len(tendencia), None, dtype=object)
    direcciones[valido & (direccion_base == 1)] = "CALL"
    direcciones[valido & (direccion_base == -1)] = "PUT"

    scores_finales = np.where(valido, score, 0).astype(int)

    return scores_finales, direcciones
