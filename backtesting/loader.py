"""
Carga de datos históricos para backtesting.

IMPORTANTE: este proyecto NO incluye datos históricos ni los genera de
ninguna forma. Tú debes exportarlos desde tu propio MT5 (con sesión real
conectada) usando el script export_historico.py incluido en esta carpeta,
y correrlo en tu máquina Windows. El backtester SOLO lee lo que tú le
entregues — así se cumple "no inventar datos ni resultados".

Formato esperado del CSV (una fila por vela M1):
    time,open,high,low,close,tick_volume
    2024-01-02 00:00:00,1.10345,1.10360,1.10330,1.10352,134
    ...
Es exactamente lo que devuelve mt5.copy_rates_range() al pasarlo por
pandas.DataFrame + to_csv() — ver export_historico.py.
"""

import logging
import os

import pandas as pd

log = logging.getLogger("thor.backtesting.loader")

_COLUMNAS_REQUERIDAS = {"time", "open", "high", "low", "close"}


def cargar_csv(path: str) -> pd.DataFrame:
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"No existe el archivo histórico: {path}. "
            f"Expórtalo primero con backtesting/export_historico.py en tu "
            f"máquina con MT5."
        )

    df = pd.read_csv(path, parse_dates=["time"])

    faltantes = _COLUMNAS_REQUERIDAS - set(df.columns)
    if faltantes:
        raise ValueError(
            f"El CSV '{path}' no tiene las columnas requeridas: {faltantes}. "
            f"Debe venir de export_historico.py sin modificar."
        )

    df = df.sort_values("time").reset_index(drop=True)

    if df["time"].duplicated().any():
        log.warning("El histórico '%s' tiene timestamps duplicados — "
                     "revisa la fuente antes de confiar en los resultados.", path)

    return df


def cargar_carpeta(carpeta: str) -> dict[str, pd.DataFrame]:
    """Espera archivos nombrados '<PAR>.csv' (ej. 'EURUSD.csv') dentro de
    la carpeta. Devuelve {par: DataFrame}."""
    if not os.path.isdir(carpeta):
        raise FileNotFoundError(f"No existe la carpeta de históricos: {carpeta}")

    resultado = {}
    for archivo in sorted(os.listdir(carpeta)):
        if not archivo.lower().endswith(".csv"):
            continue
        par = os.path.splitext(archivo)[0].upper()
        resultado[par] = cargar_csv(os.path.join(carpeta, archivo))

    if not resultado:
        raise FileNotFoundError(
            f"No se encontró ningún .csv en '{carpeta}'. "
            f"Corre export_historico.py primero."
        )

    return resultado
