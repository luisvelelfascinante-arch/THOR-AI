"""
CLI de backtesting. Corre sobre datos históricos REALES exportados con
export_historico.py — no genera ni simula datos.

Uso:
    python backtesting/run_backtest.py --carpeta data_files/historicos
    python backtesting/run_backtest.py --carpeta data_files/historicos --motor score_ponderado
"""

import argparse
import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd

from backtesting.backtest_engine import backtest_par, calcular_estadisticas
from backtesting.loader import cargar_carpeta
from backtesting.monte_carlo import simular_drawdowns
from core.config import rutas, operativa as O


def _procesar_par(args_tupla):
    """Función a nivel de módulo (requisito de multiprocessing en Windows:
    debe ser importable/picklable, no una función anidada). Procesa UN
    par de principio a fin en un proceso separado."""
    par, df, motor, atr_filtro = args_tupla
    trades = backtest_par(par, df, motor=motor, aplicar_filtro_atr=atr_filtro)
    return par, trades


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--carpeta", required=True, help="Carpeta con <PAR>.csv")
    ap.add_argument("--motor", choices=["confluencia_total", "score_ponderado"],
                     default="confluencia_total")
    ap.add_argument("--atr-filtro", action="store_true",
                     help="Aplica el filtro de volatilidad ATR (v2.1) — "
                          "compara resultados con/sin él corriendo dos veces.")
    ap.add_argument("--monte-carlo", action="store_true",
                     help="Corre reshuffle de operaciones para bandas de "
                          "drawdown (ver backtesting/monte_carlo.py).")
    ap.add_argument("--sin-paralelo", action="store_true",
                     help="Desactiva multiprocessing (útil para depurar errores; "
                          "por defecto procesa los pares en paralelo, uno por núcleo).")
    ap.add_argument("--limpiar-cache", action="store_true",
                     help="Borra la caché de indicadores antes de correr (fuerza recálculo total).")
    args = ap.parse_args()

    if args.limpiar_cache:
        from indicators.cache import limpiar_cache
        borrados = limpiar_cache()
        print(f"Caché de indicadores borrada ({borrados} archivos).\n")

    datos_por_par = cargar_carpeta(args.carpeta)
    print(f"Pares cargados: {list(datos_por_par.keys())}")
    print(f"Motor evaluado: {args.motor}")
    print(f"Modo: {'secuencial' if args.sin_paralelo else 'paralelo (multiprocessing)'}\n")

    t0 = time.time()
    todas = []

    if args.sin_paralelo or len(datos_por_par) == 1:
        for par, df in datos_por_par.items():
            print(f"Procesando {par} ({len(df)} velas)...")
            _, trades = _procesar_par((par, df, args.motor, args.atr_filtro))
            print(f"  -> {len(trades)} señales generadas.")
            todas.append(trades)
    else:
        tareas = [(par, df, args.motor, args.atr_filtro) for par, df in datos_por_par.items()]
        with ProcessPoolExecutor(max_workers=min(len(tareas), os.cpu_count() or 4)) as executor:
            futuros = {executor.submit(_procesar_par, t): t[0] for t in tareas}
            for futuro in as_completed(futuros):
                par = futuros[futuro]
                try:
                    _, trades = futuro.result()
                    print(f"  -> {par}: {len(trades)} señales generadas.")
                    todas.append(trades)
                except Exception as exc:
                    print(f"  ❌ {par} falló: {exc}")

    t1 = time.time()
    print(f"\n⏱️  Backtesting de {len(datos_por_par)} pares terminado en {t1 - t0:.2f}s.")

    trades_totales = pd.concat(todas, ignore_index=True) if todas else pd.DataFrame()

    sufijo = f"{args.motor}{'_atr' if args.atr_filtro else ''}"
    os.makedirs(rutas.BACKTEST_RESULTS_DIR, exist_ok=True)
    salida_csv = os.path.join(rutas.BACKTEST_RESULTS_DIR, f"trades_{sufijo}.csv")
    trades_totales.to_csv(salida_csv, index=False)

    stats = calcular_estadisticas(trades_totales)

    if args.monte_carlo:
        stats["monte_carlo_drawdown"] = simular_drawdowns(
            trades_totales, payout=O.PAYOUT_PCT
        )

    salida_json = os.path.join(rutas.BACKTEST_RESULTS_DIR, f"stats_{sufijo}.json")
    with open(salida_json, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 60)
    print(f"RESULTADOS — motor: {args.motor}")
    print("=" * 60)
    print(json.dumps(stats, indent=2, ensure_ascii=False))
    print(f"\nOperaciones detalladas: {salida_csv}")
    print(f"Estadísticas: {salida_json}")


if __name__ == "__main__":
    main()
