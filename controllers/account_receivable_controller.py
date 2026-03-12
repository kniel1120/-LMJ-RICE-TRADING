import sqlite3
from database.init_db import DB_NAME

class AccountReceivableController:
    @staticmethod
    def delete_receivable(receivable_id):
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('DELETE FROM account_receivables WHERE id = ?', (receivable_id,))
        conn.commit()
        conn.close()

    @staticmethod
    def add_receivable(customer_name, address, contact, amount, due_date, cost=0, status='Pending', partial_amount=0, sale_type=None, unit_price=None, sack_size=None, sack_price=None, quantity=None, product_name=None):
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        sacks_sold = None
        if sale_type and sale_type.lower() == 'per sack':
            try:
                sacks_sold = float(quantity) if quantity not in [None, '', 'undefined'] else 0
            except Exception:
                sacks_sold = 0
        elif sale_type and sale_type.lower() == 'per kilo':
            sacks_sold = None
        cursor.execute('''
            INSERT INTO account_receivables (customer_name, address, contact, amount, partial_amount, due_date, status, cost, sale_type, unit_price, sack_size, sack_price, quantity, sacks_sold, product_name)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (customer_name, address, contact, amount, partial_amount, due_date, status, cost, sale_type, unit_price, sack_size, sack_price, quantity, sacks_sold, product_name))
        conn.commit()
        conn.close()
    @staticmethod
    def add_partial_payment(receivable_id, partial_amount):
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('SELECT amount, partial_amount FROM account_receivables WHERE id = ?', (receivable_id,))
        row = cursor.fetchone()
        if row:
            total_partial = row[1] + partial_amount
            status = 'Paid' if total_partial >= row[0] else ('Partial' if total_partial > 0 else 'Pending')
            cursor.execute('''
                UPDATE account_receivables SET partial_amount = ?, status = ? WHERE id = ?
            ''', (total_partial, status, receivable_id))
            conn.commit()
        conn.close()

    @staticmethod
    def set_paid_and_zero_balance(receivable_id):
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        # Set partial_amount = amount and status = 'Paid'
        cursor.execute('UPDATE account_receivables SET partial_amount = amount, status = ? WHERE id = ?', ('Paid', receivable_id))
        conn.commit()
        conn.close()

    @staticmethod
    def get_all_receivables():
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM account_receivables')
        receivables = cursor.fetchall()
        conn.close()
        return receivables

    @staticmethod
    def mark_as_paid(receivable_id):
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE account_receivables SET status = 'Paid' WHERE id = ?
        ''', (receivable_id,))
        conn.commit()
        conn.close()

    @staticmethod
    def get_receivable_by_id(receivable_id):
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM account_receivables WHERE id = ?', (receivable_id,))
        receivable = cursor.fetchone()
        conn.close()
        return receivable

    @staticmethod
    def get_receivable_product_and_cost(receivable_id):
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('SELECT product_name, cost FROM account_receivables WHERE id = ?', (receivable_id,))
        row = cursor.fetchone()
        conn.close()
        return row
