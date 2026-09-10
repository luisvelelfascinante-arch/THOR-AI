"""Pruebas de backtesting/monte_carlo.py. No requiere `ta` ni MT5 (el
módulo solo usa pandas y random de la librería estándar)."""

import unittest

import pandas as pd

from backtesting.monte_carlo import simular_drawdowns


class TestMonteCarlo(unittest.TestCase):

    def test_pocas_operaciones_no_aplica(self):
        trades = pd.DataFrame({"resultado": ["WIN", "LOSS", "WIN"]})
        r = simular_drawdowns(trades, payout=0.87)
        self.assertFalse(r["aplica"])

    def test_dataframe_vacio_no_revienta(self):
        r = simular_drawdowns(pd.DataFrame(), payout=0.87)
        self.assertFalse(r["aplica"])

    def test_sin_columna_resultado_no_revienta(self):
        """Caso encontrado en pruebas reales: run_backtest.py --monte-carlo
        fallaba con KeyError cuando el backtest no generaba ninguna señal
        (DataFrame vacío sin columnas). Corregido — ver CHANGELOG v3.0."""
        r = simular_drawdowns(pd.DataFrame({"otra_columna": [1, 2, 3]}), payout=0.87)
        self.assertFalse(r["aplica"])

    def test_racha_de_perdidas_agrupada_da_peor_drawdown_que_la_mediana(self):
        resultados = ["WIN"] * 55 + ["LOSS"] * 35 + ["LOSS"] * 10  # racha al final
        trades = pd.DataFrame({"resultado": resultados})
        r = simular_drawdowns(trades, payout=0.87, n_simulaciones=500)
        self.assertTrue(r["aplica"])
        self.assertLessEqual(
            r["drawdown_observado_orden_real"],
            r["drawdown_por_percentil_de_riesgo"]["p50"],
        )


if __name__ == "__main__":
    unittest.main()
