"""
Estadísticas del historial en vivo (no confundir con backtesting/ — esto
lee data_files/historial.csv, las señales realmente enviadas). Sin cambios
de lógica respecto a v1 (services/stats.py), reubicado en storage/.
"""

import os
from collections import Counter

import pandas as pd

from core.config import rutas


def generar_estadisticas() -> dict:
    if not os.path.exists(rutas.HISTORIAL_PATH):
        return {"total_senales": 0}

    df = pd.read_csv(rutas.HISTORIAL_PATH)
    if df.empty:
        return {"total_senales": 0}

    stats = {
        "total_senales": len(df),
        "por_par": df["par"].value_counts().to_dict(),
        "por_direccion": df["direccion"].value_counts().to_dict(),
        "score_promedio": round(df["score"].mean(), 2),
        "score_maximo": int(df["score"].max()),
        "ultima_senal": df.iloc[-1]["timestamp"],
    }

    con_resultado = df[df["resultado"].isin(["WIN", "LOSS"])]
    if not con_resultado.empty:
        conteo = Counter(con_resultado["resultado"])
        total = len(con_resultado)
        stats["operaciones_con_resultado"] = total
        stats["winrate_pct"] = round(conteo.get("WIN", 0) / total * 100, 2)
    else:
        stats["operaciones_con_resultado"] = 0
        stats["winrate_pct"] = None

    return stats


def imprimir_estadisticas() -> None:
    stats = generar_estadisticas()
    print("\n" + "=" * 40)
    print("        THOR IA — ESTADÍSTICAS (en vivo)")
    print("=" * 40)
    if stats["total_senales"] == 0:
        print("Aún no hay señales registradas.")
        print("=" * 40)
        return

    print(f"Total de señales     : {stats['total_senales']}")
    print(f"Por par              : {stats['por_par']}")
    print(f"Por dirección        : {stats['por_direccion']}")
    print(f"Score promedio       : {stats['score_promedio']}")
    print(f"Score máximo         : {stats['score_maximo']}")
    print(f"Última señal         : {stats['ultima_senal']}")
    if stats["winrate_pct"] is not None:
        print(f"Winrate (con resultado): {stats['winrate_pct']}% "
              f"({stats['operaciones_con_resultado']} operaciones)")
    else:
        print("Winrate              : sin datos (no hay resultados cargados)")
    print("=" * 40)
