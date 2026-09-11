"""
Modo diagnóstico — funciona con cualquiera de las 2 fuentes de datos
(core.config.operativa.DATA_SOURCE = "twelve_data" | "mt5"). Ciclo único,
muestra el motivo exacto de rechazo por par.

Uso: python diagnostico.py
"""

from core.consola import forzar_utf8

forzar_utf8()

from core.config import estrategia as E, operativa as O, conexion as C
from data.data_provider import obtener_velas, velas_disponibles
from indicators.indicator_bank import calcular_confluencia
from indicators.volatility_filter import volatilidad_suficiente
from strategy.strategy_engine import evaluar_datos

NOMBRES_CONFIRMACION = {
    "tendencia": "Tendencia (precio/EMA100/EMA200/SMA200)",
    "rsi2": "RSI(2) 90/10",
    "macd": "MACD(12,26,9) histograma",
    "stochastic": "Stochastic(14,3,3) 80/20",
    "bollinger": "Bollinger Bands(10,2)",
    "parabolic_sar": "Parabolic SAR (0.02/0.2)",
}


def _preparar_conexion() -> bool:
    """Devuelve True si se puede continuar. Imprime el diagnóstico de la
    fuente configurada y hace lo que haga falta para dejarla lista."""
    print(f"Fuente de datos configurada: {O.DATA_SOURCE}")

    if O.DATA_SOURCE == "twelve_data":
        if not C.TWELVE_DATA_API_KEY:
            print("\n❌ TWELVE_DATA_API_KEY no está configurada en tu .env.")
            print("   Consigue una gratis en https://twelvedata.com/pricing "
                  "(plan Basic/Free) y pégala en TWELVE_DATA_API_KEY=.")
            return False

        from connectors.twelve_data_connector import estado_cupo
        cupo = estado_cupo()
        print(f"✅ TWELVE_DATA_API_KEY configurada.")
        print(f"   Cupo de hoy: {cupo['llamadas_hoy']}/{cupo['margen_seguridad']} "
              f"usadas (límite real del plan gratuito: {cupo['limite_real_dia']}/día, "
              f"8/minuto).")
        return True

    else:  # mt5
        from connectors.mt5_connector import conectar, info_cuenta
        if not conectar():
            import connectors.mt5_connector as mtc
            print("\n❌ FALLA CRÍTICA: no se pudo conectar a MetaTrader 5.")
            try:
                mt5 = mtc._cargar_mt5()
                print(f"   Detalle MT5: {mt5.last_error()}")
            except Exception:
                pass
            return False

        print("✅ Conexión MT5 OK.")
        terminal, cuenta = info_cuenta()
        if terminal:
            print(f"   Terminal conectado: {getattr(terminal, 'connected', '?')} | "
                  f"Trade permitido: {getattr(terminal, 'trade_allowed', '?')}")
        if cuenta:
            print(f"   Cuenta: {cuenta.login} | Servidor: {cuenta.server} | "
                  f"Modo: {'DEMO' if cuenta.trade_mode == 0 else 'REAL/OTRO'}")
        return True


def _asegurar_simbolo_si_aplica(par: str) -> bool:
    """Solo MT5 necesita 'activar' el símbolo en Market Watch antes de
    pedir velas; Twelve Data no tiene ese concepto."""
    if O.DATA_SOURCE == "mt5":
        from connectors.mt5_connector import asegurar_simbolo
        return asegurar_simbolo(par)
    return True


def diagnosticar():
    print("=" * 72)
    print(f"THOR IA v4 — MODO DIAGNÓSTICO (motor activo: {E.STRATEGY_MODE})")
    print("=" * 72)

    if not _preparar_conexion():
        return

    for par in E.PARES:
        print("\n" + "-" * 72)
        print(f"PAR: {par}")
        print("-" * 72)

        if not _asegurar_simbolo_si_aplica(par):
            continue

        v_conf = velas_disponibles(par, "M1", int(E.VELAS_MINIMAS))
        print(f"  Velas M1 para confluencia: {v_conf} "
              f"(necesita >= {max(E.SMA_LARGA, E.EMA_LARGA) + 5})")

        df = obtener_velas(par, "M1", int(E.VELAS_MINIMAS))
        if df is None:
            print(f"  ❌ {O.DATA_SOURCE} no entregó velas suficientes para {par}.")
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
        print(f"  ATR({E.ATR_PERIODO}) actual/promedio: {datos['atr_actual']:.6f} / "
              f"{datos['atr_promedio']:.6f} "
              f"(filtro ATR {'ACTIVO' if E.ATR_FILTRO_ACTIVO else 'inactivo'}: "
              f"{'✅ pasa' if volatilidad_suficiente(datos) else '❌ mercado de baja volatilidad'})")
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

    if O.DATA_SOURCE == "mt5":
        from connectors.mt5_connector import desconectar
        desconectar()

    print("\n" + "=" * 72)
    print("Diagnóstico terminado.")
    print("=" * 72)


if __name__ == "__main__":
    diagnosticar()
