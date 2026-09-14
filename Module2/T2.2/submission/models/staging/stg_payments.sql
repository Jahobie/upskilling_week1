select
    payment_id,
    order_id,
    amount,
    method
from {{ source('raw', 'raw_payments') }}
