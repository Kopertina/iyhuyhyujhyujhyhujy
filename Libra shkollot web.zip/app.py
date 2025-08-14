import os
import sqlite3
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formatdate
from flask import Flask, render_template, request, redirect, url_for, session, flash, g
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev_secret_change_me')
DB_PATH = os.path.join(os.path.dirname(__file__), 'data', 'bookstore.db')

ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'admin')
SMTP_HOST = os.getenv('SMTP_HOST')
SMTP_PORT = int(os.getenv('SMTP_PORT', '587'))
SMTP_USER = os.getenv('SMTP_USER')
SMTP_PASS = os.getenv('SMTP_PASS')
NOTIFY_EMAIL = os.getenv('NOTIFY_EMAIL', 'erikselimi996@gmail.com')

# ------------- DB helpers -------------
def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(error=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()

def query_db(query, args=(), one=False):
    cur = get_db().execute(query, args)
    rv = cur.fetchall()
    cur.close()
    return (rv[0] if rv else None) if one else rv

def exec_db(query, args=()):
    db = get_db()
    cur = db.execute(query, args)
    db.commit()
    return cur.lastrowid

# ------------- Utils -------------
def send_email(subject, html_body, to_email=NOTIFY_EMAIL):
    if not (SMTP_HOST and SMTP_USER and SMTP_PASS and to_email):
        # Skip silently if not configured
        return False
    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = SMTP_USER
    msg['To'] = to_email
    msg['Date'] = formatdate(localtime=True)
    part = MIMEText(html_body, 'html', 'utf-8')
    msg.attach(part)
    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SMTP_USER, [to_email], msg.as_string())
        return True
    except Exception as e:
        print("Email error:", e)
        return False

def format_eur(value):
    return f"{value:.2f} €"

# ------------- Session cart -------------
def get_cart():
    return session.get('cart', {})

def save_cart(cart):
    session['cart'] = cart
    session.modified = True

def cart_total(cart):
    total = 0.0
    if not cart:
        return 0.0
    ids = list(map(int, cart.keys()))
    if not ids:
        return 0.0
    placeholders = ",".join("?" for _ in ids)
    rows = query_db(f"SELECT id, price FROM products WHERE id IN ({placeholders})", ids)
    price_map = {r['id']: r['price'] for r in rows}
    for pid, qty in cart.items():
        total += price_map.get(int(pid), 0.0) * qty
    return total

# ------------- Routes -------------
@app.route('/')
def index():
    # Featured: latest 9
    products = query_db("SELECT * FROM products ORDER BY id DESC LIMIT 9")
    grades = list(range(1, 10))
    return render_template('index.html', products=products, grades=grades)

@app.route('/shop')
def shop():
    grade = request.args.get('grade')
    q = request.args.get('q', '').strip()
    params = []
    where = []
    if grade and grade.isdigit():
        where.append("grade = ?")
        params.append(int(grade))
    if q:
        where.append("(LOWER(title) LIKE ? OR LOWER(author) LIKE ?)")
        params.extend([f"%{q.lower()}%", f"%{q.lower()}%"])
    sql = "SELECT * FROM products"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY title ASC"
    products = query_db(sql, params)
    grades = list(range(1, 10))
    return render_template('shop.html', products=products, grades=grades, active_grade=grade, q=q)

@app.route('/cart')
def cart_view():
    cart = get_cart()
    items = []
    if cart:
        ids = list(map(int, cart.keys()))
        placeholders = ",".join("?" for _ in ids)
        rows = query_db(f"SELECT * FROM products WHERE id IN ({placeholders})", ids)
        for r in rows:
            pid = str(r['id'])
            qty = cart.get(pid, 0)
            items.append({
                'id': r['id'],
                'title': r['title'],
                'author': r['author'],
                'price': r['price'],
                'qty': qty,
                'subtotal': r['price'] * qty,
                'image_url': r['image_url']
            })
    total = cart_total(cart)
    return render_template('cart.html', items=items, total=total, format_eur=format_eur)

@app.route('/add_to_cart', methods=['POST'])
def add_to_cart():
    pid = request.form.get('product_id')
    qty = request.form.get('quantity', '1')
    if not (pid and pid.isdigit()):
        return redirect(request.referrer or url_for('shop'))
    qty = int(qty)
    cart = get_cart()
    cart[pid] = cart.get(pid, 0) + max(1, qty)
    save_cart(cart)
    flash('Produkti u shtua në shportë.', 'success')
    return redirect(request.referrer or url_for('shop'))

@app.route('/update_cart', methods=['POST'])
def update_cart():
    cart = {}
    for key, val in request.form.items():
        if key.startswith('qty_'):
            pid = key[4:]
            if pid.isdigit():
                try:
                    q = max(0, int(val))
                except:
                    q = 0
                if q > 0:
                    cart[pid] = q
    save_cart(cart)
    flash('Shporta u përditësua.', 'info')
    return redirect(url_for('cart_view'))

@app.route('/checkout', methods=['GET', 'POST'])
def checkout():
    cart = get_cart()
    if not cart:
        flash('Shporta është bosh.', 'warning')
        return redirect(url_for('shop'))
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        phone = request.form.get('phone', '').strip()
        address = request.form.get('address', '').strip()
        note = request.form.get('note', '').strip()

        if not (name and phone and address):
            flash('Ju lutem plotësoni: Emër, Telefon, Adresë.', 'danger')
            return redirect(url_for('checkout'))

        # Create order
        db = get_db()
        total = cart_total(cart)
        order_id = exec_db(
            "INSERT INTO orders (customer_name, phone, address, note, total_price, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (name, phone, address, note, total, 'PENDING', datetime.utcnow().isoformat())
        )
        # items
        ids = list(map(int, cart.keys()))
        placeholders = ",".join("?" for _ in ids)
        rows = query_db(f"SELECT id, title, price FROM products WHERE id IN ({placeholders})", ids)
        price_map = {r['id']: (r['title'], r['price']) for r in rows}
        for pid_str, qty in cart.items():
            pid = int(pid_str)
            title, price = price_map.get(pid, ('', 0.0))
            exec_db(
                "INSERT INTO order_items (order_id, product_id, quantity, unit_price, title_snapshot) VALUES (?, ?, ?, ?, ?)",
                (order_id, pid, qty, price, title)
            )

        # send email
        items_html = ""
        for pid_str, qty in cart.items():
            pid = int(pid_str)
            title, price = price_map.get(pid, ('', 0.0))
            items_html += f"<tr><td>{title}</td><td>{qty}</td><td>{format_eur(price)}</td><td>{format_eur(price*qty)}</td></tr>"
        html = f"""
        <h3>Porosi e re #{order_id}</h3>
        <p><b>Emri:</b> {name}<br><b>Telefoni:</b> {phone}<br><b>Adresa:</b> {address}<br><b>Shënim:</b> {note or '-'}<br><b>Total:</b> {format_eur(total)}</p>
        <table border="1" cellpadding="6" cellspacing="0">
            <thead><tr><th>Produkt</th><th>Sasia</th><th>Çmimi</th><th>Nëntotali</th></tr></thead>
            <tbody>{items_html}</tbody>
        </table>
        <p>Status: PENDING (Pagesa bëhet dorazi)</p>
        """
        send_email(subject=f"Porosi e re #{order_id}", html_body=html)

        # clear cart
        save_cart({})
        return redirect(url_for('thank_you', order_id=order_id))
    total = cart_total(cart)
    return render_template('checkout.html', total=total, format_eur=format_eur)

@app.route('/thank-you')
def thank_you():
    order_id = request.args.get('order_id')
    return render_template('thank_you.html', order_id=order_id)

@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        phone = request.form.get('phone', '').strip()
        message = request.form.get('message', '').strip()
        if not (name and message):
            flash('Ju lutem plotësoni: Emër dhe Mesazh.', 'danger')
            return redirect(url_for('contact'))
        exec_db(
            "INSERT INTO messages (name, email, phone, message, created_at) VALUES (?, ?, ?, ?, ?)",
            (name, email, phone, message, datetime.utcnow().isoformat())
        )
        html = f"""
        <h3>Mesazh i ri kontakti</h3>
        <p><b>Emri:</b> {name}<br><b>Email:</b> {email or '-'}<br><b>Tel:</b> {phone or '-'}</p>
        <p>{message}</p>
        """
        send_email("Mesazh i ri nga faqja", html)
        flash('Faleminderit! Mesazhi u dërgua.', 'success')
        return redirect(url_for('contact'))
    return render_template('contact.html')

# ------------- Admin -------------
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        password = request.form.get('password')
        if password == ADMIN_PASSWORD:
            session['is_admin'] = True
            return redirect(url_for('admin_orders'))
        flash('Fjalëkalim i pasaktë.', 'danger')
    return render_template('admin_login.html')

@app.route('/admin/logout')
def admin_logout():
    session.pop('is_admin', None)
    flash('Dolate nga admin.', 'info')
    return redirect(url_for('admin_login'))

def admin_required():
    return session.get('is_admin') is True

@app.route('/admin/orders')
def admin_orders():
    if not admin_required():
        return redirect(url_for('admin_login'))
    status = request.args.get('status', '')
    params = []
    sql = """
    SELECT o.*, 
           GROUP_CONCAT(oi.title_snapshot || ' x' || oi.quantity, ' | ') AS items
    FROM orders o
    LEFT JOIN order_items oi ON oi.order_id = o.id
    """
    if status:
        sql += " WHERE o.status = ?"
        params.append(status)
    sql += " GROUP BY o.id ORDER BY o.created_at DESC"
    orders = query_db(sql, params)
    return render_template('admin_orders.html', orders=orders, active_status=status)

@app.route('/admin/orders/<int:order_id>/status', methods=['POST'])
def admin_update_status(order_id):
    if not admin_required():
        return redirect(url_for('admin_login'))
    new_status = request.form.get('status', 'PENDING')
    exec_db("UPDATE orders SET status = ? WHERE id = ?", (new_status, order_id))
    flash(f'Statusi u përditësua në {new_status}.', 'success')
    return redirect(url_for('admin_orders'))

# ------------- Errors -------------
@app.errorhandler(404)
def not_found(e):
    return render_template('base.html', content="<h2>404</h2><p>Faqja nuk u gjet.</p>"), 404

if __name__ == '__main__':
    app.run(debug=True)