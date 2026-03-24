from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from datetime import timedelta, datetime
import bcrypt
from database import db, User, GlucoseReading, FoodLog
import numpy as np
from sklearn.linear_model import LinearRegression
import json

app = Flask(__name__)
CORS(app)

# Configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///gluconova.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['JWT_SECRET_KEY'] = 'your-secret-key-change-in-production'
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=24)

db.init_app(app)
jwt = JWTManager(app)

# Create tables
with app.app_context():
    db.create_all()

# Glycemic index database for food prediction
GLYCEMIC_INDEX = {
    'pizza': 85, 'rice': 73, 'burger': 66, 'pasta': 55, 'apple': 36,
    'banana': 52, 'chocolate': 40, 'soda': 78, 'bread': 70, 'cake': 65,
    'salad': 15, 'chicken': 0, 'fries': 70, 'ice cream': 57, 'orange': 43,
    'potato': 85, 'cereal': 74, 'donut': 76, 'pancake': 67, 'yogurt': 35
}

# ==================== AUTH ROUTES ====================

@app.route('/api/register', methods=['POST'])
def register():
    try:
        data = request.json
        name = data.get('name')
        email = data.get('email')
        password = data.get('password')
        
        if not name or not email or not password:
            return jsonify({'error': 'Missing fields'}), 400
        
        # Check if user exists
        if User.query.filter_by(email=email).first():
            return jsonify({'error': 'User already exists'}), 400
        
        # Hash password
        salt = bcrypt.gensalt()
        password_hash = bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')
        
        user = User(name=name, email=email, password_hash=password_hash)
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
        
        if bcrypt.checkpw(password.encode('utf-8'), user.password_hash.encode('utf-8')):
            access_token = create_access_token(identity=user.id)
            return jsonify({
                'token': access_token,
                'user': {
                    'id': user.id,
                    'name': user.name,
                    'email': user.email
                }
            }), 200
        else:
            return jsonify({'error': 'Invalid password'}), 401
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ==================== GLUCOSE READINGS ====================

@app.route('/api/glucose', methods=['POST'])
@jwt_required()
def add_glucose_reading():
    try:
        user_id = get_jwt_identity()
        data = request.json
        value = data.get('value')
        
        reading = GlucoseReading(
            user_id=user_id,
            value=value,
            is_esp32_reading=data.get('is_esp32', True)
        )
        db.session.add(reading)
        db.session.commit()
        
        # Update food logs with actual impacts
        update_food_impacts(user_id, value)
        
        return jsonify({'message': 'Reading added', 'id': reading.id}), 201
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/glucose', methods=['GET'])
@jwt_required()
def get_glucose_readings():
    try:
        user_id = get_jwt_identity()
        limit = request.args.get('limit', 30, type=int)
        
        readings = GlucoseReading.query.filter_by(user_id=user_id)\
            .order_by(GlucoseReading.timestamp.desc())\
            .limit(limit).all()
        
        return jsonify([{
            'id': r.id,
            'value': r.value,
            'timestamp': r.timestamp.isoformat(),
            'is_esp32': r.is_esp32_reading
        } for r in readings]), 200
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/glucose/latest', methods=['GET'])
@jwt_required()
def get_latest_glucose():
    try:
        user_id = get_jwt_identity()
        latest = GlucoseReading.query.filter_by(user_id=user_id)\
            .order_by(GlucoseReading.timestamp.desc()).first()
        
        if latest:
            return jsonify({
                'value': latest.value,
                'timestamp': latest.timestamp.isoformat()
            }), 200
        return jsonify({'message': 'No readings yet'}), 404
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ==================== FOOD LOGS ====================

def predict_glucose_impact(food_name, user_id):
    """AI prediction based on glycemic index and user history"""
    food_lower = food_name.lower()
    
    # Find matching food in GI database
    base_gi = 50  # default medium GI
    for key, gi in GLYCEMIC_INDEX.items():
        if key in food_lower:
            base_gi = gi
            break
    
    # Get user's average glucose
    recent_readings = GlucoseReading.query.filter_by(user_id=user_id)\
        .order_by(GlucoseReading.timestamp.desc())\
        .limit(10).all()
    
    avg_glucose = sum(r.value for r in recent_readings) / len(recent_readings) if recent_readings else 100
    
    # Adjust impact based on user's baseline
    if avg_glucose > 140:
        adjustment = 8
    elif avg_glucose > 100:
        adjustment = 3
    else:
        adjustment = -2
    
    # Calculate predicted impact (mg/dL increase)
    impact = (base_gi / 10) + adjustment
    return round(max(2, min(45, impact)), 1)

def update_food_impacts(user_id, new_glucose_value):
    """Update food logs with actual impact after glucose reading"""
    # Get food logs from last 3 hours without actual impact
    from datetime import timedelta
    time_threshold = datetime.utcnow() - timedelta(hours=3)
    
    recent_foods = FoodLog.query.filter(
        FoodLog.user_id == user_id,
        FoodLog.timestamp >= time_threshold,
        FoodLog.actual_impact == None
    ).all()
    
    for food_log in recent_foods:
        # Get glucose reading just before food
        before_food = GlucoseReading.query.filter(
            GlucoseReading.user_id == user_id,
            GlucoseReading.timestamp < food_log.timestamp
        ).order_by(GlucoseReading.timestamp.desc()).first()
        
        if before_food:
            actual_impact = new_glucose_value - before_food.value
            food_log.actual_impact = round(actual_impact, 1)
            db.session.commit()

@app.route('/api/food/predict', methods=['POST'])
@jwt_required()
def predict_food():
    try:
        user_id = get_jwt_identity()
        data = request.json
        food_name = data.get('food_name')
        
        predicted_impact = predict_glucose_impact(food_name, user_id)
        
        return jsonify({
            'food': food_name,
            'predicted_impact': predicted_impact,
            'message': f'Predicted spike: +{predicted_impact} mg/dL'
        }), 200
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/food/log', methods=['POST'])
@jwt_required()
def log_food():
    try:
        user_id = get_jwt_identity()
        data = request.json
        food_name = data.get('food_name')
        predicted_impact = data.get('predicted_impact')
        
        food_log = FoodLog(
            user_id=user_id,
            food_name=food_name,
            predicted_impact=predicted_impact
        )
        db.session.add(food_log)
        db.session.commit()
        
        return jsonify({
            'message': 'Food logged successfully',
            'id': food_log.id
        }), 201
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/food/weekly-report', methods=['GET'])
@jwt_required()
def weekly_report():
    try:
        user_id = get_jwt_identity()
        from datetime import datetime, timedelta
        
        week_ago = datetime.utcnow() - timedelta(days=7)
        food_logs = FoodLog.query.filter(
            FoodLog.user_id == user_id,
            FoodLog.timestamp >= week_ago
        ).all()
        
        # Group by food name
        food_stats = {}
        for log in food_logs:
            name = log.food_name.lower()
            if name not in food_stats:
                food_stats[name] = {
                    'food': log.food_name,
                    'count': 0,
                    'total_predicted': 0,
                    'total_actual': 0,
                    'actual_count': 0
                }
            
            stats = food_stats[name]
            stats['count'] += 1
            stats['total_predicted'] += log.predicted_impact
            
            if log.actual_impact is not None:
                stats['total_actual'] += log.actual_impact
                stats['actual_count'] += 1
        
        # Calculate averages
        report = []
        for name, stats in food_stats.items():
            avg_predicted = stats['total_predicted'] / stats['count']
            avg_actual = stats['total_actual'] / stats['actual_count'] if stats['actual_count'] > 0 else None
            
            report.append({
                'food': stats['food'],
                'occurrences': stats['count'],
                'avg_predicted_impact': round(avg_predicted, 1),
                'avg_actual_impact': round(avg_actual, 1) if avg_actual else None
            })
        
        # Sort by predicted impact
        report.sort(key=lambda x: x['avg_predicted_impact'], reverse=True)
        
        return jsonify(report), 200
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ==================== AI INSIGHTS ====================

@app.route('/api/insights', methods=['GET'])
@jwt_required()
def get_insights():
    try:
        user_id = get_jwt_identity()
        
        # Get recent readings
        readings = GlucoseReading.query.filter_by(user_id=user_id)\
            .order_by(GlucoseReading.timestamp.desc())\
            .limit(24).all()
        
        if len(readings) < 3:
            return jsonify({'insight': 'Not enough data for insights yet'}), 200
        
        values = [r.value for r in readings]
        latest = values[0]
        avg_7day = sum(values[:7]) / min(7, len(values))
        
        # Trend detection
        if len(values) >= 3:
            trend = values[0] - values[2]
        else:
            trend = 0
        
        # Generate insights
        insights = []
        
        if latest > 180:
            insights.append("🔴 CRITICAL: High glucose detected. Seek medical attention if persistent.")
        elif latest > 140:
            insights.append("⚠️ Elevated glucose. Consider reducing carbohydrate intake.")
        elif latest < 70:
            insights.append("🟡 Low glucose detected. Consume fast-acting carbohydrates.")
        
        if trend > 15:
            insights.append("📈 Rapidly rising trend. Monitor closely.")
        elif trend < -15:
            insights.append("📉 Rapidly falling trend. Be cautious of hypoglycemia.")
        
        if avg_7day > 130:
            insights.append("📊 Your 7-day average is above target. Schedule a doctor consultation.")
        elif avg_7day < 100:
            insights.append("✅ Great control! Your glucose levels are well-managed.")
        
        # ML prediction for next reading
        if len(values) >= 5:
            X = np.array(range(len(values[:5]))).reshape(-1, 1)
            y = np.array(values[:5])
            model = LinearRegression()
            model.fit(X, y)
            next_prediction = model.predict([[5]])[0]
            insights.append(f"🤖 AI predicts next reading: {next_prediction:.0f} mg/dL")
        
        return jsonify({
            'insights': insights,
            'latest_value': latest,
            'avg_7day': round(avg_7day, 1),
            'trend': trend
        }), 200
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ==================== ESP32 SIMULATION ====================

@app.route('/api/esp32/simulate', methods=['POST'])
@jwt_required()
def simulate_esp32():
    """Simulate ESP32 sensor reading"""
    try:
        user_id = get_jwt_identity()
        import random
        
        # Simulate realistic glucose reading (70-200 mg/dL)
        value = random.randint(70, 200)
        
        reading = GlucoseReading(
            user_id=user_id,
            value=value,
            is_esp32_reading=True
        )
        db.session.add(reading)
        db.session.commit()
        
        # Update food impacts
        update_food_impacts(user_id, value)
        
        return jsonify({
            'value': value,
            'timestamp': reading.timestamp.isoformat(),
            'message': 'ESP32 reading simulated'
        }), 200
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)