"""
THOR SCORE: puntaje 0-100 que combina las 4 confirmaciones oficiales
(EMA 50, RSI, Price Action, doble timeframe M1/M5).

Corrige un bug del proyecto original: el cálculo de score solo premiaba
la dirección alcista (rsi >= 65), por lo que el PUT nunca llegaba a
tener un score real y se decidía con una regla aparte y más débil.
Aquí el cálculo es simétrico para CALL y PUT.

Reparto de puntos (máximo 100):
  30 -> RSI M1 en zona de fuerza (>=65 para CALL, <=35 para PUT)
  30 -> RSI M5 confirma la misma dirección (>=55 / <=45)
  20 -> Precio actual alineado con la EMA 50 (tendencia)
  20 -> Price Action confirma la misma dirección
"""

RSI_FUERZA_ALTA = 65
RSI_FUERZA_BAJA = 35
RSI_M5_ALTA = 55
RSI_M5_BAJA = 45


def calcular_thor_score(ema, rsi_m1, rsi_m5, precio_actual, pa_senal):
    """
    Devuelve (score:int, direccion:str|None).
    direccion es "CALL", "PUT" o None si no hay sesgo mínimo de RSI M1.
    """
    if rsi_m1 >= RSI_FUERZA_ALTA:
        bias = 1
    elif rsi_m1 <= RSI_FUERZA_BAJA:
        bias = -1
    else:
        return 0, None

    score = 30  # RSI M1 ya cumplió el umbral base

    if (bias == 1 and rsi_m5 >= RSI_M5_ALTA) or (bias == -1 and rsi_m5 <= RSI_M5_BAJA):
        score += 30

    if (bias == 1 and precio_actual > ema) or (bias == -1 and precio_actual < ema):
        score += 20

    if pa_senal == bias:
        score += 20

    direccion = "CALL" if bias == 1 else "PUT"
    return score, direccion

# --- NOTA v2 ---
# Movido aquí por la auditoría Fase 1: no lo importa ningún módulo activo
# (ni v1 ni v2). Se conserva por si decides combinarlo con scoring/score_engine.py
# más adelante, pero hoy es código inerte.
