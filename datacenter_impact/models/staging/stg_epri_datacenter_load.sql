with source as (
    select * from {{ source('datacenter_impact', 'epri_datacenter_load') }}
),

cleaned as (
    select
        state,
        stateid,
        year,
        scenario,
        annual_energy_gwh,
        pct_state_consumed
    from source
    where
        stateid is not null
        and year is not null
        and scenario is not null
)

select * from cleaned