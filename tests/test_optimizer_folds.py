"""Pruebas de la división en folds del walk-forward (optimization/optimizer.py)."""

import unittest

import pandas as pd

from optimization.optimizer import _dividir_en_folds, _concatenar_folds


class TestFolds(unittest.TestCase):

    def setUp(self):
        self.df = pd.DataFrame({"close": range(100)})
        self.datos = {"EURUSD": self.df}

    def test_reparte_todas_las_filas_sin_perder_ni_duplicar(self):
        folds = _dividir_en_folds(self.datos, n_folds=5)
        self.assertEqual(len(folds), 5)
        total = sum(len(f["EURUSD"]) for f in folds)
        self.assertEqual(total, 100)

    def test_folds_son_cronologicos_y_consecutivos(self):
        folds = _dividir_en_folds(self.datos, n_folds=5)
        acumulado = 0
        for f in folds:
            primero = f["EURUSD"]["close"].iloc[0]
            self.assertEqual(primero, acumulado)
            acumulado += len(f["EURUSD"])

    def test_concatenar_folds_preserva_orden(self):
        folds = _dividir_en_folds(self.datos, n_folds=5)
        unidos = _concatenar_folds(folds[:3])
        self.assertEqual(len(unidos["EURUSD"]), sum(len(f["EURUSD"]) for f in folds[:3]))
        self.assertEqual(unidos["EURUSD"]["close"].iloc[0], 0)
        self.assertEqual(unidos["EURUSD"]["close"].iloc[-1], folds[2]["EURUSD"]["close"].iloc[-1])


if __name__ == "__main__":
    unittest.main()
