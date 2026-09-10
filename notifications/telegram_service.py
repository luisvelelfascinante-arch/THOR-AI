"""
Envío de señales a Telegram. Mensaje enriquecido (Fase 6) respecto a v1:
ahora incluye hora, indicadores que confirmaron/rechazaron individualmente,
nivel de confianza, y el motivo de entrada — no solo los valores crudos.
"""

import logging
from datetime import datetime

import requests

from core.config import estrategia as E, telegram as T

log = logging.getLogger("thor.telegram")

_URL = "https://api.telegram.org/bot{token}/sendMessage"

_NOMBRES = {
    "tendencia": "Tendencia (medias)",
    "rsi2": "RSI(2)",
    "macd": "MACD",
    "stochastic": "Stochastic",
    "bollinger": "Bollinger",
    "parabolic_sar": "Parabolic SAR",
}


def _nivel_confianza(score: int) -> str:
    if score >= 90:
        return "Alto"
    if score >= 75:
        return "Medio"
    return "Bajo"


def _confirmaron_y_rechazaron(detalle: dict, direccion: str) -> tuple[list[str], list[str]]:
    factores = detalle.get("factores", detalle) if isinstance(detalle, dict) else {}
    signo = 1 if direccion == "CALL" else -1
    confirmaron, rechazaron = [], []
    for clave, valor in factores.items():
        if clave not in _NOMBRES:
            continue
        nombre = _NOMBRES[clave]
        if valor == signo:
            confirmaron.append(nombre)
        elif valor == -signo:
            rechazaron.append(nombre)
    return confirmaron, rechazaron


def _motivo_entrada(senal: dict, confirmaron: list[str]) -> str:
    if senal["score"] == 100:
        return "Las 6 confirmaciones de Confluencia Total coinciden en la misma dirección."
    return f"Confirmado por: {', '.join(confirmaron)}. Score {senal['score']}/100."


def _formatear_mensaje(senal: dict) -> str:
    emoji = "🟢" if senal["direccion"] == "CALL" else "🔴"
    confirmaron, rechazaron = _confirmaron_y_rechazaron(
        senal.get("detalle", {}), senal["direccion"]
    )
    confianza = _nivel_confianza(senal["score"])
    motivo = _motivo_entrada(senal, confirmaron)

    return (
        f"🧠 *THOR IA — Nueva señal*\n\n"
        f"{emoji} *{senal['direccion']}*\n"
        f"Par: `{senal['par']}`\n"
        f"Hora: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"Expiración: {E.EXPIRACION_MINUTOS} min\n"
        f"THOR SCORE: {senal['score']}/100\n"
        f"Nivel de confianza: {confianza}\n\n"
        f"✅ Confirmaron: {', '.join(confirmaron) if confirmaron else '—'}\n"
        f"❌ Rechazaron: {', '.join(rechazaron) if rechazaron else '—'}\n\n"
        f"Motivo de entrada: {motivo}\n\n"
        f"Precio: {senal['precio']}\n"
        f"EMA100/EMA200/SMA200: {round(senal['ema100'], 5)} / "
        f"{round(senal['ema200'], 5)} / {round(senal['sma200'], 5)}\n"
        f"Bollinger (10,2): {round(senal['bb_inferior'], 5)} — "
        f"{round(senal['bb_superior'], 5)}\n"
        f"RSI(2): {round(senal['rsi2'], 2)}\n"
        f"MACD hist: {round(senal['macd_hist'], 5)}\n"
        f"Stochastic %K/%D: {round(senal['stoch_k'], 2)} / {round(senal['stoch_d'], 2)}\n"
        f"Parabolic SAR: {round(senal['psar'], 5)}\n\n"
        f"⚠️ Señal informativa basada en análisis técnico. No garantiza "
        f"ganancias — opera bajo tu propio criterio y gestión de riesgo."
    )


def enviar_senal(senal: dict) -> bool:
    if not T.BOT_TOKEN or not T.CHAT_ID:
        log.warning("TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID no configurados: "
                     "la señal no se envió, solo quedó en el log/historial.")
        return False

    url = _URL.format(token=T.BOT_TOKEN)
    payload = {"chat_id": T.CHAT_ID, "text": _formatear_mensaje(senal), "parse_mode": "Markdown"}

    try:
        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code == 200:
            log.info("Señal enviada a Telegram: %s %s", senal["par"], senal["direccion"])
            return True
        log.error("Telegram respondió %s: %s", resp.status_code, resp.text)
        return False
    except requests.RequestException as exc:
        log.error("Error de red enviando a Telegram: %s", exc)
        return False
