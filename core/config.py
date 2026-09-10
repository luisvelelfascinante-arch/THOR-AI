"""
Configuración central de THOR AI, separada por dominio.
Los secretos se leen SIEMPRE de variables de entorno, nunca hardcodeados.
"""

import math
import os
from dotenv import load_dotenv

load_dotenv()


class EstrategiaConfig:
    """Todo lo que define QUÉ se opera y con qué parámetros de mercado.
    NO modificar valores de indicadores sin justificación técnica o de
    backtesting — ver CHANGELOG.md."""

    # SYMBOLS es el nombre nuevo (v4.0, alineado a la fuente de datos
    # Twelve Data); PARES sigue funcionando por compatibilidad con v2/v3.
    # Prioridad: SYMBOLS > PARES > lista por defecto.
    _pares_env = os.getenv("SYMBOLS") or os.getenv("PARES") or ""
    PARES = [p.strip().upper() for p in _pares_env.split(",") if p.strip()] or [
        "EURUSD",
        "GBPUSD",
        "USDJPY",
        "EURJPY",
        "GBPJPY",
    ]
    SYMBOLS = PARES  # alias, mismo objeto — así cualquiera de los dos nombres sirve

    TEMPORALIDAD_PRINCIPAL = "M1"  # usado solo por el conector MT5 (timeframe MT5)

    # INTERVAL es el nombre nuevo (v4.0) para el timeframe de velas, en el
    # formato que espera Twelve Data ("1min", "5min", "15min", etc.).
    INTERVAL = os.getenv("INTERVAL", "1min")

    # EXPIRY_MINUTES (nuevo) / EXPIRACION_MINUTOS (nombre original) — mismo valor.
    EXPIRACION_MINUTOS = int(os.getenv("EXPIRY_MINUTES") or os.getenv("EXPIRACION_MINUTOS") or 3)
    EXPIRY_MINUTES = EXPIRACION_MINUTOS  # alias

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

    # MIN_SCORE (nuevo) / PROBABILIDAD_MINIMA (nombre original) — mismo valor.
    PROBABILIDAD_MINIMA = int(os.getenv("MIN_SCORE") or os.getenv("PROBABILIDAD_MINIMA") or 90)
    MIN_SCORE = PROBABILIDAD_MINIMA  # alias

    # Fuente de datos para el modo EN VIVO (el backtesting siempre lee CSV,
    # esto no lo afecta). "twelve_data" (nuevo, v4.0, API en la nube — no
    # requiere MT5 abierto) o "mt5" (requiere terminal MT5 abierto en Windows).
    DATA_SOURCE = os.getenv("DATA_SOURCE", "twelve_data").lower()

    # SCAN_SECONDS (nuevo) / INTERVALO_ESCANEO_SEGUNDOS (nombre original).
    # Con Twelve Data en el plan gratuito el límite es 8 llamadas/minuto y
    # 800/día (1 crédito por símbolo por llamada) — ver
    # connectors/twelve_data_connector.py. Si no se especifica explícito,
    # se calcula un intervalo que NO agote el cupo diario con la cantidad
    # de símbolos configurada, en vez de heredar el 15s pensado para MT5
    # (que no tiene ese límite).
    _scan_env = os.getenv("SCAN_SECONDS") or os.getenv("INTERVALO_ESCANEO_SEGUNDOS")
    if _scan_env:
        INTERVALO_ESCANEO_SEGUNDOS = int(_scan_env)
    elif DATA_SOURCE == "twelve_data":
        _n_simbolos = max(len(EstrategiaConfig.PARES), 1)
        # margen de seguridad: apunta a 750/día, no a los 800 exactos
        _segundos_seguros = math.ceil(_n_simbolos * 86400 / 750)
        INTERVALO_ESCANEO_SEGUNDOS = max(60, math.ceil(_segundos_seguros / 60) * 60)
    else:
        INTERVALO_ESCANEO_SEGUNDOS = 15
    SCAN_SECONDS = INTERVALO_ESCANEO_SEGUNDOS  # alias

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

    # NUEVO v4.0 — Twelve Data (twelvedata.com). Plan gratuito: 8
    # llamadas/minuto, 800/día, 1 crédito por símbolo por llamada. Ver
    # connectors/twelve_data_connector.py para el detalle del rate limiter.
    TWELVE_DATA_API_KEY = os.getenv("TWELVE_DATA_API_KEY", "")


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
