{{ config(materialized='view') }}

with order_lines as (
    select
        o.order_date,
        cast(strftime(o.order_date, '%V') as integer) as iso_week,
        s.city,
        p.category,
        i.quantity,
        round(i.quantity * i.unit_price - i.discount, 2) as line_revenue,
        c.unit_cost_sar
    from {{ ref('stg_order_items') }} i
    join {{ ref('stg_orders') }} o
        on i.order_id = o.order_id
    join {{ ref('stg_products') }} p
        on i.product_id = p.product_id
    join {{ ref('stg_stores') }} s
        on o.store_id = s.store_id
    left join {{ ref('product_cost_history') }} c
        on p.sku = c.sku
        and o.order_date >= c.valid_from
        and (
            o.order_date < c.valid_to
            or c.valid_to is null
        )
    where o.status = 'delivered'
      and i.quantity > 0
      and o.order_date >= date '2026-08-31'
)

select
    iso_week,
    city,
    category,
    cast(count(*) as integer) as lines,
    cast(round(sum(line_revenue), 2) as double) as revenue_sar,
    cast(round(sum(
        case when unit_cost_sar is not null
             then line_revenue else 0 end
    ), 2) as double) as costed_revenue_sar,
    cast(round(sum(
        case when unit_cost_sar is not null
             then quantity * unit_cost_sar else 0 end
    ), 2) as double) as cost_sar,
    cast(round(sum(
        case when unit_cost_sar is not null
             then line_revenue - quantity * unit_cost_sar
             else 0 end
    ), 2) as double) as margin_sar,
    cast(count(*) filter (
        where unit_cost_sar is null
    ) as integer) as uncosted_lines
from order_lines
group by iso_week, city, category