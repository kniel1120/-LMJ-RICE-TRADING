import sqlite3
import os

DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'lmj_pos.db'))

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()
cursor.execute('DELETE FROM sales')
conn.commit()
print('All sales records deleted.')
conn.close()
