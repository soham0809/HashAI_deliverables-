from flask import Flask, request, jsonify, send_from_directory, redirect
import jwt
from datetime import datetime, timedelta
from functools import wraps
import os
from pymongo import MongoClient, ASCENDING, DESCENDING
from bson.objectid import ObjectId

app = Flask(__name__, static_folder='../frontend', static_url_path='/static')
SECRET = os.environ.get('SECRET', 'dev-secret')
MONGODB_URI = os.environ.get('MONGODB_URI')
MONGODB_DB = os.environ.get('MONGODB_DB', 'hashai')

if not MONGODB_URI:
    raise RuntimeError('MONGODB_URI is not set')

_client = MongoClient(MONGODB_URI)
_db = _client[MONGODB_DB]

def to_lead(doc):
    return {
        'id': str(doc.get('_id')),
        'name': doc.get('name', ''),
        'email': doc.get('email', ''),
        'phone': doc.get('phone', ''),
        'status': doc.get('status', 'New')
    }

def init_db():
    _db.users.create_index([('email', ASCENDING)], unique=True)
    _db.leads.create_index([('_id', ASCENDING)])
    if _db.users.count_documents({}) == 0:
        _db.users.insert_one({'email': 'test@example.com', 'password': 'password123'})
    if _db.leads.count_documents({}) == 0:
        _db.leads.insert_many([
            {'name': 'Alice', 'email': 'alice@example.com', 'phone': '1234567890', 'status': 'New'},
            {'name': 'Bob', 'email': 'bob@example.com', 'phone': '9876543210', 'status': 'In Progress'},
        ])

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
    return send_from_directory('../frontend', 'login.html')

@app.route('/leads')
def leads_page():
    return send_from_directory('../frontend', 'leads.html')

@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.get_json(silent=True) or {}
    email = (data.get('email') or '').strip().lower()
    password = data.get('password') or ''
    user = _db.users.find_one({'email': email})
    if user and user.get('password') == password:
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
    skip = (page - 1) * limit
    total = _db.leads.count_documents({})
    cursor = _db.leads.find({}, sort=[('_id', DESCENDING)]).skip(skip).limit(limit)
    items = [to_lead(d) for d in cursor]
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
    res = _db.leads.insert_one({'name': name, 'email': email, 'phone': phone, 'status': status})
    doc = _db.leads.find_one({'_id': res.inserted_id})
    return jsonify(to_lead(doc)), 201

@app.route('/api/leads/<lead_id>', methods=['PUT'])
@require_auth
def update_lead(lead_id):
    data = request.get_json(silent=True) or {}
    try:
        oid = ObjectId(lead_id)
    except Exception:
        return jsonify({'error': 'Not found'}), 404
    existing = _db.leads.find_one({'_id': oid})
    if not existing:
        return jsonify({'error': 'Not found'}), 404
    name = (data.get('name') or '').strip() or existing.get('name', '')
    email = (data.get('email') or '').strip() or existing.get('email', '')
    phone = (data.get('phone') or '').strip() or existing.get('phone', '')
    status = data.get('status') or existing.get('status', 'New')
    if status not in ['New', 'In Progress', 'Converted']:
        return jsonify({'error': 'Bad request'}), 400
    _db.leads.update_one({'_id': oid}, {'$set': {'name': name, 'email': email, 'phone': phone, 'status': status}})
    updated = _db.leads.find_one({'_id': oid})
    return jsonify(to_lead(updated))

@app.route('/api/leads/<lead_id>', methods=['DELETE'])
@require_auth
def delete_lead(lead_id):
    try:
        oid = ObjectId(lead_id)
    except Exception:
        return jsonify({'error': 'Not found'}), 404
    res = _db.leads.delete_one({'_id': oid})
    if res.deleted_count == 0:
        return jsonify({'error': 'Not found'}), 404
    return '', 204

# Export the Flask app for Vercel
# Vercel will automatically use the 'app' variable
app.debug = False
