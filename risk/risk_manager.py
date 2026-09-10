"""
Gestor de riesgo — NUEVO módulo, no existía en v1.

Hoy THOR IA solo envía señales (no ejecuta órdenes), así que "riesgo" aquí
significa: no saturar de notificaciones, y llevar la cuenta de rachas de
pérdidas SI en algún momento se carga el resultado real (WIN/LOSS) al
historial (ver storage/history.py). No calcula tamaño de posición porque
no hay ejecución de órdenes — ese cálculo se agrega el día que THOR
ejecute operaciones reales, y es una decisión aparte (ver README Fase 3
de v1, "Decisiones pendientes").
"""

import logging
from datetime import datetime, timedelta

from core.config import riesgo as R

log = logging.getLogger("thor.risk")

_senales_enviadas: list[datetime] = []          # timestamps, para límite por hora
_senales_por_par_dia: dict[str, list[datetime]] = {}  # par -> timestamps del día


def _limpiar_antiguas():
    ahora = datetime.now()
    global _senales_enviadas
    _senales_enviadas = [t for t in _senales_enviadas if ahora - t < timedelta(hours=1)]
    for par in list(_senales_por_par_dia):
        _senales_por_par_dia[par] = [
            t for t in _senales_por_par_dia[par] if ahora - t < timedelta(days=1)
        ]


def permitir_senal(par: str) -> tuple[bool, str]:
    """Devuelve (permitido, motivo_si_no). No modifica estado — solo
    consulta. registrar_senal() es quien confirma el envío."""
    _limpiar_antiguas()

    if len(_senales_enviadas) >= R.MAX_SENALES_POR_HORA:
        return False, f"Límite de {R.MAX_SENALES_POR_HORA} señales/hora alcanzado."

    historial_par = _senales_por_par_dia.get(par, [])
    if len(historial_par) >= R.MAX_SENALES_POR_PAR_POR_DIA:
        return False, (f"Límite de {R.MAX_SENALES_POR_PAR_POR_DIA} "
                        f"señales/día para {par} alcanzado.")

    return True, ""


def registrar_senal(par: str) -> None:
    ahora = datetime.now()
    _senales_enviadas.append(ahora)
    _senales_por_par_dia.setdefault(par, []).append(ahora)


def evaluar_racha_perdidas(resultados_recientes: list[str]) -> tuple[bool, str]:
    """resultados_recientes: lista de 'WIN'/'LOSS' en orden cronológico
    (viene de storage/stats.py, que lee el historial con resultado
    cargado). Devuelve (debe_pausar, motivo). Solo tiene sentido si el
    historial tiene resultados reales cargados — ver
    services/history.py 'Decisiones pendientes' en el README original."""
    if not resultados_recientes:
        return False, ""

    racha = 0
    for r in reversed(resultados_recientes):
        if r == "LOSS":
            racha += 1
        else:
            break

    if racha >= R.MAX_PERDIDAS_CONSECUTIVAS:
        return True, (f"{racha} pérdidas consecutivas — supera el máximo "
                       f"configurado ({R.MAX_PERDIDAS_CONSECUTIVAS}).")
    return False, ""
