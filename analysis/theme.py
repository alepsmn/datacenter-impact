"""Tokens de color y estilo de las figuras.

Un único sitio donde vive el aspecto de los gráficos, para que las tres figuras
se lean como un sistema y no como tres scripts distintos. Misma idea que
`scripts/config.py` con la configuración: un punto de verdad.

Los valores salen de una paleta de referencia ya validada (bandas de luminosidad,
contraste y separación bajo daltonismo). No se inventan hues: el azul es el hue
único para magnitud, y el par azul↔rojo con gris neutro en el centro es el
divergente documentado para polaridad (positivo/negativo).

Cada figura se genera en dos versiones, clara y oscura. No es un capricho: el
README se lee en ambos temas de GitHub, y una imagen clara sobre fondo oscuro
canta. El tema oscuro no es una inversión automática — usa sus propios pasos de
la misma rampa, elegidos para esa superficie.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Theme:
    """Paleta y tipografía de una figura, para un modo (claro u oscuro)."""

    name: str
    surface: str  # fondo del lienzo
    ink: str  # texto principal (títulos)
    ink_secondary: str  # texto de apoyo (subtítulos)
    ink_muted: str  # ejes y etiquetas de escala
    grid: str  # rejilla, línea capilar
    axis: str  # línea de base / eje
    accent: str  # hue único: magnitud y series de un solo color
    accent_soft: str  # el mismo hue, paso claro (barras no destacadas)
    positive: str  # polo cálido del divergente (correlación positiva)
    negative: str  # polo frío del divergente (correlación negativa)
    neutral: str  # punto medio neutro del divergente


LIGHT = Theme(
    name="light",
    surface="#fcfcfb",
    ink="#0b0b0b",
    ink_secondary="#52514e",
    ink_muted="#898781",
    grid="#e1e0d9",
    axis="#c3c2b7",
    accent="#2a78d6",
    accent_soft="#86b6ef",
    positive="#e34948",
    negative="#2a78d6",
    neutral="#f0efec",
)

DARK = Theme(
    name="dark",
    surface="#1a1a19",
    ink="#ffffff",
    ink_secondary="#c3c2b7",
    ink_muted="#898781",
    grid="#2c2c2a",
    axis="#383835",
    accent="#3987e5",
    accent_soft="#184f95",
    positive="#e66767",
    negative="#3987e5",
    neutral="#383835",
)

THEMES = (LIGHT, DARK)
