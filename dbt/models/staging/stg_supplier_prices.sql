with cleaned as (
    select
        trim(sku) as sku,
        trim(source_file) as source_file,
        try_cast(valid_from as date) as valid_from,
        coalesce(
            nullif(trim(cost_sar), ''),
            nullif(trim(unit_cost), '')
        ) as raw_cost
    from {{ source('raw', 'supplier_prices') }}
),

normalized as (
    select
        *,
        translate(
            replace(replace(raw_cost, '٫', '.'), ',', '.'),
            '٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹',
            '01234567890123456789'
        ) as normalized_cost
    from cleaned
)

select
    sku,
    source_file,
    valid_from,
    raw_cost,
    round(try_cast(normalized_cost as double), 2) as unit_cost_sar
from normalized