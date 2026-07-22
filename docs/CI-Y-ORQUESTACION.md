# Fases 5 y 6 — CI y orquestación

Notas de qué se añadió, **por qué**, y cómo comprobarlo tú mismo. Cierra el
[ROADMAP](../mds/ROADMAP.md) de endurecimiento del repo.

---

## Fase 5 — Integración continua

### La idea

CI = cada `push` dispara, en una **máquina limpia**, las mismas comprobaciones
que harías a mano. El valor no es "correr los tests" (eso ya lo haces en local);
es correrlos en un entorno construido desde cero a partir de `requirements.txt`.
Eso demuestra dos cosas a la vez:

1. El código pasa sus pruebas.
2. El repo es **reproducible** — no depende de nada que tengas instalado a mano.

Un badge verde en el README es la versión corta de ese mensaje.

### Los tres jobs

`.github/workflows/ci.yml` define tres trabajos independientes, que corren en
paralelo. Independientes a propósito: si el lint falla, quieres saber igualmente
si los tests pasaban.

| Job | Comando | Qué caza |
|-----|---------|----------|
| **lint** | `ruff check` | imports sin usar, variables indefinidas, imports desordenados, sintaxis anticuada, líneas kilométricas |
| **test** | `pytest` | los 70 tests de la Fase 4 (sin red: la API de EIA está mockeada) |
| **dbt** | `dbt parse --warn-error` | `ref` a un modelo inexistente, YAML mal formado, test mal declarado, deprecaciones |

### Por qué `dbt parse` y no `dbt run`

`dbt compile` y `dbt run` **necesitan conexión al warehouse**. En CI no hay
credenciales de BigQuery, y es correcto que no las haya: meter una service
account en los secretos de GitHub para validar sintaxis sería pagar un riesgo
de seguridad por nada.

`dbt parse` construye el *manifest* —resuelve refs, sources, tests y todo el
Jinja— **sin abrir conexión**. Valida todo lo validable sin nube. Lo que sí
necesita datos reales (que `stateid` no esté duplicado, que no haya nulos) lo
ejecuta el DAG en su tarea `dbt_test`, que es donde tiene sentido.

Para que `dbt parse` arranque necesita *un* perfil con el nombre que declara
`dbt_project.yml`. De ahí `ci/profiles.yml`: un perfil con `method: oauth`, sin
keyfile ni secretos.

`--warn-error` convierte cualquier warning de dbt en fallo. Es lo que mantiene
el proyecto limpio: las deprecaciones que arrastraba la Fase 4 no volverán a
colarse sin que alguien se entere.

### Lo que el CI *no* hace, y por qué

- **No fuerza `ruff format`.** El formateador automático colapsaría tablas
  alineadas a mano que se leen mejor así (el `STATE_TO_ID` de `extract_epri.py`,
  50 estados en 14 líneas). El linter cubre lo que de verdad importa —errores—
  y el formato queda como decisión humana. Si algún día quieres formateo
  automático: `ruff format .`
- **No importa el DAG de Airflow.** Validarlo de verdad exige instalar Airflow
  entero en el runner (~1 min por ejecución) para un solo fichero. `ruff` ya
  caza los errores de sintaxis y los nombres indefinidos; el fallo que se
  escaparía (un import de Airflow inexistente) lo caza el scheduler al desplegar.

### `pre-commit` (opcional)

`.pre-commit-config.yaml` ejecuta las mismas reglas **antes** de cada commit:
el CI adelantado a tu máquina, 1 segundo en local en vez de 40 en GitHub.
Añade además dos redes de seguridad que no son de estilo:
`detect-private-key` y `check-added-large-files`.

```bash
pip install pre-commit && pre-commit install   # una vez por clon
pre-commit run --all-files                     # a mano, sobre todo el repo
```

### Reproducir el CI en local

Exactamente lo que corre GitHub, en el mismo orden:

```bash
ruff check .                                        # job "lint"
pytest -v                                           # job "test"
cd datacenter_impact
dbt parse --profiles-dir ../ci --target ci --warn-error   # job "dbt"
```

> Si lanzas dbt como tu usuario y no dentro del contenedor, añade
> `--log-path` y `--target-path` a un directorio en el que puedas escribir:
> el `logs/` del proyecto pertenece al usuario del contenedor (uid 50000).

---

## Fase 6 — Orquestación

### Fechas parametrizadas

Antes, la ventana temporal de EIA estaba **hardcodeada** dentro de
`fetch_eia` (`"start": "2015-01"`). Cambiarla exigía editar código.

Ahora recorre esta cadena:

```
DAG params (UI de Airflow)  →  env vars  →  config.EIA_START/EIA_END  →  fetch_eia
```

- `config.py` las lee del entorno con un valor por defecto (`2015-01` / `2024-12`),
  igual que el resto de la configuración.
- El DAG las declara como `Param` con validación de formato (`^\d{4}-\d{2}$`) y
  las inyecta al script como variables de entorno.
- Desde la UI: *Trigger DAG w/ config* permite lanzar otra ventana sin tocar
  ni una línea de código.

Un detalle que cuesta un incidente aprender: `BashOperator(env=...)` **reemplaza
el entorno entero** del proceso hijo. Sin `append_env=True`, el script se
quedaría sin `EIA_API_KEY` ni `GOOGLE_APPLICATION_CREDENTIALS` y fallaría con un
error que no menciona la causa.

### Idempotencia: por qué se puede reintentar sin miedo

Idempotente = ejecutarlo N veces deja el sistema igual que ejecutarlo una vez.
Sin esa propiedad, un reintento automático **duplica datos**, y entonces los
reintentos dejan de ser una red de seguridad para convertirse en una fuente de
corrupción silenciosa.

Cada etapa lo consigue de una forma distinta:

| Etapa | Por qué es idempotente |
|-------|------------------------|
| `extract_eia` / `extract_epri` | Sobrescriben el fichero de salida (`open(..., "w")`), no le añaden |
| `upload_gcs` | Subir al mismo blob lo reemplaza |
| `load_bigquery` | `WRITE_TRUNCATE`: la tabla se reemplaza, no se acumula |
| `dbt run` | Reconstruye modelos por definición (vistas y tablas `CREATE OR REPLACE`) |
| `dbt test` | Solo lee |

Por eso el DAG puede permitirse `retries: 2` sin riesgo.

### Reintentos en dos niveles

Son complementarios, no redundantes:

- **Dentro del script** (`extract_eia.py`): backoff exponencial ante 429/5xx.
  Cubre el hipo de la API — un 503 que se resuelve en 2 segundos. Reintentar la
  tarea entera por eso sería desperdiciar 5 minutos.
- **A nivel de tarea** (`default_args.retries`): cubre lo que el script no puede
  ver porque le mata — worker reiniciado, OOM, credencial expirada, red del
  contenedor caída.

Añadido también `execution_timeout: 30 min`: una tarea colgada se corta en vez
de ocupar un slot del pool indefinidamente, y `max_active_runs: 1`, para que dos
ejecuciones del pipeline no se pisen escribiendo los mismos ficheros.

### `BashOperator` vs `PythonOperator`

El ROADMAP pedía *valorarlo*. La conclusión es quedarse con `BashOperator`, y el
motivo es de diseño, no de pereza:

Un `PythonOperator` importaría los scripts **dentro del proceso worker** de
Airflow. Eso acopla el ciclo de vida del pipeline al de la orquesta: comparten
memoria, comparten intérprete, y un `sys.exit()` o una fuga de memoria del
script afecta al worker. Con `BashOperator` cada etapa es un proceso
independiente que muere al terminar; el coste (arrancar un intérprete) es
despreciable frente a la duración de la tarea. Además dos de las seis tareas son
inherentemente CLI (`dbt run`, `dbt test`).

El día que este pipeline creciera, el salto natural no sería `PythonOperator`
sino aislamiento aún mayor: `DockerOperator` / `KubernetesPodOperator`.

### Autenticación: el `keyfile.json` montado

Hoy `docker-compose.yml` monta `keyfile.json` dentro del contenedor. Funciona y
está fuera de git (`.gitignore`), pero **una clave de service account en disco
es una credencial de larga duración**: no caduca, y quien la copia es esa
service account para siempre.

En producción se sustituiría por credenciales efímeras:

- **En GCP** (GKE/Cloud Composer): *Workload Identity*. El pod obtiene un token
  de corta duración de la metadata del entorno. No hay fichero de clave.
- **Fuera de GCP** (GitHub Actions, otro cloud): *Workload Identity Federation*.
  El proveedor de identidad emite un token que GCP intercambia por uno suyo.
- **En local**: `gcloud auth application-default login`.

El código ya está preparado: la ruta del keyfile sale de `config.KEY_FILE`
(env var `GCP_KEYFILE`), así que migrar es cambiar la autenticación en un solo
sitio, no en cuatro scripts.

---

## Limpieza incluida

- Borrado `models/example/` — los modelos de juguete que crea `dbt init` y nunca
  se usaron.
- `dbt_project.yml`: donde configuraba el directorio de ejemplo, ahora declara
  la materialización real por capa — **staging → vistas** (baratas, siempre
  frescas, solo limpian y tipan) y **marts → tablas** (se consultan desde BI;
  materializarlas evita recalcular JOINs y agregaciones en cada consulta).
  ⚠️ Es un cambio de comportamiento: el próximo `dbt run` recreará los marts
  como tablas en vez de vistas. Para revertirlo, `+materialized: view`.
- Deprecaciones de dbt 1.11 resueltas: `tests:` → `data_tests:` y los argumentos
  de `accepted_values` anidados bajo `arguments:`. `dbt parse --warn-error`
  ahora pasa limpio.
- Deuda de estilo saldada por ruff: imports ordenados, espacios finales,
  ficheros sin salto de línea final.

## Pendientes conocidos (no bloquean nada)

- **Typo en el nombre del modelo**: `mart_datecenter_price_impact` (debería ser
  `datacenter`). Renombrarlo implica cambiar el modelo, su `schema.yml`, el
  README y la tabla ya creada en BigQuery. Se deja consciente, no por descuido.
- El DAG no tiene un test de importación (ver "Lo que el CI no hace").
