"""Tests de scripts/extract_epri.py.

Primer test del proyecto. Empezamos por lo más simple: el diccionario
STATE_TO_ID, que es dato puro (no toca red ni ficheros). Así aislamos los
mecanismos de pytest sin mezclarlos con conceptos avanzados (mocks, I/O).
"""

import pytest
import extract_epri


# def test_texas_mapea_a_tx():
#     Arrange: la entrada es una clave conocida del diccionario.
#     estado = "Texas"

#     Act: "ejecutar" el código bajo prueba. Aquí es una simple consulta.
#     codigo = extract_epri.STATE_TO_ID[estado]

#     Assert: afirmamos el resultado esperado. Si es falso, el test falla
#     y pytest muestra qué valor obtuvo en vez del esperado.
#     # assert codigo == "TZ" mal a proposito
#     assert codigo == "TX"

# --- parametrize: una tabla de casos, un solo test ---------------------------
# En vez de un test por cada estado, damos una lista de tuplas (entrada,
# esperado). pytest ejecuta el test UNA VEZ POR FILA y las reporta por
# separado. Añadir un caso nuevo = añadir una línea, no copiar el test.
@pytest.mark.parametrize(
    ("estado", "esperado"),
    [
        ("Texas", "TX"),
        ("California", "CA"),
        ("New York", "NY"),
        ("Florida", "FL"),
    ],
)
def test_estado_mapea_a_su_codigo(estado, esperado):
    assert extract_epri.STATE_TO_ID[estado] == esperado

def test_hay_50_estados():
    # El diccionario debe cubrir los 50 estados. Un conteo distinto delata
    # una fila borrada o duplicada por accidente.
    #
    # -------------------------------------------------------------------------
    #
    # Un conteo NO se parametriza: es una sola afirmación sobre el conjunto.
    # Distinto conteo = una fila borrada o duplicada por accidente.
    assert len(extract_epri.STATE_TO_ID) == 50


# def test_todos_los_codigos_son_dos_letras_mayusculas():
#     Contrato del formato: cada código de estado son 2 letras en mayúscula.
#     Recorremos todos y comprobamos cada uno; si uno falla, el mensaje nos
#     dice cuál gracias al f-string.
#     for estado, codigo in extract_epri.STATE_TO_ID.items():
#         assert len(codigo) == 2, f"{estado} -> {codigo!r} no tiene 2 caracteres"
#         assert codigo.isupper(), f"{estado} -> {codigo!r} no está en mayúsculas"
#
#--------------------------------------------------------------------------------
#
# Parametrizamos sobre TODOS los items del diccionario. Cada estado pasa a ser
# un caso independiente: si tres códigos están mal, veremos TRES fallos con
# nombre propio, no un único fallo que se detiene en el primero (que es lo que
# pasaría con un bucle `for` dentro de un solo test).
@pytest.mark.parametrize(
    ("estado", "codigo"),
    list(extract_epri.STATE_TO_ID.items()),
)
def test_codigo_es_dos_letras_mayusculas(estado, codigo):
    assert len(codigo) == 2, f"{estado} -> {codigo!r} no tiene 2 caracteres"
    assert codigo.isupper(), f"{estado} -> {codigo!r} no está en mayúsculas"

    # para verificar que todos esten bien el bucle valdria, este otro metodo permite filtrar

# Si quisiera correr solo el de Texas: python -m pytest -v **-k** "Texas"  -> -k es el parametro para seleccionar


# =============================================================================
# row_to_records: la LÓGICA DE NEGOCIO de EPRI (transformar una fila).
# Al ser una función pura (datos -> datos) fabricamos las filas a mano: no
# hace falta ningún .xlsx real. Una fila es una tupla:
#   índice 0 = estado; luego pares (carga_MWh, %) por escenario, en el orden
#   de SCENARIOS: 1,2 baseline | 3,4 low | 5,6 moderate | 7,8 high | 9,10 higher
# =============================================================================

def make_row(estado, pares):
    """Construye una fila-tupla como la que daría openpyxl.

    `pares` = lista de 5 tuplas (carga_mwh, pct) en el orden de SCENARIOS.
    Es un pequeño helper de test para no escribir tuplas de 11 elementos a mano
    en cada caso. (No empieza por test_, así que pytest no lo trata como test.)
    """
    row = [estado]
    for carga, pct in pares:
        row += [carga, pct]
    return tuple(row)


# Fila "completa" reutilizable: los 5 escenarios con carga y % 
# Su unico riesgo es si fuese mutable - copia fresca necesaria, pero es solo lectura
PARES_COMPLETOS = [
    (5000, 1.5),   # baseline 2023
    (6000, 1.8),   # low 2030
    (7000, 2.1),   # moderate 2030
    (8000, 2.4),   # high 2030
    (9000, 2.7),   # higher 2030
]


def test_fila_valida_da_cinco_registros():
    # Camino feliz: un estado válido con los 5 escenarios -> 5 registros.
    registros = extract_epri.row_to_records(make_row("Texas", PARES_COMPLETOS))
    assert len(registros) == 5


def test_primer_registro_tiene_los_campos_correctos():
    # Comprobamos el registro entero de un tirón: dict esperado == dict real.
    # Es la mejor forma de fijar el "contrato" de salida de la transformación.
    baseline = extract_epri.row_to_records(make_row("Texas", PARES_COMPLETOS))[0]
    assert baseline == {
        "state": "Texas",
        "stateid": "TX",
        "year": 2023,
        "scenario": "baseline",
        "annual_energy_gwh": 5.0,      # 5000 MWh / 1000
        "pct_state_consumed": 1.5,
    }


def test_convierte_mwh_a_gwh_redondeando_a_4_decimales():
    # 12345 MWh -> 12.345 GWh. Aísla la conversión y el round(..., 4).
    row = make_row("Texas", [(12345, 1.0), *PARES_COMPLETOS[1:]])
    baseline = extract_epri.row_to_records(row)[0]
    assert baseline["annual_energy_gwh"] == 12.345


@pytest.mark.parametrize("estado", [None, "", "Puerto Rico", "Total U.S."])
def test_estado_invalido_no_produce_registros(estado):
    # Filas sin estado, vacías o de "estados" fuera del mapa (filas de totales
    # o notas del Excel) se descartan enteras. Este filtrado es negocio, y por
    # eso lo testeamos explícitamente.
    assert extract_epri.row_to_records(make_row(estado, PARES_COMPLETOS)) == []


def test_escenario_sin_carga_se_omite():
    # Si la carga de un escenario viene vacía (None), ese escenario no genera
    # registro; los demás sí. Ponemos None en 'low' -> quedan 4 escenarios.
    pares = [
        (5000, 1.5),   # baseline OK
        (None, 1.8),   # low SIN carga -> se omite
        (7000, 2.1),   # moderate OK
        (8000, 2.4),   # high OK
        (9000, 2.7),   # higher OK
    ]
    registros = extract_epri.row_to_records(make_row("Texas", pares))
    escenarios = [r["scenario"] for r in registros]
    assert escenarios == ["baseline", "moderate", "high", "higher"]