import random
from datetime import date, timedelta

import psycopg2
from psycopg2.extras import execute_values

from .db import DSN

random.seed(42)

SCHEMA = """
drop table if exists fact_sales;
drop table if exists dim_date;
drop table if exists dim_customer;
drop table if exists dim_product;
drop table if exists dim_store;

create table dim_date (
    date_key int primary key,
    date_actual date not null,
    year int not null,
    quarter int not null,
    month int not null,
    weekday text not null
);

create table dim_customer (
    customer_key int primary key,
    name text not null,
    segment text not null,
    city text not null,
    country text not null
);

create table dim_product (
    product_key int primary key,
    name text not null,
    category text not null,
    brand text not null,
    unit_price numeric(10, 2) not null
);

create table dim_store (
    store_key int primary key,
    name text not null,
    region text not null,
    country text not null
);

create table fact_sales (
    sale_id int primary key,
    date_key int not null references dim_date,
    customer_key int not null references dim_customer,
    product_key int not null references dim_product,
    store_key int not null references dim_store,
    quantity int not null,
    amount numeric(12, 2) not null
);
"""

SEGMENTS = ["Enterprise", "SMB", "Consumer", "Government"]
CATEGORIES = ["Laptops", "Phones", "Monitors", "Audio", "Accessories"]
BRANDS = ["Acme", "Globex", "Initech", "Umbrella", "Soylent"]
REGIONS = ["North", "South", "East", "West"]
CITIES = ["Berlin", "Paris", "Madrid", "Rome", "Warsaw", "Lisbon"]
COUNTRIES = ["Germany", "France", "Spain", "Italy", "Poland", "Portugal"]


def gen_dates():
    rows, day = [], date(2023, 1, 1)
    while day <= date(2024, 12, 31):
        key = day.year * 10000 + day.month * 100 + day.day
        rows.append((key, day, day.year, (day.month - 1) // 3 + 1, day.month, day.strftime("%A")))
        day += timedelta(days=1)
    return rows


def gen_customers(n=200):
    rows = []
    for i in range(1, n + 1):
        c = random.randrange(len(CITIES))
        rows.append((i, f"Customer {i}", random.choice(SEGMENTS), CITIES[c], COUNTRIES[c]))
    return rows


def gen_products(n=80):
    rows = []
    for i in range(1, n + 1):
        rows.append((i, f"Product {i}", random.choice(CATEGORIES), random.choice(BRANDS),
                     round(random.uniform(20, 2000), 2)))
    return rows


def gen_stores(n=15):
    return [(i, f"Store {i}", random.choice(REGIONS), random.choice(COUNTRIES)) for i in range(1, n + 1)]


def gen_sales(dates, customers, products, stores, n=20000):
    rows = []
    for i in range(1, n + 1):
        d = random.choice(dates)
        p = random.choice(products)
        qty = random.randint(1, 10)
        amount = round(qty * float(p[4]) * random.uniform(0.8, 1.0), 2)
        rows.append((i, d[0], random.choice(customers)[0], p[0], random.choice(stores)[0], qty, amount))
    return rows


def main():
    dates = gen_dates()
    customers = gen_customers()
    products = gen_products()
    stores = gen_stores()
    sales = gen_sales(dates, customers, products, stores)

    conn = psycopg2.connect(DSN)
    conn.autocommit = False
    try:
        with conn.cursor() as cur:
            cur.execute(SCHEMA)
            execute_values(cur, "insert into dim_date values %s", dates)
            execute_values(cur, "insert into dim_customer values %s", customers)
            execute_values(cur, "insert into dim_product values %s", products)
            execute_values(cur, "insert into dim_store values %s", stores)
            execute_values(cur, "insert into fact_sales values %s", sales)
        conn.commit()
    finally:
        conn.close()

    print(f"seeded {len(sales)} sales across {len(dates)} days")


if __name__ == "__main__":
    main()
