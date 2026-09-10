"""
THOR SCORE — motor de puntuación ponderado (Fase 3, revisado en v2.1).

*** ESTADO: PROPUESTA, NO ACTIVA EN PRODUCCIÓN ***
core.config.estrategia.STRATEGY_MODE sigue en "confluencia_total" por
defecto.

CORRECCIÓN v2.1 (con fuentes, no opinión) respecto a la primera versión
de este motor:

La versión anterior trataba RSI(2), MACD y Stochastic como 3
confirmaciones ponderadas independientes (25 puntos cada una). Investigar
buenas prácticas muestra que esto es un error de diseño conocido:
RSI, MACD y Stochastic son los tres osciladores de "familia momentum",
calculados sobre el mismo precio de cierre — están matemáticamente
correlacionados, no son evidencia independiente. Cuando los 3 coinciden,
es la MISMA información vista 3 veces, no 3 confirmaciones distintas
(fuentes: Pomegra — "Indicator Overload", capítulo sobre correlación de
indicadores; Tradeciety — "How To Combine The Best Indicators And Avoid
Wrong Signals", ejemplo explícito de RSI+MACD+Stochastic moviéndose
juntos; Yellow.com — "Why Most Crypto Traders Use Indicators Wrong").
Sumar 75 puntos (25x3) por una sola señal de momentum infla el score
artificialmente.

DISEÑO CORREGIDO — 3 dimensiones genuinamente distintas en vez de 6
señales tratadas como si fueran independientes:

  1. TENDENCIA (obligatoria, filtro): estructura de medias
     (precio/EMA100/EMA200/SMA200). Mide dirección de largo plazo.

  2. MOMENTUM - CONSENSO, no 3 votos (obligatorio, filtro): en vez de
     sumar puntos por cada oscilador de momentum, se exige que la
     MAYORÍA (2 de 3: RSI(2), MACD, Stochastic) confirme la misma
     dirección que la tendencia. Esto reconoce que son la misma familia
     de información y evita inflar el score por redundancia, pero
     sigue exigiendo que el "impulso" de corto plazo esté presente.

  3. VOLATILIDAD / REVERSIÓN (Bollinger) — ponderado, peso 60: mide algo
     genuinamente distinto (desviación estándar del precio, no momentum
     ni tendencia). Es la confirmación más "independiente" del conjunto.

  4. PARABOLIC SAR — ponderado, peso 40: técnicamente es otro indicador
     de tendencia (correlacionado con el factor 1), así que se pondera
     como confirmación secundaria/menor, no como una señal nueva.

  (Nota aparte, no incluida como confirmación de dirección: el filtro de
  ATR en indicators/volatility_filter.py bloquea señales en mercado de
  baja volatilidad ANTES de llegar aquí — ver ese módulo.)

Esto sigue siendo una PROPUESTA técnica mía basada en evidencia general
de trading algorítmico, no una transcripción del curso de Juan Fernández.
Valídala con backtesting/run_backtest.py --motor score_ponderado antes de
activarla en vivo.
"""

from strategy.confluence import (
    _tendencia, _rsi2, _macd, _stochastic, _bollinger, _parabolic_sar,
)

PESOS = {
    "bollinger": 60,
    "parabolic_sar": 40,
}


def _consenso_momentum(rsi2_v: int, macd_v: int, stoch_v: int) -> int:
    """Devuelve +1/-1 si al menos 2 de los 3 osciladores de momentum
    coinciden en la misma dirección, 0 si no hay mayoría clara. Esto
    reemplaza sumar 3 pesos independientes por un voto de familia."""
    votos = [rsi2_v, macd_v, stoch_v]
    positivos = votos.count(1)
    negativos = votos.count(-1)
    if positivos >= 2:
        return 1
    if negativos >= 2:
        return -1
    return 0


def calcular_score(datos: dict):
    """Devuelve (score:int 0-100, direccion:str|None, detalle:dict)."""
    tendencia_v = _tendencia(datos)
    rsi2_v = _rsi2(datos)
    macd_v = _macd(datos)
    stoch_v = _stochastic(datos)
    bollinger_v = _bollinger(datos)
    psar_v = _parabolic_sar(datos)

    momentum_v = _consenso_momentum(rsi2_v, macd_v, stoch_v)

    factores_individuales = {
        "tendencia": tendencia_v, "rsi2": rsi2_v, "macd": macd_v,
        "stochastic": stoch_v, "bollinger": bollinger_v,
        "parabolic_sar": psar_v,
    }

    # 1. Filtro obligatorio: tendencia y consenso de momentum deben
    #    coincidir entre sí. Si alguno es 0 o no coinciden, no hay señal.
    if tendencia_v == 0 or momentum_v == 0 or tendencia_v != momentum_v:
        return 0, None, {
            "factores": factores_individuales,
            "momentum_consenso": momentum_v,
            "motivo": "Filtro obligatorio no superado: tendencia y consenso "
                      "de momentum (2 de 3 entre RSI(2)/MACD/Stochastic) no "
                      "coinciden, o alguno es neutro.",
        }

    direccion_base = tendencia_v  # ya validado que coincide con momentum_v

    # 2. Score ponderado sobre las 2 dimensiones genuinamente distintas.
    score = 0
    for factor, peso in PESOS.items():
        valor = factores_individuales[factor]
        if valor == direccion_base:
            score += peso
        elif valor == -direccion_base:
            score -= peso

    score = max(0, min(100, score))
    direccion = "CALL" if direccion_base == 1 else "PUT"

    return score, direccion, {
        "factores": factores_individuales,
        "momentum_consenso": momentum_v,
        "obligatorios_ok": True,
        "direccion_base": direccion,
    }
