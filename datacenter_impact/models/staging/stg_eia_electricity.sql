with source as ( 
    select * from {{ source('datacenter_impact', 'eia_electricity') }} --  apunta ala tabl a creuda en BigQuery
),
cleaned as (
    select
        period,
        cast(left(period, 4) as int64)  as year,
        cast(right(period, 2) as int64) as month,
        stateid,
        stateDescription                as state_name,
        sectorid                        as sector_id,
        sectorName                      as sector_name,
        sales,
        revenue,
        price,
        customers
    from source -- consume la Common Table Expression anterior
    where stateid is not null
      and period is not null
)
select * from cleaned -- esto es lo q dbt materializa