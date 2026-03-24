from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from datetime import datetime, timedelta
import bcrypt
import random

app = Flask(__name__)
CORS(app)  # Allow frontend to connect

# Database setup
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///gluconova.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['JWT_SECRET_KEY'] = 'gluconova-secret-key-2024'
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=24)

db = SQLAlchemy(app)
jwt = JWTManager(app)

# Database Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class GlucoseReading(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer)
    value = db.Column(db.Float)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

class FoodLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer)
    food_name = db.Column(db.String(100))
    predicted_impact = db.Column(db.Float)
    actual_impact = db.Column(db.Float)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

# Create tables
with app.app_context():
    db.create_all()
    print("✅ Database created successfully!")

# ============= AUTH ROUTES =============
@app.route('/api/register', methods=['POST'])
def register():
    try:
        data = request.json
        name = data.get('name')
        email = data.get('email')
        password = data.get('password')
        
        if User.query.filter_by(email=email).first():
            return jsonify({'error': 'User already exists'}), 400
        
        hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        user = User(name=name, email=email, password=hashed.decode('utf-8'))
        db.session.add(user)
        db.session.commit()
        
        return jsonify({'message': 'User created successfully'}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/login', methods=['POST'])
def login():
    try:
        data = request.json
        email = data.get('email')
        password = data.get('password')
        
        user = User.query.filter_by(email=email).first()
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        if bcrypt.checkpw(password.encode('utf-8'), user.password.encode('utf-8')):
            token = create_access_token(identity=user.id)
            return jsonify({
                'token': token,
                'user': {'id': user.id, 'name': user.name, 'email': user.email}
            }), 200
        return jsonify({'error': 'Invalid password'}), 401
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ============= GLUCOSE ROUTES =============
@app.route('/api/glucose', methods=['GET'])
@jwt_required()
def get_glucose():
    try:
        user_id = get_jwt_identity()
        readings = GlucoseReading.query.filter_by(user_id=user_id)\
            .order_by(GlucoseReading.timestamp.desc()).limit(30).all()
        
        return jsonify([{
            'id': r.id,
            'value': r.value,
            'timestamp': r.timestamp.isoformat()
        } for r in readings]), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/glucose', methods=['POST'])
@jwt_required()
def add_glucose():
    try:
        user_id = get_jwt_identity()
        value = request.json.get('value')
        
        reading = GlucoseReading(user_id=user_id, value=value)
        db.session.add(reading)
        db.session.commit()
        
        return jsonify({'message': 'Reading added'}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/glucose/latest', methods=['GET'])
@jwt_required()
def get_latest():
    try:
        user_id = get_jwt_identity()
        latest = GlucoseReading.query.filter_by(user_id=user_id)\
            .order_by(GlucoseReading.timestamp.desc()).first()
        
        if latest:
            return jsonify({'value': latest.value, 'timestamp': latest.timestamp.isoformat()}), 200
        return jsonify({'message': 'No readings'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ============= ESP32 SIMULATION =============
@app.route('/api/esp32/simulate', methods=['POST'])
@jwt_required()
def simulate_esp32():
    try:
        user_id = get_jwt_identity()
        value = random.randint(70, 200)
        
        reading = GlucoseReading(user_id=user_id, value=value)
        db.session.add(reading)
        db.session.commit()
        
        return jsonify({'value': value, 'timestamp': reading.timestamp.isoformat()}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ============= FOOD ROUTES =============
@app.route('/api/food/predict', methods=['POST'])
@jwt_required()
def predict_food():
    try:
        data = request.json
        food_name = data.get('food_name', '').lower()
        
        # Glycemic impact database
        impacts = {
            'pizza': 25, 'rice': 28, 'burger': 22, 'pasta': 20,
            'apple': 6, 'banana': 12, 'chocolate': 18, 'soda': 32,
            'bread': 20, 'cake': 28, 'salad': 3, 'chicken': 2,
            'fries': 26, 'ice cream': 16, 'orange': 8, 'potato': 24
        }
        
        impact = 10  # default
        for key, val in impacts.items():
            if key in food_name:
                impact = val
                break
        
        return jsonify({'food': food_name, 'predicted_impact': impact}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/food/log', methods=['POST'])
@jwt_required()
def log_food():
    try:
        user_id = get_jwt_identity()
        data = request.json
        
        food = FoodLog(
            user_id=user_id,
            food_name=data.get('food_name'),
            predicted_impact=data.get('predicted_impact')
        )
        db.session.add(food)
        db.session.commit()
        
        return jsonify({'message': 'Food logged'}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/food/weekly-report', methods=['GET'])
@jwt_required()
def weekly_report():
    try:
        user_id = get_jwt_identity()
        week_ago = datetime.utcnow() - timedelta(days=7)
        
        logs = FoodLog.query.filter(
            FoodLog.user_id == user_id,
            FoodLog.timestamp >= week_ago
        ).all()
        
        # Group by food
        food_stats = {}
        for log in logs:
            name = log.food_name
            if name not in food_stats:
                food_stats[name] = {'count': 0, 'total': 0}
            food_stats[name]['count'] += 1
            food_stats[name]['total'] += log.predicted_impact
        
        report = []
        for name, stats in food_stats.items():
            report.append({
                'food': name,
                'occurrences': stats['count'],
                'avg_predicted_impact': round(stats['total'] / stats['count'], 1)
            })
        
        return jsonify(report), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/insights', methods=['GET'])
@jwt_required()
def get_insights():
    try:
        user_id = get_jwt_identity()
        readings = GlucoseReading.query.filter_by(user_id=user_id)\
            .order_by(GlucoseReading.timestamp.desc()).limit(10).all()
        
        if len(readings) < 3:
            return jsonify({'insights': ['📊 Log more readings for AI insights']}), 200
        
        latest = readings[0].value
        avg = sum(r.value for r in readings) / len(readings)
        
        insights = []
        if latest > 180:
            insights.append(f"🔴 CRITICAL: {latest} mg/dL - Seek medical attention")
        elif latest > 140:
            insights.append(f"⚠️ ELEVATED: {latest} mg/dL - Reduce carbs")
        elif latest < 70:
            insights.append(f"🟡 LOW: {latest} mg/dL - Eat fast-acting carbs")
        else:
            insights.append(f"✅ NORMAL: {latest} mg/dL - Good control")
        
        if avg > 130:
            insights.append(f"📊 Weekly avg: {avg:.0f} mg/dL - Consider checkup")
        
        return jsonify({'insights': insights}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    print("=" * 50)
    print("🚀 GLUCONOVA BACKEND RUNNING")
    print("📍 http://localhost:5000")
    print("=" * 50)
    app.run(debug=True, port=5000)