{{ config(materialized='incremental', unique_key='order_id') }}

select
    order_id,
    customer_id,
    order_date,
    status
from {{ source('raw', 'raw_orders') }}

{% if is_incremental() %}
where order_date > (select coalesce(max(order_date), '1900-01-01'::date) from {{ this }})
{% endif %}
