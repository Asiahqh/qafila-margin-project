{{ config(materialized='view') }}

with valid_prices as (
    select
        s.sku,
        s.unit_cost_sar,
        s.valid_from,
        s.source_file
    from {{ ref('stg_supplier_prices') }} s
    left join {{ ref('price_quarantine') }} q
        on s.source_file = q.source_file
        and s.sku = q.sku
        and s.valid_from = q.valid_from
    where q.sku is null
),

latest_per_day as (
    select
        sku,
        unit_cost_sar,
        valid_from
    from valid_prices
    qualify row_number() over (
        partition by sku, valid_from
        order by source_file desc
    ) = 1
),

price_changes as (
    select
        *,
        lag(unit_cost_sar) over (
            partition by sku
            order by valid_from
        ) as previous_cost
    from latest_per_day
),

changed_only as (
    select
        sku,
        unit_cost_sar,
        valid_from
    from price_changes
    where previous_cost is null
       or unit_cost_sar <> previous_cost
)

select
    sku,
    unit_cost_sar,
    valid_from,
    lead(valid_from) over (
        partition by sku
        order by valid_from
    ) as valid_to,
    lead(valid_from) over (
        partition by sku
        order by valid_from
    ) is null as is_current
from changed_only