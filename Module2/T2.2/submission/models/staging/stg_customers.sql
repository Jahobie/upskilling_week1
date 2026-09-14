select
    customer_id,
    first_name,
    last_name,
    first_name || ' ' || last_name as customer_name,
    signup_date
from {{ source('raw', 'raw_customers') }}
