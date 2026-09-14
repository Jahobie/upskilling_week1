with orders as (

    select *
    from {{ ref('stg_orders') }}
    where status in ('completed', 'shipped')

),

payments as (

    select * from {{ ref('stg_payments') }}

),

order_payments as (

    select
        orders.order_id,
        orders.customer_id,
        orders.order_date,
        coalesce(sum(payments.amount), 0) as order_amount
    from orders
    left join payments on payments.order_id = orders.order_id
    group by orders.order_id, orders.customer_id, orders.order_date

),

customer_agg as (

    select
        customer_id,
        count(*) as n_orders,
        sum(order_amount) as total_amount,
        min(order_date) as first_order_date,
        max(order_date) as most_recent_order_date
    from order_payments
    group by customer_id

)

select
    c.customer_id,
    c.customer_name,
    a.n_orders,
    a.total_amount,
    a.first_order_date,
    a.most_recent_order_date
from customer_agg a
inner join {{ ref('stg_customers') }} c on c.customer_id = a.customer_id
