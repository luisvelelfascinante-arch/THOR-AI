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

El contador de llamadas se persiste en disco (rutas.RATE_LIMIT_STATE_PATH)
en vez de vivir solo en memoria: main.py, diagnostico.py y
test_twelve_data.py son procesos distintos pero comparten el mismo cupo
REAL de la cuenta de Twelve Data, así que si no comparten también el
contador, cada proceso cree tener 8/min y 800/día completos para sí
mismo y entre todos exceden el límite real. Un lock basado en archivo
(creación exclusiva) serializa el acceso entre procesos.
"""

import contextlib
import json
import logging
import os
import tempfile
import time
from datetime import datetime, timedelta

import pandas as pd
import requests

from core.config import conexion, rutas

log = logging.getLogger("thor.twelve_data")

_URL = "https://api.twelvedata.com/time_series"

_LIMITE_POR_MINUTO = 8
_LIMITE_POR_DIA = 800
_MARGEN_SEGURIDAD_DIA = 750  # apunta a 750, no a los 800 exactos
_REINTENTO_ESPERA_SEGUNDOS = 60  # espera antes de reintentar un 429

_ESTADO_PATH = rutas.RATE_LIMIT_STATE_PATH
_LOCK_PATH = _ESTADO_PATH + ".lock"
_LOCK_TIMEOUT_SEGUNDOS = 15
_LOCK_ESPERA_PASO_SEGUNDOS = 0.05


def _simbolo_twelve_data(symbol: str) -> str:
    """Convierte 'EURUSD' (formato interno de THOR) a 'EUR/USD' (formato
    que exige Twelve Data). Si el símbolo ya trae '/', lo deja igual."""
    s = symbol.upper().strip()
    if "/" in s:
        return s
    if len(s) == 6:
        return f"{s[:3]}/{s[3:]}"
    return s  # símbolo no-forex (acciones, cripto con nombre propio, etc.)


@contextlib.contextmanager
def _lock_estado():
    """Mutex entre procesos basado en creación exclusiva de archivo. Si no
    se puede adquirir (p. ej. un proceso murió sin liberar el lock), sigue
    adelante sin bloquear indefinidamente — mejor una carrera ocasional
    que un bot congelado para siempre."""
    os.makedirs(os.path.dirname(_LOCK_PATH), exist_ok=True)
    inicio = time.monotonic()
    adquirido = False
    while time.monotonic() - inicio < _LOCK_TIMEOUT_SEGUNDOS:
        try:
            fd = os.open(_LOCK_PATH, os.O_CREAT | os.O_EXCL | os.O_RDWR)
            os.close(fd)
            adquirido = True
            break
        except FileExistsError:
            time.sleep(_LOCK_ESPERA_PASO_SEGUNDOS)

    if not adquirido:
        log.warning(
            "No se pudo adquirir el lock de rate-limit de Twelve Data tras "
            "%ss; se continúa sin lock (riesgo de carrera entre procesos).",
            _LOCK_TIMEOUT_SEGUNDOS,
        )
    try:
        yield
    finally:
        if adquirido:
            try:
                os.remove(_LOCK_PATH)
            except OSError:
                pass


def _estado_por_defecto() -> dict:
    return {"dia_actual": "", "llamadas_hoy": 0, "llamadas_recientes": []}


def _leer_estado() -> dict:
    try:
        with open(_ESTADO_PATH, "r", encoding="utf-8") as f:
            estado = json.load(f)
    except (FileNotFoundError, ValueError):
        return _estado_por_defecto()
    estado.setdefault("dia_actual", "")
    estado.setdefault("llamadas_hoy", 0)
    estado.setdefault("llamadas_recientes", [])
    return estado


def _escribir_estado(estado: dict) -> None:
    directorio = os.path.dirname(_ESTADO_PATH)
    os.makedirs(directorio, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=directorio, prefix=".tmp_rate_limit_")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(estado, f)
        os.replace(tmp_path, _ESTADO_PATH)
    except BaseException:
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        raise


def _resetear_contador_diario_si_corresponde(estado: dict) -> dict:
    hoy = datetime.now().strftime("%Y-%m-%d")
    if estado["dia_actual"] != hoy:
        estado["dia_actual"] = hoy
        estado["llamadas_hoy"] = 0
    return estado


def _podar_llamadas_recientes(estado: dict) -> dict:
    ahora = datetime.now()
    estado["llamadas_recientes"] = [
        ts for ts in estado["llamadas_recientes"]
        if ahora - datetime.fromisoformat(ts) <= timedelta(minutes=1)
    ]
    return estado


def _esperar_si_hace_falta(estado: dict) -> dict:
    """Bloquea (sleep) lo necesario para no superar 8 llamadas/minuto,
    contando también las llamadas hechas por OTROS procesos (persistidas
    en disco). Devuelve el estado actualizado (recargado tras dormir, por
    si otro proceso escribió mientras tanto)."""
    estado = _podar_llamadas_recientes(estado)
    recientes = estado["llamadas_recientes"]

    if len(recientes) >= _LIMITE_POR_MINUTO:
        mas_antigua = datetime.fromisoformat(recientes[0])
        espera = 60 - (datetime.now() - mas_antigua).total_seconds() + 0.5
        if espera > 0:
            log.info("Rate limit compartido de Twelve Data (8/min): esperando %.1fs.", espera)
            time.sleep(espera)
        estado = _podar_llamadas_recientes(_resetear_contador_diario_si_corresponde(_leer_estado()))

    return estado


def _hay_cupo_diario_disponible() -> bool:
    with _lock_estado():
        estado = _resetear_contador_diario_si_corresponde(_leer_estado())
        disponible = estado["llamadas_hoy"] < _MARGEN_SEGURIDAD_DIA
        _escribir_estado(estado)

    if not disponible:
        log.warning(
            "Cupo diario de Twelve Data alcanzado (%s/%s, margen de seguridad "
            "antes del límite real de %s). No se pide más hasta mañana.",
            estado["llamadas_hoy"], _MARGEN_SEGURIDAD_DIA, _LIMITE_POR_DIA,
        )
    return disponible


def _pedir_respetando_limite(params: dict, symbol: str):
    """Aplica el límite compartido de 8 llamadas/minuto, hace la petición
    HTTP y registra la llamada en el estado persistido. Devuelve la
    respuesta de requests, o None si hubo un error de red."""
    with _lock_estado():
        estado = _resetear_contador_diario_si_corresponde(_leer_estado())
        estado = _esperar_si_hace_falta(estado)

        try:
            resp = requests.get(_URL, params=params, timeout=15)
        except requests.RequestException as exc:
            log.error("Error de red pidiendo velas de %s a Twelve Data: %s", symbol, exc)
            resp = None
        finally:
            estado["llamadas_recientes"].append(datetime.now().isoformat())
            estado["llamadas_hoy"] += 1
            _escribir_estado(estado)

    return resp


def _es_respuesta_429(resp) -> bool:
    """Twelve Data señaliza el límite excedido a veces con el código HTTP
    429 directamente, y a veces con HTTP 200 y {"code": 429, ...} en el
    cuerpo — hay que revisar ambos."""
    if resp.status_code == 429:
        return True
    try:
        cuerpo = resp.json()
    except ValueError:
        return False
    return isinstance(cuerpo, dict) and cuerpo.get("code") == 429


def obtener_velas_twelve_data(symbol: str, interval: str, outputsize: int) -> pd.DataFrame | None:
    """Pide velas OHLC a Twelve Data. Devuelve un DataFrame con columnas
    time/open/high/low/close (mismo formato que data/data_provider.py usa
    para MT5, para que el resto del pipeline no note la diferencia), o
    None si hay error, si no hay API key, o si se alcanzó el cupo diario.

    Si la API responde 429 (límite por minuto excedido), espera
    _REINTENTO_ESPERA_SEGUNDOS y reintenta automáticamente una vez antes
    de rendirse — en vez de descartar el ciclo a la primera."""
    if not conexion.TWELVE_DATA_API_KEY:
        log.error("TWELVE_DATA_API_KEY no configurada en .env.")
        return None

    if not _hay_cupo_diario_disponible():
        return None

    params = {
        "symbol": _simbolo_twelve_data(symbol),
        "interval": interval,
        "outputsize": outputsize,
        "apikey": conexion.TWELVE_DATA_API_KEY,
    }

    resp = _pedir_respetando_limite(params, symbol)
    if resp is None:
        return None

    if _es_respuesta_429(resp):
        log.warning(
            "Twelve Data respondió 429 (límite excedido) para %s. Esperando "
            "%ss y reintentando una vez.", symbol, _REINTENTO_ESPERA_SEGUNDOS,
        )
        time.sleep(_REINTENTO_ESPERA_SEGUNDOS)

        if not _hay_cupo_diario_disponible():
            return None

        resp = _pedir_respetando_limite(params, symbol)
        if resp is None:
            return None

        if _es_respuesta_429(resp):
            log.error(
                "Twelve Data volvió a responder 429 para %s tras el "
                "reintento; se descarta este ciclo.", symbol,
            )
            return None

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
    """Para diagnóstico: cuántas llamadas van hoy (contando todos los
    procesos que comparten el estado persistido) y cuántas quedan."""
    with _lock_estado():
        estado = _resetear_contador_diario_si_corresponde(_leer_estado())
        _escribir_estado(estado)

    return {
        "llamadas_hoy": estado["llamadas_hoy"],
        "margen_seguridad": _MARGEN_SEGURIDAD_DIA,
        "limite_real_dia": _LIMITE_POR_DIA,
        "restantes_hasta_margen": max(0, _MARGEN_SEGURIDAD_DIA - estado["llamadas_hoy"]),
    }
