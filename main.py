import sys
from datetime import datetime

from core.config import estrategia as E, operativa as O
from core.logging_setup import configurar_logging
from core.brain import analizar_mercado
from connectors.mt5_connector import conectar, desconectar
from storage.stats import imprimir_estadisticas


def iniciar_thor():
    print("=" * 50)
    print("        THOR AI v2.0")
    print("=" * 50)
    print(f"Fecha  : {datetime.now()}")
    print(f"Modo   : {O.MODO}")
    print(f"Motor  : {E.STRATEGY_MODE}")
    print(f"Pares  : {', '.join(E.PARES)}")
    print(f"Umbral : THOR SCORE >= {O.PROBABILIDAD_MINIMA}/100")
    print("=" * 50)


if __name__ == "__main__":
    configurar_logging()
    iniciar_thor()

    if "--stats" in sys.argv:
        imprimir_estadisticas()
        sys.exit(0)

    if not conectar():
        print("\n❌ No se pudo conectar a MetaTrader 5. "
              "Verifica que el terminal esté abierto y con sesión iniciada, "
              "o revisa MT5_LOGIN / MT5_PASSWORD / MT5_SERVER en tu .env.")
        sys.exit(1)

    try:
        analizar_mercado()
    finally:
        desconectar()
