"""
populate_db.py

Populates shipment_database.db with the shipment records contained in
shipping_data_0.csv, shipping_data_1.csv, and shipping_data_2.csv.

Database schema:
    product(id INTEGER PK, name TEXT UNIQUE NOT NULL)
    shipment(id INTEGER PK, product_id INTEGER FK -> product,
              quantity INTEGER, origin TEXT, destination TEXT)

Data sources:
    shipping_data_0.csv
        Self-contained: one row per shipment, one product per shipment,
        quantity already given.
        Columns: origin_warehouse, destination_store, product, on_time,
                 product_quantity, driver_identifier

    shipping_data_1.csv
        One row per individual unit of product shipped. Rows must be
        grouped by (shipment_identifier, product) to determine the
        quantity of each product in a shipment.
        Columns: shipment_identifier, product, on_time

    shipping_data_2.csv
        Lookup table giving the origin/destination for each shipment
        identifier referenced in shipping_data_1.csv.
        Columns: shipment_identifier, origin_warehouse, destination_store,
                 driver_identifier

Only the columns relevant to the `product` and `shipment` tables
(product name, quantity, origin, destination) are extracted; fields such
as on_time and driver_identifier are not part of the schema and are
ignored.
"""

import csv
import sqlite3
from collections import Counter
from pathlib import Path

DB_PATH = Path("shipment_database.db")
DATA_DIR = Path("data")


def get_or_create_product_id(cursor: sqlite3.Cursor, product_name: str) -> int:
    """Return the id of `product_name`, inserting it if it doesn't exist yet."""
    cursor.execute("SELECT id FROM product WHERE name = ?", (product_name,))
    row = cursor.fetchone()
    if row is not None:
        return row[0]

    cursor.execute("INSERT INTO product (name) VALUES (?)", (product_name,))
    return cursor.lastrowid


def insert_shipment(
    cursor: sqlite3.Cursor,
    product_id: int,
    quantity: int,
    origin: str,
    destination: str,
) -> None:
    cursor.execute(
        """
        INSERT INTO shipment (product_id, quantity, origin, destination)
        VALUES (?, ?, ?, ?)
        """,
        (product_id, quantity, origin, destination),
    )


def load_shipping_data_0(cursor: sqlite3.Cursor) -> None:
    """Spreadsheet 0 is self-contained: one shipment per row."""
    with open(DATA_DIR / "shipping_data_0.csv", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            product_id = get_or_create_product_id(cursor, row["product"])
            insert_shipment(
                cursor,
                product_id=product_id,
                quantity=int(row["product_quantity"]),
                origin=row["origin_warehouse"],
                destination=row["destination_store"],
            )


def load_shipping_data_1_and_2(cursor: sqlite3.Cursor) -> None:
    """
    Spreadsheet 1 has one row per unit of product; spreadsheet 2 supplies
    the origin/destination for each shipment identifier. Combine them:
      1. Group spreadsheet 1 by (shipment_identifier, product) and count
         rows to get the quantity of each product in each shipment.
      2. Build a shipment_identifier -> (origin, destination) lookup from
         spreadsheet 2.
      3. Insert one shipment row per (shipment_identifier, product) group.
    """
    # Step 1: count product quantities per shipment.
    product_counts: Counter[tuple[str, str]] = Counter()
    with open(DATA_DIR / "shipping_data_1.csv", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            key = (row["shipment_identifier"], row["product"])
            product_counts[key] += 1

    # Step 2: build the origin/destination lookup.
    locations: dict[str, tuple[str, str]] = {}
    with open(DATA_DIR / "shipping_data_2.csv", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            locations[row["shipment_identifier"]] = (
                row["origin_warehouse"],
                row["destination_store"],
            )

    # Step 3: insert one shipment row per product per shipment.
    for (shipment_identifier, product_name), quantity in product_counts.items():
        origin, destination = locations[shipment_identifier]
        product_id = get_or_create_product_id(cursor, product_name)
        insert_shipment(
            cursor,
            product_id=product_id,
            quantity=quantity,
            origin=origin,
            destination=destination,
        )


def main() -> None:
    connection = sqlite3.connect(DB_PATH)
    try:
        cursor = connection.cursor()
        load_shipping_data_0(cursor)
        load_shipping_data_1_and_2(cursor)
        connection.commit()
        print("Database populated successfully.")
    finally:
        connection.close()


if __name__ == "__main__":
    main()