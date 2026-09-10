"""
Pruebas de backtesting/backtest_engine.py — la parte de estadísticas
(calcular_estadisticas, significancia estadística), no la parte que
calcula indicadores. Requiere que `ta` esté instalado (es una dependencia
de requirements.txt), pero NO requiere MT5 conectado ni datos reales.
"""

import unittest

import pandas as pd

from backtesting.backtest_engine import calcular_estadisticas, _significancia_estadistica


def _trades_sinteticos(wins: int, losses: int, empates: int = 0) -> pd.DataFrame:
    filas = []
    ts = pd.Timestamp("2026-01-01")
    for i in range(wins):
        filas.append({"time": ts + pd.Timedelta(minutes=i), "par": "EURUSD",
                       "direccion": "CALL", "score": 100, "resultado": "WIN",
                       "hora_del_dia": (ts + pd.Timedelta(minutes=i)).hour})
    for i in range(losses):
        filas.append({"time": ts + pd.Timedelta(minutes=wins + i), "par": "EURUSD",
                       "direccion": "CALL", "score": 100, "resultado": "LOSS",
                       "hora_del_dia": (ts + pd.Timedelta(minutes=wins + i)).hour})
    for i in range(empates):
        filas.append({"time": ts + pd.Timedelta(minutes=wins + losses + i), "par": "EURUSD",
                       "direccion": "CALL", "score": 100, "resultado": "EMPATE",
                       "hora_del_dia": (ts + pd.Timedelta(minutes=wins + losses + i)).hour})
    return pd.DataFrame(filas)


class TestCalcularEstadisticas(unittest.TestCase):

    def test_dataframe_vacio_no_revienta(self):
        stats = calcular_estadisticas(pd.DataFrame())
        self.assertEqual(stats["total_operaciones"], 0)

    def test_winrate_correcto(self):
        trades = _trades_sinteticos(wins=6, losses=4)
        stats = calcular_estadisticas(trades, payout_pct=0.87)
        self.assertEqual(stats["wins"], 6)
        self.assertEqual(stats["losses"], 4)
        self.assertAlmostEqual(stats["winrate_pct"], 60.0)

    def test_empates_no_cuentan_en_winrate(self):
        trades = _trades_sinteticos(wins=5, losses=5, empates=20)
        stats = calcular_estadisticas(trades, payout_pct=0.87)
        self.assertEqual(stats["empates"], 20)
        self.assertEqual(stats["con_resultado_valido"], 10)  # los empates no entran

    def test_profit_factor_con_solo_wins_es_infinito(self):
        trades = _trades_sinteticos(wins=10, losses=0)
        stats = calcular_estadisticas(trades, payout_pct=0.87)
        self.assertEqual(stats["profit_factor"], float("inf"))


class TestSignificanciaEstadistica(unittest.TestCase):

    def test_sin_operaciones_no_aplica(self):
        r = _significancia_estadistica(wins=0, total=0, payout=0.87)
        self.assertFalse(r["aplica"])

    def test_avisa_con_muestra_chica(self):
        r = _significancia_estadistica(wins=22, total=40, payout=0.87)
        self.assertIsNotNone(r["advertencia_muestra"])

    def test_no_avisa_con_muestra_grande(self):
        r = _significancia_estadistica(wins=280, total=500, payout=0.87)
        self.assertIsNone(r["advertencia_muestra"])

    def test_misma_tasa_mas_muestra_da_mas_confianza(self):
        """Con el mismo winrate, más operaciones debe dar un p-valor
        menor (más confianza de que no es azar)."""
        r_chico = _significancia_estadistica(wins=56, total=100, payout=0.87)
        r_grande = _significancia_estadistica(wins=560, total=1000, payout=0.87)
        self.assertLess(r_grande["p_valor_una_cola"], r_chico["p_valor_una_cola"])


if __name__ == "__main__":
    unittest.main()
