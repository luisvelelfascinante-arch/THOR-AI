"""
Configuración central de THOR AI, separada por dominio.
Los secretos se leen SIEMPRE de variables de entorno, nunca hardcodeados.
"""

import os
from dotenv import load_dotenv

load_dotenv()


class EstrategiaConfig:
    """Todo lo que define QUÉ se opera y con qué parámetros de mercado.
    NO modificar valores de indicadores sin justificación técnica o de
    backtesting — ver CHANGELOG.md."""

    PARES = os.getenv("PARES", "").split(",") if os.getenv("PARES") else [
        "EURUSD",
        "GBPUSD",
        "USDJPY",
        "EURJPY",
        "GBPJPY",
    ]

    TEMPORALIDAD_PRINCIPAL = "M1"
    EXPIRACION_MINUTOS = 3

    # Modo de decisión: "confluencia_total" (6/6 obligatorio, comportamiento
    # v1, es el que sigue corriendo en vivo) o "score_ponderado" (Fase 3,
    # nuevo motor — NO se activa solo hasta que el backtesting lo respalde
    # y tú lo confirmes explícitamente).
    STRATEGY_MODE = os.getenv("STRATEGY_MODE", "confluencia_total")

    # --- Parámetros de indicadores (idénticos a v1, tomados de la
    #     plataforma real, no reinventados) ---
    BB_PERIODO = 10
    BB_DESVIACION = 2
    EMA_CORTA = 100
    EMA_LARGA = 200
    SMA_LARGA = 200
    MACD_RAPIDA, MACD_LENTA, MACD_SENAL = 12, 26, 9
    PSAR_PASO, PSAR_MAX = 0.02, 0.2
    RSI_PERIODO_CONF = 2
    RSI_SOBRECOMPRA, RSI_SOBREVENTA = 90, 10
    STOCH_K, STOCH_SUAVIZADO, STOCH_D = 14, 3, 3
    STOCH_SOBRECOMPRA, STOCH_SOBREVENTA = 80, 20

    # ATR — NUEVO (v2.1). Filtro de volatilidad, práctica establecida en
    # trading algorítmico para evitar señales falsas en mercado "choppy"
    # (rango sin dirección). Fuentes: AlfaTactix ATR Filter, Wilder (1978)
    # "New Concepts in Technical Trading Systems"; en opciones binarias
    # específicamente: TradingFinder, guía de indicadores. Periodo 14 es
    # el estándar de Wilder, no un valor inventado para este proyecto.
    ATR_PERIODO = 14
    ATR_VENTANA_PROMEDIO = 50  # línea base para comparar "volatilidad actual vs normal"
    ATR_FILTRO_ACTIVO = os.getenv("ATR_FILTRO_ACTIVO", "false").lower() == "true"
    ATR_UMBRAL_MULTIPLICADOR = float(os.getenv("ATR_UMBRAL_MULTIPLICADOR", 0.8))

    VELAS_MINIMAS = max(SMA_LARGA, EMA_LARGA, ATR_VENTANA_PROMEDIO * 2) * 3


class OperativaConfig:
    """Todo lo que define CÓMO opera el proceso (no la estrategia)."""

    PROBABILIDAD_MINIMA = int(os.getenv("PROBABILIDAD_MINIMA", 90))
    INTERVALO_ESCANEO_SEGUNDOS = int(os.getenv("INTERVALO_ESCANEO_SEGUNDOS", 15))
    COOLDOWN_MINUTOS = int(
        os.getenv("COOLDOWN_MINUTOS", EstrategiaConfig.EXPIRACION_MINUTOS)
    )
    MODO = os.getenv("MODO", "PRACTICA")  # PRACTICA | REAL

    # Payout asumido para profit factor en backtesting (ajustar al real de
    # tu bróker/IQ Option; no se inventa, debe venir de tu plataforma).
    PAYOUT_PCT = float(os.getenv("PAYOUT_PCT", 0.87))


class RiesgoConfig:
    """Reglas de riesgo. Se aplican SIEMPRE, incluso en modo señales-only,
    porque también limitan cuántas notificaciones se disparan."""

    MAX_SENALES_POR_HORA = int(os.getenv("MAX_SENALES_POR_HORA", 4))
    MAX_SENALES_POR_PAR_POR_DIA = int(os.getenv("MAX_SENALES_POR_PAR_POR_DIA", 6))
    # Si en backtesting el drawdown simulado de una racha de pérdidas supera
    # esto, el gestor de riesgo puede pausar el bot (Fase 3/4).
    MAX_PERDIDAS_CONSECUTIVAS = int(os.getenv("MAX_PERDIDAS_CONSECUTIVAS", 4))


class ConexionConfig:
    MT5_LOGIN = os.getenv("MT5_LOGIN")
    MT5_PASSWORD = os.getenv("MT5_PASSWORD")
    MT5_SERVER = os.getenv("MT5_SERVER")


class TelegramConfig:
    BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
    CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")


class RutasConfig:
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    HISTORIAL_PATH = os.path.join(BASE_DIR, "data_files", "historial.csv")
    LOG_PATH = os.path.join(BASE_DIR, "logs", "thor.log")
    BACKTEST_RESULTS_DIR = os.path.join(BASE_DIR, "data_files", "backtests")


# Instancias únicas — el resto del proyecto importa estas, no las clases.
estrategia = EstrategiaConfig()
operativa = OperativaConfig()
riesgo = RiesgoConfig()
conexion = ConexionConfig()
telegram = TelegramConfig()
rutas = RutasConfig()
