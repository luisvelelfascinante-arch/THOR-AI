"""
Pruebas de la lógica de decisión (strategy/confluence.py y
scoring/score_engine.py). NO requieren `ta` ni MetaTrader5 — estos dos
módulos son puros (reciben un dict de valores ya calculados, no calculan
nada con librerías externas), así que estas pruebas corren en cualquier
máquina, incluso sin MT5 instalado.

Uso:
    python -m unittest discover tests
    python -m unittest tests.test_strategy_logic
"""

import unittest

from strategy.confluence import evaluar_confluencia
from scoring.score_engine import calcular_score


def _datos_call_perfecto() -> dict:
    """6/6 confirmaciones alineadas hacia CALL."""
    return {
        "precio": 1.1000, "ema100": 1.0990, "ema200": 1.0980, "sma200": 1.0975,
        "bb_inferior": 1.1000, "bb_superior": 1.1050,
        "rsi2": 5.0,
        "macd_hist": 0.0002, "macd_hist_prev": 0.0001,
        "stoch_k": 15.0, "stoch_d": 10.0,
        "psar": 1.0950,
    }


class TestConfluenciaTotal(unittest.TestCase):

    def test_seis_de_seis_da_call(self):
        score, direccion, detalle = evaluar_confluencia(_datos_call_perfecto())
        self.assertEqual(score, 100)
        self.assertEqual(direccion, "CALL")

    def test_falta_una_confirmacion_no_da_senal(self):
        datos = _datos_call_perfecto()
        datos["ema100"] = 1.1010  # tendencia deja de confirmar CALL
        score, direccion, detalle = evaluar_confluencia(datos)
        self.assertIsNone(direccion)
        self.assertLess(score, 100)

    def test_espejo_perfecto_para_put(self):
        """La misma estructura pero invertida debe dar PUT 100, no CALL
        (verifica que la lógica no tiene un sesgo direccional oculto)."""
        datos = {
            "precio": 1.1000, "ema100": 1.1010, "ema200": 1.1020, "sma200": 1.1025,
            "bb_inferior": 1.0950, "bb_superior": 1.1000,
            "rsi2": 95.0,
            "macd_hist": -0.0002, "macd_hist_prev": -0.0001,
            "stoch_k": 85.0, "stoch_d": 90.0,
            "psar": 1.1050,
        }
        score, direccion, detalle = evaluar_confluencia(datos)
        self.assertEqual(score, 100)
        self.assertEqual(direccion, "PUT")


class TestScorePonderado(unittest.TestCase):

    def test_coincide_con_confluencia_en_caso_perfecto(self):
        datos = _datos_call_perfecto()
        score, direccion, detalle = calcular_score(datos)
        self.assertEqual(direccion, "CALL")
        self.assertEqual(score, 100)

    def test_rechaza_si_tendencia_no_coincide_con_momentum(self):
        datos = _datos_call_perfecto()
        datos["ema100"] = 1.1010  # tendencia ya no es CALL
        score, direccion, detalle = calcular_score(datos)
        self.assertIsNone(direccion)
        self.assertEqual(score, 0)
        self.assertIn("motivo", detalle)

    def test_exige_mayoria_2_de_3_en_momentum_no_solo_1_de_3(self):
        """Corrección v2.1: RSI(2)/MACD/Stochastic no deben tratarse como
        3 confirmaciones independientes (están correlacionados). Con solo
        1 de los 3 a favor, NO debe haber señal aunque tendencia sí
        confirme."""
        datos = _datos_call_perfecto()
        datos["stoch_k"] = 50.0  # stochastic pasa a neutro
        datos["macd_hist"] = -0.0001
        datos["macd_hist_prev"] = 0.0001  # macd pasa a PUT
        # Solo rsi2 sigue a favor de CALL -> 1 de 3, no alcanza el consenso
        score, direccion, detalle = calcular_score(datos)
        self.assertIsNone(direccion)

    def test_2_de_3_en_momentum_si_alcanza_consenso(self):
        datos = _datos_call_perfecto()
        datos["stoch_k"] = 50.0  # stochastic pasa a neutro, pero rsi2 y macd siguen a favor
        score, direccion, detalle = calcular_score(datos)
        self.assertEqual(direccion, "CALL")


if __name__ == "__main__":
    unittest.main()
