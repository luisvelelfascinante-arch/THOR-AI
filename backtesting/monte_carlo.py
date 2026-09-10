"""
Monte Carlo por reshuffle de operaciones — NUEVO (pendiente que había
quedado abierto en FUENTES.md).

POR QUÉ EXISTE:
Un backtest muestra UN solo camino posible (el orden exacto en que
ocurrieron las operaciones). El drawdown máximo de ESE camino puede haber
sido "afortunado" — si las pérdidas se hubieran agrupado distinto, el
drawdown real pudo ser mucho peor con exactamente las mismas operaciones.
El método de reshuffle reordena aleatoriamente las mismas operaciones
miles de veces para ver el RANGO de drawdowns plausible, no solo el que
salió en el orden histórico real.

Fuentes: BuildAlpha — "Monte Carlo Simulation: Complete Guide" (método de
reshuffle para bandas de drawdown); DEV Community — "Monte Carlo
Simulation for Trading Systems", ejemplo de código de reshuffle y bandas
de confianza de drawdown.

LÍMITE HONESTO: esto es bootstrap simple (IID) sobre operaciones YA
observadas — no genera operaciones nuevas ni inventa resultados. Si el
histórico de entrada tiene autocorrelación fuerte (rachas que se repiten
por régimen de mercado), el reshuffle IID puede subestimar el riesgo real
de rachas largas — un block-bootstrap sería más preciso pero es una
mejora adicional, no incluida aquí.
"""

import random

import pandas as pd


def simular_drawdowns(trades: pd.DataFrame, payout: float,
                       n_simulaciones: int = 2000,
                       percentiles: tuple = (50, 75, 90, 95, 99)) -> dict:
    """trades: DataFrame con columna 'resultado' en {WIN, LOSS} (empates y
    sin_datos ya deben estar excluidos por el llamador). Devuelve
    percentiles del máximo drawdown simulado, y compara contra el
    drawdown observado en el orden histórico real."""
    if trades.empty or "resultado" not in trades.columns:
        return {"aplica": False, "motivo": "Sin operaciones generadas — nada que reordenar."}

    validos = trades[trades["resultado"].isin(["WIN", "LOSS"])]
    if len(validos) < 10:
        return {"aplica": False, "motivo": "Menos de 10 operaciones válidas — "
                "el reshuffle no aporta nada útil con tan pocos datos."}

    pnl = validos["resultado"].map({"WIN": payout, "LOSS": -1.0}).tolist()

    # Drawdown observado en el orden histórico real (el que ya reportaba
    # backtest_engine.calcular_estadisticas, aquí solo para comparar).
    equity_real = 0.0
    pico_real = 0.0
    dd_real = 0.0
    for p in pnl:
        equity_real += p
        pico_real = max(pico_real, equity_real)
        dd_real = min(dd_real, equity_real - pico_real)

    drawdowns_simulados = []
    rng = random.Random(42)  # semilla fija: mismo input -> mismo resultado, reproducible
    for _ in range(n_simulaciones):
        orden = pnl.copy()
        rng.shuffle(orden)
        equity = 0.0
        pico = 0.0
        dd = 0.0
        for p in orden:
            equity += p
            pico = max(pico, equity)
            dd = min(dd, equity - pico)
        drawdowns_simulados.append(dd)

    drawdowns_simulados.sort()  # ascendente (más negativo = peor, al inicio)

    def percentil(valores_ordenados, p):
        idx = int(len(valores_ordenados) * p / 100)
        idx = min(idx, len(valores_ordenados) - 1)
        return valores_ordenados[idx]

    bandas = {
        f"p{p}": round(percentil(drawdowns_simulados, 100 - p), 3)
        for p in percentiles
    }
    # p50 = drawdown mediano simulado, p99 = "casi el peor caso" simulado
    # (se invierte el percentil porque drawdown más negativo = peor).

    return {
        "aplica": True,
        "n_simulaciones": n_simulaciones,
        "drawdown_observado_orden_real": round(dd_real, 3),
        "drawdown_por_percentil_de_riesgo": bandas,
        "interpretacion": (
            f"El drawdown que realmente ocurrió en tu backtest fue "
            f"{round(dd_real, 3)}. Reordenando las MISMAS operaciones "
            f"{n_simulaciones} veces, en el percentil 95 de peores casos "
            f"el drawdown simulado es {bandas.get('p95')} — así de "
            f"'afortunado' o no fue el orden real en que ocurrieron."
        ),
        "advertencia": "Bootstrap IID simple — no modela rachas por régimen "
                        "de mercado (ver docstring del módulo).",
    }
