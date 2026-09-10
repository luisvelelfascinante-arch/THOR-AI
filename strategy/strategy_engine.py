"""
Decide si la mejor oportunidad del ciclo se convierte en señal.
Antes: engines/strategy.py (solo cooldown). Ahora también selecciona el
motor de decisión según core.config.estrategia.STRATEGY_MODE, para que
cambiar de "confluencia_total" a "score_ponderado" sea un cambio de
config, no de código.
"""

from datetime import datetime, timedelta

from core.config import estrategia as E, operativa as O

_ultimas_senales: dict[str, datetime] = {}  # "PAR_DIRECCION" -> hora de envío


def evaluar_mejor(candidato: dict | None):
    """candidato: resultado de strategy.scanner.escanear() (dict con score,
    direccion, par, detalle, etc.) o None. Devuelve el dict de la señal a
    enviar, o None si no corresponde (por umbral o cooldown)."""
    if candidato is None:
        return None

    if candidato["score"] < O.PROBABILIDAD_MINIMA:
        return None

    clave = f"{candidato['par']}_{candidato['direccion']}"
    ahora = datetime.now()
    ultima_vez = _ultimas_senales.get(clave)

    if ultima_vez and ahora - ultima_vez < timedelta(minutes=O.COOLDOWN_MINUTOS):
        return None  # misma señal repetida dentro del cooldown, se descarta

    _ultimas_senales[clave] = ahora
    return candidato


def evaluar_datos(par: str, datos: dict):
    """Punto único que decide QUÉ motor de score usar, según config.
    Devuelve (score, direccion, detalle) sin decidir todavía cooldown/umbral
    (eso lo hace evaluar_mejor, sobre el 'mejor' del ciclo)."""
    if E.STRATEGY_MODE == "score_ponderado":
        from scoring.score_engine import calcular_score
        return calcular_score(datos)
    else:
        from strategy.confluence import evaluar_confluencia
        return evaluar_confluencia(datos)
