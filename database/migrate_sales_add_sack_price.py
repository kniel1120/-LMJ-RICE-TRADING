import sqlite3
import os

DB_NAME = 'lmj_pos.db'

def get_connection():
    abs_path = os.path.abspath(DB_NAME)
    print(f"[migrate_sales_add_sack_price.py] USING DATABASE: {abs_path}")
    return sqlite3.connect(DB_NAME)

def add_sack_price_column():
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("ALTER TABLE sales ADD COLUMN sack_price REAL;")
        print("Added sack_price column to sales table.")
    except sqlite3.OperationalError as e:
        if 'duplicate column name' in str(e):
            print("sack_price column already exists.")
        else:
            print("Error:", e)
    conn.commit()
    conn.close()
    print("Migration complete.")

if __name__ == "__main__":
    add_sack_price_column()
