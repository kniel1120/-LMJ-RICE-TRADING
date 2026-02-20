from flask import Flask, render_template, request, redirect, url_for, flash, session
import os
from database.db import get_db, query_db, execute_db, close_db
from collections import defaultdict
from datetime import datetime, timedelta
import requests

# App definition before any routes
app = Flask(__name__)
app.secret_key = 'lmj-secret-key'

# Delete Expense
@app.route('/expenses/delete/<int:expense_id>', methods=['POST'])
def delete_expense(expense_id):
    execute_db('DELETE FROM expenses WHERE id = ?', (expense_id,))
    flash('Expense deleted!', 'success')
    # Preserve date filter if present
    start_date = request.args.get('start_date') or request.form.get('start_date')
    end_date = request.args.get('end_date') or request.form.get('end_date')
    if start_date and end_date:

        return redirect(url_for('financial', start_date=start_date, end_date=end_date))
    else:
        return redirect(url_for('financial'))

# Add missing route for deleting sales
@app.route('/sales/delete/<int:sale_id>', methods=['POST'])
def delete_sale(sale_id):
    execute_db('DELETE FROM sales WHERE id = ?', (sale_id,))
    flash('Sale deleted successfully!', 'success')
    ref = request.referrer or url_for('sales')
    return redirect(ref)

app.secret_key = 'lmj-secret-key'

# SMS API PH config
SMS_API_KEY = 'sk-b50c2b7886419667094fc02e'
SMS_RECIPIENT = '+639061260308'

# Process sale from dashboard form (POST only)
@app.route('/process_sale', methods=['POST'])
def process_sale_dashboard():
    rice_id = request.form.get('rice_id')
    sale_type = request.form.get('sale_type')
    quantity = request.form.get('quantity')
    if not rice_id or not sale_type or not quantity:
        flash('Missing sale information.', 'error')
        return redirect(url_for('dashboard'))
    item = query_db('SELECT * FROM inventory WHERE id = ?', (rice_id,), one=True)
    if not item:
        flash('Selected rice type not found.', 'error')
        return redirect(url_for('dashboard'))
    sales = query_db('SELECT SUM(quantity) as sold_qty FROM sales WHERE inventory_id = ?', (item['id'],), one=True)
    sold_qty = sales['sold_qty'] if sales and sales['sold_qty'] else 0
    available = item['quantity'] - sold_qty if not item['sack_size'] else item['quantity'] * item['sack_size'] - sold_qty
    if sale_type == 'Per Kilo':
        try:
            qty = float(quantity)
        except Exception:
            qty = 0
        if qty <= 0:
            flash('Please enter a valid quantity (kg).', 'error')
            return redirect(url_for('dashboard'))
        if qty > available:
            flash(f'Not enough stock for {item["product_name"]}. Only {available} kg available.', 'error')
            return redirect(url_for('dashboard'))
        unit_price = item['retail_price']
        total = qty * unit_price
        sack_size = None
        sack_price = None
        sack_cost = None
        cost_price = item['cost_price']
    elif sale_type == 'Per Sack':
        if not item['sack_size'] or not item['sack_price']:
            flash('Selected rice type does not have sack info.', 'error')
            return redirect(url_for('dashboard'))
        try:
            sack_qty = float(quantity)
        except Exception:
            sack_qty = 0
        if sack_qty <= 0:
            flash('Please enter a valid sack quantity.', 'error')
            return redirect(url_for('dashboard'))
        available_sacks = item['quantity'] - sold_qty
        if sack_qty > available_sacks:
            flash(f'Not enough stock for {item["product_name"]}. Only {available_sacks} sack(s) available.', 'error')
            return redirect(url_for('dashboard'))
        qty = sack_qty * item['sack_size']
        unit_price = item['sack_price']
        total = sack_qty * unit_price
        sack_size = item['sack_size']
        sack_price = item['sack_price']
        # Use cost_price as cost per sack for sack sales
        sack_cost = item['cost_price']
        cost_price = None
    else:
        flash('Invalid sale type.', 'error')
        return redirect(url_for('dashboard'))
    # Check if sack_cost column exists in sales table
    db = get_db()
    cur = db.execute("PRAGMA table_info(sales)")
    columns = [row[1] for row in cur.fetchall()]
    cur.close()
    if 'sack_cost' in columns:
        execute_db('INSERT INTO sales (inventory_id, quantity, total, cost_price, date, sale_type, unit_price, sack_size, sack_price, sack_cost) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                   (item['id'], qty, total, cost_price, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), sale_type, unit_price, sack_size, sack_price, sack_cost))
    else:
        execute_db('INSERT INTO sales (inventory_id, quantity, total, cost_price, date, sale_type, unit_price, sack_size, sack_price) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                   (item['id'], qty, total, cost_price, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), sale_type, unit_price, sack_size, sack_price))
    flash('Sale processed!', 'success')
    return redirect(url_for('dashboard'))

# HOME/DASHBOARD ROUTE (GET: show dashboard, POST: process sale)
@app.route('/', methods=['GET', 'POST'])
def dashboard():
    if request.method == 'POST':
        rice_type = request.form.get('rice_type')
        sale_type = request.form.get('sale_type', 'kilo')
        item = query_db('SELECT * FROM inventory WHERE product_name = ?', (rice_type,), one=True)
        if not item:
            flash('Selected rice type not found.', 'error')
            return redirect(url_for('dashboard'))
        # Get current sold quantity
        sales = query_db('SELECT SUM(quantity) as sold_qty FROM sales WHERE inventory_id = ?', (item['id'],), one=True)
        sold_qty = sales['sold_qty'] if sales and sales['sold_qty'] else 0
        available = item['quantity'] - sold_qty
        if sale_type == 'kilo':
            try:
                quantity = float(request.form.get('quantity', 0))
            except Exception:
                quantity = 0
            if quantity <= 0:
                flash('Please enter a valid quantity (kg).', 'error')
                return redirect(url_for('dashboard'))
            if quantity > available:
                flash(f'Not enough stock for {rice_type}. Only {available} kg available.', 'error')
                return redirect(url_for('dashboard'))
            unit_price = item['retail_price']
            total = quantity * unit_price
            sack_size = None
            sack_price = None
            sack_cost = None
            cost_price = item['cost_price']
        elif sale_type == 'sack':
            try:
                sack_qty = float(request.form.get('sack_qty', 0))
            except Exception:
                sack_qty = 0
            sack_size = item['sack_size']
            sack_price = item['sack_price']
            if not sack_size or not sack_price:
                flash('Selected rice type does not have sack info.', 'error')
                return redirect(url_for('dashboard'))
            quantity = sack_qty * sack_size
            if sack_qty <= 0 or quantity <= 0:
                flash('Please enter a valid sack quantity.', 'error')
                return redirect(url_for('dashboard'))
            if quantity > available:
                flash(f'Not enough stock for {rice_type}. Only {available} kg available.', 'error')
                return redirect(url_for('dashboard'))
            unit_price = sack_price
            total = sack_qty * sack_price
            sack_cost = item['cost_price']
            cost_price = None
        else:
            flash('Invalid sale type.', 'error')
            return redirect(url_for('dashboard'))
        # Insert sale with new fields, check for sack_cost column
        db = get_db()
        cur = db.execute("PRAGMA table_info(sales)")
        columns = [row[1] for row in cur.fetchall()]
        cur.close()
        if 'sack_cost' in columns:
            execute_db('INSERT INTO sales (inventory_id, quantity, total, cost_price, date, sale_type, unit_price, sack_size, sack_price, sack_cost) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                       (item['id'], quantity, total, cost_price, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), sale_type, unit_price, sack_size, sack_price, sack_cost))
        else:
            execute_db('INSERT INTO sales (inventory_id, quantity, total, cost_price, date, sale_type, unit_price, sack_size, sack_price) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                       (item['id'], quantity, total, cost_price, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), sale_type, unit_price, sack_size, sack_price))
        if sale_type == 'kilo':
            flash(f'Sale processed for {quantity} kg {rice_type}.', 'success')
        else:
            flash(f'Sale processed for {sack_qty} sack(s) ({quantity} kg) {rice_type}.', 'success')
        return redirect(url_for('dashboard'))
    # GET: show dashboard
    inventory = query_db('SELECT * FROM inventory ORDER BY product_name')
    sales = query_db('SELECT inventory_id, SUM(quantity) as sold_qty FROM sales GROUP BY inventory_id')
    sold_map = {s['inventory_id']: s['sold_qty'] if s['sold_qty'] else 0 for s in sales}
    inventory_with_stock = []
    for item in inventory:
        sold_qty = sold_map.get(item['id'], 0)
        if item['sack_size'] and item['sack_size'] > 0:
            # Sack-based: quantity = number of sacks
            sacks_sold = sold_qty / item['sack_size'] if item['sack_size'] else 0
            sacks_left = item['quantity'] - sacks_sold
            total_kilos = sacks_left * item['sack_size']
            inventory_with_stock.append({
                'id': item['id'],
                'product_name': item['product_name'],
                'retail_price': item['retail_price'],
                'sack_size': item['sack_size'],
                'sack_price': item['sack_price'],
                'stock_type': 'sack',
                'sacks_left': max(sacks_left, 0),
                'total_kilos': max(total_kilos, 0)
            })
        else:
            # Kilo-based
            kilos_left = item['quantity'] - sold_qty
            inventory_with_stock.append({
                'id': item['id'],
                'product_name': item['product_name'],
                'retail_price': item['retail_price'],
                'stock_type': 'kilo',
                'kilos_left': max(kilos_left, 0)
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
    add_type = request.form.get('add_type', 'kilo')
    if add_type == 'sack':
        # Per sack: store number of sacks, sack size, cost per sack, retail per sack
        sack_size = request.form.get('sack_size')
        sack_qty = request.form.get('sack_qty')
        sack_cost = request.form.get('sack_cost')
        sack_price = request.form.get('sack_price')
        try:
            sack_size = float(sack_size)
            sack_qty = float(sack_qty)
            sack_cost = float(sack_cost)
            sack_price = float(sack_price)
        except Exception:
            flash('Please enter valid sack details.', 'error')
            return redirect(url_for('inventory'))
        quantity = sack_qty  # store as number of sacks
        cost_price = sack_cost  # cost per sack
        retail_price = sack_price  # retail per sack
    else:
        # Per kilo: store as kilos
        try:
            quantity = float(request.form['quantity'])
            cost_price = float(request.form['cost_price'])
            retail_price = float(request.form['retail_price'])
        except Exception:
            flash('Please enter valid kilo details.', 'error')
            return redirect(url_for('inventory'))
        sack_size = None
        sack_price = None
    execute_db('INSERT INTO inventory (product_name, quantity, cost_price, retail_price, sack_size, sack_price) VALUES (?, ?, ?, ?, ?, ?)', (product_name, quantity, cost_price, retail_price, sack_size, sack_price))
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
        quantity = float(request.form['quantity'])
        cost_price = float(request.form['cost_price'])
        retail_price = float(request.form['retail_price'])
        sack_size = request.form.get('sack_size')
        sack_price = request.form.get('sack_price')
        sack_size = float(sack_size) if sack_size else None
        sack_price = float(sack_price) if sack_price else None
        execute_db('UPDATE inventory SET product_name=?, quantity=?, cost_price=?, retail_price=?, sack_size=?, sack_price=? WHERE id=?', (product_name, quantity, cost_price, retail_price, sack_size, sack_price, item_id))
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
        SELECT s.id, i.product_name, s.quantity, s.cost_price, i.retail_price, s.total, s.date,
               COALESCE(s.unit_price, i.retail_price) as unit_price,
               s.sack_size, s.sack_price, s.sale_type, s.sack_cost
        FROM sales s
        JOIN inventory i ON s.inventory_id = i.id
        WHERE date(s.date) = ?
        ORDER BY s.id DESC
    ''', (selected_date.strftime('%Y-%m-%d'),))
    # Calculate totals
    total_revenue = sum(s['total'] if s['total'] is not None else s['quantity'] * s['retail_price'] for s in sales_for_day)
    total_net = 0
    for s in sales_for_day:
        sale_type = s['sale_type'].lower() if s['sale_type'] else ''
        if sale_type == 'per sack' and s['sack_cost'] is not None and s['sack_size']:
            num_sacks = s['quantity'] / s['sack_size'] if s['sack_size'] else 1
            cost = s['sack_cost'] * num_sacks
            revenue = s['total'] if s['total'] is not None else s['quantity'] * s['retail_price']
            net_income = revenue - cost
        else:
            cost_price = s['cost_price'] if s['cost_price'] is not None else 0
            cost = s['quantity'] * cost_price
            revenue = s['total'] if s['total'] is not None else s['quantity'] * s['retail_price']
            net_income = revenue - cost
        total_net += net_income
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
    sales = query_db('SELECT total, quantity, cost_price, sale_type, unit_price, sack_size, sack_price, sack_cost FROM sales WHERE date >= ? AND date <= ?', (start_str, end_str))
    # Breakdown by sale type (case-insensitive)
    kilo_sales = [s for s in sales if s['sale_type'] and s['sale_type'].lower() in ['kilo', 'per kilo']]
    sack_sales = [s for s in sales if s['sale_type'] and s['sale_type'].lower() in ['sack', 'per sack']]
    revenue_kilo = sum([s['total'] for s in kilo_sales]) if kilo_sales else 0
    revenue_sack = sum([s['total'] for s in sack_sales]) if sack_sales else 0
    cost_kilo = sum([s['quantity'] * s['cost_price'] for s in kilo_sales if s['cost_price'] is not None]) if kilo_sales else 0
    # For sack sales, cost = sacks sold x cost per sack
    cost_sack = sum([(s['quantity'] / s['sack_size']) * s['sack_cost'] for s in sack_sales if s['sack_cost'] is not None and s['sack_size']]) if sack_sales else 0
    revenue = revenue_kilo + revenue_sack
    cost = cost_kilo + cost_sack
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
    return render_template('financial.html', expenses=expenses, revenue=revenue, cost=cost, total_expenses=total_expenses, net=net, start_date=start_date, end_date=end_date, month_days=days, revenue_kilo=revenue_kilo, revenue_sack=revenue_sack, cost_kilo=cost_kilo, cost_sack=cost_sack)

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
