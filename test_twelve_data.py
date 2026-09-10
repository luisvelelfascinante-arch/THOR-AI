"""
Prueba de conexión con Twelve Data. Pide unas pocas velas de un solo par
y muestra el resultado — no toca Telegram, no toca MT5, no genera
señales. Es el equivalente de test_telegram.py pero para la fuente de
datos.

Uso:
    python test_twelve_data.py
"""

import sys

from core.config import estrategia as E, conexion as C
from connectors.twelve_data_connector import obtener_velas_twelve_data, estado_cupo

if __name__ == "__main__":
    print("Probando conexión con Twelve Data...")

    if not C.TWELVE_DATA_API_KEY:
        print("❌ TWELVE_DATA_API_KEY está vacío en tu .env. Revísalo.")
        sys.exit(1)

    par_prueba = E.PARES[0] if E.PARES else "EURUSD"
    print(f"Pidiendo 10 velas de {par_prueba} ({E.INTERVAL})...")

    df = obtener_velas_twelve_data(par_prueba, E.INTERVAL, 10)

    if df is None:
        print("❌ No se pudo obtener velas. Revisa el log de arriba para el "
              "motivo exacto (API key inválida, símbolo no soportado, límite "
              "de cupo alcanzado, error de red, etc.).")
        sys.exit(1)

    print(f"\n✅ Conexión OK. Últimas velas de {par_prueba}:")
    print(df.tail(5).to_string(index=False))

    cupo = estado_cupo()
    print(f"\nCupo usado hoy: {cupo['llamadas_hoy']}/{cupo['margen_seguridad']} "
          f"(margen de seguridad; límite real del plan gratuito: "
          f"{cupo['limite_real_dia']}/día).")
