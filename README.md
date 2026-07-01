# datacenter-impact

**Pipeline ELT que cuantifica la relación entre la carga eléctrica proyectada de los
data centers y el precio de la electricidad en EEUU, a nivel estado.**

Combina datos históricos reales de precios y consumo (EIA) con proyecciones de demanda
de data centers (EPRI), los modela en BigQuery con dbt y orquesta todo el flujo con
Airflow. End-to-end, reproducible, con tests.

> **Stack:** Python · Google Cloud Storage · BigQuery · dbt · Apache Airflow (Celery) · Docker

---

## Qué problema resuelve

El crecimiento de los data centers (impulsado por IA) dispara la demanda eléctrica. La
pregunta de negocio: **¿se traduce esa carga adicional en precios más altos para el
consumidor, y dónde?** Este proyecto construye la base de datos analítica para responderla,
cruzando dos fuentes que no hablan el mismo idioma (granos, años y cobertura distintos).

## Arquitectura

```
            ┌─────────────────┐        ┌──────────────────────────┐
  EIA API ─▶│ extract_eia.py  │        │  EPRI_2024_Projections   │
 (precios,  │  (paginado,     │        │        .xlsx             │
  ventas)   │   NDJSON)       │        └────────────┬─────────────┘
            └────────┬────────┘                     │
                     │                     ┌─────────▼─────────┐
                     │                     │ extract_epri.py   │
                     │                     │ (xlsx → NDJSON)   │
                     │                     └─────────┬─────────┘
                     │                               │
                     └──────────────┬────────────────┘
                                    ▼
                          ┌───────────────────┐
                          │  upload_gcs.py    │   Google Cloud Storage
                          │  (raw landing)    │   gs://…-raw/{eia,epri}
                          └─────────┬─────────┘
                                    ▼
                          ┌───────────────────┐
                          │ load_bigquery.py  │   BigQuery (raw tables)
                          │ (schema + load)   │   eia_electricity · epri_datacenter_load
                          └─────────┬─────────┘
                                    ▼
              ┌─────────────────────────────────────────────┐
              │                   dbt                        │
              │  staging  → stg_eia_electricity              │
              │             stg_epri_datacenter_load         │
              │  marts    → mart_electricity_by_sector       │
              │             mart_datacenter_price_impact      │
              └─────────────────────┬───────────────────────┘
                                    ▼
                              análisis / BI

  Todo el grafo lo orquesta Apache Airflow:
  [extract_eia, extract_epri] → upload_gcs → load_bigquery → dbt run → dbt test
```

## Fuentes de datos

| Fuente | Qué aporta | Cobertura | Grano |
|--------|-----------|-----------|-------|
| **EIA** (API v2, retail-sales) | precio, ventas, ingresos, clientes | 2015–2024, mensual | estado × sector (RES/COM/IND) |
| **EPRI** (2024 Projections, xlsx) | energía anual de data centers, % consumo estatal | 2023 (baseline) y 2030 (4 escenarios) | estado × escenario |

~22.300 registros EIA descargados de la API; EPRI extraído de Excel a NDJSON.

## Modelo de datos (dbt)

- **staging** — limpia y tipa el raw. `stg_eia_electricity` deriva `year`/`month` de `period`,
  renombra columnas a snake_case y filtra nulos. `stg_epri_datacenter_load` normaliza escenarios.
- **marts**
  - `mart_electricity_by_sector` — métricas agregadas por estado × sector × año.
  - `mart_datacenter_price_impact` — el corazón analítico: cruza precio EIA con carga EPRI
    a nivel estado, incluyendo el **delta de precio 2022→2023** por sector para correlacionar
    con la penetración de data centers.

**Tests dbt** (en `models/staging/schema.yml`): `not_null`, `unique` y `accepted_values`
sobre claves y categóricas (sectores, escenarios).

## Decisiones de diseño

Lo que diferencia este proyecto de un tutorial es que las fuentes **no encajan limpiamente**
y las decisiones están documentadas:

- **Grano del JOIN.** EIA cubre 2015–2024; EPRI solo tiene 2023 (baseline) y 2030
  (proyecciones). La única intersección real es **2023**. En vez de inventar filas para 2030,
  la mart de impacto filtra `scenario = 'baseline' AND year = 2023` → JOIN limpio sobre
  44 estados, planteado como un **análisis de correlación transversal (cross-sectional)**.
  Es la opción honesta con el dato.
- **Cobertura incompleta, no error de ingesta.** EPRI no incluye 6 estados (Alaska, Arkansas,
  Mississippi, West Virginia, Vermont, Delaware). Es una ausencia intencional de la fuente,
  documentada para no confundirla con un bug del pipeline.
- **Delta de precio como señal.** La mart calcula el cambio de precio 2022→2023 por sector,
  no solo el nivel, para acercarse a un análisis de impacto en vez de una foto estática.

## Tests

Dos niveles de test, uno por cada tipo de código del pipeline.

**Python (`pytest`)** — 70 tests sobre la lógica de extracción, en `tests/`:

- **`test_extract_epri.py`**
  - `STATE_TO_ID`: el mapa estado→código es correcto, cubre los 50 estados y
    respeta el formato (2 letras mayúsculas).
  - `row_to_records` (transformación pura, extraída de `extract()`): campos del
    registro, conversión MWh→GWh redondeada y los filtros de negocio (estados
    fuera del mapa y escenarios sin carga se descartan).
- **`test_extract_eia.py`**
  - `fetch_eia` con `requests` **mockeado**: reintenta ante 5xx/429, falla
    rápido ante un 403 (no reintenta) y agota los reintentos ante fallo
    persistente — sin tocar la red real.
  - `fetch_all_pages`: paginación — concatena páginas, avanza el `offset` y
    **corta exactamente al alcanzar el `total`** (incluido el caso borde
    off-by-one).

El código se hizo testeable separando la **lógica pura del I/O**:
`row_to_records` y `fetch_all_pages` no tocan disco ni red, así que se prueban
sin ficheros ni API real (la red se sustituye con la fixture `monkeypatch`).

**dbt (tests declarativos)** — en `models/staging/schema.yml`: `not_null`,
`unique` y `accepted_values` sobre claves y categóricas (sectores, escenarios).
`dbt test` los verifica contra los datos reales en BigQuery.

```bash
pip install -r requirements.txt -r requirements-dev.txt
pytest                              # tests Python (rápidos, sin red)
cd datacenter_impact && dbt test    # tests dbt (requiere BigQuery)
```

## Cómo ejecutarlo

**Requisitos:** Docker + Docker Compose, una API key de EIA y un service account de GCP con
acceso a GCS y BigQuery.

```bash
# 1. Configurar credenciales (no se versionan)
cp .env.example .env          # añadir EIA_API_KEY
#   colocar keyfile.json del service account en la raíz

# 2. Levantar Airflow (Celery: postgres + redis + webserver + scheduler + worker)
cd airflow
docker compose up airflow-init      # migra DB y crea usuario admin
docker compose up -d

# 3. Airflow UI en http://localhost:8080 (admin/admin)
#    activar y disparar el DAG  datacenter_pipeline
```

Para ejecutar las etapas a mano (sin Airflow):

```bash
python scripts/extract_eia.py     # EIA API → data/raw/eia/*.json (NDJSON)
python scripts/extract_epri.py    # xlsx    → data/raw/epri/*.ndjson
python scripts/upload_gcs.py      # raw     → GCS
python scripts/load_bigquery.py   # GCS     → BigQuery (raw)
cd datacenter_impact && dbt run && dbt test
```

## Estructura del repo

```
scripts/            extracción y carga (EIA, EPRI, GCS, BigQuery)
tests/              tests pytest de los scripts de extracción
datacenter_impact/  proyecto dbt (staging + marts + tests)
airflow/            Dockerfile, docker-compose y DAG de orquestación
docs/               notas de diseño y log de troubleshooting
```

## Qué demuestra técnicamente

- Diseño de un pipeline **ELT** completo sobre infraestructura cloud (GCS + BigQuery).
- Modelado analítico con **dbt** (capas staging/marts, tests, fuentes).
- **Orquestación** real con Airflow sobre Celery, contenerizado.
- Integración de fuentes heterogéneas (API REST paginada + Excel) y resolución honesta
  de conflictos de grano y cobertura.
- **Testing** de la lógica de extracción con `pytest` (mocking de red, casos borde,
  separación lógica/I/O) además de los tests declarativos de dbt.

---

> Notas de troubleshooting de la puesta en marcha: [`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md).