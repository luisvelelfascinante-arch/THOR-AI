"""
Historial de señales en CSV. Sin cambios de lógica respecto a v1
(services/history.py), solo reubicado en storage/.
"""

import csv
import os
from datetime import datetime

from core.config import rutas, estrategia as E

_CAMPOS = [
    "timestamp", "par", "direccion", "score", "precio",
    "sma200", "ema200", "ema100", "bb_superior", "bb_inferior",
    "rsi2", "macd_hist", "stoch_k", "stoch_d", "psar",
    "expiracion_min", "resultado",
]


def _asegurar_archivo():
    os.makedirs(os.path.dirname(rutas.HISTORIAL_PATH), exist_ok=True)
    if not os.path.exists(rutas.HISTORIAL_PATH):
        with open(rutas.HISTORIAL_PATH, "w", newline="", encoding="utf-8") as f:
            csv.DictWriter(f, fieldnames=_CAMPOS).writeheader()


def guardar_senal(senal: dict) -> None:
    _asegurar_archivo()
    fila = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "par": senal["par"],
        "direccion": senal["direccion"],
        "score": senal["score"],
        "precio": senal["precio"],
        "sma200": round(senal["sma200"], 5),
        "ema200": round(senal["ema200"], 5),
        "ema100": round(senal["ema100"], 5),
        "bb_superior": round(senal["bb_superior"], 5),
        "bb_inferior": round(senal["bb_inferior"], 5),
        "rsi2": round(senal["rsi2"], 2),
        "macd_hist": round(senal["macd_hist"], 5),
        "stoch_k": round(senal["stoch_k"], 2),
        "stoch_d": round(senal["stoch_d"], 2),
        "psar": round(senal["psar"], 5),
        "expiracion_min": E.EXPIRACION_MINUTOS,
        "resultado": "",
    }
    with open(rutas.HISTORIAL_PATH, "a", newline="", encoding="utf-8") as f:
        csv.DictWriter(f, fieldnames=_CAMPOS).writerow(fila)
