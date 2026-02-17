import sqlite3

DB_NAME = 'lmj_pos.db'

def get_connection():
    return sqlite3.connect(DB_NAME)

def initialize_database():
    conn = get_connection()
    cursor = conn.cursor()
    # Supplier Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS suppliers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            contact TEXT
        )
    ''')
    # Inventory Table (add sack_size and sack_price)
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
    # Customer Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            contact TEXT
        )
    ''')
    # Sales Table (add cost_price for historical cost tracking, sale_type, sack_size, unit_price)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER,
            inventory_id INTEGER,
            quantity INTEGER,
            total REAL,
            cost_price REAL,
            date TEXT,
            sale_type TEXT, -- 'kilo' or 'sack'
            sack_size REAL,
            unit_price REAL,
            FOREIGN KEY (customer_id) REFERENCES customers(id),
            FOREIGN KEY (inventory_id) REFERENCES inventory(id)
        )
    ''')
    # Expenses Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            description TEXT NOT NULL,
            amount REAL NOT NULL,
            date TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

if __name__ == "__main__":
    initialize_database()
