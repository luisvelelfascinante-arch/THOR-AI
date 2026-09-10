"""
Cálculo de indicadores técnicos — responsabilidad ÚNICA: recibir un
DataFrame OHLCV ya cargado y devolver los valores de cada indicador.

Es una función PURA (mismo input -> mismo output, sin tocar MT5, sin
side-effects). Esto es lo que permite reutilizar exactamente el mismo
código en el motor en vivo (core/brain.py) y en el backtester
(backtesting/backtest_engine.py) — en v1 el backtesting no existía porque
los indicadores estaban atados a una llamada MT5 en vivo.

Todos los períodos y umbrales vienen de core.config.estrategia — no hay
ningún número hardcodeado aquí que no esté ya documentado como tomado de
la plataforma real.
"""

import pandas as pd
from ta.momentum import RSIIndicator, StochasticOscillator
from ta.trend import EMAIndicator, MACD, SMAIndicator, PSARIndicator
from ta.volatility import BollingerBands, AverageTrueRange

from core.config import estrategia as E


def calcular_confluencia(df: pd.DataFrame) -> dict | None:
    """df: DataFrame OHLCV en M1, con al menos E.VELAS_MINIMAS filas,
    ordenado cronológicamente (más reciente al final).
    Devuelve un dict con todos los valores usados por la estrategia de
    confluencia, o None si no hay suficientes datos limpios."""
    minimo = max(E.SMA_LARGA, E.EMA_LARGA) + 5
    if df is None or len(df) < minimo:
        return None

    try:
        sma200 = SMAIndicator(df["close"], window=E.SMA_LARGA).sma_indicator().iloc[-1]
        ema200 = EMAIndicator(df["close"], window=E.EMA_LARGA).ema_indicator().iloc[-1]
        ema100 = EMAIndicator(df["close"], window=E.EMA_CORTA).ema_indicator().iloc[-1]

        bb = BollingerBands(df["close"], window=E.BB_PERIODO, window_dev=E.BB_DESVIACION)
        bb_superior = bb.bollinger_hband().iloc[-1]
        bb_inferior = bb.bollinger_lband().iloc[-1]

        rsi2 = RSIIndicator(df["close"], window=E.RSI_PERIODO_CONF).rsi().iloc[-1]

        macd_ind = MACD(
            df["close"], window_slow=E.MACD_LENTA, window_fast=E.MACD_RAPIDA,
            window_sign=E.MACD_SENAL,
        )
        macd_hist = macd_ind.macd_diff().iloc[-1]
        macd_hist_prev = macd_ind.macd_diff().iloc[-2]

        stoch_ind = StochasticOscillator(
            df["high"], df["low"], df["close"],
            window=E.STOCH_K, smooth_window=E.STOCH_SUAVIZADO,
        )
        stoch_k = stoch_ind.stoch().iloc[-1]
        stoch_d = stoch_ind.stoch_signal().iloc[-1]

        psar = PSARIndicator(
            df["high"], df["low"], df["close"], step=E.PSAR_PASO, max_step=E.PSAR_MAX,
        ).psar().iloc[-1]

        # ATR — NUEVO (v2.1). Se usa como filtro de volatilidad, no como
        # confirmación direccional (ATR no tiene signo). Justificación y
        # fuentes en indicators/volatility_filter.py.
        atr_serie = AverageTrueRange(
            df["high"], df["low"], df["close"], window=E.ATR_PERIODO
        ).average_true_range()
        atr_actual = atr_serie.iloc[-1]
        atr_promedio = atr_serie.rolling(E.ATR_VENTANA_PROMEDIO).mean().iloc[-1]
    except Exception:
        return None

    valores = [sma200, ema200, ema100, bb_superior, bb_inferior, rsi2,
               macd_hist, stoch_k, stoch_d, psar, atr_actual, atr_promedio]
    if any(pd.isna(v) for v in valores):
        return None

    return {
        "precio": float(df["close"].iloc[-1]),
        "sma200": float(sma200),
        "ema200": float(ema200),
        "ema100": float(ema100),
        "bb_superior": float(bb_superior),
        "bb_inferior": float(bb_inferior),
        "rsi2": float(rsi2),
        "macd_hist": float(macd_hist),
        "macd_hist_prev": float(macd_hist_prev),
        "stoch_k": float(stoch_k),
        "stoch_d": float(stoch_d),
        "psar": float(psar),
        "atr_actual": float(atr_actual),
        "atr_promedio": float(atr_promedio),
    }


def calcular_confluencia_serie(df: pd.DataFrame) -> pd.DataFrame | None:
    """Versión VECTORIZADA de calcular_confluencia — SOLO para backtesting.

    calcular_confluencia() recibe una ventana de ~600 velas y recalcula
    todos los indicadores desde cero, pensado para llamarse UNA vez por
    ciclo en vivo (cada 15 segundos, ver core/brain.py) — ahí no importa
    que tarde unos milisegundos.

    En backtesting eso se llamaba una vez POR CADA VELA histórica (decenas
    de miles), así que el mismo cálculo se repetía completo cada vez —
    con ~30,000 velas eso son millones de operaciones redundantes y el
    backtest podía tardar horas en vez de segundos.

    Esta versión calcula cada indicador UNA sola vez sobre TODA la serie
    (lo que estas librerías ya hacen internamente de forma vectorizada) y
    devuelve un DataFrame alineado con `df`, una fila por vela.

    ADVERTENCIA DE PRECISIÓN (honesta, no oculta): para indicadores
    recursivos/exponenciales (EMA, MACD, PSAR, RSI vía suavizado) el valor
    en la fila i depende de TODO el historial hasta ahí, no solo de las
    últimas ~600 velas. calcular_confluencia() (la versión en vivo, que
    recibe una ventana corta) y esta versión NO producen números idénticos
    para esos indicadores — esta versión es más precisa (más calentamiento
    = más estable), pero eso significa que resultados de backtesting con
    esta función no son 100% comparables número a número con el
    comportamiento exacto del bot en vivo, que sí trabaja con ventana
    corta por diseño (ver connectors/mt5_connector.py y
    core.config.estrategia.VELAS_MINIMAS). La diferencia práctica suele
    ser pequeña una vez pasado el período de calentamiento, pero no es
    cero — no se afirma lo contrario."""
    minimo = max(E.SMA_LARGA, E.EMA_LARGA) + 5
    if df is None or len(df) < minimo:
        return None

    out = pd.DataFrame(index=df.index)
    out["precio"] = df["close"]
    out["sma200"] = SMAIndicator(df["close"], window=E.SMA_LARGA).sma_indicator()
    out["ema200"] = EMAIndicator(df["close"], window=E.EMA_LARGA).ema_indicator()
    out["ema100"] = EMAIndicator(df["close"], window=E.EMA_CORTA).ema_indicator()

    bb = BollingerBands(df["close"], window=E.BB_PERIODO, window_dev=E.BB_DESVIACION)
    out["bb_superior"] = bb.bollinger_hband()
    out["bb_inferior"] = bb.bollinger_lband()

    out["rsi2"] = RSIIndicator(df["close"], window=E.RSI_PERIODO_CONF).rsi()

    macd_ind = MACD(
        df["close"], window_slow=E.MACD_LENTA, window_fast=E.MACD_RAPIDA,
        window_sign=E.MACD_SENAL,
    )
    out["macd_hist"] = macd_ind.macd_diff()
    out["macd_hist_prev"] = out["macd_hist"].shift(1)

    stoch_ind = StochasticOscillator(
        df["high"], df["low"], df["close"],
        window=E.STOCH_K, smooth_window=E.STOCH_SUAVIZADO,
    )
    out["stoch_k"] = stoch_ind.stoch()
    out["stoch_d"] = stoch_ind.stoch_signal()

    out["psar"] = PSARIndicator(
        df["high"], df["low"], df["close"], step=E.PSAR_PASO, max_step=E.PSAR_MAX,
    ).psar()

    atr_serie = AverageTrueRange(
        df["high"], df["low"], df["close"], window=E.ATR_PERIODO
    ).average_true_range()
    out["atr_actual"] = atr_serie
    out["atr_promedio"] = atr_serie.rolling(E.ATR_VENTANA_PROMEDIO).mean()

    return out
