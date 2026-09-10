"""
Motor de backtesting — corre la MISMA lógica de indicadores/estrategia que
el bot en vivo (indicators/indicator_bank.py, strategy/confluence.py,
scoring/score_engine.py) sobre velas históricas reales, vela por vela,
sin mirar al futuro (en cada punto i solo usa datos hasta i).

SUPUESTOS EXPLÍCITOS (no ocultos, para que los puedas cuestionar):
  - Resultado de una operación: se compara el precio de cierre de la vela
    de la señal contra el precio de cierre de la vela N minutos después
    (N = EXPIRACION_MINUTOS). CALL gana si sube, PUT gana si baja.
  - Empate (mismo precio): se cuenta aparte, NO como WIN ni LOSS, y se
    excluye del winrate — así no se infla ni castiga artificialmente.
  - Profit factor: asume stake fijo de 1 unidad y payout de
    core.config.operativa.PAYOUT_PCT (ajústalo al payout real de tu
    bróker/IQ Option antes de confiar en el número).
  - No hay slippage ni comisión modelados (opciones binarias no suelen
    tenerlos vía spread de esa forma) — si tu bróker sí los aplica, dímelo
    y se incorpora.

Esto es una simulación de "qué hubiera pasado" — NO una garantía de
resultados futuros, y así se lo advierte también en el reporte de salida.
"""

import logging
import math

import numpy as np
import pandas as pd

from core.config import estrategia as E, operativa as O
from indicators.cache import obtener_o_calcular
from indicators.indicator_bank import calcular_confluencia_serie
from indicators.signal_bank import (
    calcular_senales_vectorizadas,
    calcular_score_vectorizado,
    evaluar_confluencia_vectorizado,
)

log = logging.getLogger("thor.backtesting.engine")


def preparar_serie_y_senales(par: str, df: pd.DataFrame, usar_cache: bool = True):
    """ETAPA 1 (cara, se hace UNA vez por par/segmento de datos): calcula
    la serie completa de indicadores y las 6 señales vectorizadas.
    Cacheada en disco (ver indicators/cache.py) — si ya se calculó antes
    para este mismo par+datos+configuración, se lee de disco en vez de
    recalcular. Devuelve (serie, senales) o (None, None) si no hay datos
    suficientes."""
    if usar_cache:
        serie = obtener_o_calcular(par, df, calcular_confluencia_serie)
    else:
        serie = calcular_confluencia_serie(df)

    if serie is None:
        return None, None

    senales = calcular_senales_vectorizadas(serie)
    return serie, senales


def _resultado_operacion(df: pd.DataFrame, idx_entrada: int, direccion: str,
                          velas_expiracion: int) -> tuple[str, float, float]:
    idx_salida = idx_entrada + velas_expiracion
    if idx_salida >= len(df):
        return "SIN_DATOS", float("nan"), float("nan")

    precio_entrada = float(df["close"].iloc[idx_entrada])
    precio_salida = float(df["close"].iloc[idx_salida])

    if precio_salida == precio_entrada:
        return "EMPATE", precio_entrada, precio_salida
    if direccion == "CALL":
        return ("WIN" if precio_salida > precio_entrada else "LOSS"), precio_entrada, precio_salida
    return ("WIN" if precio_salida < precio_entrada else "LOSS"), precio_entrada, precio_salida


def generar_operaciones(par: str, df: pd.DataFrame, serie: pd.DataFrame, senales: dict,
                         motor: str = "confluencia_total",
                         umbral_minimo: int | None = None,
                         cooldown_minutos: int | None = None,
                         aplicar_filtro_atr: bool | None = None) -> pd.DataFrame:
    """ETAPA 2 (barata, se puede repetir cientos de veces reutilizando la
    misma `serie`/`senales` de la etapa 1 — así es como el optimizador
    prueba 10+ combinaciones de umbral×motor sin recalcular indicadores
    cada vez).

    IMPORTANTE (corrección de un bug real): `umbral_minimo` se recibe
    como parámetro explícito, NUNCA se lee mutando
    core.config.operativa.PROBABILIDAD_MINIMA como hacía la versión
    anterior del optimizador — esa mutación global no sobrevive a
    multiprocessing (cada proceso hijo relee su propio config desde
    cero) y además es un patrón frágil incluso en un solo proceso."""
    velas_minimas = int(E.VELAS_MINIMAS)
    velas_expiracion = E.EXPIRACION_MINUTOS
    cooldown = cooldown_minutos if cooldown_minutos is not None else O.COOLDOWN_MINUTOS
    umbral = umbral_minimo if umbral_minimo is not None else O.PROBABILIDAD_MINIMA

    if motor == "score_ponderado":
        scores, direcciones = calcular_score_vectorizado(senales)
    else:
        scores, direcciones = evaluar_confluencia_vectorizado(senales)

    n = len(df)
    mascara = (direcciones != None) & (scores >= umbral)  # noqa: E711

    usar_filtro_atr = E.ATR_FILTRO_ACTIVO if aplicar_filtro_atr is None else aplicar_filtro_atr
    if usar_filtro_atr:
        atr_actual = serie["atr_actual"].to_numpy()
        atr_promedio = serie["atr_promedio"].to_numpy()
        with np.errstate(invalid="ignore"):
            atr_ok = atr_actual >= (atr_promedio * E.ATR_UMBRAL_MULTIPLICADOR)
        mascara &= np.nan_to_num(atr_ok, nan=False).astype(bool)

    # Fuera de rango válido (necesita historial previo y velas futuras
    # para saber el resultado de la expiración).
    mascara[:velas_minimas] = False
    if velas_expiracion > 0:
        mascara[n - velas_expiracion:] = False

    indices_candidatos = np.nonzero(mascara)[0]

    # A partir de aquí el bucle de Python solo recorre las señales que YA
    # pasaron el filtro vectorizado (normalmente un puñado, no las 30,000+
    # velas totales) — es donde se aplica el cooldown, que por depender
    # del orden y del tiempo transcurrido no se presta a vectorizar limpio,
    # pero como el conjunto ya es pequeño, no es un costo real.
    operaciones = []
    ultima_senal: dict[str, pd.Timestamp] = {}
    tiempos = df["time"]

    for i in indices_candidatos:
        direccion = direcciones[i]
        ts = tiempos.iloc[i]
        clave = f"{par}_{direccion}"
        if clave in ultima_senal and (ts - ultima_senal[clave]).total_seconds() < cooldown * 60:
            continue
        ultima_senal[clave] = ts

        resultado, precio_entrada, precio_salida = _resultado_operacion(
            df, int(i), direccion, velas_expiracion
        )

        operaciones.append({
            "time": ts, "par": par, "direccion": direccion, "score": int(scores[i]),
            "precio_entrada": precio_entrada, "precio_salida": precio_salida,
            "resultado": resultado, "hora_del_dia": ts.hour,
        })

    return pd.DataFrame(operaciones)


def backtest_par(par: str, df: pd.DataFrame, motor: str = "confluencia_total",
                  cooldown_minutos: int | None = None,
                  aplicar_filtro_atr: bool | None = None,
                  umbral_minimo: int | None = None,
                  usar_cache: bool = True) -> pd.DataFrame:
    """Conveniencia: corre las 2 etapas juntas para un uso simple (una
    sola combinación de motor/umbral). Si vas a probar MUCHAS
    combinaciones sobre el mismo par (como hace optimization/optimizer.py),
    llama preparar_serie_y_senales() una vez y generar_operaciones() por
    cada combinación en vez de esto — evita recalcular indicadores.

    OJO (heredado, sigue aplicando): para indicadores recursivos (EMA,
    MACD, PSAR, RSI) el resultado usa como "calentamiento" TODO el
    historial que le pases en `df`, no una ventana corta — ver docstring
    de indicators.indicator_bank.calcular_confluencia_serie para el
    detalle de por qué esto no es 100% idéntico al modo en vivo."""
    serie, senales = preparar_serie_y_senales(par, df, usar_cache=usar_cache)
    if serie is None:
        return pd.DataFrame()

    return generar_operaciones(
        par, df, serie, senales, motor=motor, umbral_minimo=umbral_minimo,
        cooldown_minutos=cooldown_minutos, aplicar_filtro_atr=aplicar_filtro_atr,
    )


def _significancia_estadistica(wins: int, total: int, payout: float) -> dict:
    """Test z de una cola contra el winrate de equilibrio (breakeven) dado
    el payout: p_breakeven = 1/(1+payout). Un winrate observado apenas por
    encima del breakeven, con pocas operaciones, puede ser puro azar — el
    z-test cuantifica esa duda en vez de dejarla implícita.

    Fuentes sobre por qué esto importa y qué umbral de muestra usar:
    QuestDB "Statistical Power Analysis in Backtesting Models"; guía de
    Medium "How Many Trades Are Enough? A Guide to Statistical
    Significance in Backtesting" (mínimo 30 para empezar a inferir algo,
    100+ para confiar en las métricas); TestMax "How to Backtest a
    Trading Strategy" (50 mínimo, 100+ estándar). Este proyecto usa 50
    como mínimo para el ranking del optimizador (ver optimization/optimizer.py)."""
    if total == 0:
        return {"aplica": False, "motivo": "Sin operaciones."}

    p_breakeven = 1 / (1 + payout)
    p_observado = wins / total
    error_estandar = math.sqrt(p_breakeven * (1 - p_breakeven) / total)
    if error_estandar == 0:
        return {"aplica": False, "motivo": "Error estándar no calculable."}

    z = (p_observado - p_breakeven) / error_estandar
    # CDF normal estándar vía función error (sin dependencia de scipy)
    p_valor = 1 - 0.5 * (1 + math.erf(z / math.sqrt(2)))

    return {
        "aplica": True,
        "winrate_breakeven_pct": round(p_breakeven * 100, 2),
        "z_score": round(z, 3),
        "p_valor_una_cola": round(p_valor, 4),
        "significativo_95pct": bool(p_valor < 0.05),
        "advertencia_muestra": (
            "Muestra < 50 operaciones: incluso si es significativo, la "
            "confianza en este resultado es baja." if total < 50 else None
        ),
    }


def calcular_estadisticas(trades: pd.DataFrame, payout_pct: float | None = None) -> dict:
    """trades: salida de backtest_par (o concatenación de varios pares)."""
    payout = payout_pct if payout_pct is not None else O.PAYOUT_PCT

    if trades.empty:
        return {"total_operaciones": 0, "mensaje": "Sin operaciones generadas en el rango dado."}

    validas = trades[trades["resultado"].isin(["WIN", "LOSS"])].copy()
    empates = int((trades["resultado"] == "EMPATE").sum())
    sin_datos = int((trades["resultado"] == "SIN_DATOS").sum())

    if validas.empty:
        return {
            "total_operaciones": len(trades),
            "con_resultado_valido": 0,
            "empates": empates,
            "sin_datos_de_cierre": sin_datos,
            "mensaje": "No hubo operaciones con resultado WIN/LOSS válido.",
        }

    wins = int((validas["resultado"] == "WIN").sum())
    losses = int((validas["resultado"] == "LOSS").sum())
    total = wins + losses

    ganancia_bruta = wins * payout
    perdida_bruta = losses * 1.0
    profit_factor = (ganancia_bruta / perdida_bruta) if perdida_bruta > 0 else float("inf")

    # Curva de equity y máximo drawdown (stake=1, payout configurable)
    validas = validas.sort_values("time")
    validas["pnl"] = validas["resultado"].map({"WIN": payout, "LOSS": -1.0})
    validas["equity"] = validas["pnl"].cumsum()
    pico = validas["equity"].cummax()
    drawdown = validas["equity"] - pico
    max_drawdown = float(drawdown.min()) if not drawdown.empty else 0.0

    por_hora = (
        validas.groupby("hora_del_dia")["resultado"]
        .apply(lambda s: round((s == "WIN").mean() * 100, 1))
        .sort_values(ascending=False)
        .to_dict()
    )
    por_par = (
        validas.groupby("par")["resultado"]
        .apply(lambda s: round((s == "WIN").mean() * 100, 1))
        .sort_values(ascending=False)
        .to_dict()
    )

    return {
        "total_operaciones": len(trades),
        "con_resultado_valido": total,
        "empates": empates,
        "sin_datos_de_cierre": sin_datos,
        "wins": wins,
        "losses": losses,
        "winrate_pct": round(wins / total * 100, 2) if total else None,
        "profit_factor": round(profit_factor, 3) if total else None,
        "max_drawdown": round(max_drawdown, 3),
        "winrate_por_hora_pct": por_hora,
        "winrate_por_par_pct": por_par,
        "payout_asumido": payout,
        "significancia_estadistica": _significancia_estadistica(wins, total, payout),
        "advertencia": "Simulación histórica — no garantiza resultados futuros.",
    }
