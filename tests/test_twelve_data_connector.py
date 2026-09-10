"""
Pruebas de connectors/twelve_data_connector.py. Usa unittest.mock para
simular las respuestas HTTP de Twelve Data — NO hace llamadas de red
reales (esta suite debe poder correr sin internet). La prueba de
conexión REAL contra la API vive en test_twelve_data.py (requiere tu
API key real y sí necesita red).
"""

import unittest
from unittest.mock import patch, MagicMock

from connectors import twelve_data_connector as td


class TestConversionDeSimbolo(unittest.TestCase):

    def test_convierte_par_sin_slash(self):
        self.assertEqual(td._simbolo_twelve_data("EURUSD"), "EUR/USD")

    def test_deja_igual_si_ya_tiene_slash(self):
        self.assertEqual(td._simbolo_twelve_data("EUR/USD"), "EUR/USD")

    def test_normaliza_minusculas(self):
        self.assertEqual(td._simbolo_twelve_data("eurusd"), "EUR/USD")


class TestObtenerVelas(unittest.TestCase):

    def setUp(self):
        # Aislar el estado global del rate limiter entre pruebas
        td._llamadas_recientes.clear()
        td._llamadas_hoy = 0
        td._dia_actual = ""

    @patch("connectors.twelve_data_connector.conexion")
    def test_sin_api_key_devuelve_none(self, conexion_mock):
        conexion_mock.TWELVE_DATA_API_KEY = ""
        resultado = td.obtener_velas_twelve_data("EURUSD", "1min", 10)
        self.assertIsNone(resultado)

    @patch("connectors.twelve_data_connector.requests.get")
    @patch("connectors.twelve_data_connector.conexion")
    def test_respuesta_exitosa_se_parsea_bien(self, conexion_mock, get_mock):
        conexion_mock.TWELVE_DATA_API_KEY = "clave-de-prueba"
        get_mock.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "status": "ok",
                "values": [
                    {"datetime": "2026-01-01 00:02:00", "open": "1.10", "high": "1.11", "low": "1.09", "close": "1.105"},
                    {"datetime": "2026-01-01 00:01:00", "open": "1.09", "high": "1.10", "low": "1.08", "close": "1.095"},
                    {"datetime": "2026-01-01 00:00:00", "open": "1.08", "high": "1.09", "low": "1.07", "close": "1.085"},
                ],
            },
        )
        df = td.obtener_velas_twelve_data("EURUSD", "1min", 3)
        self.assertIsNotNone(df)
        self.assertEqual(len(df), 3)
        self.assertListEqual(list(df.columns), ["time", "open", "high", "low", "close"])
        # Twelve Data manda descendente (más reciente primero) -- el
        # conector debe invertirlo a ascendente para el resto del pipeline.
        self.assertTrue(df["time"].is_monotonic_increasing)
        self.assertAlmostEqual(df["close"].iloc[0], 1.085)  # la más antigua queda primera

    @patch("connectors.twelve_data_connector.requests.get")
    @patch("connectors.twelve_data_connector.conexion")
    def test_status_error_devuelve_none(self, conexion_mock, get_mock):
        conexion_mock.TWELVE_DATA_API_KEY = "clave-de-prueba"
        get_mock.return_value = MagicMock(
            status_code=200,
            json=lambda: {"status": "error", "message": "invalid API key"},
        )
        df = td.obtener_velas_twelve_data("EURUSD", "1min", 10)
        self.assertIsNone(df)

    @patch("connectors.twelve_data_connector.requests.get")
    @patch("connectors.twelve_data_connector.conexion")
    def test_error_http_devuelve_none(self, conexion_mock, get_mock):
        conexion_mock.TWELVE_DATA_API_KEY = "clave-de-prueba"
        get_mock.return_value = MagicMock(status_code=429, text="rate limit exceeded")
        df = td.obtener_velas_twelve_data("EURUSD", "1min", 10)
        self.assertIsNone(df)

    @patch("connectors.twelve_data_connector.requests.get")
    @patch("connectors.twelve_data_connector.conexion")
    def test_cupo_diario_agotado_no_llama_a_la_api(self, conexion_mock, get_mock):
        from datetime import datetime
        conexion_mock.TWELVE_DATA_API_KEY = "clave-de-prueba"
        # Hay que fijar también _dia_actual a HOY -- si no, el reset diario
        # automático (correcto, ver _reset_contador_diario_si_corresponde)
        # pisa el contador antes de que se pueda probar el límite.
        td._dia_actual = datetime.now().strftime("%Y-%m-%d")
        td._llamadas_hoy = td._MARGEN_SEGURIDAD_DIA  # ya al límite
        df = td.obtener_velas_twelve_data("EURUSD", "1min", 10)
        self.assertIsNone(df)
        get_mock.assert_not_called()


class TestRateLimiter(unittest.TestCase):

    def setUp(self):
        td._llamadas_recientes.clear()

    @patch("connectors.twelve_data_connector.time.sleep")
    def test_espera_al_alcanzar_8_llamadas_en_el_minuto(self, sleep_mock):
        from datetime import datetime
        ahora = datetime.now()
        for _ in range(td._LIMITE_POR_MINUTO):
            td._llamadas_recientes.append(ahora)

        td._esperar_si_hace_falta()
        sleep_mock.assert_called_once()
        segundos_esperados = sleep_mock.call_args[0][0]
        self.assertGreater(segundos_esperados, 0)

    @patch("connectors.twelve_data_connector.time.sleep")
    def test_no_espera_con_pocas_llamadas_recientes(self, sleep_mock):
        td._esperar_si_hace_falta()
        sleep_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
