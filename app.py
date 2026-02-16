
import os
from flask import Flask, render_template, request, redirect, url_for, flash, session
from database.db import get_db, query_db, execute_db, close_db
from collections import defaultdict
from datetime import datetime, timedelta
import requests

# SMS API PH config
SMS_API_KEY = 'sk-b50c2b7886419667094fc02e'
SMS_RECIPIENT = '+639061260308'

app = Flask(__name__)
app.secret_key = 'lmj-secret-key'


# HOME/DASHBOARD ROUTE (GET: show dashboard, POST: process sale)
@app.route('/', methods=['GET', 'POST'])
def dashboard():
    if request.method == 'POST':
        rice_type = request.form.get('rice_type')
        quantity = float(request.form.get('quantity', 0))
        # Find inventory item
        item = query_db('SELECT * FROM inventory WHERE product_name = ?', (rice_type,), one=True)
        if not item:
            flash('Selected rice type not found.', 'error')
            return redirect(url_for('dashboard'))
        # Check available stock
        sales = query_db('SELECT SUM(quantity) as sold_qty FROM sales WHERE inventory_id = ?', (item['id'],), one=True)
        sold_qty = sales['sold_qty'] if sales and sales['sold_qty'] else 0
        available = item['quantity'] - sold_qty
        if quantity > available:
            flash(f'Not enough stock for {rice_type}. Only {available} kg available.', 'error')
            return redirect(url_for('dashboard'))
        # Insert sale
        total = quantity * item['retail_price']
        execute_db('INSERT INTO sales (inventory_id, quantity, total, cost_price, date) VALUES (?, ?, ?, ?, ?)',
                   (item['id'], quantity, total, item['cost_price'], datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        flash(f'Sale processed for {quantity} kg {rice_type}.', 'success')
        return redirect(url_for('dashboard'))
    # GET: show dashboard
    inventory = query_db('SELECT * FROM inventory ORDER BY product_name')
    sales = query_db('SELECT inventory_id, SUM(quantity) as sold_qty FROM sales GROUP BY inventory_id')
    sold_map = {s['inventory_id']: s['sold_qty'] if s['sold_qty'] else 0 for s in sales}
    inventory_with_stock = []
    for item in inventory:
        sold_qty = sold_map.get(item['id'], 0)
        total_kilos = item['quantity'] - sold_qty
        inventory_with_stock.append({
            'id': item['id'],
            'product_name': item['product_name'],
            'retail_price': item['retail_price'],
            'total_kilos': max(total_kilos, 0)
        })
    return render_template('dashboard.html', inventory=inventory_with_stock)



# SUPPLIER MANAGEMENT
@app.route('/suppliers')
def suppliers():
    suppliers = query_db('SELECT * FROM suppliers')
    return render_template('suppliers.html', suppliers=suppliers)

@app.route('/suppliers/add', methods=['POST'])
def add_supplier():
    name = request.form['name']
    contact = request.form['contact']
    if not name:
        flash('Supplier name is required!', 'error')
        return redirect(url_for('suppliers'))
    execute_db('INSERT INTO suppliers (name, contact) VALUES (?, ?)', (name, contact))
    flash('Supplier added successfully!', 'success')
    return redirect(url_for('suppliers'))

@app.route('/suppliers/delete/<int:supplier_id>', methods=['POST'])
def delete_supplier(supplier_id):
    execute_db('DELETE FROM suppliers WHERE id = ?', (supplier_id,))
    flash('Supplier deleted!', 'success')
    return redirect(url_for('suppliers'))

@app.route('/suppliers/edit/<int:supplier_id>', methods=['GET', 'POST'])
def edit_supplier(supplier_id):
    if request.method == 'POST':
        name = request.form['name']
        contact = request.form['contact']
        if not name:
            flash('Supplier name is required!', 'error')
            return redirect(url_for('edit_supplier', supplier_id=supplier_id))
        execute_db('UPDATE suppliers SET name = ?, contact = ? WHERE id = ?', (name, contact, supplier_id))
        flash('Supplier updated!', 'success')
        return redirect(url_for('suppliers'))
    supplier = query_db('SELECT * FROM suppliers WHERE id = ?', (supplier_id,), one=True)
    return render_template('edit_supplier.html', supplier=supplier)


# INVENTORY MANAGEMENT
@app.route('/inventory')
def inventory():
    inventory = query_db('SELECT * FROM inventory ORDER BY product_name')
    return render_template('inventory.html', inventory=inventory)

@app.route('/inventory/add', methods=['POST'])
def add_inventory():
    product_name = request.form['product_name']
    quantity = int(request.form['quantity'])
    cost_price = float(request.form['cost_price'])
    retail_price = float(request.form['retail_price'])
    execute_db('INSERT INTO inventory (product_name, quantity, cost_price, retail_price) VALUES (?, ?, ?, ?)', (product_name, quantity, cost_price, retail_price))
    flash('Rice added to inventory!', 'success')
    return redirect(url_for('inventory'))

@app.route('/inventory/delete/<int:item_id>', methods=['POST'])
def delete_inventory(item_id):
    execute_db('DELETE FROM inventory WHERE id = ?', (item_id,))
    flash('Inventory item deleted!', 'success')
    return redirect(url_for('inventory'))

@app.route('/inventory/edit/<int:item_id>', methods=['GET', 'POST'])
def edit_inventory(item_id):
    if request.method == 'POST':
        product_name = request.form['product_name']
        quantity = int(request.form['quantity'])
        cost_price = float(request.form['cost_price'])
        retail_price = float(request.form['retail_price'])
        execute_db('UPDATE inventory SET product_name=?, quantity=?, cost_price=?, retail_price=? WHERE id=?', (product_name, quantity, cost_price, retail_price, item_id))
        flash('Inventory item updated!', 'success')
        return redirect(url_for('inventory'))
    item = query_db('SELECT * FROM inventory WHERE id = ?', (item_id,), one=True)
    return render_template('edit_inventory.html', item=item)

@app.route('/sales')
def sales():
    from datetime import datetime, timedelta, date
    import calendar
    # Get all sales dates
    sales_dates = query_db('SELECT DISTINCT date(date) as sale_date FROM sales ORDER BY sale_date DESC')
    sales_dates = [row['sale_date'] for row in sales_dates]
    today = datetime.now().date()
    selected_date_str = request.args.get('date')
    if selected_date_str:
        selected_date = datetime.strptime(selected_date_str, '%Y-%m-%d').date()
    else:
        selected_date = today
    # Calendar month navigation
    month = selected_date.month
    year = selected_date.year
    cal = calendar.Calendar(calendar.SUNDAY)
    month_days = [d for d in cal.itermonthdates(year, month)]

    # Calculate running total sales for the month
    month_start = date(year, month, 1)
    if month == 12:
        month_end = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        month_end = date(year, month + 1, 1) - timedelta(days=1)
    total_sales_row = query_db('SELECT SUM(total) as total_sales FROM sales WHERE date(date) >= ? AND date(date) <= ?', (month_start.strftime('%Y-%m-%d'), month_end.strftime('%Y-%m-%d')), one=True)
    total_sales = total_sales_row['total_sales'] if total_sales_row and total_sales_row['total_sales'] else 0

    return render_template('sales.html', sales_dates=sales_dates, today=today, selected_date=selected_date, month_days=month_days, total_sales=total_sales)

@app.route('/sales/<date_str>')
def sales_day(date_str):
    from datetime import datetime
    import calendar
    # Parse date
    try:
        selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except Exception:
        flash('Invalid date format.', 'error')
        return redirect(url_for('sales'))
    # Get sales for selected date
    sales_for_day = query_db('''
        SELECT s.id, i.product_name, s.quantity, i.cost_price, i.retail_price, s.total, s.date
        FROM sales s
        JOIN inventory i ON s.inventory_id = i.id
        WHERE date(s.date) = ?
        ORDER BY s.id DESC
    ''', (selected_date.strftime('%Y-%m-%d'),))
    # Calculate totals
    total_revenue = sum(s['quantity'] * s['retail_price'] for s in sales_for_day)
    total_net = sum((s['quantity'] * s['retail_price']) - (s['quantity'] * s['cost_price']) for s in sales_for_day)
    return render_template('sales_day.html', sales_for_day=sales_for_day, selected_date=selected_date, total_revenue=total_revenue, total_net=total_net)

def datetimeformat(value):
    from datetime import datetime
    try:
        dt = datetime.strptime(value, '%Y-%m-%d %H:%M:%S')
        return dt.strftime('%Y-%m-%d %I:%M %p')
    except Exception:
        return value

app.jinja_env.filters['datetimeformat'] = datetimeformat

# FINANCIAL STATEMENT PAGE WITH MONTH FILTER
@app.route('/financial', methods=['GET', 'POST'])
def financial():
    import calendar
    now = datetime.now()
    # Get start and end date from query params or default to current month
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    if not start_date or not end_date:
        # Default to current month
        start_date = now.replace(day=1).strftime('%Y-%m-%d')
        last_day = calendar.monthrange(now.year, now.month)[1]
        end_date = now.replace(day=last_day).strftime('%Y-%m-%d')
    # For SQL, use full day range
    start_dt = datetime.strptime(start_date, '%Y-%m-%d')
    end_dt = datetime.strptime(end_date, '%Y-%m-%d')
    start_str = start_dt.strftime('%Y-%m-%d 00:00:00')
    end_str = end_dt.strftime('%Y-%m-%d 23:59:59')
    # Sales and expenses for selected range
    sales = query_db('SELECT total, quantity, cost_price FROM sales WHERE date >= ? AND date <= ?', (start_str, end_str))
    revenue = sum([s['total'] for s in sales]) if sales else 0
    cost = sum([s['quantity'] * s['cost_price'] for s in sales if s['cost_price'] is not None]) if sales else 0
    expenses = query_db('SELECT * FROM expenses WHERE date >= ? AND date <= ? ORDER BY date DESC', (start_str, end_str))
    total_expenses = sum([e['amount'] for e in expenses]) if expenses else 0
    net = revenue - cost - total_expenses
    # Calendar days for the selected range
    days = []
    d = start_dt
    while d <= end_dt:
        days.append(d)
        d += timedelta(days=1)
    # Handle add expense
    if request.method == 'POST':
        desc = request.form['description']
        amount = float(request.form['amount'])
        date_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        execute_db('INSERT INTO expenses (description, amount, date) VALUES (?, ?, ?)', (desc, amount, date_str))
        flash('Expense added!', 'success')
        return redirect(url_for('financial', start_date=start_date, end_date=end_date))
    return render_template('financial.html', expenses=expenses, revenue=revenue, cost=cost, total_expenses=total_expenses, net=net, start_date=start_date, end_date=end_date, month_days=days)

if __name__ == '__main__':
    import random
    from flask import session

    # Edit Expense with OTP
    @app.route('/expenses/edit/<int:expense_id>', methods=['GET', 'POST'])
    def edit_expense(expense_id):
        # Step 1: If no OTP in session, generate and send
        if 'otp_verified' not in session or session.get('otp_expense_id') != expense_id:
            if request.method == 'POST' or request.args.get('send_otp') == '1':
                otp = str(random.randint(100000, 999999))
                session['otp'] = otp
                session['otp_expense_id'] = expense_id
                session['otp_verified'] = False
                # Send OTP via SMS
                sms_message = f"Your LMJ POS OTP for editing expense #{expense_id} is: {otp}"
                sms_payload = {
                    'recipient': SMS_RECIPIENT,
                    'message': sms_message
                }
                sms_headers = {
                    'x-api-key': SMS_API_KEY,
                    'Content-Type': 'application/json'
                }
                try:
                    requests.post('https://api.semaphore.co/api/v4/messages', json=sms_payload, headers=sms_headers, timeout=10)
                except Exception as e:
                    flash('Failed to send OTP SMS. Please try again.', 'error')
                    return redirect(url_for('financial'))
                return render_template('otp_form.html', expense_id=expense_id)
            # Show button to send OTP
            return render_template('otp_form.html', expense_id=expense_id, show_send=True)
        # Step 2: OTP form submit
        if request.method == 'POST' and 'otp_input' in request.form:
            otp_input = request.form['otp_input']
            if otp_input == session.get('otp'):
                session['otp_verified'] = True
            else:
                flash('Invalid OTP. Please try again.', 'error')
                return render_template('otp_form.html', expense_id=expense_id)
        # Step 3: If verified, show edit form
        if session.get('otp_verified') and session.get('otp_expense_id') == expense_id:
            expense = query_db('SELECT * FROM expenses WHERE id = ?', (expense_id,), one=True)
            if not expense:
                flash('Expense not found.', 'error')
                return redirect(url_for('financial'))
            if request.method == 'POST' and 'description' in request.form and 'amount' in request.form:
                desc = request.form['description']
                amount = float(request.form['amount'])
                execute_db('UPDATE expenses SET description = ?, amount = ? WHERE id = ?', (desc, amount, expense_id))
                flash('Expense updated successfully!', 'success')
                # Clear OTP session
                session.pop('otp', None)
                session.pop('otp_verified', None)
                session.pop('otp_expense_id', None)
                return redirect(url_for('financial'))
            return render_template('edit_expense.html', expense=expense)
        # Default: show OTP form
        return render_template('otp_form.html', expense_id=expense_id)

    # Edit Sale with OTP
    @app.route('/sales/edit/<int:sale_id>', methods=['GET', 'POST'])
    def edit_sale(sale_id):
        # Step 1: If no OTP in session, generate and send
        if 'otp_verified_sale' not in session or session.get('otp_sale_id') != sale_id:
            if request.method == 'POST' or request.args.get('send_otp') == '1':
                otp = str(random.randint(100000, 999999))
                session['otp_sale'] = otp
                session['otp_sale_id'] = sale_id
                session['otp_verified_sale'] = False
                # Send OTP via SMS
                sms_message = f"Your LMJ POS OTP for editing sale #{sale_id} is: {otp}"
                sms_payload = {
                    'recipient': SMS_RECIPIENT,
                    'message': sms_message
                }
                sms_headers = {
                    'x-api-key': SMS_API_KEY,
                    'Content-Type': 'application/json'
                }
                try:
                    requests.post('https://api.semaphore.co/api/v4/messages', json=sms_payload, headers=sms_headers, timeout=10)
                except Exception as e:
                    flash('Failed to send OTP SMS. Please try again.', 'error')
                    return redirect(url_for('sales'))
                return render_template('otp_form.html', sale_id=sale_id, is_sale=True)
            # Show button to send OTP
            return render_template('otp_form.html', sale_id=sale_id, show_send=True, is_sale=True)
        # Step 2: OTP form submit
        if request.method == 'POST' and 'otp_input' in request.form:
            otp_input = request.form['otp_input']
            if otp_input == session.get('otp_sale'):
                session['otp_verified_sale'] = True
            else:
                flash('Invalid OTP. Please try again.', 'error')
                return render_template('otp_form.html', sale_id=sale_id, is_sale=True)
        # Step 3: If verified, show edit form
        if session.get('otp_verified_sale') and session.get('otp_sale_id') == sale_id:
            sale = query_db('SELECT * FROM sales WHERE id = ?', (sale_id,), one=True)
            if not sale:
                flash('Sale not found.', 'error')
                return redirect(url_for('sales'))
            if request.method == 'POST' and 'quantity' in request.form and 'total' in request.form:
                quantity = float(request.form['quantity'])
                total = float(request.form['total'])
                execute_db('UPDATE sales SET quantity = ?, total = ? WHERE id = ?', (quantity, total, sale_id))
                flash('Sale updated successfully!', 'success')
                # Clear OTP session
                session.pop('otp_sale', None)
                session.pop('otp_verified_sale', None)
                session.pop('otp_sale_id', None)
                return redirect(url_for('sales'))
            return render_template('edit_sale.html', sale=sale)
        # Default: show OTP form
        return render_template('otp_form.html', sale_id=sale_id, is_sale=True)
    # Uncomment the following lines to clear all expenses on startup
    # with app.app_context():
    #     execute_db('DELETE FROM expenses')
    app.run(debug=True)
