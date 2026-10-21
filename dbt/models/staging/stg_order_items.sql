select
    try_cast(order_id as integer) as order_id,
    try_cast(line_no as integer) as line_no,
    try_cast(product_id as integer) as product_id,
    try_cast(quantity as integer) as quantity,
    try_cast(unit_price as double) as unit_price,
    coalesce(try_cast(discount as double), 0) as discount
from {{ source('raw', 'order_items') }}