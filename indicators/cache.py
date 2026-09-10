"""
Caché en disco para la serie de indicadores ya calculada
(indicators.indicator_bank.calcular_confluencia_serie). Evita recalcular
lo mismo entre corridas repetidas de run_backtest.py / optimizer.py sobre
el mismo CSV histórico.

INVALIDACIÓN AUTOMÁTICA: la clave de caché incluye un hash de TODOS los
parámetros de configuración que afectan el cálculo (períodos de RSI,
MACD, Bollinger, etc. — ver core.config.EstrategiaConfig). Si cambias
cualquiera de esos valores en tu .env o en config.py, la clave cambia
sola y la caché vieja simplemente no se usa (no hay que borrarla a mano,
y nunca te sirve un resultado calculado con parámetros distintos a los
actuales sin que te des cuenta).
"""

import hashlib
import logging
import os
import pickle

import pandas as pd

from core.config import estrategia as E, rutas

log = logging.getLogger("thor.indicators.cache")

CACHE_DIR = os.path.join(rutas.BASE_DIR, "data_files", "cache")


def _hash_config() -> str:
    campos = (
        E.BB_PERIODO, E.BB_DESVIACION, E.EMA_CORTA, E.EMA_LARGA, E.SMA_LARGA,
        E.MACD_RAPIDA, E.MACD_LENTA, E.MACD_SENAL, E.PSAR_PASO, E.PSAR_MAX,
        E.RSI_PERIODO_CONF, E.RSI_SOBRECOMPRA, E.RSI_SOBREVENTA,
        E.STOCH_K, E.STOCH_SUAVIZADO, E.STOCH_D, E.STOCH_SOBRECOMPRA, E.STOCH_SOBREVENTA,
        E.ATR_PERIODO, E.ATR_VENTANA_PROMEDIO,
    )
    return hashlib.md5(str(campos).encode()).hexdigest()[:10]


def _clave(par: str, df: pd.DataFrame) -> str:
    if df.empty:
        firma = f"{par}_vacio_{_hash_config()}"
    else:
        firma = (f"{par}_{len(df)}_{df['time'].iloc[0]}_{df['time'].iloc[-1]}_"
                 f"{_hash_config()}")
    return hashlib.md5(firma.encode()).hexdigest()


def obtener_o_calcular(par: str, df: pd.DataFrame, funcion_calculo):
    """funcion_calculo: callable que recibe `df` y devuelve el DataFrame
    de indicadores (o None). Si ya existe en caché para esta combinación
    exacta de par+datos+config, se lee de disco; si no, se calcula, se
    guarda, y se devuelve."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    clave = _clave(par, df)
    ruta = os.path.join(CACHE_DIR, f"{clave}.pkl")

    if os.path.exists(ruta):
        try:
            with open(ruta, "rb") as f:
                log.debug("Caché hit: %s", par)
                return pickle.load(f)
        except Exception as exc:
            log.warning("Caché corrupta para %s (%s), recalculando.", par, exc)

    resultado = funcion_calculo(df)
    if resultado is not None:
        try:
            with open(ruta, "wb") as f:
                pickle.dump(resultado, f)
        except Exception as exc:
            log.warning("No se pudo guardar caché para %s: %s", par, exc)

    return resultado


def limpiar_cache() -> int:
    """Borra toda la caché de indicadores. Devuelve cuántos archivos borró.
    Útil si sospechas de un problema y quieres forzar recálculo total."""
    if not os.path.isdir(CACHE_DIR):
        return 0
    borrados = 0
    for archivo in os.listdir(CACHE_DIR):
        if archivo.endswith(".pkl"):
            os.remove(os.path.join(CACHE_DIR, archivo))
            borrados += 1
    return borrados
