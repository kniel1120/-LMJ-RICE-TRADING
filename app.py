from flask import Flask, render_template, request, redirect, url_for, flash
from datetime import datetime
import requests
from database.db import query_db, execute_db, get_db, close_db
from database.init_db import initialize_database

initialize_database()
app = Flask(__name__)
app.secret_key = 'lmj-secret-key'
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.teardown_appcontext(close_db)

# --- ADMIN/DEBUG: CLEAR ALL SALES ---
@app.route('/admin/clear_all_sales', methods=['POST'])
def clear_all_sales():
    execute_db('DELETE FROM sales')
    flash('All sales records have been deleted.', 'success')
    return redirect(url_for('sales'))


# Account Receivables imports
from controllers.account_receivable_controller import AccountReceivableController

# Add missing route for partial payment
@app.route('/add_partial_payment', methods=['POST'])
def add_partial_payment():
    receivable_id = request.form.get('receivable_id')
    partial_amount = request.form.get('partial_amount')
    try:
        partial_amount = float(partial_amount)
    except Exception:
        partial_amount = 0
    AccountReceivableController.add_partial_payment(receivable_id, partial_amount)
    flash('Partial payment added!', 'success')
    return redirect(url_for('account_receivables'))

# Add missing route for deleting receivable
@app.route('/delete_receivable', methods=['POST'])
def delete_receivable():
    receivable_id = request.form.get('receivable_id')
    AccountReceivableController.delete_receivable(receivable_id)
    flash('Receivable deleted!', 'success')
    return redirect(url_for('account_receivables'))

@app.route('/account_receivables', methods=['GET'])
def account_receivables():
    from flask import session
    receivables = AccountReceivableController.get_all_receivables()
    inventory = query_db('SELECT * FROM inventory ORDER BY product_name')
    return render_template('account_receivables.html', receivables=receivables, inventory=inventory, session=session)

@app.route('/add_receivable', methods=['POST'])
def add_receivable():
    name = request.form.get('customer_name')
    address = request.form.get('address')
    contact = request.form.get('contact')
    due_date = request.form.get('due_date')
    inventory_id = request.form.get('inventory_id')
    sale_type = request.form.get('sale_type')
    # Get inventory details
    from database.db import query_db
    item = query_db('SELECT * FROM inventory WHERE id = ?', (inventory_id,), one=True) if inventory_id else None
    unit_price = float(item['retail_price']) if item and item['retail_price'] else 0
    cost = float(item['cost_price']) if item and item['cost_price'] else 0
    sack_size = float(item['sack_size']) if item and item['sack_size'] else None
    sack_price = float(item['sack_price']) if item and item['sack_price'] else None
    # Always use amount from form (set by JS)
    try:
        amount = float(request.form.get('amount') or 0)
    except (ValueError, TypeError):
        amount = 0
    if sale_type == 'Per sack':
        try:
            quantity = float(request.form.get('sack_qty_count') or 0) or None
        except (ValueError, TypeError):
            quantity = None
    else:
        try:
            quantity = float(request.form.get('quantity') or 0) or None
        except (ValueError, TypeError):
            quantity = None
    product_name = item['product_name'] if item else None
    if sale_type == 'Per sack':
        unit_price = None
    elif sale_type == 'Per kilo':
        sack_size = None
        sack_price = None
    AccountReceivableController.add_receivable(name, address, contact, amount, due_date, cost, 'Pending', 0, sale_type, unit_price, sack_size, sack_price, quantity, product_name)
    # Deduct inventory immediately for Per Sack
    if sale_type == 'Per sack' and sack_size and quantity:
        from database.db import execute_db
        execute_db('UPDATE inventory SET quantity = quantity - ? WHERE sack_size = ?', (float(quantity), float(sack_size)))
    from flask import session
    session.pop('receivable_prefill', None)
    flash('Receivable added!', 'success')
    return redirect(url_for('account_receivables'))

@app.route('/mark_receivable_paid', methods=['POST'])
def mark_receivable_paid():
    receivable_id = request.form.get('receivable_id')
    # Set partial_amount to amount and status to Paid
    AccountReceivableController.set_paid_and_zero_balance(receivable_id)
    # Record sale and update financial statement
    receivable = AccountReceivableController.get_receivable_by_id(receivable_id)
    if receivable:
        customer_name = receivable[1] if len(receivable) > 1 else ''
        amount = receivable[4]
        cost = receivable[8] if len(receivable) > 8 else None
        sale_type = receivable[9] if len(receivable) > 9 else None
        unit_price = receivable[10] if len(receivable) > 10 else None
        sack_size = receivable[11] if len(receivable) > 11 else None
        sack_price = receivable[12] if len(receivable) > 12 else None
        quantity = receivable[13] if len(receivable) > 13 else None
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        sacks_sold = receivable[14] if len(receivable) > 14 and receivable[14] is not None else 0
        product_name = receivable[15] if len(receivable) > 15 else None
        # Look up inventory_id by product_name
        inv_item = query_db('SELECT id FROM inventory WHERE product_name = ?', (product_name,), one=True) if product_name else None
        inventory_id = inv_item['id'] if inv_item else None
        # For Per sack: quantity in sales = sacks_sold * sack_size (kg total)
        if sale_type == 'Per sack' and sack_size:
            sales_quantity = float(sacks_sold) * float(sack_size)
            sales_unit_price = sack_price
            sales_cost_price = cost  # cost per sack
        else:
            sales_quantity = float(quantity) if quantity else None
            sales_unit_price = unit_price
            sales_cost_price = cost
        execute_db('INSERT INTO sales (inventory_id, customer_id, total, date, sale_type, unit_price, cost_price, sack_size, sack_price, quantity) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
               (inventory_id, None, amount, now, sale_type or 'Receivable', sales_unit_price, sales_cost_price, sack_size, sack_price, sales_quantity))
        # Deduct inventory
        if sale_type == 'Per sack' and sack_size:
            execute_db('UPDATE inventory SET quantity = quantity - ? WHERE sack_size = ?', (float(sacks_sold), float(sack_size)))
        elif sale_type == 'Per kilo' and sales_quantity:
            execute_db('UPDATE inventory SET quantity = quantity - ? WHERE product_name = ?', (sales_quantity, product_name))
    flash('Receivable marked as paid and recorded in sales/financials!', 'success')
    return redirect(url_for('account_receivables'))
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

# SMS API PH config
SMS_API_KEY = 'sk-b50c2b7886419667094fc02e'
SMS_RECIPIENT = '+639061260308'

# Process sale from dashboard form (POST only)
@app.route('/process_sale', methods=['POST'])
def process_sale_dashboard():
    rice_id = request.form.get('rice_id')
    sale_type = request.form.get('sale_type')
    quantity = request.form.get('quantity')
    payment_type = request.form.get('payment_type')
    if not rice_id or not sale_type or not quantity:
        flash('Missing sale information.', 'error')
        return redirect(url_for('dashboard'))
    item = query_db('SELECT * FROM inventory WHERE id = ?', (rice_id,), one=True)
    if not item:
        flash('Selected rice type not found.', 'error')
        return redirect(url_for('dashboard'))
    available = item['quantity'] or 0
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
        cost_price = item['cost_price']
        calculated_cost = qty * cost_price
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
        available_sacks = item['quantity'] or 0
        if sack_qty > available_sacks:
            flash(f'Not enough stock for {item["product_name"]}. Only {available_sacks:.0f} sack(s) available.', 'error')
            return redirect(url_for('dashboard'))
        qty = sack_qty * item['sack_size']
        unit_price = item['sack_price']
        total = sack_qty * unit_price
        cost_price = item['cost_price']
        calculated_cost = sack_qty * item['sack_size'] * cost_price
    else:
        flash('Invalid sale type.', 'error')
        return redirect(url_for('dashboard'))

    if payment_type == 'Cash':
        # Normal sale logic
        db = get_db()
        cur = db.execute("PRAGMA table_info(sales)")
        columns = [row[1] for row in cur.fetchall()]
        cur.close()
        if 'sack_cost' in columns:
            execute_db('INSERT INTO sales (inventory_id, quantity, total, cost_price, date, sale_type, unit_price, sack_size, sack_price, sack_cost) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                       (item['id'], qty, total, cost_price, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), sale_type, unit_price, item['sack_size'], item['sack_price'], item['cost_price']))
        else:
            execute_db('INSERT INTO sales (inventory_id, quantity, total, cost_price, date, sale_type, unit_price, sack_size, sack_price) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
                       (item['id'], qty, total, cost_price, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), sale_type, unit_price, item['sack_size'], item['sack_price']))
        # Deduct from inventory
        if sale_type == 'Per Sack':
            execute_db('UPDATE inventory SET quantity = quantity - ? WHERE id = ?', (sack_qty, item['id']))
        else:
            execute_db('UPDATE inventory SET quantity = quantity - ? WHERE id = ?', (qty, item['id']))
        flash('Sale processed!', 'success')
        return redirect(url_for('dashboard'))
    else:
        # Paylater logic: redirect to account_receivables with pre-filled info
        # Store info in session or pass as query params
        from flask import session
        session['receivable_prefill'] = {
            'customer_name': '',
            'address': '',
            'contact': '',
            'amount': total,
            'cost': calculated_cost,
            'due_date': '',
            'rice_type': item['product_name']
        }
        flash('Fill out customer info for Paylater.', 'info')
        return redirect(url_for('account_receivables'))

# HOME/DASHBOARD ROUTE (GET: show dashboard, POST: process sale)
@app.route('/', methods=['GET', 'POST'])
def dashboard():
    if request.method == 'POST':
        rice_type = request.form.get('rice_type')
        sale_type = request.form.get('sale_type', 'kilo')
        sale_type_lc = sale_type.strip().lower()
        item = query_db('SELECT * FROM inventory WHERE product_name = ?', (rice_type,), one=True)
        if not item:
            flash('Selected rice type not found.', 'error')
            return redirect(url_for('dashboard'))
        available = item['quantity'] or 0
        if sale_type_lc in ['kilo', 'per kilo']:
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
        elif sale_type_lc in ['sack', 'per sack']:
            try:
                sack_qty = float(request.form.get('sack_qty', 0))
            except Exception:
                sack_qty = 0
            sack_size = item['sack_size']
            sack_price = item['sack_price']
            if sack_size is None or sack_size == 0 or sack_price is None:
                flash('Selected rice type does not have sack info.', 'error')
                return redirect(url_for('dashboard'))
            available_sacks = item['quantity'] or 0
            if sack_qty <= 0:
                flash('Please enter a valid sack quantity.', 'error')
                return redirect(url_for('dashboard'))
            if available_sacks <= 0:
                flash(f'Not enough stock for {rice_type}. Only 0 sack(s) available.', 'error')
                return redirect(url_for('dashboard'))
            if sack_qty > available_sacks:
                flash(f'Not enough stock for {rice_type}. Only {available_sacks:.2f} sack(s) available.', 'error')
                return redirect(url_for('dashboard'))
            quantity = sack_qty * sack_size
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
            execute_db('INSERT INTO sales (inventory_id, quantity, total, cost_price, date, sale_type, unit_price, sack_size, sack_price, sack_cost) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                       (item['id'], quantity, total, cost_price, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), sale_type, unit_price, sack_size, sack_price, sack_cost))
        else:
            execute_db('INSERT INTO sales (inventory_id, quantity, total, cost_price, date, sale_type, unit_price, sack_size, sack_price) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
                       (item['id'], quantity, total, cost_price, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), sale_type, unit_price, sack_size, sack_price))
        # Deduct from inventory
        if sale_type_lc in ['sack', 'per sack']:
            execute_db('UPDATE inventory SET quantity = quantity - ? WHERE id = ?', (sack_qty, item['id']))
        else:
            execute_db('UPDATE inventory SET quantity = quantity - ? WHERE id = ?', (quantity, item['id']))
        if sale_type == 'kilo':
            flash(f'Sale processed for {quantity} kg {rice_type}.', 'success')
        else:
            flash(f'Sale processed for {sack_qty} sack(s) ({quantity} kg) {rice_type}.', 'success')
        return redirect(url_for('dashboard'))
    # GET: show dashboard
    inventory = query_db('SELECT * FROM inventory ORDER BY product_name')
    inventory_with_stock = []
    for item in inventory:
        if item['sack_size'] and item['sack_size'] > 0:
            # Sack-based: quantity = number of sacks
            sacks_left = item['quantity'] or 0
            total_kilos = sacks_left * (item['sack_size'] or 0)
            inventory_with_stock.append({
                'id': item['id'],
                'product_name': item['product_name'],
                'retail_price': item['retail_price'] or 0,
                'sack_size': item['sack_size'] or 0,
                'sack_price': item['sack_price'] or 0,
                'stock_type': 'sack',
                'sacks_left': max(sacks_left, 0),
                'total_kilos': max(total_kilos, 0)
            })
        else:
            # Kilo-based
            kilos_left = item['quantity'] or 0
            inventory_with_stock.append({
                'id': item['id'],
                'product_name': item['product_name'],
                'retail_price': item['retail_price'] or 0,
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
    if request.is_json:
        data = request.get_json()
        name = data.get('name')
        contact = data.get('contact')
    else:
        name = request.form.get('name')
        contact = request.form.get('contact')
    if not name:
        if request.is_json:
            return {"success": False, "error": "Supplier name is required!"}, 400
        flash('Supplier name is required!', 'error')
        return redirect(url_for('suppliers'))
    execute_db('INSERT INTO suppliers (name, contact) VALUES (?, ?)', (name, contact))
    if request.is_json:
        return {"success": True, "message": "Supplier added successfully!"}
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
        product_name = request.form.get('product_name', '')
        try:
            quantity = float(request.form.get('quantity', 0))
            cost_price = float(request.form.get('cost_price', 0))
            retail_price = float(request.form.get('retail_price', 0))
        except (ValueError, TypeError):
            flash('Please enter valid numeric values.', 'error')
            return redirect(url_for('edit_inventory', item_id=item_id))
        sack_size = request.form.get('sack_size')
        sack_price = request.form.get('sack_price')
        try:
            sack_size = float(sack_size) if sack_size else None
        except (ValueError, TypeError):
            sack_size = None
        try:
            sack_price = float(sack_price) if sack_price else None
        except (ValueError, TypeError):
            sack_price = None
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
    sales_dates = query_db('SELECT date(date) as sale_date FROM sales WHERE total > 0 GROUP BY date(date) HAVING SUM(total) > 0 ORDER BY sale_date DESC')
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
    from controllers.account_receivable_controller import AccountReceivableController
    # Parse date
    try:
        selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except Exception:
        flash('Invalid date format.', 'error')
        return redirect(url_for('sales'))
    # Get sales for selected date
    sales_for_day = query_db('''
        SELECT s.id, s.customer_id, s.total, s.quantity, s.cost_price, s.date, s.sale_type, s.unit_price, s.sack_size, s.sack_price, s.sack_cost, s.inventory_id
        FROM sales s
        WHERE date(s.date) = ?
        ORDER BY s.id DESC
    ''', (selected_date.strftime('%Y-%m-%d'),))
    # Convert sqlite3.Row to dict for mutability
    sales_for_day = [dict(row) for row in sales_for_day]
    # Attach rice name and cost from account_receivables for receivable sales
    for sale in sales_for_day:
        if sale['sale_type'] and sale['sale_type'].lower() == 'receivable':
            # Find matching receivable by amount and date
            row = query_db('SELECT product_name, cost FROM account_receivables WHERE amount = ? AND due_date = ?', (sale['total'], selected_date.strftime('%Y-%m-%d')), one=True)
            if row:
                sale['product_name'] = row['product_name']
                sale['cost'] = row['cost']
            else:
                sale['product_name'] = 'None'
                sale['cost'] = 0
        else:
            # For non-receivable sales, get product name from inventory
            inv = query_db('SELECT product_name FROM inventory WHERE id = ?', (sale['inventory_id'],), one=True)
            sale['product_name'] = inv['product_name'] if inv else 'None'
            sale['cost'] = sale['cost_price']
    # Calculate totals
    total_revenue = 0
    total_net = 0
    for s in sales_for_day:
        sale_type = s['sale_type'].lower() if s['sale_type'] else ''
        if sale_type == 'receivable':
            revenue = s['total'] if s['total'] is not None else 0
            cost = s['cost'] if 'cost' in s and s['cost'] is not None else 0
            net_income = revenue - cost
        elif sale_type == 'per sack' and s['sack_cost'] is not None and s['sack_size'] and s['quantity'] is not None:
            try:
                num_sacks = float(s['quantity']) / float(s['sack_size']) if s['sack_size'] else 1
                cost = float(s['sack_cost']) * num_sacks
            except Exception:
                cost = 0
            revenue = float(s['total']) if s['total'] is not None else float(s['quantity'] or 0) * float(s['unit_price'] or 0)
            net_income = revenue - cost
        else:
            try:
                cost_price = float(s['cost_price']) if s['cost_price'] is not None else 0
                quantity = float(s['quantity']) if s['quantity'] is not None else 0
            except Exception:
                cost_price = 0
                quantity = 0
            cost = quantity * cost_price
            revenue = float(s['total']) if s['total'] is not None else quantity * float(s['unit_price'] or 0)
            net_income = revenue - cost
        total_revenue += revenue
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
    from datetime import datetime, timedelta
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
    kilo_sales = [s for s in sales if s['sale_type'] and s['sale_type'].lower() in ['kilo', 'per kilo', 'receivable'] and (s['quantity'] and (not s['sack_size'] or float(s['sack_size']) == 0))]
    sack_sales = [s for s in sales if s['sale_type'] and s['sale_type'].lower() in ['sack', 'per sack', 'receivable'] and (s['sack_size'] and float(s['sack_size']) > 0)]
    revenue_kilo = sum([s['total'] for s in kilo_sales]) if kilo_sales else 0
    revenue_sack = sum([s['total'] for s in sack_sales]) if sack_sales else 0
    cost_kilo = sum([(s['quantity'] or 0) * (s['cost_price'] or 0) for s in kilo_sales if s['cost_price'] is not None and s['quantity'] is not None]) if kilo_sales else 0
    cost_sack = sum([(s['quantity'] / s['sack_size']) * s['sack_cost'] for s in sack_sales if s['sack_cost'] is not None and s['sack_size'] and s['quantity'] is not None]) if sack_sales else 0
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
        desc = request.form.get('description', '')
        try:
            amount = float(request.form.get('amount', 0))
        except (ValueError, TypeError):
            amount = 0
        date_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        execute_db('INSERT INTO expenses (description, amount, date) VALUES (?, ?, ?)', (desc, amount, date_str))
        flash('Expense added!', 'success')
        return redirect(url_for('financial', start_date=start_date, end_date=end_date))
    return render_template('financial.html', expenses=expenses, revenue=revenue, cost=cost, total_expenses=total_expenses, net=net, start_date=start_date, end_date=end_date, month_days=days, revenue_kilo=revenue_kilo, revenue_sack=revenue_sack, cost_kilo=cost_kilo, cost_sack=cost_sack)

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
                'apikey': SMS_API_KEY,
                'number': SMS_RECIPIENT,
                'message': sms_message
            }
            try:
                requests.post('https://api.semaphore.co/api/v4/messages', data=sms_payload, timeout=10)
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
            desc = request.form.get('description', '')
            try:
                amount = float(request.form.get('amount', 0))
            except (ValueError, TypeError):
                flash('Please enter a valid amount.', 'error')
                return render_template('edit_expense.html', expense=expense)
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
                'apikey': SMS_API_KEY,
                'number': SMS_RECIPIENT,
                'message': sms_message
            }
            try:
                requests.post('https://api.semaphore.co/api/v4/messages', data=sms_payload, timeout=10)
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
            try:
                quantity = float(request.form.get('quantity', 0))
                total = float(request.form.get('total', 0))
            except (ValueError, TypeError):
                flash('Please enter valid numeric values.', 'error')
                return render_template('edit_sale.html', sale=sale)
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

if __name__ == '__main__':
    app.run(debug=False)
