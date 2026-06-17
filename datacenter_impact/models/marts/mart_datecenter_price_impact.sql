with eia_annual as (
    select
        stateid,
        year,
        sector_id,
        avg(price) as avg_price
    from {{ ref('stg_eia_electricity') }}
    where price is not null
    group by stateid, year, sector_id
),

eia_2023 as (
    select
        stateid,
        max(case when sector_id = 'RES' then avg_price end) as price_res,
        max(case when sector_id = 'COM' then avg_price end) as price_com,
        max(case when sector_id = 'IND' then avg_price end) as price_ind
    from eia_annual
    where year = 2023
    group by stateid
),

eia_2022 as (
    select
        stateid,
        max(case when sector_id = 'RES' then avg_price end) as price_res_2022,
        max(case when sector_id = 'COM' then avg_price end) as price_com_2022,
        max(case when sector_id = 'IND' then avg_price end) as price_ind_2022
    from eia_annual
    where year = 2022
    group by stateid
),

epri_baseline as (
    select
        stateid,
        annual_energy_gwh,
        pct_state_consumed
    from {{ ref('stg_epri_datacenter_load') }}
    where scenario = 'baseline' and year = 2023
),

joined as (
    select
        e23.stateid,
        e23.price_res,
        e23.price_com,
        e23.price_ind,
        e23.price_res - e22.price_res_2022 as delta_price_res,
        e23.price_com - e22.price_com_2022 as delta_price_com,
        e23.price_ind - e22.price_ind_2022 as delta_price_ind,
        ep.annual_energy_gwh,
        ep.pct_state_consumed
    from eia_2023 e23
    left join eia_2022 e22
        on e23.stateid = e22.stateid
    inner join epri_baseline ep
        on e23.stateid = ep.stateid
)

select * from joined