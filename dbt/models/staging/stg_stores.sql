select
    trim(store_id) as store_id,
    trim(city) as city
from {{ source('raw', 'stores') }}