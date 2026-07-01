"""Tests de scripts/extract_epri.py.

Primer test del proyecto. Empezamos por lo más simple: el diccionario
STATE_TO_ID, que es dato puro (no toca red ni ficheros). Así aislamos los
mecanismos de pytest sin mezclarlos con conceptos avanzados (mocks, I/O).
"""

import extract_epri


def test_texas_mapea_a_tx():
    # Arrange: la entrada es una clave conocida del diccionario.
    estado = "Texas"

    # Act: "ejecutar" el código bajo prueba. Aquí es una simple consulta.
    codigo = extract_epri.STATE_TO_ID[estado]

    # Assert: afirmamos el resultado esperado. Si es falso, el test falla
    # y pytest muestra qué valor obtuvo en vez del esperado.
    assert codigo == "TX"


def test_hay_50_estados():
    # El diccionario debe cubrir los 50 estados. Un conteo distinto delata
    # una fila borrada o duplicada por accidente.
    assert len(extract_epri.STATE_TO_ID) == 50


def test_todos_los_codigos_son_dos_letras_mayusculas():
    # Contrato del formato: cada código de estado son 2 letras en mayúscula.
    # Recorremos todos y comprobamos cada uno; si uno falla, el mensaje nos
    # dice cuál gracias al f-string.
    for estado, codigo in extract_epri.STATE_TO_ID.items():
        assert len(codigo) == 2, f"{estado} -> {codigo!r} no tiene 2 caracteres"
        assert codigo.isupper(), f"{estado} -> {codigo!r} no está en mayúsculas"
