"""
Conexión a MetaTrader 5 — responsabilidad ÚNICA: abrir/cerrar sesión y
exponer utilidades de símbolo. NO calcula nada, NO pide velas de estrategia.
(v1 tenía esto mezclado con el cálculo de indicadores en
engines/indicators.py; se separa aquí para que un cambio de broker/sesión
no obligue a tocar código de indicadores, y viceversa.)

IMPORT PEREZOSO (v4.0): el paquete `MetaTrader5` solo se importa la
primera vez que se usa una función de este módulo, no al cargar THOR AI.
Así, con core.config.operativa.DATA_SOURCE = "twelve_data" (el default
desde v4.0), el proyecto entero funciona sin tener el paquete
`MetaTrader5` instalado ni el terminal de Windows abierto — solo hace
falta si de verdad usas DATA_SOURCE=mt5 o los scripts de backtesting que
exportan histórico real desde tu terminal.
"""

import logging
import time

from core.config import conexion

log = logging.getLogger("thor.mt5_connector")

_conectado = False
mt5 = None  # se carga con _cargar_mt5() al primer uso


def _cargar_mt5():
    global mt5
    if mt5 is None:
        try:
            import MetaTrader5 as _mt5
        except ImportError as exc:
            raise RuntimeError(
                "El paquete 'MetaTrader5' no está instalado. Es necesario "
                "solo si usas DATA_SOURCE=mt5 o los scripts de backtesting "
                "que exportan histórico desde tu terminal MT5. Instálalo con "
                "'pip install MetaTrader5' (solo funciona en Windows)."
            ) from exc
        mt5 = _mt5
    return mt5


def conectar(reintentos: int = 3, espera_seg: int = 5) -> bool:
    global _conectado
    if _conectado:
        return True

    mt5 = _cargar_mt5()
    kwargs = {}
    if conexion.MT5_LOGIN and conexion.MT5_PASSWORD and conexion.MT5_SERVER:
        kwargs = {
            "login": int(conexion.MT5_LOGIN),
            "password": conexion.MT5_PASSWORD,
            "server": conexion.MT5_SERVER,
        }

    for intento in range(1, reintentos + 1):
        if mt5.initialize(**kwargs):
            _conectado = True
            log.info("Conexión MT5 establecida (intento %s).", intento)
            return True
        log.warning(
            "Fallo al conectar con MT5 (intento %s/%s): %s",
            intento, reintentos, mt5.last_error(),
        )
        time.sleep(espera_seg)

    log.error("No fue posible conectar con MT5 tras %s intentos.", reintentos)
    return False


def desconectar() -> None:
    global _conectado
    if _conectado:
        mt5 = _cargar_mt5()
        mt5.shutdown()
        _conectado = False
        log.info("Conexión MT5 cerrada.")


def esta_conectado() -> bool:
    return _conectado


def asegurar_simbolo(symbol: str) -> bool:
    """Verifica que el símbolo exista y esté visible en Market Watch.
    Devuelve False si el símbolo no existe en absoluto para este broker."""
    mt5 = _cargar_mt5()
    info = mt5.symbol_info(symbol)
    if info is None:
        log.error("MT5 no reconoce el símbolo '%s' en este broker.", symbol)
        return False
    if not info.visible:
        ok = mt5.symbol_select(symbol, True)
        log.warning("'%s' no estaba visible en Market Watch. Activación: %s",
                     symbol, "OK" if ok else "FALLÓ")
        return ok
    return True


def info_cuenta():
    """Devuelve (terminal_info, account_info) o (None, None) si no hay sesión."""
    if not _conectado:
        return None, None
    mt5 = _cargar_mt5()
    return mt5.terminal_info(), mt5.account_info()
