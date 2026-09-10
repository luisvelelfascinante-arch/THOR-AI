import sys
from datetime import datetime

from core.config import estrategia as E, operativa as O, conexion as C
from core.logging_setup import configurar_logging
from core.brain import analizar_mercado
from storage.stats import imprimir_estadisticas


def iniciar_thor():
    print("=" * 50)
    print("        THOR AI v4.0")
    print("=" * 50)
    print(f"Fecha       : {datetime.now()}")
    print(f"Modo        : {O.MODO}")
    print(f"Fuente datos: {O.DATA_SOURCE}")
    print(f"Motor       : {E.STRATEGY_MODE}")
    print(f"Pares       : {', '.join(E.PARES)}")
    print(f"Intervalo   : {E.INTERVAL} | Escaneo cada {O.INTERVALO_ESCANEO_SEGUNDOS}s")
    print(f"Umbral      : THOR SCORE >= {O.PROBABILIDAD_MINIMA}/100")
    print("=" * 50)


if __name__ == "__main__":
    configurar_logging()
    iniciar_thor()

    if "--stats" in sys.argv:
        imprimir_estadisticas()
        sys.exit(0)

    if O.DATA_SOURCE == "twelve_data":
        if not C.TWELVE_DATA_API_KEY:
            print("\n❌ TWELVE_DATA_API_KEY no está configurada en tu .env.")
            sys.exit(1)
        try:
            analizar_mercado()
        except KeyboardInterrupt:
            pass
    else:  # mt5
        from connectors.mt5_connector import conectar, desconectar
        if not conectar():
            print("\n❌ No se pudo conectar a MetaTrader 5. "
                  "Verifica que el terminal esté abierto y con sesión iniciada, "
                  "o revisa MT5_LOGIN / MT5_PASSWORD / MT5_SERVER en tu .env.")
            sys.exit(1)
        try:
            analizar_mercado()
        finally:
            desconectar()
