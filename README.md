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

#######################################################################################################################
# Phase 5 — Troubleshooting Log

## 1. `logs/` permission denied (Airflow init)
**Error:** `PermissionError: /opt/airflow/logs/scheduler`  
**Causa:** Directorio creado por usuario host; contenedor corre como UID 50000.  
**Fix:**
```bash
sudo chown -R 50000:0 ~/datacenter-impact/airflow/logs
```

## 2. `airflow-init` command not found
**Error:** `/bin/bash: line 3: --username: command not found`  
**Causa:** El bloque `command: >` en docker-compose.yml parte el comando multilinea en bash.  
**Fix:** Comando en una sola línea:
```yaml
command: bash -c "airflow db migrate && airflow users create --username admin --password admin --firstname Admin --lastname User --role Admin --email admin@example.com"
```

## 3. Celery worker `NoneType` hostname
**Error:** `AttributeError: 'NoneType' object has no attribute 'split'`  
**Causa:** Celery no puede resolver el hostname del contenedor.  
**Fix:**
```yaml
airflow-worker:
  hostname: airflow-worker
  command: celery worker -H airflow-worker@%h
```

## 4. Scripts no montados en el contenedor
**Error:** `No such file or directory: /opt/airflow/scripts/`  
**Causa:** Volumen `scripts/` ausente en docker-compose.yml.  
**Fix:** Añadir al bloque de volúmenes:
```yaml
- ../scripts:/opt/airflow/scripts
- ../data:/opt/airflow/data
```

## 5. `EIA_API_KEY` no disponible en el contenedor
**Error:** `403 Forbidden` en API de EIA.  
**Causa:** Variable de entorno no propagada al contenedor.  
**Fix:** Referenciar `.env` del proyecto en docker-compose.yml:
```yaml
env_file:
  - ../.env
```
No añadir `EIA_API_KEY` manualmente en `environment:` — sobreescribe el valor del `.env`.

## 6. Módulos faltantes en la imagen
**Error:** `ModuleNotFoundError: No module named 'openpyxl'`  
**Fix:** Añadir al Dockerfile:
```dockerfile
RUN pip install --no-cache-dir \
    dbt-bigquery==1.11.1 \
    apache-airflow-providers-google==10.20.0 \
    openpyxl \
    python-dotenv
```

## 7. `extract_eia.py` genera JSON array en vez de NDJSON
**Error:** `JSON parsing error: Start of array encountered without start of object`  
**Causa:** `json.dump(all_data, f)` escribe array; BigQuery requiere NDJSON.  
**Fix:**
```python
for record in all_data:
    f.write(json.dumps(record) + "\n")
```

## 8. Permisos en directorio dbt
**Error:** `PermissionError: /opt/airflow/dbt/logs/dbt.log`  
**Error:** `PermissionError: /opt/airflow/dbt/target/partial_parse.msgpack`  
**Causa:** Directorio dbt montado desde host con permisos de usuario local.  
**Fix:**
```bash
sudo chown -R 50000:0 ~/datacenter-impact/datacenter_impact