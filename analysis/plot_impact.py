"""Capa de visualización: convierte la mart de impacto en las figuras del README.

Es el último eslabón del pipeline —la caja `análisis / BI` del diagrama de
arquitectura— y responde a la pregunta de negocio del proyecto: ¿la carga de
data centers se traduce en precios más altos para el consumidor?

Genera tres figuras, cada una con un trabajo distinto:

  1. scatter_pct_vs_price  — la relación, un panel por sector (¿hay señal?)
  2. top_states            — la magnitud, qué estados concentran la carga
  3. correlations          — la polaridad, signo y fuerza de cada correlación

Uso:
    python analysis/plot_impact.py          # requiere keyfile.json y BigQuery

Diseño (mismo criterio que el resto del repo): la lógica pura —`pearson`,
`correlations`, `top_states`— está separada del I/O y del dibujo, así que se
testea sin BigQuery ni ficheros (ver tests/test_plot_impact.py).
"""

import logging
import sys
from pathlib import Path
from typing import Any

import matplotlib
import matplotlib.pyplot as plt
from google.cloud import bigquery

from theme import THEMES, Theme

# El repo no es un paquete instalable: los scripts se importan por ruta, igual
# que hace pytest.ini con `pythonpath = scripts`. Añadir scripts/ aquí permite
# reutilizar la configuración centralizada en vez de duplicar project/dataset.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import config  # noqa: E402

logger = logging.getLogger(__name__)

FIGURES_DIR = Path(__file__).resolve().parent / "figures"
MART = "mart_datecenter_price_impact"

# (sufijo de columna, etiqueta legible). El orden es el de la tabla: del sector
# que más gente toca de cerca (residencial) al más lejano (industrial).
SECTORS: tuple[tuple[str, str], ...] = (
    ("res", "Residencial"),
    ("com", "Comercial"),
    ("ind", "Industrial"),
)


# =============================================================================
# Lógica pura (datos → datos). Sin red, sin ficheros, sin matplotlib.
# =============================================================================

def pearson(xs: list[float], ys: list[float]) -> float:
    """Coeficiente de correlación de Pearson entre dos series.

    Mide si dos variables se mueven juntas: +1 perfectamente en el mismo
    sentido, -1 en sentidos opuestos, 0 sin relación lineal. Se implementa a
    mano (en vez de traer scipy) porque son cuatro líneas y así la dependencia
    del proyecto no crece por una fórmula de libro.

    Lanza ValueError si las series no miden lo mismo o si una es constante
    (una recta horizontal no tiene correlación definida: la varianza es 0).
    """
    if len(xs) != len(ys):
        raise ValueError(f"Series de distinta longitud: {len(xs)} vs {len(ys)}")
    if len(xs) < 2:
        raise ValueError("Hacen falta al menos 2 puntos para correlacionar")

    media_x = sum(xs) / len(xs)
    media_y = sum(ys) / len(ys)
    covarianza = sum((x - media_x) * (y - media_y) for x, y in zip(xs, ys, strict=True))
    var_x = sum((x - media_x) ** 2 for x in xs)
    var_y = sum((y - media_y) ** 2 for y in ys)
    if var_x == 0 or var_y == 0:
        raise ValueError("Una de las series es constante: correlación indefinida")

    return covarianza / (var_x * var_y) ** 0.5


def correlations(rows: list[dict[str, Any]]) -> dict[str, float]:
    """Correlación de la penetración de data centers con cada métrica de precio.

    Devuelve seis valores: el nivel de precio de 2023 por sector y el delta
    2022→2023 por sector. El delta importa tanto como el nivel: un precio alto
    puede ser estructural, pero una *subida* es lo que notaría el consumidor.
    """
    pct = [r["pct_state_consumed"] for r in rows]
    return {
        col: pearson(pct, [r[col] for r in rows])
        for col in (
            *(f"price_{s}" for s, _ in SECTORS),
            *(f"delta_price_{s}" for s, _ in SECTORS),
        )
    }


def top_states(rows: list[dict[str, Any]], n: int = 15) -> list[dict[str, Any]]:
    """Los `n` estados con mayor porcentaje de consumo eléctrico en data centers."""
    return sorted(rows, key=lambda r: r["pct_state_consumed"], reverse=True)[:n]


def trend_line(xs: list[float], ys: list[float]) -> tuple[float, float]:
    """Recta de ajuste por mínimos cuadrados. Devuelve (pendiente, intercepto)."""
    media_x = sum(xs) / len(xs)
    media_y = sum(ys) / len(ys)
    var_x = sum((x - media_x) ** 2 for x in xs)
    if var_x == 0:
        raise ValueError("No hay recta de ajuste: todos los x son iguales")
    pendiente = sum((x - media_x) * (y - media_y) for x, y in zip(xs, ys, strict=True)) / var_x
    return pendiente, media_y - pendiente * media_x


# =============================================================================
# I/O: la única función que habla con BigQuery.
# =============================================================================

def fetch_mart() -> list[dict[str, Any]]:
    """Descarga la mart de impacto entera (44 filas, una por estado)."""
    if not Path(config.KEY_FILE).exists():
        raise FileNotFoundError(
            f"No se encuentra la credencial '{config.KEY_FILE}'. "
            "Configúrala con GCP_KEYFILE o coloca keyfile.json en la raíz."
        )
    client = bigquery.Client.from_service_account_json(config.KEY_FILE)
    query = f"select * from `{config.PROJECT_ID}.{config.DATASET}.{MART}`"
    rows = [dict(r) for r in client.query(query).result()]
    logger.info("Descargadas %s filas de %s", len(rows), MART)
    return rows


# =============================================================================
# Figuras. Cada una recibe el tema (claro/oscuro) y escribe un PNG.
# =============================================================================

def _apply_theme(theme: Theme) -> None:
    """Aplica los tokens del tema a los valores por defecto de matplotlib."""
    plt.rcParams.update({
        "figure.facecolor": theme.surface,
        "axes.facecolor": theme.surface,
        "savefig.facecolor": theme.surface,
        "text.color": theme.ink,
        "axes.labelcolor": theme.ink_secondary,
        "axes.edgecolor": theme.axis,
        "xtick.color": theme.ink_muted,
        "ytick.color": theme.ink_muted,
        "grid.color": theme.grid,
        "font.size": 9,
        "figure.dpi": 160,
    })


def _titular(
    fig: plt.Figure, theme: Theme, titulo: str, subtitulo: str, fuente: str
) -> None:
    """Coloca título, subtítulo y línea de fuente alineados a la izquierda.

    Todo por `fig.text` en lugar de `ax.set_title`: el título de un eje se
    alinea con el ÁREA DE DIBUJO, que empieza después de las etiquetas del eje
    Y, así que en un gráfico de barras horizontales aparecería desplazado a la
    derecha. Anclarlo a la figura lo alinea con el borde real de la imagen.
    """
    fig.text(0.008, 0.985, titulo, fontsize=12.5, fontweight="bold",
             color=theme.ink, ha="left", va="top")
    fig.text(0.008, 0.925, subtitulo, fontsize=8.8,
             color=theme.ink_secondary, ha="left", va="top")
    fig.text(0.008, 0.012, fuente, fontsize=7.5, color=theme.ink_muted, ha="left")


def _despine(ax: plt.Axes, keep: tuple[str, ...] = ("left", "bottom")) -> None:
    """Quita los bordes del panel salvo los que sirven de eje.

    El marco completo no aporta información y compite con los datos por la
    atención. Es la aplicación más barata de "cromo recesivo".
    """
    for lado, spine in ax.spines.items():
        spine.set_visible(lado in keep)


def plot_scatter(rows: list[dict[str, Any]], theme: Theme, out: Path) -> None:
    """Panel por sector: penetración de data centers vs precio de 2023.

    Forma: dispersión en múltiplos pequeños (un panel por sector) en vez de tres
    series superpuestas — los tres sectores tienen escalas de precio distintas y
    solaparlos obligaría a un doble eje, que es la peor decisión posible.
    Una sola serie por panel, así que no hace falta leyenda: el título la nombra.
    """
    corr = correlations(rows)
    pct = [r["pct_state_consumed"] * 100 for r in rows]

    fig, axes = plt.subplots(1, 3, figsize=(11, 3.8), sharex=True)
    for ax, (suf, etiqueta) in zip(axes, SECTORS, strict=True):
        precios = [r[f"price_{suf}"] for r in rows]

        ax.grid(True, linewidth=0.6, alpha=0.9, zorder=0)
        ax.set_axisbelow(True)

        # Recta de tendencia primero, para que quede por debajo de los puntos.
        pendiente, intercepto = trend_line(pct, precios)
        xs = [min(pct), max(pct)]
        ax.plot(xs, [pendiente * x + intercepto for x in xs],
                color=theme.ink_muted, linewidth=2, linestyle="--", zorder=2)

        # Anillo de 2px del color de la superficie: separa puntos que se solapan.
        ax.scatter(pct, precios, s=46, color=theme.accent, alpha=0.9,
                   edgecolors=theme.surface, linewidths=2, zorder=3)

        # Etiqueta directa solo de los casos que cuentan la historia, no de los
        # 44. Van por encima del punto para no chocar con la recta de tendencia.
        for r in top_states(rows, 3):
            ax.annotate(
                r["stateid"],
                (r["pct_state_consumed"] * 100, r[f"price_{suf}"]),
                textcoords="offset points", xytext=(0, 11), ha="center",
                fontsize=8.5, fontweight="bold", color=theme.ink,
            )

        ax.set_title(f"{etiqueta}    r = {corr[f'price_{suf}']:+.2f}",
                     fontsize=10, color=theme.ink, pad=10, loc="left")
        _despine(ax)

    axes[0].set_ylabel("Precio 2023 (¢/kWh)")
    # Un solo rótulo de eje X, bajo el panel central: los tres comparten escala.
    axes[1].set_xlabel("% del consumo eléctrico estatal atribuido a data centers")

    _titular(
        fig, theme,
        "Más data centers no significa luz más cara",
        "Correlación negativa en los tres sectores: se instalan donde la "
        "electricidad YA era barata.",
        "44 estados · 2023 · fuentes: EIA (precio) y EPRI (carga baseline)",
    )
    fig.tight_layout(rect=(0, 0.03, 1, 0.87))
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)


def plot_top_states(rows: list[dict[str, Any]], theme: Theme, out: Path) -> None:
    """Ranking de estados por penetración de data centers.

    Forma: barra horizontal ordenada — el trabajo es comparar magnitudes y los
    nombres son etiquetas, no una escala. Color secuencial de un solo hue (más
    oscuro = más alto): el color refuerza el orden en vez de inventar categorías.
    """
    top = top_states(rows, 15)
    etiquetas = [r["stateid"] for r in top]
    valores = [r["pct_state_consumed"] * 100 for r in top]

    # Rampa secuencial del mismo azul: el valor más alto se lleva el paso más
    # oscuro. Interpolamos entre el paso claro y el de acento del tema.
    c_claro = matplotlib.colors.to_rgb(theme.accent_soft)
    c_oscuro = matplotlib.colors.to_rgb(theme.accent)
    maximo = max(valores)
    colores = [
        tuple(claro + (oscuro - claro) * (v / maximo)
              for claro, oscuro in zip(c_claro, c_oscuro, strict=True))
        for v in valores
    ]

    fig, ax = plt.subplots(figsize=(7.6, 5.2))
    posiciones = range(len(top))
    # height < 1 deja aire entre barras: separa las formas sin dibujar nada.
    ax.barh(posiciones, valores, height=0.72, color=colores, zorder=3)

    # Etiqueta directa al final de cada barra: sustituye al eje X entero.
    for y, v in zip(posiciones, valores, strict=True):
        ax.text(v + maximo * 0.015, y, f"{v:.1f}%", va="center",
                fontsize=8.5, color=theme.ink_secondary)

    ax.set_yticks(list(posiciones), etiquetas, fontsize=9, color=theme.ink)
    ax.invert_yaxis()  # el mayor arriba: se lee de arriba abajo
    ax.set_xticks([])
    ax.set_xlim(0, maximo * 1.12)
    _despine(ax, keep=())
    ax.tick_params(axis="y", length=0)  # sin marcas: el borde ya no existe

    _titular(
        fig, theme,
        "Virginia concentra un cuarto de su consumo eléctrico en data centers",
        "% del consumo eléctrico estatal atribuido a data centers · 15 estados "
        "con mayor penetración · 2023",
        "Fuente: EPRI 2024 Projections (baseline)",
    )
    fig.tight_layout(rect=(0, 0.02, 1, 0.90))
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)


def plot_correlations(rows: list[dict[str, Any]], theme: Theme, out: Path) -> None:
    """Signo y fuerza de las seis correlaciones.

    Forma: barra divergente centrada en 0 — el trabajo aquí es la POLARIDAD
    (¿sube o baja?), no la magnitud. Par divergente azul↔rojo con el cero
    marcado: dos hues opuestos que se leen como sentidos contrarios.
    """
    corr = correlations(rows)
    filas = [
        (f"Precio {etiqueta.lower()}", corr[f"price_{suf}"]) for suf, etiqueta in SECTORS
    ] + [
        (f"Δ precio {etiqueta.lower()} 22→23", corr[f"delta_price_{suf}"])
        for suf, etiqueta in SECTORS
    ]

    fig, ax = plt.subplots(figsize=(7.6, 4.2))
    posiciones = range(len(filas))
    valores = [v for _, v in filas]
    colores = [theme.positive if v > 0 else theme.negative for v in valores]

    ax.barh(posiciones, valores, height=0.66, color=colores, zorder=3)
    ax.axvline(0, color=theme.axis, linewidth=1.5, zorder=4)

    for y, v in zip(posiciones, valores, strict=True):
        # La etiqueta se aparta del cero hacia el lado de la barra.
        desplazamiento = 0.012 if v > 0 else -0.012
        ax.text(v + desplazamiento, y, f"{v:+.2f}", va="center",
                ha="left" if v > 0 else "right",
                fontsize=8.5, color=theme.ink_secondary)

    ax.set_yticks(list(posiciones), [etiqueta for etiqueta, _ in filas],
                  fontsize=9, color=theme.ink)
    ax.invert_yaxis()
    ax.set_xlim(-0.45, 0.45)
    ax.set_xlabel("Correlación con el % de consumo en data centers (Pearson)")
    ax.set_xticks([-0.4, -0.2, 0, 0.2, 0.4])
    ax.grid(True, axis="x", linewidth=0.6, alpha=0.9, zorder=0)
    ax.set_axisbelow(True)
    _despine(ax, keep=("bottom",))
    ax.tick_params(axis="y", length=0)

    _titular(
        fig, theme,
        "La única señal positiva está en el precio industrial",
        "Rojo = sube con la penetración de data centers · Azul = baja · n = 44 estados",
        "Correlación no implica causalidad: con n=44 y |r|<0.35, ninguna relación "
        "es concluyente.",
    )
    fig.tight_layout(rect=(0, 0.02, 1, 0.90))
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    config.configure_logging()
    matplotlib.use("Agg")  # backend sin ventana: sirve en CI y por SSH

    rows = fetch_mart()
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)

    corr = correlations(rows)
    logger.info("Correlaciones: %s", {k: round(v, 3) for k, v in corr.items()})

    # Cada figura en tema claro y oscuro: el README las sirve con <picture>
    # según el tema de quien lo lee.
    for theme in THEMES:
        _apply_theme(theme)
        sufijo = "" if theme.name == "light" else "-dark"
        for nombre, dibujar in (
            ("scatter_pct_vs_price", plot_scatter),
            ("top_states", plot_top_states),
            ("correlations", plot_correlations),
        ):
            destino = FIGURES_DIR / f"{nombre}{sufijo}.png"
            dibujar(rows, theme, destino)
            logger.info("Figura escrita: %s", destino)


if __name__ == "__main__":
    main()
