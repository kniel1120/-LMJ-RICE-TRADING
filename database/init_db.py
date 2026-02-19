
import sqlite3
import os

DB_NAME = 'lmj_pos.db'

def get_connection():
    abs_path = os.path.abspath(DB_NAME)
    print(f"[init_db.py] USING DATABASE: {abs_path}")
    return sqlite3.connect(DB_NAME)

def initialize_database():
    conn = get_connection()
    print("Connected to database, creating tables...")
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS suppliers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            contact TEXT
        )
    ''')
    print("Created suppliers table")
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_name TEXT NOT NULL,
            supplier_id INTEGER,
            quantity INTEGER,
            cost_price REAL,
            retail_price REAL,
            sack_size REAL,
            sack_price REAL,
            FOREIGN KEY (supplier_id) REFERENCES suppliers(id)
        )
    ''')
    print("Created inventory table")
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            contact TEXT
        )
    ''')
    print("Created customers table")
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER,
            inventory_id INTEGER,
            quantity INTEGER,
            total REAL,
            cost_price REAL,
            date TEXT,
            sale_type TEXT,
            sack_size REAL,
            unit_price REAL,
            FOREIGN KEY (customer_id) REFERENCES customers(id),
            FOREIGN KEY (inventory_id) REFERENCES inventory(id)
        )
    ''')
    print("Created sales table")
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            description TEXT NOT NULL,
            amount REAL NOT NULL,
            date TEXT NOT NULL
        )
    ''')
    print("Created expenses table")
    conn.commit()
    print("All tables created and committed.")
    conn.close()
    print("Connection closed.")

if __name__ == "__main__":
    initialize_database()
