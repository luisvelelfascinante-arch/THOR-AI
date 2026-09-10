"""
Optimización — v3.0.

CORRECCIÓN DE RENDIMIENTO respecto a v2.x (ver PERFORMANCE.md, puntos 2 y
6): antes, cada combinación de umbral×motor volvía a calcular los
indicadores desde cero para el mismo segmento de datos — con 5 umbrales
× 2 motores eso eran 10 recálculos idénticos. Ahora los indicadores se
calculan UNA vez por (par, segmento) con preparar_serie_y_senales() y se
REUTILIZAN para las 10 combinaciones — solo cambia la evaluación barata
de motor/umbral sobre esos indicadores ya calculados.

También se corrigió un bug real: la versión anterior mutaba
core.config.operativa.PROBABILIDAD_MINIMA como forma de "pasar" el umbral
a probar — eso no sobrevive a multiprocessing (cada proceso hijo relee su
.env desde cero) y es frágil incluso sin paralelismo. Ahora el umbral se
pasa como parámetro explícito en toda la cadena.

MÉTODOS DISPONIBLES:
  - optimizar(): un solo split train/test (70/30 cronológico).
  - walk_forward_rolling(): walk-forward ANCHORED con N folds (más
    riguroso, ver FUENTES.md punto 6).

Uso:
    python optimization/optimizer.py --carpeta data_files/historicos
    python optimization/optimizer.py --carpeta data_files/historicos --rolling --folds 5
"""

import argparse
import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd

from backtesting.backtest_engine import (
    calcular_estadisticas, generar_operaciones, preparar_serie_y_senales,
)
from backtesting.loader import cargar_carpeta
from core.config import rutas

UMBRALES_PROBAR = [70, 75, 80, 85, 90]
MOTORES_PROBAR = ["confluencia_total", "score_ponderado"]
TRAIN_PCT = 0.7

# 50 en vez de 30 -- ver FUENTES.md punto 4 (tamaño mínimo de muestra).
MIN_OPERACIONES_PARA_CONSIDERAR = 50


# ---------------------------------------------------------------------------
# Preparación de datos (indicadores) — la parte cara, se hace UNA vez
# ---------------------------------------------------------------------------

def _preparar_par(args_tupla):
    """Nivel de módulo (picklable para multiprocessing). Calcula
    indicadores+señales de UN par para UN segmento de datos."""
    par, df = args_tupla
    serie, senales = preparar_serie_y_senales(par, df)
    return par, df, serie, senales


def _preparar_todos_los_pares(datos_por_par: dict, en_paralelo: bool = True) -> dict:
    """Devuelve {par: (df, serie, senales)}, calculado en paralelo por
    par cuando hay más de uno (independientes entre sí, CPU-bound —
    caso ideal para multiprocessing)."""
    resultado = {}
    tareas = list(datos_por_par.items())

    if not en_paralelo or len(tareas) <= 1:
        for par, df in tareas:
            _, df2, serie, senales = _preparar_par((par, df))
            if serie is not None:
                resultado[par] = (df2, serie, senales)
        return resultado

    with ProcessPoolExecutor(max_workers=min(len(tareas), os.cpu_count() or 4)) as executor:
        futuros = {executor.submit(_preparar_par, t): t[0] for t in tareas}
        for futuro in as_completed(futuros):
            par = futuros[futuro]
            try:
                _, df2, serie, senales = futuro.result()
                if serie is not None:
                    resultado[par] = (df2, serie, senales)
            except Exception as exc:
                print(f"  ❌ {par} falló al preparar indicadores: {exc}")

    return resultado


# ---------------------------------------------------------------------------
# Evaluación de una combinación motor×umbral — barata, se repite mucho
# ---------------------------------------------------------------------------

def _correr_config(pares_preparados: dict, motor: str, umbral: int) -> dict:
    """pares_preparados: salida de _preparar_todos_los_pares().
    NO recalcula indicadores — solo aplica motor+umbral sobre lo que ya
    está calculado. Esto es lo que hace posible probar 10+ combinaciones
    en segundos en vez de minutos."""
    todas = []
    for par, (df, serie, senales) in pares_preparados.items():
        trades = generar_operaciones(
            par, df, serie, senales, motor=motor, umbral_minimo=umbral,
        )
        todas.append(trades)

    trades_totales = pd.concat(todas, ignore_index=True) if todas else pd.DataFrame()
    stats = calcular_estadisticas(trades_totales)
    stats["motor"] = motor
    stats["umbral"] = umbral
    return stats


def _grid_search(pares_preparados: dict) -> list[dict]:
    resultados = []
    for motor in MOTORES_PROBAR:
        for umbral in UMBRALES_PROBAR:
            resultados.append(_correr_config(pares_preparados, motor, umbral))
    return resultados


def _mejores_validos(resultados: list[dict]) -> list[dict]:
    validos = [
        r for r in resultados
        if r.get("con_resultado_valido", 0) >= MIN_OPERACIONES_PARA_CONSIDERAR
        and r.get("profit_factor") is not None
    ]
    validos.sort(key=lambda r: r["profit_factor"], reverse=True)
    return validos


# ---------------------------------------------------------------------------
# Split único train/test
# ---------------------------------------------------------------------------

def _dividir_train_test(datos_por_par: dict) -> tuple[dict, dict]:
    train, test = {}, {}
    for par, df in datos_por_par.items():
        corte = int(len(df) * TRAIN_PCT)
        train[par] = df.iloc[:corte].reset_index(drop=True)
        test[par] = df.iloc[corte:].reset_index(drop=True)
    return train, test


def optimizar(carpeta: str) -> dict:
    datos_por_par = cargar_carpeta(carpeta)
    train, test = _dividir_train_test(datos_por_par)

    print("Preparando indicadores de TRAIN (una vez, en paralelo por par)...")
    t0 = time.time()
    train_preparado = _preparar_todos_los_pares(train)
    print(f"  -> listo en {time.time() - t0:.2f}s.")

    resultados_train = _grid_search(train_preparado)
    validos_train = _mejores_validos(resultados_train)

    resultado_test = None
    if validos_train:
        mejor = validos_train[0]
        print(f"\nPreparando indicadores de TEST...")
        test_preparado = _preparar_todos_los_pares(test)
        resultado_test = _correr_config(test_preparado, mejor["motor"], mejor["umbral"])

    return {
        "todos_train": resultados_train,
        "ranking_train": validos_train,
        "mejor_config_train": validos_train[0] if validos_train else None,
        "validacion_test": resultado_test,
    }


def _advertencia_overfitting(train: dict, test: dict) -> str | None:
    if not train or not test:
        return None
    wr_train = train.get("winrate_pct")
    wr_test = test.get("winrate_pct")
    if wr_train is None or wr_test is None:
        return None
    caida = wr_train - wr_test
    if caida > 10:
        return (f"⚠️ El winrate cae {round(caida, 1)} puntos de train ({wr_train}%) "
                f"a test ({wr_test}%). Señal de posible overfitting — no actives "
                f"esta configuración en vivo solo por el resultado de train.")
    return None


# ---------------------------------------------------------------------------
# Walk-forward anchored (múltiples folds)
# ---------------------------------------------------------------------------

def _dividir_en_folds(datos_por_par: dict, n_folds: int) -> list[dict]:
    folds = [dict() for _ in range(n_folds)]
    for par, df in datos_por_par.items():
        tam = len(df) // n_folds
        for i in range(n_folds):
            inicio = i * tam
            fin = len(df) if i == n_folds - 1 else (i + 1) * tam
            folds[i][par] = df.iloc[inicio:fin].reset_index(drop=True)
    return folds


def _concatenar_folds(folds: list[dict]) -> dict:
    pares = folds[0].keys()
    return {
        par: pd.concat([f[par] for f in folds], ignore_index=True)
        for par in pares
    }


def walk_forward_rolling(carpeta: str, n_folds: int = 5) -> dict:
    """Walk-forward ANCHORED — ver FUENTES.md punto 6."""
    datos_por_par = cargar_carpeta(carpeta)
    folds = _dividir_en_folds(datos_por_par, n_folds)

    resultados_por_fold = []
    for i in range(1, n_folds):
        train = _concatenar_folds(folds[:i])
        test = folds[i]

        print(f"\n[Fold {i}] Preparando indicadores de train ({i} folds acumulados)...")
        train_preparado = _preparar_todos_los_pares(train)
        candidatos = _grid_search(train_preparado)
        validos = _mejores_validos(candidatos)

        if not validos:
            resultados_por_fold.append({
                "fold": i, "mensaje": "Sin config válida en este train (muestra insuficiente)."
            })
            continue

        mejor = validos[0]
        test_preparado = _preparar_todos_los_pares(test)
        resultado_test = _correr_config(test_preparado, mejor["motor"], mejor["umbral"])

        resultados_por_fold.append({
            "fold": i,
            "train_folds_usados": i,
            "motor": mejor["motor"],
            "umbral": mejor["umbral"],
            "train_winrate_pct": mejor.get("winrate_pct"),
            "train_profit_factor": mejor.get("profit_factor"),
            "test_winrate_pct": resultado_test.get("winrate_pct"),
            "test_profit_factor": resultado_test.get("profit_factor"),
            "test_operaciones": resultado_test.get("con_resultado_valido"),
        })

    motores_elegidos = [r.get("motor") for r in resultados_por_fold if "motor" in r]
    umbrales_elegidos = [r.get("umbral") for r in resultados_por_fold if "umbral" in r]

    return {
        "n_folds": n_folds,
        "resultados_por_fold": resultados_por_fold,
        "motor_mas_elegido": max(set(motores_elegidos), key=motores_elegidos.count) if motores_elegidos else None,
        "consistencia_motor": (motores_elegidos.count(motores_elegidos[0]) == len(motores_elegidos)
                                 if motores_elegidos else None),
        "umbrales_elegidos_por_fold": umbrales_elegidos,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--carpeta", required=True)
    ap.add_argument("--rolling", action="store_true",
                     help="Walk-forward anchored con múltiples folds en vez "
                          "de un solo split train/test.")
    ap.add_argument("--folds", type=int, default=5)
    args = ap.parse_args()

    os.makedirs(rutas.BACKTEST_RESULTS_DIR, exist_ok=True)
    t_total = time.time()

    if args.rolling:
        resultado = walk_forward_rolling(args.carpeta, n_folds=args.folds)
        salida = os.path.join(rutas.BACKTEST_RESULTS_DIR, "walk_forward_rolling.json")
        with open(salida, "w", encoding="utf-8") as f:
            json.dump(resultado, f, indent=2, ensure_ascii=False)

        print("\n" + "=" * 60)
        print(f"WALK-FORWARD ANCHORED — {args.folds} folds")
        print("=" * 60)
        for r in resultado["resultados_por_fold"]:
            if "mensaje" in r:
                print(f"  Fold {r['fold']}: {r['mensaje']}")
                continue
            print(f"  Fold {r['fold']} (train={r['train_folds_usados']} folds): "
                  f"motor={r['motor']:18s} umbral={r['umbral']:3d} | "
                  f"train WR={r['train_winrate_pct']}% PF={r['train_profit_factor']} "
                  f"-> test WR={r['test_winrate_pct']}% PF={r['test_profit_factor']} "
                  f"({r['test_operaciones']} ops)")
        print(f"\nConfiguración más elegida entre folds: {resultado['motor_mas_elegido']}")
        print(f"¿Misma config en todos los folds?: {resultado['consistencia_motor']}")
        if resultado["consistencia_motor"] is False:
            print("⚠️  La configuración ganadora cambia de fold a fold — indicio de que "
                  "no hay un patrón estable, no solo suerte de un split particular.")
        print(f"\nDetalle completo: {salida}")
        print(f"⏱️  Tiempo total: {time.time() - t_total:.2f}s")
        return

    resultado = optimizar(args.carpeta)

    salida = os.path.join(rutas.BACKTEST_RESULTS_DIR, "optimizacion.json")
    with open(salida, "w", encoding="utf-8") as f:
        json.dump(resultado, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 60)
    print(f"RANKING EN TRAIN (solo configs con >= "
          f"{MIN_OPERACIONES_PARA_CONSIDERAR} operaciones)")
    print("=" * 60)
    if not resultado["ranking_train"]:
        print("Ninguna configuración alcanzó la muestra mínima en train — "
              "exporta más histórico con export_historico.py.")
    for r in resultado["ranking_train"][:5]:
        print(f"  motor={r['motor']:18s} umbral={r['umbral']:3d}  "
              f"winrate={r['winrate_pct']}%  profit_factor={r['profit_factor']}  "
              f"operaciones={r['con_resultado_valido']}")

    if resultado["validacion_test"]:
        print("\n" + "=" * 60)
        print("VALIDACIÓN EN TEST (datos que NO se usaron para elegir el umbral)")
        print("=" * 60)
        t = resultado["validacion_test"]
        print(f"  winrate={t.get('winrate_pct')}%  "
              f"profit_factor={t.get('profit_factor')}  "
              f"operaciones={t.get('con_resultado_valido')}")
        alerta = _advertencia_overfitting(resultado["mejor_config_train"], t)
        if alerta:
            print(f"\n{alerta}")
        else:
            print("\n✅ El resultado en test es consistente con train — "
                  "no hay señal fuerte de overfitting, pero sigue siendo "
                  "una única validación, no una garantía.")

    print(f"\nDetalle completo: {salida}")
    print(f"⏱️  Tiempo total: {time.time() - t_total:.2f}s")


if __name__ == "__main__":
    main()
