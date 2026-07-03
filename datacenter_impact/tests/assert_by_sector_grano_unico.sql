-- Test singular: la clave del mart es (stateid, sector_id, year).
-- Un test dbt "pasa" cuando esta consulta NO devuelve filas. Aquí buscamos
-- combinaciones que aparezcan más de una vez: si existen, el grano está roto
-- (agregación mal agrupada) y el test falla mostrando justo los duplicados.
select
    stateid,
    sector_id,
    year,
    count(*) as n_filas
from {{ ref('mart_electricity_by_sector') }}
group by stateid, sector_id, year
having count(*) > 1
