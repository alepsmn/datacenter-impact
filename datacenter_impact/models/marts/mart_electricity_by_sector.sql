with stg as (
    select * from {{ ref('stg_eia_electricity') }}
)
select
    stateid,
    state_name,
    sector_id,
    sector_name,
    year,
    avg(price)      as avg_price,
    sum(sales)      as total_sales,
    sum(revenue)    as total_revenue,
    avg(customers)  as avg_customers
from stg
group by 1, 2, 3, 4, 5