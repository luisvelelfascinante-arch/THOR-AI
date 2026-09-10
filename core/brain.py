"""
Loop principal de THOR IA.
Ciclo: escanear -> filtrar por score+cooldown (strategy_engine) -> filtrar
por gestor de riesgo (risk_manager) -> si pasa, notificar + guardar.
"""

import logging
import time

from core.config import estrategia as E, operativa as O
from strategy.scanner import escanear
from strategy.strategy_engine import evaluar_mejor
from risk.risk_manager import permitir_senal, registrar_senal
from storage.history import guardar_senal
from notifications.telegram_service import enviar_senal

log = logging.getLogger("thor.brain")


def _log_estado(mejor):
    if mejor is None:
        print("⏳ Sin oportunidades este ciclo (sin datos o sin sesgo suficiente).")
        return

    print("\n" + "=" * 40)
    print(f"🧠 THOR IA — mejor candidato del ciclo (motor: {E.STRATEGY_MODE})")
    print("=" * 40)
    print(f"PAR       : {mejor['par']}")
    print(f"DIRECCIÓN : {mejor['direccion']}")
    print(f"SCORE     : {mejor['score']}/100 (mínimo: {O.PROBABILIDAD_MINIMA})")


def analizar_mercado():
    log.info("THOR IA iniciado. Motor=%s. Escaneando %s pares cada %ss.",
              E.STRATEGY_MODE, len(E.PARES), O.INTERVALO_ESCANEO_SEGUNDOS)

    while True:
        try:
            mejor = escanear()
            _log_estado(mejor)

            senal = evaluar_mejor(mejor)

            if senal:
                permitido, motivo = permitir_senal(senal["par"])
                if not permitido:
                    log.warning("Señal descartada por gestor de riesgo: %s", motivo)
                    print(f"🛑 Señal descartada por riesgo: {motivo}")
                else:
                    print(f"\n🚨 SEÑAL CONFIRMADA: {senal['direccion']} en {senal['par']} "
                          f"(score {senal['score']}/100)")
                    guardar_senal(senal)
                    enviar_senal(senal)
                    registrar_senal(senal["par"])

        except KeyboardInterrupt:
            log.info("Detenido manualmente por el usuario.")
            break
        except Exception as exc:
            log.exception("Error inesperado en el ciclo principal: %s", exc)

        time.sleep(O.INTERVALO_ESCANEO_SEGUNDOS)
