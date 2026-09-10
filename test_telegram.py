"""
Prueba rápida: envía un mensaje de prueba a Telegram usando lo que
tengas configurado en tu .env. No toca MT5. Uso: python test_telegram.py
"""

from core.config import telegram as T
from notifications.telegram_service import enviar_senal

if __name__ == "__main__":
    print("Probando conexión con Telegram...")

    if not T.BOT_TOKEN:
        print("❌ TELEGRAM_BOT_TOKEN está vacío en tu .env.")
        raise SystemExit(1)
    if not T.CHAT_ID:
        print("❌ TELEGRAM_CHAT_ID está vacío en tu .env.")
        raise SystemExit(1)

    senal_prueba = {
        "par": "EURUSD", "direccion": "CALL", "score": 100,
        "precio": 1.08765, "sma200": 1.08700, "ema200": 1.08710,
        "ema100": 1.08750, "bb_superior": 1.08800, "bb_inferior": 1.08650,
        "rsi2": 8.5, "macd_hist": 0.00012, "stoch_k": 15.2, "stoch_d": 12.1,
        "psar": 1.08600,
        "detalle": {
            "tendencia": 1, "rsi2": 1, "macd": 1,
            "stochastic": 1, "bollinger": 1, "parabolic_sar": 1,
        },
    }

    ok = enviar_senal(senal_prueba)
    print("✅ Mensaje de prueba enviado. Revisa tu Telegram." if ok else
          "❌ No se pudo enviar. Revisa TELEGRAM_BOT_TOKEN/CHAT_ID.")
