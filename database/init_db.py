
import sqlite3
import os

DB_NAME = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'lmj_pos.db'))

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
        CREATE TABLE IF NOT EXISTS sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER,
            inventory_id INTEGER,
            quantity REAL,
            total REAL,
            cost_price REAL,
            date TEXT,
            sale_type TEXT,
            sack_size REAL,
            sack_price REAL,
            unit_price REAL,
            sack_cost REAL,
            FOREIGN KEY (customer_id) REFERENCES customers(id),
            FOREIGN KEY (inventory_id) REFERENCES inventory(id)
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_name TEXT NOT NULL,
            supplier_id INTEGER,
            quantity REAL,
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
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            description TEXT NOT NULL,
            amount REAL NOT NULL,
            date TEXT NOT NULL
        )
    ''')
    print("Created expenses table")
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS account_receivables (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_name TEXT NOT NULL,
            address TEXT,
            contact TEXT,
            amount REAL NOT NULL,
            partial_amount REAL DEFAULT 0,
            due_date TEXT NOT NULL,
            status TEXT NOT NULL,
            cost REAL DEFAULT 0,
            sale_type TEXT,
            unit_price REAL,
            sack_size REAL,
            sack_price REAL,
            quantity REAL,
            sacks_sold REAL DEFAULT 0,
            product_name TEXT
        )
    ''')
    print("Created account_receivables table")
    # Add product_name column to existing databases that predate this schema
    try:
        cursor.execute('ALTER TABLE account_receivables ADD COLUMN product_name TEXT')
        print("Added product_name column to account_receivables")
    except Exception:
        pass  # Column already exists
    conn.commit()
    print("All tables created and committed.")
    conn.close()
    print("Connection closed.")

if __name__ == "__main__":
    initialize_database()
