"""
Modo diagnóstico — adaptado a la arquitectura v2. Mismo comportamiento
que el diagnostico.py que ya usaste (ciclo único, motivo exacto de
rechazo), ahora usando los módulos separados de v2.

Uso: python diagnostico.py
"""

import MetaTrader5 as mt5

from core.config import estrategia as E, operativa as O
from connectors.mt5_connector import conectar, desconectar, asegurar_simbolo
from data.data_provider import obtener_velas, velas_disponibles
from indicators.indicator_bank import calcular_confluencia
from strategy.strategy_engine import evaluar_datos

NOMBRES_CONFIRMACION = {
    "tendencia": "Tendencia (precio/EMA100/EMA200/SMA200)",
    "rsi2": "RSI(2) 90/10",
    "macd": "MACD(12,26,9) histograma",
    "stochastic": "Stochastic(14,3,3) 80/20",
    "bollinger": "Bollinger Bands(10,2)",
    "parabolic_sar": "Parabolic SAR (0.02/0.2)",
}


def diagnosticar():
    print("=" * 72)
    print(f"THOR IA v2 — MODO DIAGNÓSTICO (motor activo: {E.STRATEGY_MODE})")
    print("=" * 72)

    if not conectar():
        print("\n❌ FALLA CRÍTICA: no se pudo conectar a MetaTrader 5.")
        print(f"   Detalle MT5: {mt5.last_error()}")
        return

    print("✅ Conexión MT5 OK.")

    for par in E.PARES:
        print("\n" + "-" * 72)
        print(f"PAR: {par}")
        print("-" * 72)

        if not asegurar_simbolo(par):
            continue

        v_conf = velas_disponibles(par, "M1", int(E.VELAS_MINIMAS))
        print(f"  Velas M1 para confluencia: {v_conf} "
              f"(necesita >= {max(E.SMA_LARGA, E.EMA_LARGA) + 5})")

        df = obtener_velas(par, "M1", int(E.VELAS_MINIMAS))
        if df is None:
            print(f"  ❌ MT5 no entregó velas suficientes para {par}.")
            continue

        datos = calcular_confluencia(df)
        if datos is None:
            print(f"  ❌ Datos insuficientes o con NaN tras calcular indicadores.")
            continue

        score, direccion, detalle = evaluar_datos(par, datos)

        print(f"  Precio               : {datos['precio']:.5f}")
        print(f"  SMA200/EMA200/EMA100 : {datos['sma200']:.5f} / "
              f"{datos['ema200']:.5f} / {datos['ema100']:.5f}")
        print(f"  Bollinger(10,2)      : {datos['bb_inferior']:.5f} — {datos['bb_superior']:.5f}")
        print(f"  RSI(2)               : {datos['rsi2']:.2f}")
        print(f"  MACD hist            : {datos['macd_hist']:.6f} (prev: {datos['macd_hist_prev']:.6f})")
        print(f"  Stochastic %K/%D     : {datos['stoch_k']:.2f} / {datos['stoch_d']:.2f}")
        print(f"  Parabolic SAR        : {datos['psar']:.5f}")
        print(f"  THOR SCORE           : {score}/100 (mínimo: {O.PROBABILIDAD_MINIMA})")

        if direccion:
            print(f"  ✅ SEÑAL VÁLIDA: {direccion}")
        else:
            print(f"  ⏳ SIN SEÑAL.")
            factores = detalle.get("factores", detalle) if isinstance(detalle, dict) else {}
            for clave, valor in factores.items():
                if clave not in NOMBRES_CONFIRMACION:
                    continue
                estado = {1: "CALL", -1: "PUT", 0: "neutro"}.get(valor, "?")
                marca = "✅" if valor != 0 else "❌"
                print(f"      {marca} {NOMBRES_CONFIRMACION[clave]:42s}: {estado}")

    desconectar()
    print("\n" + "=" * 72)
    print("Diagnóstico terminado.")
    print("=" * 72)


if __name__ == "__main__":
    diagnosticar()
