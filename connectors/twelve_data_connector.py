"""
Conector de Twelve Data (twelvedata.com) — fuente de datos en la nube,
alternativa a MT5 que NO requiere tener ningún terminal abierto.

Endpoint real (verificado contra la documentación oficial, no inventado):
    GET https://api.twelvedata.com/time_series
        ?symbol=EUR/USD&interval=1min&outputsize=N&apikey=TU_KEY

LÍMITES DEL PLAN GRATUITO (verificados, no inventados — twelvedata.com/pricing
y support.twelvedata.com/en/articles/5194820-api-call-limits):
    - 8 llamadas por minuto
    - 800 llamadas por día
    - 1 crédito consumido por símbolo por llamada (5 símbolos = 5 créditos
      por ciclo de escaneo, aunque se pidan en llamadas separadas)

Este módulo implementa un rate limiter real que respeta esos dos límites
— no es opcional ni decorativo: sin esto, escanear varios pares sin
control agota el cupo diario en minutos y la API empieza a devolver error
429. Ver core.config.operativa.INTERVALO_ESCANEO_SEGUNDOS, que se calcula
automáticamente para no exceder el cupo diario según cuántos símbolos
tengas configurados.
"""

import logging
import time
from collections import deque
from datetime import datetime, timedelta

import pandas as pd
import requests

from core.config import conexion, estrategia as E

log = logging.getLogger("thor.twelve_data")

_URL = "https://api.twelvedata.com/time_series"

_LIMITE_POR_MINUTO = 8
_LIMITE_POR_DIA = 800
_MARGEN_SEGURIDAD_DIA = 750  # apunta a 750, no a los 800 exactos

_llamadas_recientes: deque = deque()  # timestamps de los últimos 60s
_llamadas_hoy: int = 0
_dia_actual: str = ""


def _simbolo_twelve_data(symbol: str) -> str:
    """Convierte 'EURUSD' (formato interno de THOR) a 'EUR/USD' (formato
    que exige Twelve Data). Si el símbolo ya trae '/', lo deja igual."""
    s = symbol.upper().strip()
    if "/" in s:
        return s
    if len(s) == 6:
        return f"{s[:3]}/{s[3:]}"
    return s  # símbolo no-forex (acciones, cripto con nombre propio, etc.)


def _reset_contador_diario_si_corresponde() -> None:
    global _llamadas_hoy, _dia_actual
    hoy = datetime.now().strftime("%Y-%m-%d")
    if hoy != _dia_actual:
        _dia_actual = hoy
        _llamadas_hoy = 0


def _esperar_si_hace_falta() -> None:
    """Bloquea (sleep) lo necesario para no superar 8 llamadas/minuto.
    No es una sugerencia — sin esto, con 5+ símbolos por ciclo, se supera
    el límite en la primera vuelta del loop."""
    ahora = datetime.now()
    while _llamadas_recientes and (ahora - _llamadas_recientes[0]) > timedelta(minutes=1):
        _llamadas_recientes.popleft()

    if len(_llamadas_recientes) >= _LIMITE_POR_MINUTO:
        mas_antigua = _llamadas_recientes[0]
        espera = 60 - (ahora - mas_antigua).total_seconds() + 0.5
        if espera > 0:
            log.info("Rate limit de Twelve Data (8/min): esperando %.1fs.", espera)
            time.sleep(espera)


def obtener_velas_twelve_data(symbol: str, interval: str, outputsize: int) -> pd.DataFrame | None:
    """Pide velas OHLC a Twelve Data. Devuelve un DataFrame con columnas
    time/open/high/low/close (mismo formato que data/data_provider.py usa
    para MT5, para que el resto del pipeline no note la diferencia), o
    None si hay error, si no hay API key, o si se alcanzó el cupo diario."""
    global _llamadas_hoy

    if not conexion.TWELVE_DATA_API_KEY:
        log.error("TWELVE_DATA_API_KEY no configurada en .env.")
        return None

    _reset_contador_diario_si_corresponde()
    if _llamadas_hoy >= _MARGEN_SEGURIDAD_DIA:
        log.warning(
            "Cupo diario de Twelve Data alcanzado (%s/%s, margen de seguridad "
            "antes del límite real de %s). No se pide más hasta mañana.",
            _llamadas_hoy, _MARGEN_SEGURIDAD_DIA, _LIMITE_POR_DIA,
        )
        return None

    _esperar_si_hace_falta()

    params = {
        "symbol": _simbolo_twelve_data(symbol),
        "interval": interval,
        "outputsize": outputsize,
        "apikey": conexion.TWELVE_DATA_API_KEY,
    }

    try:
        resp = requests.get(_URL, params=params, timeout=15)
    except requests.RequestException as exc:
        log.error("Error de red pidiendo velas de %s a Twelve Data: %s", symbol, exc)
        return None
    finally:
        _llamadas_recientes.append(datetime.now())
        _llamadas_hoy += 1

    if resp.status_code != 200:
        log.error("Twelve Data respondió HTTP %s para %s: %s", resp.status_code, symbol, resp.text[:300])
        return None

    data = resp.json()

    # Twelve Data devuelve HTTP 200 incluso en errores propios (símbolo
    # inválido, API key mala, límite excedido) — el error real viene en
    # el campo "status"/"message" del cuerpo, no en el código HTTP.
    if data.get("status") == "error":
        log.error("Twelve Data devolvió error para %s: %s", symbol, data.get("message"))
        return None

    valores = data.get("values")
    if not valores:
        log.warning("Twelve Data no devolvió velas para %s.", symbol)
        return None

    df = pd.DataFrame(valores)
    df["time"] = pd.to_datetime(df["datetime"])
    for col in ("open", "high", "low", "close"):
        df[col] = df[col].astype(float)

    # Twelve Data devuelve más reciente primero (orden descendente) — el
    # resto del proyecto espera orden cronológico ascendente (igual que
    # MT5 copy_rates_*), así que se invierte.
    df = df.sort_values("time").reset_index(drop=True)

    return df[["time", "open", "high", "low", "close"]]


def estado_cupo() -> dict:
    """Para diagnóstico: cuántas llamadas van hoy y cuántas quedan."""
    _reset_contador_diario_si_corresponde()
    return {
        "llamadas_hoy": _llamadas_hoy,
        "margen_seguridad": _MARGEN_SEGURIDAD_DIA,
        "limite_real_dia": _LIMITE_POR_DIA,
        "restantes_hasta_margen": max(0, _MARGEN_SEGURIDAD_DIA - _llamadas_hoy),
    }
