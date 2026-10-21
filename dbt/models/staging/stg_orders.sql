select
    try_cast(order_id as integer) as order_id,
    trim(store_id) as store_id,
    trim(status) as status,
    cast(
        try_cast(created_at as timestamp) + interval '3 hours'
        as date
    ) as order_date
from {{ source('raw', 'orders') }}