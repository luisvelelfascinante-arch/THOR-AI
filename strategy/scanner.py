"""
Escanea todos los pares y devuelve la mejor oportunidad del ciclo.

CORRIGE el bug de v1 (engines/scanner.py): antes la comparación
`candidato["score"] > mejor["score"]` nunca se activaba porque solo
entraban candidatos con score=100 en modo confluencia_total, así que el
"mejor" en realidad era "el primero en config.PARES". Ahora la comparación
sí es efectiva porque score_ponderado (Fase 3) produce valores intermedios
reales, y aunque estés en confluencia_total, dejar la comparación correcta
no tiene costo y deja de mentir sobre lo que hace.
"""

import logging

from core.config import estrategia as E
from data.data_provider import obtener_velas
from indicators.indicator_bank import calcular_confluencia
from indicators.volatility_filter import volatilidad_suficiente
from strategy.strategy_engine import evaluar_datos

log = logging.getLogger("thor.scanner")

_CAMPOS_SENAL = [
    "precio", "sma200", "ema200", "ema100", "bb_superior", "bb_inferior",
    "rsi2", "macd_hist", "stoch_k", "stoch_d", "psar",
]


def escanear():
    mejor = None

    for par in E.PARES:
        try:
            df = obtener_velas(par, "M1", int(E.VELAS_MINIMAS))
            if df is None:
                continue

            datos = calcular_confluencia(df)
            if datos is None:
                continue

            if not volatilidad_suficiente(datos):
                continue  # mercado en rango/choppy (ATR bajo) — se descarta, ver indicators/volatility_filter.py

            score, direccion, detalle = evaluar_datos(par, datos)
            if direccion is None:
                continue

            candidato = {"par": par, "direccion": direccion, "score": score,
                         "detalle": detalle}
            candidato.update({k: datos[k] for k in _CAMPOS_SENAL})

            if mejor is None or candidato["score"] > mejor["score"]:
                mejor = candidato

        except Exception as exc:
            log.error("Error escaneando %s: %s", par, exc)

    return mejor
