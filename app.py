from flask import Flask, request, jsonify, render_template, redirect, url_for, session, flash
from flask_cors import CORS
from flask_wtf.csrf import CSRFProtect, generate_csrf
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime
import os
import csv
import util

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})
app.secret_key = os.urandom(24)
csrf = CSRFProtect(app)

# Configuration
app.config['WTF_CSRF_ENABLED'] = True
app.config['SESSION_COOKIE_SECURE'] = False
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['REMEMBER_COOKIE_SECURE'] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'}
app.config['PROPERTIES_CSV'] = 'server/bengaluru_house_prices.csv'  # Changed CSV file name

# Ensure directories exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Mock user database (unchanged)
users = {
    "admin": {
        "password": generate_password_hash("admin123"),
        "email": "admin@example.com",
        "created_at": datetime.now().isoformat()
    }
}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def init_properties_csv():
    if not os.path.exists(app.config['PROPERTIES_CSV']):
        with open(app.config['PROPERTIES_CSV'], mode='w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow([
                'area_type', 'availability', 'location', 'size', 'society',
                'total_sqft', 'bath', 'balcony', 'price', 'username', 'timestamp',
                'title', 'description', 'contact', 'image_path' # Added missing columns
            ])

@app.after_request
def add_csrf_token(response):
    csrf_token = generate_csrf()
    response.set_cookie('csrf_token', csrf_token)
    return response

def load_artifacts():
    print("Initializing application...")
    try:
        util.load_saved_artifacts()
        init_properties_csv()
        print("Artifacts loaded successfully")
    except Exception as e:
        print(f"Failed to load artifacts: {str(e)}")
        raise RuntimeError("Server initialization failed") from e

with app.app_context():
    load_artifacts()

# Existing routes (mostly unchanged, some might need adjustments based on the new CSV)
@app.route('/')
def home():
    if 'username' in session:
        return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'username' in session:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        if request.is_json:
            data = request.get_json()
            username = data.get('username')
            password = data.get('password')
        else:
            username = request.form.get('username')
            password = request.form.get('password')

        user = users.get(username)

        if user and check_password_hash(user['password'], password):
            session['username'] = username
            session.permanent = True

            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({
                    'success': True,
                    'redirect': url_for('dashboard')
                })

            flash('Login successful!', 'success')
            return redirect(url_for('dashboard'))

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'error': 'Invalid username or password'
            }), 401

        flash('Invalid username or password', 'error')
        return redirect(url_for('login'))

    return render_template('login.html')

@app.route('/register', methods=['POST'])
def register():
    try:
        data = request.get_json() if request.is_json else request.form
        username = data.get('username')
        email = data.get('email')
        password = data.get('password')

        if not username or not email or not password:
            return jsonify({'error': 'All fields are required'}), 400

        if username in users:
            return jsonify({'error': 'Username already exists'}), 400

        users[username] = {
            'password': generate_password_hash(password),
            'email': email,
            'created_at': datetime.now().isoformat()
        }

        return jsonify({
            'success': True,
            'message': 'Registration successful. Please login.',
            'redirect': url_for('login')
        })

    except Exception as e:
        return jsonify({
            'error': f'Registration failed: {str(e)}'
        }), 500

@app.route('/logout')
def logout():
    session.pop('username', None)
    flash('You have been logged out', 'info')
    return redirect(url_for('login'))

@app.route('/dashboard')
def dashboard():
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template('dashboard.html', username=session['username'])

@app.route('/predictor')
def predictor():
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template('predictor.html')

@app.route('/predict')
def predict():
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template('predict.html')

@app.route('/buysell')
def buysell():
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template('buysell.html')

@app.route('/analytics')
def analytics():
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template('analytics.html')

@app.route('/sell')
def sell():
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template('sell.html')

# API routes (existing - might need review for compatibility with new CSV)
@app.route('/api/locations')
def get_location_names():
    try:
        locations = util.get_location_names()
        return jsonify({
            'status': 'success',
            'locations': locations,
            'count': len(locations),
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/api/area_types')
def get_area_types():
    try:
        area_types = util.get_area_types()
        return jsonify({
            'status': 'success',
            'area_types': area_types,
            'count': len(area_types),
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/api/societies')
def get_society_names():
    location = request.args.get('location', '').strip()
    try:
        societies = util.get_society_names(location if location else None)

        # Add user-submitted properties (adjusting for new CSV structure)
        if os.path.exists(app.config['PROPERTIES_CSV']):
            with open(app.config['PROPERTIES_CSV'], mode='r') as file:
                reader = csv.DictReader(file)
                for row in reader:
                    if not location or row['location'].lower() == location.lower():
                        if row['society'] and row['society'] not in societies:
                            societies.append(row['society'])

        return jsonify({
            'status': 'success',
            'societies': societies,
            'count': len(societies),
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500
@app.route('/api/predict', methods=['POST'])
@csrf.exempt  # Temporarily exempt CSRF for testing
def predict_home_price():
    try:
        if not request.is_json:
            return jsonify({
                'status': 'error',
                'message': 'Request must be JSON',
                'timestamp': datetime.now().isoformat()
            }), 400

        data = request.get_json()
        print("Received prediction data:", data)  # Debug logging

        required = ['total_sqft', 'location', 'bhk', 'bath']
        if not all(field in data for field in required):
            return jsonify({
                'status': 'error',
                'message': f'Missing required fields: {", ".join(required)}',
                'timestamp': datetime.now().isoformat()
            }), 400

        try:
            total_sqft = float(data['total_sqft'])
            bhk = int(data['bhk'])
            bath = int(data['bath'])
            location = str(data['location'])
        except (ValueError, TypeError) as e:
            return jsonify({
                'status': 'error',
                'message': 'Invalid numeric values',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }), 400

        # Debug: Print available locations
        available_locations = util.get_location_names()
        print("Available locations:", available_locations)
        
        if location not in available_locations:
            return jsonify({
                'status': 'error',
                'message': f'Invalid location. Available locations: {", ".join(available_locations)}',
                'timestamp': datetime.now().isoformat()
            }), 400

        base_price = util.get_estimated_price(
            location,
            total_sqft,
            bhk,
            bath
        )
        print("Base price calculated:", base_price)  # Debug logging

        # Apply adjustments
        adjustments = {
            'society': data.get('society', ''),
            'area_type': data.get('area_type', 'Apartment'),  # Default to Apartment
            'amenities': data.get('amenities', []),
            'floor': int(data.get('floor', 0)),
            'age': int(data.get('age', 0))
        }
        print("Applying adjustments:", adjustments)  # Debug logging
        
        adjusted_price = util.apply_price_adjustments(base_price, adjustments)
        print("Adjusted price:", adjusted_price)  # Debug logging

        return jsonify({
            'status': 'success',
            'data': {
                'base_price': round(base_price, 2),
                'adjusted_price': round(adjusted_price, 2),
                'currency': 'INR',
                'unit': 'lakh',
                'parameters': {
                    'location': location,
                    'total_sqft': total_sqft,
                    'bhk': bhk,
                    'bath': bath,
                    'adjustments': adjustments
                }
            },
            'timestamp': datetime.now().isoformat()
        })

    except Exception as e:
        print("Prediction error:", str(e))  # Detailed error logging
        return jsonify({
            'status': 'error',
            'message': 'Prediction failed',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500
# New property submission endpoint (MODIFIED FOR NEW CSV STRUCTURE)
@app.route('/api/submit_property', methods=['POST'])
def submit_property():
    if 'username' not in session:
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401

    try:
        data = request.form
        file = request.files.get('image')

        # Process image upload (unchanged)
        image_path = ''
        if file and allowed_file(file.filename):
            filename = secure_filename(f"{datetime.now().timestamp()}_{file.filename}")
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            image_path = filename

        # Prepare property data
        property_data = {
            'area_type': data.get('area_type'),
            'availability': data.get('availability'),
            'location': data.get('location'),
            'size': (f"{data.get('size')} BHK"),
            'society': data.get('society', ''),
            'total_sqft': float(data.get('total_sqft', 0)),
            'bath': int(data.get('bath', 1)),
            'balcony': int(data.get('balcony', 0)),
            'price': float(data.get('price'))
        }

        # Add to dataset
        util.add_property(property_data)
        
        return jsonify({
            'status': 'success',
            'message': 'Property added successfully!'
        })

    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 400 

    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

if __name__ == '__main__':
    print('Starting Bangalore Home Price Prediction Server...')
    app.run(debug=True, host='0.0.0.0', port=5000)