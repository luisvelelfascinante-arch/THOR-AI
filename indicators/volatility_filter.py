"""
Filtro de volatilidad basado en ATR (Average True Range) — NUEVO en v2.1,
agregado por investigación de buenas prácticas, no por el curso ni por
capricho.

POR QUÉ EXISTE (con fuentes, no opinión):
Operar en periodos de baja volatilidad ("mercado choppy", sin dirección
clara) aumenta la tasa de señales falsas — reportado en un 30-40% más
en periodos de ATR bajo vs. ATR alto (AlfaTactix, "ATR Filter: Volatility
Gate for Better Trade Quality"). Es una técnica estándar desde Wilder
(1978, "New Concepts in Technical Trading Systems") y se recomienda
específicamente para opciones binarias por la sensibilidad del resultado
a movimientos pequeños en expiraciones cortas (TradingFinder, guía de
indicadores para binarias).

CÓMO SE APLICA AQUÍ:
No es una confirmación direccional (ATR no tiene signo, no dice si el
precio va a subir o bajar). Es un FILTRO: si la volatilidad actual está
muy por debajo de su propio promedio reciente, el mercado probablemente
está en rango/choppy, y se descarta la señal aunque los 6 indicadores de
dirección hayan coincidido — porque la evidencia dice que en ese contexto
la señal es menos confiable, no porque "sobre el curso" diga otra cosa.

ESTADO: apagado por defecto (core.config.estrategia.ATR_FILTRO_ACTIVO =
False vía .env ATR_FILTRO_ACTIVO=false). Actívalo solo después de
comparar en backtesting con y sin el filtro — ver
backtesting/run_backtest.py --atr-filtro.
"""

from core.config import estrategia as E


def volatilidad_suficiente(datos: dict) -> bool:
    """datos: dict de indicators.indicator_bank.calcular_confluencia()
    (debe incluir 'atr_actual' y 'atr_promedio'). Devuelve True si la
    volatilidad actual es razonable respecto a su propio promedio
    reciente (no un umbral absoluto — cada par tiene su propia escala
    de movimiento, comparar contra sí mismo evita ese problema)."""
    if not E.ATR_FILTRO_ACTIVO:
        return True  # filtro apagado: no bloquea nada

    atr_actual = datos.get("atr_actual")
    atr_promedio = datos.get("atr_promedio")
    if atr_actual is None or atr_promedio is None or atr_promedio == 0:
        return True  # sin datos de ATR, no bloquear por un dato faltante

    return atr_actual >= (atr_promedio * E.ATR_UMBRAL_MULTIPLICADOR)
