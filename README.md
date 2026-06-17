Dataset EPRI no cubre 6 estados (Alaska, Arkansas, Mississippi, West Virginia, Vermont, Delaware) — ausencia intencional, no error de ingesta.
Schema real difiere del planificado (sin nominal_capacity_mw, sin peak_load_mw).

El JOIN tiene un problema de grano:

EIA: años 2015–2024
EPRI: solo años 2023 (baseline) y 2030 (4 escenarios)

Intersección real: solo 2023.
Para la mart de impacto, hay dos opciones:
A) Filtrar a scenario = 'baseline' AND year = 2023 → JOIN limpio, 44 estados, análisis de correlación cross-sectional.
B) JOIN general por stateid + year → solo produce filas para 2023 de todos modos, pero el modelo queda más genérico.
La opción A es más honesta con el dato