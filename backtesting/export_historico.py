"""
Exporta histórico REAL de MT5 a CSV, listo para backtesting/loader.py.
Correr en tu máquina Windows con MT5 abierto y sesión iniciada — este
script no genera ni simula ningún dato, solo pide a MT5 lo que ya tiene
almacenado.

Uso:
    python backtesting/export_historico.py --desde 2024-01-01 --hasta 2024-06-01
    (exporta todos los pares de core.config.estrategia.PARES a
    data_files/historicos/<PAR>.csv)
"""

import argparse
import os
import sys
from datetime import datetime

# Bootstrap: permite ejecutar este script directo con
# "python backtesting/export_historico.py" (y no solo con "python -m
# backtesting.export_historico") agregando la raíz del proyecto al
# path -- sin esto, Python solo ve la carpeta backtesting/ y no
# encuentra connectors/, core/, etc.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import MetaTrader5 as mt5
import pandas as pd

from connectors.mt5_connector import conectar, desconectar, asegurar_simbolo
from core.config import estrategia as E, rutas


def exportar_par(par: str, desde: datetime, hasta: datetime, carpeta_salida: str):
    if not asegurar_simbolo(par):
        print(f"  ❌ {par}: símbolo no disponible en este broker, se omite.")
        return

    velas = mt5.copy_rates_range(par, mt5.TIMEFRAME_M1, desde, hasta)
    if velas is None or len(velas) == 0:
        print(f"  ❌ {par}: MT5 no devolvió velas para ese rango de fechas.")
        return

    df = pd.DataFrame(velas)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    df = df[["time", "open", "high", "low", "close", "tick_volume"]]

    os.makedirs(carpeta_salida, exist_ok=True)
    destino = os.path.join(carpeta_salida, f"{par}.csv")
    df.to_csv(destino, index=False)
    print(f"  ✅ {par}: {len(df)} velas exportadas a {destino}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--desde", required=True, help="YYYY-MM-DD")
    ap.add_argument("--hasta", required=True, help="YYYY-MM-DD")
    ap.add_argument("--pares", nargs="*", default=E.PARES)
    args = ap.parse_args()

    desde = datetime.strptime(args.desde, "%Y-%m-%d")
    hasta = datetime.strptime(args.hasta, "%Y-%m-%d")
    carpeta_salida = os.path.join(rutas.BASE_DIR, "data_files", "historicos")

    if not conectar():
        print("❌ No se pudo conectar a MT5. Abre el terminal e inicia sesión.")
        return

    print(f"Exportando histórico M1 de {desde.date()} a {hasta.date()}...")
    for par in args.pares:
        exportar_par(par, desde, hasta, carpeta_salida)

    desconectar()
    print(f"\nListo. Corre ahora: python backtesting/run_backtest.py "
          f"--carpeta {carpeta_salida}")


if __name__ == "__main__":
    main()
