"""
Pruebas de connectors/twelve_data_connector.py. Usa unittest.mock para
simular las respuestas HTTP de Twelve Data — NO hace llamadas de red
reales (esta suite debe poder correr sin internet). La prueba de
conexión REAL contra la API vive en test_twelve_data.py (requiere tu
API key real y sí necesita red).

El estado del rate limiter se persiste en disco (compartido entre
procesos) — cada test apunta _ESTADO_PATH/_LOCK_PATH a un archivo
temporal propio para no tocar el estado real ni interferir entre tests.
"""

import os
import shutil
import tempfile
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from connectors import twelve_data_connector as td


class TestConversionDeSimbolo(unittest.TestCase):

    def test_convierte_par_sin_slash(self):
        self.assertEqual(td._simbolo_twelve_data("EURUSD"), "EUR/USD")

    def test_deja_igual_si_ya_tiene_slash(self):
        self.assertEqual(td._simbolo_twelve_data("EUR/USD"), "EUR/USD")

    def test_normaliza_minusculas(self):
        self.assertEqual(td._simbolo_twelve_data("eurusd"), "EUR/USD")


class _EstadoAisladoTestCase(unittest.TestCase):
    """Apunta el estado persistido del rate limiter a un directorio
    temporal propio de cada test, para no dejar residuos ni interferir
    con el estado real de data_files/."""

    def setUp(self):
        self._tmp_dir = tempfile.mkdtemp()
        self._estado_path_original = td._ESTADO_PATH
        self._lock_path_original = td._LOCK_PATH
        td._ESTADO_PATH = os.path.join(self._tmp_dir, "rate_limit.json")
        td._LOCK_PATH = td._ESTADO_PATH + ".lock"

    def tearDown(self):
        td._ESTADO_PATH = self._estado_path_original
        td._LOCK_PATH = self._lock_path_original
        shutil.rmtree(self._tmp_dir, ignore_errors=True)


class TestObtenerVelas(_EstadoAisladoTestCase):

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
        self.assertEqual(get_mock.call_count, 1)

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

    @patch("connectors.twelve_data_connector.time.sleep")
    @patch("connectors.twelve_data_connector.requests.get")
    @patch("connectors.twelve_data_connector.conexion")
    def test_error_429_reintenta_una_vez_y_luego_se_rinde(self, conexion_mock, get_mock, sleep_mock):
        conexion_mock.TWELVE_DATA_API_KEY = "clave-de-prueba"
        get_mock.return_value = MagicMock(status_code=429, text="rate limit exceeded", json=lambda: {"code": 429})

        df = td.obtener_velas_twelve_data("EURUSD", "1min", 10)

        self.assertIsNone(df)
        self.assertEqual(get_mock.call_count, 2)  # intento original + 1 reintento
        # Se durmió 60s por el reintento (además de cualquier espera del
        # limitador de 8/min, que aquí no debería activarse).
        self.assertIn(td._REINTENTO_ESPERA_SEGUNDOS, [c.args[0] for c in sleep_mock.call_args_list])

    @patch("connectors.twelve_data_connector.time.sleep")
    @patch("connectors.twelve_data_connector.requests.get")
    @patch("connectors.twelve_data_connector.conexion")
    def test_error_429_reintenta_y_luego_funciona(self, conexion_mock, get_mock, sleep_mock):
        conexion_mock.TWELVE_DATA_API_KEY = "clave-de-prueba"
        respuesta_429 = MagicMock(status_code=429, text="rate limit exceeded", json=lambda: {"code": 429})
        respuesta_ok = MagicMock(
            status_code=200,
            json=lambda: {
                "status": "ok",
                "values": [
                    {"datetime": "2026-01-01 00:00:00", "open": "1.08", "high": "1.09", "low": "1.07", "close": "1.085"},
                ],
            },
        )
        get_mock.side_effect = [respuesta_429, respuesta_ok]

        df = td.obtener_velas_twelve_data("EURUSD", "1min", 1)

        self.assertIsNotNone(df)
        self.assertEqual(get_mock.call_count, 2)

    @patch("connectors.twelve_data_connector.requests.get")
    @patch("connectors.twelve_data_connector.conexion")
    def test_cupo_diario_agotado_no_llama_a_la_api(self, conexion_mock, get_mock):
        conexion_mock.TWELVE_DATA_API_KEY = "clave-de-prueba"
        td._escribir_estado({
            "dia_actual": datetime.now().strftime("%Y-%m-%d"),
            "llamadas_hoy": td._MARGEN_SEGURIDAD_DIA,  # ya al límite
            "llamadas_recientes": [],
        })
        df = td.obtener_velas_twelve_data("EURUSD", "1min", 10)
        self.assertIsNone(df)
        get_mock.assert_not_called()


class TestRateLimiter(_EstadoAisladoTestCase):

    @patch("connectors.twelve_data_connector.time.sleep")
    def test_espera_al_alcanzar_8_llamadas_en_el_minuto(self, sleep_mock):
        ahora = datetime.now()
        estado = td._estado_por_defecto()
        estado["llamadas_recientes"] = [ahora.isoformat()] * td._LIMITE_POR_MINUTO

        td._esperar_si_hace_falta(estado)

        sleep_mock.assert_called_once()
        segundos_esperados = sleep_mock.call_args[0][0]
        self.assertGreater(segundos_esperados, 0)

    @patch("connectors.twelve_data_connector.time.sleep")
    def test_no_espera_con_pocas_llamadas_recientes(self, sleep_mock):
        estado = td._estado_por_defecto()
        td._esperar_si_hace_falta(estado)
        sleep_mock.assert_not_called()

    @patch("connectors.twelve_data_connector.time.sleep")
    def test_ignora_llamadas_recientes_vencidas(self, sleep_mock):
        vencida = (datetime.now() - timedelta(minutes=2)).isoformat()
        estado = td._estado_por_defecto()
        estado["llamadas_recientes"] = [vencida] * td._LIMITE_POR_MINUTO

        td._esperar_si_hace_falta(estado)

        sleep_mock.assert_not_called()


class TestEstadoPersistidoEntreProcesos(_EstadoAisladoTestCase):
    """El punto central del fix: dos "procesos" (aquí, dos llamadas
    secuenciales que releen el archivo desde cero) deben ver el mismo
    contador, como si compartieran cuenta de Twelve Data."""

    @patch("connectors.twelve_data_connector.requests.get")
    @patch("connectors.twelve_data_connector.conexion")
    def test_llamadas_hoy_se_acumulan_entre_lecturas_independientes(self, conexion_mock, get_mock):
        conexion_mock.TWELVE_DATA_API_KEY = "clave-de-prueba"
        get_mock.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "status": "ok",
                "values": [
                    {"datetime": "2026-01-01 00:00:00", "open": "1.08", "high": "1.09", "low": "1.07", "close": "1.085"},
                ],
            },
        )

        td.obtener_velas_twelve_data("EURUSD", "1min", 1)
        # Simula un proceso NUEVO leyendo el mismo archivo de estado.
        cupo = td.estado_cupo()
        self.assertEqual(cupo["llamadas_hoy"], 1)

        td.obtener_velas_twelve_data("GBPUSD", "1min", 1)
        cupo = td.estado_cupo()
        self.assertEqual(cupo["llamadas_hoy"], 2)


if __name__ == "__main__":
    unittest.main()
