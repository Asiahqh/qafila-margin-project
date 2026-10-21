select
    try_cast(product_id as integer) as product_id,
    trim(sku) as sku,
    category,
    try_cast(unit_price as double) as unit_price
from {{ source('raw', 'products') }}