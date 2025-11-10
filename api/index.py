from flask import Flask, request, jsonify, send_from_directory, redirect
import jwt
from datetime import datetime, timedelta
from functools import wraps
import os
import sqlite3
import traceback
import uuid

app = Flask(__name__, static_folder='../frontend', static_url_path='/static')
SECRET = os.environ.get('SECRET', 'dev-secret')

# SQLite database path (works perfectly on Vercel)
DB_PATH = '/tmp/app.db'

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # This enables column access by name
    return conn

def to_lead(row):
    return {
        'id': str(row['id']),
        'name': row['name'],
        'email': row['email'],
        'phone': row['phone'],
        'status': row['status']
    }

def init_db():
    try:
        conn = get_db()
        cursor = conn.cursor()
        print("Initializing SQLite database...")
        
        # Create tables
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS leads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL,
                phone TEXT NOT NULL,
                status TEXT DEFAULT 'New'
            )
        ''')
        
        # Check if test user exists
        cursor.execute('SELECT * FROM users WHERE email = ?', ('test@example.com',))
        test_user = cursor.fetchone()
        
        if not test_user:
            cursor.execute('INSERT INTO users (email, password) VALUES (?, ?)', 
                         ('test@example.com', 'password123'))
            print("Created test user")
        else:
            print("Test user already exists")
            
        # Add sample leads if none exist
        cursor.execute('SELECT COUNT(*) FROM leads')
        lead_count = cursor.fetchone()[0]
        
        if lead_count == 0:
            sample_leads = [
                ('Alice', 'alice@example.com', '1234567890', 'New'),
                ('Bob', 'bob@example.com', '9876543210', 'In Progress'),
            ]
            cursor.executemany('INSERT INTO leads (name, email, phone, status) VALUES (?, ?, ?, ?)', 
                             sample_leads)
            print(f"Created {len(sample_leads)} sample leads")
        else:
            print("Sample leads already exist")
            
        conn.commit()
        conn.close()
        print("Database initialization completed successfully")
        
    except Exception as e:
        print(f"Database initialization error: {e}")
        import traceback
        traceback.print_exc()

# Initialize database lazily, not on import
# init_db()

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

@app.route('/health')
def health():
    try:
        # Test database connection
        conn = get_db()
        cursor = conn.cursor()
        
        # Check if test user exists
        cursor.execute('SELECT COUNT(*) FROM users')
        user_count = cursor.fetchone()[0]
        
        cursor.execute('SELECT * FROM users WHERE email = ?', ('test@example.com',))
        test_user = cursor.fetchone()
        
        conn.close()
        
        return jsonify({
            'status': 'healthy', 
            'database': 'SQLite connected',
            'user_count': user_count,
            'test_user_exists': test_user is not None
        })
    except Exception as e:
        return jsonify({'status': 'unhealthy', 'error': str(e)}), 500

@app.route('/init-db')
def manual_init_db():
    try:
        init_db()
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute('SELECT COUNT(*) FROM users')
        user_count = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM leads')
        leads_count = cursor.fetchone()[0]
        
        conn.close()
        
        return jsonify({
            'status': 'initialized',
            'users_created': user_count,
            'leads_created': leads_count
        })
    except Exception as e:
        return jsonify({'status': 'error', 'error': str(e)}), 500

@app.route('/login')
def login_page():
    return send_from_directory('../frontend', 'login.html')

@app.route('/leads')
def leads_page():
    return send_from_directory('../frontend', 'leads.html')

@app.route('/api/auth/login', methods=['POST'])
def login():
    try:
        init_db()  # Initialize database on first API call
        conn = get_db()
        cursor = conn.cursor()
        
        data = request.get_json(silent=True) or {}
        email = (data.get('email') or '').strip().lower()
        password = data.get('password') or ''
        
        cursor.execute('SELECT * FROM users WHERE email = ? AND password = ?', (email, password))
        user = cursor.fetchone()
        conn.close()
        
        if user:
            return jsonify({'token': token_for(email)})
        return jsonify({'error': 'Invalid credentials'}), 401
    except Exception as e:
        print(f"Login error: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/leads', methods=['GET'])
@require_auth
def get_leads():
    try:
        conn = get_db()
        cursor = conn.cursor()
        
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
        
        # Get total count
        cursor.execute('SELECT COUNT(*) FROM leads')
        total = cursor.fetchone()[0]
        
        # Get paginated leads
        cursor.execute('SELECT * FROM leads ORDER BY id DESC LIMIT ? OFFSET ?', (limit, offset))
        rows = cursor.fetchall()
        items = [to_lead(row) for row in rows]
        
        conn.close()
        
        pages = (total + limit - 1) // limit if limit else 1
        return jsonify({'leads': items, 'page': page, 'limit': limit, 'total': total, 'pages': pages})
    except Exception as e:
        print(f"Get leads error: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/leads', methods=['POST'])
@require_auth
def add_lead():
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        data = request.get_json(silent=True) or {}
        name = (data.get('name') or '').strip()
        email = (data.get('email') or '').strip()
        phone = (data.get('phone') or '').strip()
        status = data.get('status') or 'New'
        
        if not name or not email or not phone or status not in ['New', 'In Progress', 'Converted']:
            return jsonify({'error': 'Bad request'}), 400
            
        cursor.execute('INSERT INTO leads (name, email, phone, status) VALUES (?, ?, ?, ?)',
                      (name, email, phone, status))
        lead_id = cursor.lastrowid
        
        cursor.execute('SELECT * FROM leads WHERE id = ?', (lead_id,))
        row = cursor.fetchone()
        
        conn.commit()
        conn.close()
        
        return jsonify(to_lead(row)), 201
    except Exception as e:
        print(f'Add lead error: {e}')
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/leads/<lead_id>', methods=['PUT'])
@require_auth
def update_lead(lead_id):
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        data = request.get_json(silent=True) or {}
        try:
            lead_id = int(lead_id)
        except ValueError:
            return jsonify({'error': 'Invalid lead ID'}), 400
            
        # Check if lead exists
        cursor.execute('SELECT * FROM leads WHERE id = ?', (lead_id,))
        existing = cursor.fetchone()
        if not existing:
            conn.close()
            return jsonify({'error': 'Not found'}), 404
            
        name = (data.get('name') or '').strip() or existing['name']
        email = (data.get('email') or '').strip() or existing['email']
        phone = (data.get('phone') or '').strip() or existing['phone']
        status = data.get('status') or existing['status']
        
        if status not in ['New', 'In Progress', 'Converted']:
            conn.close()
            return jsonify({'error': 'Bad request'}), 400
            
        cursor.execute('UPDATE leads SET name = ?, email = ?, phone = ?, status = ? WHERE id = ?',
                      (name, email, phone, status, lead_id))
        
        cursor.execute('SELECT * FROM leads WHERE id = ?', (lead_id,))
        updated = cursor.fetchone()
        
        conn.commit()
        conn.close()
        
        return jsonify(to_lead(updated))
    except Exception as e:
        print(f'Update lead error: {e}')
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/leads/<lead_id>', methods=['DELETE'])
@require_auth
def delete_lead(lead_id):
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        try:
            lead_id = int(lead_id)
        except ValueError:
            conn.close()
            return jsonify({'error': 'Invalid lead ID'}), 400
            
        cursor.execute('DELETE FROM leads WHERE id = ?', (lead_id,))
        
        if cursor.rowcount == 0:
            conn.close()
            return jsonify({'error': 'Not found'}), 404
            
        conn.commit()
        conn.close()
        
        return '', 204
    except Exception as e:
        print(f'Delete lead error: {e}')
        return jsonify({'error': 'Internal server error'}), 500

# Export the Flask app for Vercel
# Vercel will automatically use the 'app' variable
app.debug = False
