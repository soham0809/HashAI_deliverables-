from flask import Flask, request, jsonify, send_from_directory, redirect
import jwt
from datetime import datetime, timedelta
from functools import wraps
import os, sqlite3

app = Flask(__name__, static_folder='frontend', static_url_path='/static')
SECRET = 'dev-secret'
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, 'app.db')

def dict_factory(cursor, row):
    return {cursor.description[i][0]: row[i] for i in range(len(row))}

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = dict_factory
    return conn

def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute('CREATE TABLE IF NOT EXISTS users (email TEXT PRIMARY KEY, password TEXT NOT NULL)')
    cur.execute('CREATE TABLE IF NOT EXISTS leads (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, email TEXT NOT NULL, phone TEXT NOT NULL, status TEXT NOT NULL)')
    cur.execute('SELECT COUNT(*) as c FROM users')
    if cur.fetchone()['c'] == 0:
        cur.execute('INSERT INTO users(email, password) VALUES (?,?)', ('test@example.com', 'password123'))
    cur.execute('SELECT COUNT(*) as c FROM leads')
    if cur.fetchone()['c'] == 0:
        cur.executemany('INSERT INTO leads(name, email, phone, status) VALUES (?,?,?,?)', [
            ('Alice', 'alice@example.com', '1234567890', 'New'),
            ('Bob', 'bob@example.com', '9876543210', 'In Progress')
        ])
    conn.commit()
    conn.close()

init_db()

def token_for(email):
    payload = {'sub': email, 'exp': datetime.utcnow() + timedelta(hours=8)}
    return jwt.encode(payload, SECRET, algorithm='HS256')

def require_auth(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        auth = request.headers.get('Authorization', '')
        if not auth.startswith('Bearer '):
            return jsonify({'error': 'Unauthorized'}), 401
        token = auth.split(' ', 1)[1]
        try:
            jwt.decode(token, SECRET, algorithms=['HS256'])
        except Exception:
            return jsonify({'error': 'Unauthorized'}), 401
        return f(*args, **kwargs)
    return wrapper

@app.route('/')
def index():
    return redirect('/login')

@app.route('/login')
def login_page():
    return send_from_directory('frontend', 'login.html')

@app.route('/leads')
def leads_page():
    return send_from_directory('frontend', 'leads.html')

@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.get_json(silent=True) or {}
    email = (data.get('email') or '').strip().lower()
    password = data.get('password') or ''
    conn = get_db()
    cur = conn.cursor()
    cur.execute('SELECT password FROM users WHERE email = ?', (email,))
    row = cur.fetchone()
    conn.close()
    if row and row['password'] == password:
        return jsonify({'token': token_for(email)})
    return jsonify({'error': 'Invalid credentials'}), 401

@app.route('/api/leads', methods=['GET'])
@require_auth
def get_leads():
    try:
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 5))
    except Exception:
        page, limit = 1, 5
    if page < 1:
        page = 1
    if limit < 1:
        limit = 5
    offset = (page - 1) * limit
    conn = get_db()
    cur = conn.cursor()
    cur.execute('SELECT COUNT(*) as total FROM leads')
    total = cur.fetchone()['total']
    cur.execute('SELECT id, name, email, phone, status FROM leads ORDER BY id DESC LIMIT ? OFFSET ?', (limit, offset))
    items = cur.fetchall()
    conn.close()
    pages = (total + limit - 1) // limit if limit else 1
    return jsonify({'leads': items, 'page': page, 'limit': limit, 'total': total, 'pages': pages})

@app.route('/api/leads', methods=['POST'])
@require_auth
def add_lead():
    data = request.get_json(silent=True) or {}
    name = (data.get('name') or '').strip()
    email = (data.get('email') or '').strip()
    phone = (data.get('phone') or '').strip()
    status = data.get('status') or 'New'
    if not name or not email or not phone or status not in ['New', 'In Progress', 'Converted']:
        return jsonify({'error': 'Bad request'}), 400
    conn = get_db()
    cur = conn.cursor()
    cur.execute('INSERT INTO leads(name, email, phone, status) VALUES (?,?,?,?)', (name, email, phone, status))
    lead_id = cur.lastrowid
    conn.commit()
    cur.execute('SELECT id, name, email, phone, status FROM leads WHERE id = ?', (lead_id,))
    item = cur.fetchone()
    conn.close()
    return jsonify(item), 201

@app.route('/api/leads/<int:lead_id>', methods=['PUT'])
@require_auth
def update_lead(lead_id):
    data = request.get_json(silent=True) or {}
    conn = get_db()
    cur = conn.cursor()
    cur.execute('SELECT id, name, email, phone, status FROM leads WHERE id = ?', (lead_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return jsonify({'error': 'Not found'}), 404
    name = (data.get('name') or '').strip() or row['name']
    email = (data.get('email') or '').strip() or row['email']
    phone = (data.get('phone') or '').strip() or row['phone']
    status = data.get('status') or row['status']
    if status not in ['New', 'In Progress', 'Converted']:
        conn.close()
        return jsonify({'error': 'Bad request'}), 400
    cur.execute('UPDATE leads SET name=?, email=?, phone=?, status=? WHERE id=?', (name, email, phone, status, lead_id))
    conn.commit()
    cur.execute('SELECT id, name, email, phone, status FROM leads WHERE id = ?', (lead_id,))
    updated = cur.fetchone()
    conn.close()
    return jsonify(updated)

@app.route('/api/leads/<int:lead_id>', methods=['DELETE'])
@require_auth
def delete_lead(lead_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute('DELETE FROM leads WHERE id = ?', (lead_id,))
    if cur.rowcount == 0:
        conn.close()
        return jsonify({'error': 'Not found'}), 404
    conn.commit()
    conn.close()
    return '', 204

if __name__ == '__main__':
    app.run()
