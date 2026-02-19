import sqlite3
import os

DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'lmj_pos.db'))

def add_sack_cost_column():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    # Check if column already exists
    cur.execute("PRAGMA table_info(sales)")
    columns = [row[1] for row in cur.fetchall()]
    if 'sack_cost' not in columns:
        cur.execute("ALTER TABLE sales ADD COLUMN sack_cost REAL")
        print('sack_cost column added.')
    else:
        print('sack_cost column already exists.')
    conn.commit()
    conn.close()

if __name__ == '__main__':
    add_sack_cost_column()
