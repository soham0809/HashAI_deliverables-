from flask import Flask, request, jsonify, send_from_directory, redirect
import jwt
from datetime import datetime, timedelta
from functools import wraps
import os
from pymongo import MongoClient, ASCENDING, DESCENDING
from bson.objectid import ObjectId
import traceback

app = Flask(__name__, static_folder='../frontend', static_url_path='/static')
SECRET = os.environ.get('SECRET', 'dev-secret')
MONGODB_URI = os.environ.get('MONGODB_URI')
MONGODB_DB = os.environ.get('MONGODB_DB', 'hashai')

# Global variables for database connection
_client = None
_db = None

def get_db():
    global _client, _db
    if _client is None:
        if not MONGODB_URI:
            raise RuntimeError('MONGODB_URI is not set')
        try:
            _client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
            _db = _client[MONGODB_DB]
            # Test connection
            _client.admin.command('ping')
        except Exception as e:
            print(f"MongoDB connection error: {e}")
            raise
    return _db

def to_lead(doc):
    return {
        'id': str(doc.get('_id')),
        'name': doc.get('name', ''),
        'email': doc.get('email', ''),
        'phone': doc.get('phone', ''),
        'status': doc.get('status', 'New')
    }

def init_db():
    try:
        db = get_db()
        print("Initializing database...")
        
        # Create indexes (ignore if already exists)
        try:
            db.users.create_index([('email', ASCENDING)], unique=True)
            print("Created users email index")
        except Exception as e:
            print(f"Users index already exists or error: {e}")
        
        # Ensure test user exists
        test_user = db.users.find_one({'email': 'test@example.com'})
        if not test_user:
            result = db.users.insert_one({'email': 'test@example.com', 'password': 'password123'})
            print(f"Created test user with ID: {result.inserted_id}")
        else:
            print("Test user already exists")
            
        # Add sample leads if none exist
        if db.leads.count_documents({}) == 0:
            result = db.leads.insert_many([
                {'name': 'Alice', 'email': 'alice@example.com', 'phone': '1234567890', 'status': 'New'},
                {'name': 'Bob', 'email': 'bob@example.com', 'phone': '9876543210', 'status': 'In Progress'},
            ])
            print(f"Created {len(result.inserted_ids)} sample leads")
        else:
            print("Sample leads already exist")
            
        print("Database initialization completed successfully")
        
    except Exception as e:
        print(f"Database initialization error: {e}")
        import traceback
        traceback.print_exc()
        # Don't fail completely, just log the error

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
        db = get_db()
        db.admin.command('ping')
        
        # Check if test user exists
        user_count = db.users.count_documents({})
        test_user = db.users.find_one({'email': 'test@example.com'})
        
        return jsonify({
            'status': 'healthy', 
            'database': 'connected',
            'user_count': user_count,
            'test_user_exists': test_user is not None
        })
    except Exception as e:
        return jsonify({'status': 'unhealthy', 'error': str(e)}), 500

@app.route('/init-db')
def manual_init_db():
    try:
        init_db()
        db = get_db()
        user_count = db.users.count_documents({})
        leads_count = db.leads.count_documents({})
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
        db = get_db()
        data = request.get_json(silent=True) or {}
        email = (data.get('email') or '').strip().lower()
        password = data.get('password') or ''
        user = db.users.find_one({'email': email})
        if user and user.get('password') == password:
            return jsonify({'token': token_for(email)})
        return jsonify({'error': 'Invalid credentials'}), 401
    except Exception as e:
        print(f"Login error: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/leads', methods=['GET'])
@require_auth
def get_leads():
    try:
        db = get_db()
        try:
            page = int(request.args.get('page', 1))
            limit = int(request.args.get('limit', 5))
        except Exception:
            page, limit = 1, 5
        if page < 1:
            page = 1
        if limit < 1:
            limit = 5
        skip = (page - 1) * limit
        total = db.leads.count_documents({})
        cursor = db.leads.find({}, sort=[('_id', DESCENDING)]).skip(skip).limit(limit)
        items = [to_lead(d) for d in cursor]
        pages = (total + limit - 1) // limit if limit else 1
        return jsonify({'leads': items, 'page': page, 'limit': limit, 'total': total, 'pages': pages})
    except Exception as e:
        print(f"Get leads error: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/leads', methods=['POST'])
@require_auth
def add_lead():
    try:
        db = get_db()
        data = request.get_json(silent=True) or {}
        name = (data.get('name') or '').strip()
        email = (data.get('email') or '').strip()
        phone = (data.get('phone') or '').strip()
        status = data.get('status') or 'New'
        if not name or not email or not phone or status not in ['New', 'In Progress', 'Converted']:
            return jsonify({'error': 'Bad request'}), 400
        res = db.leads.insert_one({'name': name, 'email': email, 'phone': phone, 'status': status})
        doc = db.leads.find_one({'_id': res.inserted_id})
        return jsonify(to_lead(doc)), 201
    except Exception as e:
        print(f'Add lead error: {e}')
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/leads/<lead_id>', methods=['PUT'])
@require_auth
def update_lead(lead_id):
    try:
        data = request.get_json(silent=True) or {}
        try:
            oid = ObjectId(lead_id)
        except Exception:
            return jsonify({'error': 'Not found'}), 404
        db = get_db()
        existing = db.leads.find_one({'_id': oid})
        if not existing:
            return jsonify({'error': 'Not found'}), 404
        name = (data.get('name') or '').strip() or existing.get('name', '')
        email = (data.get('email') or '').strip() or existing.get('email', '')
        phone = (data.get('phone') or '').strip() or existing.get('phone', '')
        status = data.get('status') or existing.get('status', 'New')
        if status not in ['New', 'In Progress', 'Converted']:
            return jsonify({'error': 'Bad request'}), 400
        db.leads.update_one({'_id': oid}, {'$set': {'name': name, 'email': email, 'phone': phone, 'status': status}})
        updated = db.leads.find_one({'_id': oid})
        return jsonify(to_lead(updated))
    except Exception as e:
        print(f'Update lead error: {e}')
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/leads/<lead_id>', methods=['DELETE'])
@require_auth
def delete_lead(lead_id):
    try:
        try:
            oid = ObjectId(lead_id)
        except Exception:
            return jsonify({'error': 'Not found'}), 404
        db = get_db()
        res = db.leads.delete_one({'_id': oid})
        if res.deleted_count == 0:
            return jsonify({'error': 'Not found'}), 404
        return '', 204
    except Exception as e:
        print(f'Delete lead error: {e}')
        return jsonify({'error': 'Internal server error'}), 500

# Export the Flask app for Vercel
# Vercel will automatically use the 'app' variable
app.debug = False
