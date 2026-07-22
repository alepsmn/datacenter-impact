"""Tests de analysis/plot_impact.py — la estadística, no el dibujo.

Qué se testea y qué no, que es la decisión interesante: se testea la LÓGICA
(`pearson`, `trend_line`, `correlations`, `top_states`), que es dato → dato y
donde un error silencioso cambiaría la conclusión del análisis. No se testea el
dibujo: comparar PNGs píxel a píxel es frágil (cambia con la versión de
matplotlib o la fuente del sistema) y no cazaría ningún error real.

Es la misma separación lógica/I-O de los otros scripts: por eso estas funciones
no reciben ni un cliente de BigQuery ni un `Axes`.
"""

import pytest

import plot_impact

# =============================================================================
# pearson: el cálculo del que cuelga toda la conclusión del análisis.
# =============================================================================

def test_correlacion_perfecta_positiva():
    # y = 2x exacto -> +1. Si esto fallara, todo lo demás sobra.
    assert plot_impact.pearson([1, 2, 3, 4], [2, 4, 6, 8]) == pytest.approx(1.0)


def test_correlacion_perfecta_negativa():
    # y baja exactamente cuando x sube -> -1.
    assert plot_impact.pearson([1, 2, 3, 4], [8, 6, 4, 2]) == pytest.approx(-1.0)


def test_correlacion_es_invariante_al_desplazamiento_y_la_escala():
    # Propiedad clave de Pearson: sumar una constante o multiplicar por una
    # positiva no cambia r. Es lo que permite comparar ¢/kWh con porcentajes.
    xs = [1.0, 4.0, 2.0, 8.0, 5.0]
    ys = [3.0, 1.0, 7.0, 2.0, 9.0]
    base = plot_impact.pearson(xs, ys)
    escalado = plot_impact.pearson([x * 100 + 7 for x in xs], [y * 3 for y in ys])
    assert escalado == pytest.approx(base)


def test_correlacion_conocida():
    # Valor comprobable a mano: medias 2 y 2, covarianza 1, varianzas 2 y 2
    # -> r = 1 / sqrt(2*2) = 0.5. Fija el resultado exacto, no solo la propiedad.
    assert plot_impact.pearson([1, 2, 3], [1, 3, 2]) == pytest.approx(0.5)


def test_series_sin_relacion_dan_cero():
    # Covarianza exactamente 0: las desviaciones se cancelan por pares. Es el
    # caso que distingue "no hay relación lineal" de "no se puede calcular"
    # (una serie constante, que sí es un error — ver el test de abajo).
    assert plot_impact.pearson([1, 2, 3, 4], [3, 1, 4, 2]) == pytest.approx(0.0, abs=1e-12)


@pytest.mark.parametrize(
    ("xs", "ys", "motivo"),
    [
        ([1, 2, 3], [1, 2], "longitudes distintas"),
        ([1], [1], "menos de 2 puntos"),
        ([5, 5, 5], [1, 2, 3], "x constante -> varianza 0"),
        ([1, 2, 3], [7, 7, 7], "y constante -> varianza 0"),
    ],
)
def test_entradas_invalidas_lanzan_valueerror(xs, ys, motivo):
    # Una serie constante NO tiene correlación 0: no está definida. Devolver 0
    # sería mentir en el gráfico, así que la función se niega a calcularla.
    with pytest.raises(ValueError):
        plot_impact.pearson(xs, ys)


# =============================================================================
# trend_line: la recta que se dibuja sobre la nube de puntos.
# =============================================================================

def test_recta_de_ajuste_sobre_puntos_alineados():
    # Puntos exactamente sobre y = 3x + 1 -> la recta debe recuperarlos.
    pendiente, intercepto = plot_impact.trend_line([0, 1, 2, 3], [1, 4, 7, 10])
    assert pendiente == pytest.approx(3.0)
    assert intercepto == pytest.approx(1.0)


def test_recta_de_ajuste_con_x_constante_lanza_error():
    with pytest.raises(ValueError):
        plot_impact.trend_line([2, 2, 2], [1, 2, 3])


# =============================================================================
# correlations / top_states: operan sobre las filas de la mart.
# =============================================================================

def make_row(stateid: str, pct: float, precio: float) -> dict:
    """Fila mínima con la forma de la mart (solo las columnas que se usan)."""
    return {
        "stateid": stateid,
        "pct_state_consumed": pct,
        **{f"price_{s}": precio for s, _ in plot_impact.SECTORS},
        **{f"delta_price_{s}": precio / 10 for s, _ in plot_impact.SECTORS},
    }


FILAS = [
    make_row("AA", 0.01, 20.0),
    make_row("BB", 0.05, 15.0),
    make_row("CC", 0.10, 12.0),
    make_row("DD", 0.25, 9.0),
]


def test_correlations_cubre_los_seis_indicadores():
    # Tres sectores × (nivel de precio + delta) = 6. Si alguien añade un sector
    # a SECTORS y no toca nada más, este test lo acompaña automáticamente.
    corr = plot_impact.correlations(FILAS)
    assert len(corr) == len(plot_impact.SECTORS) * 2
    assert set(corr) == {
        f"{prefijo}_{suf}"
        for prefijo in ("price", "delta_price")
        for suf, _ in plot_impact.SECTORS
    }


def test_correlations_detecta_el_signo():
    # En FILAS el precio BAJA según sube el porcentaje: correlación negativa.
    # Es exactamente el hallazgo del proyecto, fijado como test.
    corr = plot_impact.correlations(FILAS)
    assert corr["price_res"] < 0


def test_top_states_ordena_de_mayor_a_menor():
    top = plot_impact.top_states(FILAS)
    assert [r["stateid"] for r in top] == ["DD", "CC", "BB", "AA"]


def test_top_states_recorta_a_n():
    assert len(plot_impact.top_states(FILAS, n=2)) == 2


def test_top_states_no_muta_la_lista_original():
    # `sorted` devuelve una lista nueva; `list.sort` mutaría la entrada y
    # reordenaría la mart para el resto del programa. Este test fija esa
    # elección para que un refactor no la rompa sin avisar.
    antes = [r["stateid"] for r in FILAS]
    plot_impact.top_states(FILAS)
    assert [r["stateid"] for r in FILAS] == antes
