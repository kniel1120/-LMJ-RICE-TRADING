import sqlite3
import os

DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'lmj_pos.db'))


def sync_inventory():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    # For each inventory item, recalculate stock based on sales
    cur.execute('SELECT * FROM inventory')
    inventory = cur.fetchall()
    for item in inventory:
        item_id = item['id']
        sack_size = item['sack_size']
        orig_qty = item['quantity']
        # Get total sold for this item
        cur.execute('SELECT SUM(quantity) as sold_qty FROM sales WHERE inventory_id = ?', (item_id,))
        sold_qty = cur.fetchone()['sold_qty'] or 0
        # If sack_size is set, treat as sack-based, else kilo-based
        if sack_size and sack_size > 0:
            # Stock is number of sacks
            # orig_qty is number of sacks, sold_qty is in kilos, so convert
            sacks_sold = sold_qty / sack_size
            new_qty = max(orig_qty - sacks_sold, 0)
            cur.execute('UPDATE inventory SET quantity = ? WHERE id = ?', (new_qty, item_id))
        else:
            # Stock is in kilos
            new_qty = max(orig_qty - sold_qty, 0)
            cur.execute('UPDATE inventory SET quantity = ? WHERE id = ?', (new_qty, item_id))
    conn.commit()
    conn.close()
    print('Inventory sync complete.')

if __name__ == '__main__':
    sync_inventory()
