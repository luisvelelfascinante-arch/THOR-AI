"""Pruebas de risk/risk_manager.py. No requiere `ta` ni MT5."""

import unittest

from risk import risk_manager


class TestRiskManager(unittest.TestCase):

    def setUp(self):
        # El módulo usa estado a nivel de módulo (listas globales) -- se
        # reinicia entre pruebas para que no se contaminen entre sí.
        risk_manager._senales_enviadas.clear()
        risk_manager._senales_por_par_dia.clear()

    def test_permite_hasta_el_limite_por_hora(self):
        from core.config import riesgo as R
        for i in range(R.MAX_SENALES_POR_HORA):
            permitido, motivo = risk_manager.permitir_senal("EURUSD")
            self.assertTrue(permitido, f"Señal #{i + 1} debería permitirse")
            risk_manager.registrar_senal("EURUSD")

    def test_bloquea_al_superar_el_limite_por_hora(self):
        from core.config import riesgo as R
        for _ in range(R.MAX_SENALES_POR_HORA):
            risk_manager.permitir_senal("EURUSD")
            risk_manager.registrar_senal("EURUSD")
        permitido, motivo = risk_manager.permitir_senal("GBPUSD")
        self.assertFalse(permitido)
        self.assertIn("hora", motivo.lower())

    def test_racha_de_perdidas_dispara_pausa(self):
        from core.config import riesgo as R
        resultados = ["WIN"] + ["LOSS"] * R.MAX_PERDIDAS_CONSECUTIVAS
        pausar, motivo = risk_manager.evaluar_racha_perdidas(resultados)
        self.assertTrue(pausar)

    def test_sin_racha_no_pausa(self):
        resultados = ["WIN", "LOSS", "WIN", "WIN"]
        pausar, motivo = risk_manager.evaluar_racha_perdidas(resultados)
        self.assertFalse(pausar)

    def test_lista_vacia_no_pausa(self):
        pausar, motivo = risk_manager.evaluar_racha_perdidas([])
        self.assertFalse(pausar)


if __name__ == "__main__":
    unittest.main()
