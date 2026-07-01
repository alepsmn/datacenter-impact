"""Tests de scripts/extract_eia.py — fetch_eia con la red MOCKEADA.

fetch_eia llama a requests.get contra la API real de EIA. No queremos eso en un
test (lento, necesita internet + API key, y no podemos provocar un 500 a
voluntad). La técnica: sustituir requests.get por una función falsa que
controlamos, usando la fixture `monkeypatch` de pytest.
"""

import pytest
import requests

import extract_eia


class FakeResponse:
    """Imita lo justo de un requests.Response para fetch_eia.

    fetch_eia solo usa dos métodos del response: .raise_for_status() y .json().
    Con imitar esos dos basta: no necesitamos un Response real. `status_code`
    decide si raise_for_status "explota" (como hace requests ante un 4xx/5xx).
    """

    def __init__(self, json_data=None, status_code=200):
        self._json = json_data or {}
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            # requests adjunta el response a la excepción; fetch_eia lee
            # exc.response.status_code para decidir si reintenta.
            raise requests.HTTPError(f"HTTP {self.status_code}", response=self)

    def json(self):
        return self._json


def test_fetch_eia_devuelve_el_json_en_camino_feliz(monkeypatch):
    # Arrange: un 200 con un payload conocido, y parcheamos requests.get para
    # que devuelva NUESTRA respuesta falsa en vez de llamar a la API.
    payload = {"response": {"data": [{"period": "2015-01"}], "total": 1}}

    def fake_get(url, params=None, timeout=None):
        return FakeResponse(json_data=payload, status_code=200)

    monkeypatch.setattr(extract_eia.requests, "get", fake_get)

    # Act
    resultado = extract_eia.fetch_eia(offset=0, length=5000)

    # Assert: fetch_eia devuelve tal cual el .json() de la respuesta.
    assert resultado == payload


def test_fetch_eia_reintenta_tras_un_500_y_luego_tiene_exito(monkeypatch):
    # Escenario: la primera llamada da 500 (retryable), la segunda va bien.
    # Comprobamos que fetch_eia REINTENTA y acaba devolviendo el payload.
    payload = {"ok": True}
    llamadas = []

    def fake_get(url, params=None, timeout=None):
        llamadas.append(1)
        if len(llamadas) == 1:
            return FakeResponse(status_code=500)   # 1er intento: fallo servidor
        return FakeResponse(json_data=payload, status_code=200)

    monkeypatch.setattr(extract_eia.requests, "get", fake_get)
    # Mockeamos time.sleep para que el backoff no espere de verdad: el test
    # es instantáneo y seguimos comprobando la lógica de reintento.
    monkeypatch.setattr(extract_eia.time, "sleep", lambda segundos: None)

    resultado = extract_eia.fetch_eia()

    assert resultado == payload
    assert len(llamadas) == 2      # hubo exactamente 1 reintento


def test_fetch_eia_no_reintenta_ante_403(monkeypatch):
    # Un 403 (API key inválida) es determinista: reintentar no arregla nada.
    # fetch_eia debe RELANZAR el HTTPError de inmediato, sin reintentos.
    llamadas = []

    def fake_get(url, params=None, timeout=None):
        llamadas.append(1)
        return FakeResponse(status_code=403)

    monkeypatch.setattr(extract_eia.requests, "get", fake_get)
    monkeypatch.setattr(extract_eia.time, "sleep", lambda segundos: None)

    # pytest.raises comprueba que el bloque LANZA esa excepción. Si no la
    # lanzara, el test fallaría. Es el "assert" para excepciones.
    with pytest.raises(requests.HTTPError):
        extract_eia.fetch_eia()

    assert len(llamadas) == 1      # falló rápido: una sola llamada


def test_fetch_eia_agota_reintentos_y_lanza_runtimeerror(monkeypatch):
    # Si SIEMPRE da 503, agota los MAX_RETRIES y lanza RuntimeError (el error
    # "de rendición" que fetch_eia levanta al final del bucle).
    llamadas = []

    def fake_get(url, params=None, timeout=None):
        llamadas.append(1)
        return FakeResponse(status_code=503)

    monkeypatch.setattr(extract_eia.requests, "get", fake_get)
    monkeypatch.setattr(extract_eia.time, "sleep", lambda segundos: None)

    with pytest.raises(RuntimeError):
        extract_eia.fetch_eia()

    assert len(llamadas) == extract_eia.MAX_RETRIES   # lo intentó N veces
